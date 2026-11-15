"""Live any-story claim check on Bluesky (docs/DEMO.md, Architecture, component 4: Live path).

    from src.retrieval.live import analyze_live
    result = analyze_live("Is the NYC congestion toll being repealed?")

Returns the /claim contract from docs/DEMO.md with scope="live", plus `steps` ([{name, seconds}]),
`counts`, `queries` and `live` (search window, similarity floor, k). Pipeline:

1. searching: DeepSeek writes a broad topic query plus 2-3 specific Bluesky search queries (JSON);
   app.bsky.feed.searchPosts (sort=latest,
   limit 100, sliding `until`, timestamps normalized to UTC as in src/ingest/bluesky_search.py) over the
   last `days` days, all queries in parallel.
2. grouping into narratives: bge-small embeddings, keep posts whose cosine to the prefixed claim is at least
   LIVE_FLOOR (LIVE_FLOOR + TOPIC_MARGIN for posts only the broad topic query found; best MAX_POSTS), k-means k<=5 chosen by silhouette with clusters of at least 10 posts,
   DeepSeek names each cluster (<=6 words) and assigns a side. Naming runs while accounts are scored.
3. scoring accounts: getProfiles (25 per call) and getAuthorFeed (limit 30, compact history format of
   src/ingest/bluesky_history.py) for every distinct author, 8 threads with backoff, then the bot model
   behind src.integration.bots.score_accounts. Per narrative: likely-automated post share with the shared
   bootstrap (src.stats.share_ci); the baseline is the overall share in this live sample. Commonalities:
   coordination clusters (src.integration.coordination.find_clusters) and account-creation-month
   concentration among likely-automated authors.
4. finding amplifiers: getRepostedBy + getLikes (one page each) for the top AMP_POSTS posts by
   likely-automated authors (p >= config.AUTOMATED_MIN), actors scored cheaply (profiles plus 10-item
   histories), real accounts (p < config.HUMAN_MAX) assigned archetypes; lift is the archetype's share among
   those amplifiers over its share among real authors posting about the claim in the same sample.

reply_text comes from src.api.reply.compose (code, never an LLM). Results are cached by claim_id for
CACHE_TTL_S and written to data/processed/claims/<claim_id>.json. Every network and model dependency is
injectable (http_get, llm, embedder, scorer, assigner) so tests run offline and without torch.
Read-only: only public AppView GET endpoints are called; nothing is ever posted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from src import config as cfg
from src.api import reply
from src.ingest.bluesky_history import compact
from src.ingest.bluesky_search import post_time, utc
from src.model.schema import is_public, public_ref
from src.retrieval.corpus import QUERY_PREFIX
from src.stats import share_ci

APPVIEW = "https://api.bsky.app/xrpc/"
UA = {"User-Agent": "socialnet-bot-tracker (HackPrinceton research, read-only)"}
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

DAYS = 7
MAX_POSTS = 300  # matched posts kept for analysis
PER_QUERY_CAP = 300  # raw posts per search query (3 pages)
EMBED_CAP = 450  # unique posts embedded; CPU embedding is the slowest step (10-50 posts/s on the shared VM)
EMBED_BUDGET_S = 20.0  # stop embedding further (lower-priority) posts after this many seconds
EMBED_MIN = 150  # ...but always embed at least this many
EMBED_BATCH = 64
LIVE_FLOOR = 0.62  # cosine to the prefixed claim; bge-small query->post sims sit lower than corpus text->text
TOPIC_MARGIN = 0.03  # posts found only by the broad topic query must clear LIVE_FLOOR + this
MAX_K = 5
MIN_CLUSTER = 10
WORKERS = 8
HISTORY_LIMIT = 30
AMP_POSTS = 20
AMP_HISTORY_LIMIT = 10
AMP_ACTOR_CAP = 300
BUDGET_S = 55.0  # amplifier histories are skipped when the check is running out of time
CACHE_TTL_S = 1800
CLAIMS_DIR = os.environ.get("CLAIMS_DIR", "data/processed/claims")
SIDES = ("supports_claim", "disputes_claim", "neutral_news", "humor", "other")
STEP_NAMES = ("searching", "grouping into narratives", "scoring accounts", "finding amplifiers")

HttpGet = Callable[[str, object], "dict | None"]
Llm = Callable[[str, str], str]
Embedder = Callable[[list], np.ndarray]

_CACHE: dict[str, tuple[float, dict]] = {}
_LOCK = threading.Lock()
_STOP = set(
    "a an the is are was were be been being do does did to of in on for at by with from and or not no it its this "
    "that these those about as into over after before than then so if but has have had will would can could should "
    "may might must just really actually what who whom which why how when where true false claim rumor heard "
    "say says said people".split()
)


# ---------------------------------------------------------------- HTTP (AppView, read-only)


class AppView:
    """GET on the public AppView with short backoff (the whole check has a 60 s budget)."""

    def __init__(self, timeout: float = 10.0, retries: int = 3):
        import httpx

        self._httpx = httpx
        self.client = httpx.Client(timeout=timeout, headers=UA, limits=httpx.Limits(max_connections=16))
        self.retries = retries
        self.errors: Counter = Counter()
        self.calls = 0

    def __call__(self, endpoint: str, params) -> dict | None:
        for attempt in range(self.retries):
            self.calls += 1
            try:
                r = self.client.get(APPVIEW + endpoint, params=params)
            except self._httpx.HTTPError:
                self.errors["network"] += 1
                time.sleep(0.5 * 2**attempt)
                continue
            if r.status_code == 200:
                return r.json()
            self.errors[str(r.status_code)] += 1
            if r.status_code in (429, 500, 502, 503, 504):
                try:
                    wait = float(r.headers.get("retry-after", 0))
                except ValueError:
                    wait = 0.0
                time.sleep(min(max(wait, 0.5 * 2**attempt), 4.0))
                continue
            return None
        return None

    def close(self) -> None:
        self.client.close()


# ---------------------------------------------------------------- LLM (DeepSeek, JSON output)


def deepseek(system: str, user: str, timeout: float = 25.0) -> str:
    import httpx

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            key = os.environ.get("DEEPSEEK_API_KEY")
        except ImportError:
            pass
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    r = httpx.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "deepseek-chat",
            "temperature": 0,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _json(s: str) -> dict:
    s = re.sub(r"^```(?:json)?|```$", "", (s or "").strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", s, flags=re.S)
    return json.loads(m.group(0) if m else s)


QUERY_SYSTEM = (
    "You write Bluesky search queries to find posts discussing a claim. Bluesky search matches posts containing "
    "ALL the words of a query, so long queries find almost nothing. Give \"topic\": the single broadest search "
    "for the story, usually one named entity or subject of 1 or 2 words (e.g. 'Mamdani', 'congestion pricing'). "
    "Then 2 or 3 \"queries\" of 2 or 3 plain keywords each (no boolean operators, no quotes, no hashtags) that "
    "cover other ways people word this claim (short names, nicknames, the key verb). A downstream filter "
    "removes off-topic posts, so favor recall. Also say whether the claim targets a private individual: true "
    "ONLY when it is clearly about a named person who is not a public figure (politicians, executives, celebrities, "
    "journalists and organizations are public). When unsure, false. Reply with JSON only: "
    '{"topic": "...", "queries": ["...", "..."], "private_individual": false}'
)

NAME_SYSTEM = (
    "You label groups of Bluesky posts that discuss a claim. For each group, write a neutral, complete label of 3 "
    "to 6 words (never more than 6) describing what the posts say (the narrative), and a side relative to the claim: supports_claim, "
    "disputes_claim, neutral_news, humor or other. Never judge whether the claim is true, never name accounts, "
    "never use the word bots. Reply with JSON only: "
    '{"narratives": [{"id": "n1", "label": "...", "side": "..."}]}'
)


def keywords(text: str, n: int = 4) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9'\-]+", text.lower()) if w not in _STOP and len(w) > 2]
    return list(dict.fromkeys(words))[:n]


def write_queries(llm: Llm | None, text: str) -> tuple[list[str], bool, str | None]:
    """Returns (queries, private_individual, error)."""
    fallback = [" ".join(keywords(text))] if keywords(text) else [text[:60]]
    if llm is None:
        return fallback, False, "no llm"
    try:
        d = _json(llm(QUERY_SYSTEM, f"Claim: {text}"))
        raw = [d.get("topic")] + list(d.get("queries", []) or [])
        qs = [re.sub(r"[\"#]", "", q).strip() for q in raw if isinstance(q, str)]
        qs = list(dict.fromkeys(q for q in qs if q))[:4]
        return (qs or fallback), bool(d.get("private_individual", False)), None
    except Exception as e:  # noqa: BLE001 - any LLM failure falls back to keywords
        return fallback, False, f"llm: {type(e).__name__}"


def fallback_label(texts: list[str]) -> str:
    c = Counter(w for t in texts for w in set(keywords(t, 50)))
    top = [w for w, _ in c.most_common(3)]
    return ("Posts about " + ", ".join(top)) if top else "Other posts"


def name_clusters(llm: Llm | None, claim: str, examples: dict[str, list[str]]) -> dict[str, tuple[str, str]]:
    out = {nid: (fallback_label(ex), "other") for nid, ex in examples.items()}
    if llm is None or not examples:
        return out
    body = "\n\n".join(f"Group {nid}:\n" + "\n".join(f"- {t[:240]}" for t in ex) for nid, ex in examples.items())
    try:
        d = _json(llm(NAME_SYSTEM, f"Claim: {claim}\n\n{body}"))
        for item in d.get("narratives", []):
            nid = item.get("id")
            if nid in out and isinstance(item.get("label"), str) and item["label"].strip():
                words = item["label"].strip().rstrip(".").split()[:6]
                while len(words) > 1 and words[-1].lower() in _STOP:  # a cut label must not end on "and"
                    words.pop()
                label = " ".join(words)
                label = re.sub(r"\bbots?\b", "automated accounts", label, flags=re.I)
                side = item.get("side") if item.get("side") in SIDES else "other"
                out[nid] = (label[:1].upper() + label[1:], side)
    except Exception:  # noqa: BLE001 - keep fallback labels
        pass
    return out


# ---------------------------------------------------------------- embeddings (torch only when used)

_EMBED_MODEL = None


def default_embedder(texts: list[str]) -> np.ndarray:
    global _EMBED_MODEL
    with _LOCK:
        if _EMBED_MODEL is None:
            from sentence_transformers import SentenceTransformer

            _EMBED_MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
            _EMBED_MODEL.max_seq_length = 128  # posts are <= 300 characters; shorter padding is much faster
    return np.asarray(_EMBED_MODEL.encode(texts, normalize_embeddings=True, batch_size=64))


def warm(embedder: Embedder | None = None) -> None:
    """Load the embedding model, bot model and archetypes once (the API calls this at startup; a cold
    sentence-transformers import alone takes 20-40 s on the VM)."""
    (embedder or default_embedder)(["warm up"])
    default_scorer([], {}, {})
    default_assigner([], {})


# ---------------------------------------------------------------- default scorer / archetypes

_BOT_MODEL = None
_ARCH = None


def default_scorer(profiles: list[dict], histories: dict, story_posts: dict | None) -> list[dict]:
    global _BOT_MODEL
    from src.integration import bots

    if _BOT_MODEL is None:
        _BOT_MODEL = bots.load_model()
    return bots.score_accounts(_BOT_MODEL, profiles, histories, story_posts)


def default_assigner(profiles: list[dict], histories: dict) -> list[dict]:
    global _ARCH
    from src.integration import archetypes

    try:
        if _ARCH is None:
            _ARCH = archetypes.load_archetypes()
        return archetypes.assign(_ARCH, profiles, histories)
    except Exception:  # noqa: BLE001 - archetype artifact mismatch must not kill the check
        from src.stubs import analysis as stub

        return stub.assign(stub.load_archetypes(), profiles, histories)


# ---------------------------------------------------------------- Bluesky fetchers


def search_posts(http_get: HttpGet, query: str, since: str, until: str, cap: int = PER_QUERY_CAP, max_pages: int = 4) -> tuple[list[dict], int]:
    """searchPosts sort=latest, sliding `until` to the oldest UTC createdAt seen (cursor paging 403s).

    Returns (posts, successful_pages)."""
    seen: set[str] = set()
    out: list[dict] = []
    ok = 0
    for _ in range(max_pages):
        d = http_get("app.bsky.feed.searchPosts", {"q": query, "sort": "latest", "limit": 100, "since": since, "until": until})
        if d is None:
            break
        ok += 1
        posts = d.get("posts", []) or []
        new = [p for p in posts if p.get("uri") and p["uri"] not in seen]
        for p in new:
            seen.add(p["uri"])
            out.append(p)
        # backdated or future createdAt values are ignored when sliding, so one bad clock can't skip days
        times = [t for t in (post_time(p) for p in posts) if t and since <= t <= until]
        if not posts or not times or len(out) >= cap:
            break
        oldest = min(times)
        if oldest >= until and not new:
            break
        until = oldest
    return out[:cap], ok


def fetch_profiles(http_get: HttpGet, dids: list[str], workers: int = WORKERS) -> dict[str, dict]:
    def one(batch: list[str]) -> list[dict]:
        d = http_get("app.bsky.actor.getProfiles", [("actors", x) for x in batch])
        if d is None and len(batch) > 1:  # one bad actor can fail a batch; split once
            mid = len(batch) // 2
            return [p for half in (batch[:mid], batch[mid:]) for p in ((http_get("app.bsky.actor.getProfiles", [("actors", x) for x in half]) or {}).get("profiles", []))]
        return (d or {}).get("profiles", [])

    batches = [dids[i : i + 25] for i in range(0, len(dids), 25)]
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(workers) as pool:
        for profs in pool.map(one, batches):
            for p in profs:
                if p.get("did"):
                    out[p["did"]] = p
    return out


def fetch_histories(http_get: HttpGet, dids: list[str], limit: int, workers: int = WORKERS) -> dict[str, list[dict]]:
    def one(did: str) -> tuple[str, list[dict]]:
        d = http_get("app.bsky.feed.getAuthorFeed", {"actor": did, "limit": limit})
        return did, [compact(i, did) for i in (d or {}).get("feed", [])]

    with ThreadPoolExecutor(workers) as pool:
        return dict(pool.map(one, dids))


ENGAGEMENT = (("app.bsky.feed.getRepostedBy", "repostedBy", "repost"), ("app.bsky.feed.getLikes", "likes", "like"))


def fetch_engagers(http_get: HttpGet, uris: list[str], workers: int = WORKERS) -> list[tuple[str, str, str]]:
    """[(post_uri, kind, actor_did)] from one page of reposters and likers per post."""

    def one(job):
        uri, (ep, key, kind) = job
        d = http_get(ep, {"uri": uri, "limit": 100}) or {}
        rows = []
        for it in d.get(key, []) or []:
            did = (it.get("actor") or {}).get("did") if kind == "like" else it.get("did")
            if did:
                rows.append((uri, kind, did))
        return rows

    jobs = [(u, e) for u in uris for e in ENGAGEMENT]
    with ThreadPoolExecutor(workers) as pool:
        return [r for rows in pool.map(one, jobs) for r in rows]


# ---------------------------------------------------------------- helpers


def post_text(p: dict) -> str:
    return ((p.get("record") or {}).get("text") or "").strip()


def embed_doc(p: dict) -> str:
    """Post text plus the title of a linked card, so link-only news posts still embed on topic."""
    rec = p.get("record") or {}
    emb = rec.get("embed") or {}
    ext = emb.get("external") or (emb.get("media") or {}).get("external") or {}
    t = re.sub(r"https?://\S+", "", rec.get("text") or "").strip()
    title = (ext.get("title") or "").strip()
    return (t + (" | " + title if title else "")).strip()[:256]


def post_urls(p: dict) -> list[str]:
    rec = p.get("record") or {}
    urls = [ft["uri"] for fc in rec.get("facets") or [] for ft in fc.get("features") or [] if ft.get("uri")]
    e = rec.get("embed") or {}
    x = (e.get("external") or (e.get("media") or {}).get("external") or {}).get("uri")
    if x:
        urls.append(x)
    return urls


def choose_clusters(X: np.ndarray, max_k: int = MAX_K, min_cluster: int = MIN_CLUSTER, seed: int = 42) -> tuple[np.ndarray, int, float | None]:
    """k-means for k in 2..max_k, keeping only solutions whose smallest cluster has min_cluster points;
    best silhouette wins. One cluster when no k qualifies. Returns (labels, k, silhouette)."""
    n = len(X)
    best: tuple[np.ndarray | None, int, float | None] = (None, 1, None)
    if n >= 2 * min_cluster:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        for k in range(2, min(max_k, n // min_cluster) + 1):
            lab = KMeans(n_clusters=k, n_init=4, random_state=seed).fit_predict(X)
            if np.bincount(lab, minlength=k).min() < min_cluster:
                continue
            s = float(silhouette_score(X, lab))
            if best[2] is None or s > best[2]:
                best = (lab, k, s)
    if best[0] is None:
        return np.zeros(n, dtype=int), 1, None
    return best  # type: ignore[return-value]


def claim_id_for(text: str) -> str:
    norm = " ".join(text.lower().split())
    return hashlib.sha256((norm + "live").encode()).hexdigest()[:12]


def _profile_for(did: str, profiles: dict, author_basic: dict) -> dict:
    return profiles.get(did) or {**(author_basic.get(did) or {}), "did": did}


def _ref(did: str, prof: dict) -> dict:
    return public_ref(did, prof.get("handle"), is_public(prof))


_URL_RE = re.compile(r"https?://\S+|\b(?:[a-z0-9-]+\.)+(?:com|net|org|social|io|ai|co|news|blog|xyz|me|app|dev)(?:/\S*)?", re.I)
_MENTION_RE = re.compile(r"@[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z0-9-]+")


def safe_example_text(text: str, author_public: bool) -> str:
    """Example posts are shown verbatim, so they must not name private accounts indirectly: @mentions are masked
    (we don't know whether the mentioned account is public), and a private author's links are masked too, because
    many Bluesky handles are the owner's own domain (a post linking to its own site names its author)."""
    text = _MENTION_RE.sub("@[account]", text)
    return text if author_public else _URL_RE.sub("[link]", text)


def cached(claim_id: str) -> dict | None:
    with _LOCK:
        hit = _CACHE.get(claim_id)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1]
    return None


# ---------------------------------------------------------------- main entry point


def analyze_live(
    text: str,
    scorer: Callable | None = None,
    *,
    http_get: HttpGet | None = None,
    llm: Llm | None | bool = True,
    embedder: Embedder | None = None,
    assigner: Callable | None = None,
    days: int = DAYS,
    floor: float = LIVE_FLOOR,
    max_posts: int = MAX_POSTS,
    now: datetime | None = None,
    dashboard_base: str | None = None,
    save_dir: str | None = CLAIMS_DIR,
    use_cache: bool = True,
) -> dict:
    """Live /claim for any story. scorer(profiles, histories, story_posts) -> [{did, p_automated, reasons}]
    defaults to the bot model behind src.integration.bots. llm(system, user) -> JSON string defaults to
    DeepSeek (pass llm=None to use keyword queries and term labels only)."""
    t0 = time.time()
    text = " ".join(text.split())
    claim_id = claim_id_for(text)
    if use_cache and (hit := cached(claim_id)):
        return hit
    scorer = scorer or default_scorer
    assigner = assigner or default_assigner
    embedder = embedder or default_embedder
    llm_fn: Llm | None = deepseek if llm is True else (llm or None)
    own_http = http_get is None
    http = AppView() if own_http else http_get
    dashboard_base = dashboard_base or os.environ.get("DASHBOARD_BASE", "http://localhost:5173")
    steps: list[dict] = []
    counts: dict = {}
    notes: list[str] = []

    def step(name: str, t_start: float) -> None:
        steps.append({"name": name, "seconds": round(time.time() - t_start, 2)})

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    since, until = utc((now - timedelta(days=days)).isoformat()), utc(now.isoformat())
    result: dict = {
        "claim_id": claim_id,
        "claim": text,
        "scope": "live",
        "matched_posts": 0,
        "window": {"from": None, "to": None},
        "narratives": [],
        "bot_commonalities": [],
        "amplifiers": {"n_humans": 0, "archetype_mix": []},
        "baseline_bot_share": 0.0,
        "chart_png_url": f"/claim/{claim_id}/chart.png",
        "dashboard_url": f"{dashboard_base}/claim/{claim_id}",
        "live": {"since": since, "until": until, "days": days, "floor": floor},
    }
    try:
        from src.integration import versions

        result["modules"] = versions()
    except Exception:  # noqa: BLE001
        pass
    try:
        _run(result, text, http, llm_fn, embedder, scorer, assigner, since, until, floor, max_posts, t0, steps, counts, notes)
    finally:
        if own_http:
            counts["http_calls"] = http.calls
            counts["http_errors"] = dict(http.errors)
            http.close()
    result["steps"] = steps
    result["counts"] = counts
    if notes:
        result["notes"] = notes
    if result.get("declined"):
        result["reply_text"] = reply.DECLINE
    elif result.get("error"):
        result["reply_text"] = reply.FAILURE
    else:
        result["reply_text"] = reply.compose(result)
    result["seconds"] = round(time.time() - t0, 2)
    if not result.get("error"):
        with _LOCK:
            _CACHE[claim_id] = (time.time(), result)
        if save_dir:
            try:
                d = Path(save_dir)
                d.mkdir(parents=True, exist_ok=True)
                tmp = d / f".{claim_id}.json.tmp"
                tmp.write_text(json.dumps(result, default=str))
                tmp.rename(d / f"{claim_id}.json")
            except OSError:
                pass
    return result


def _run(result, text, http, llm_fn, embedder, scorer, assigner, since, until, floor, max_posts, t0, steps, counts, notes) -> None:
    # ---- 1. searching
    ts = time.time()
    queries, private, qerr = write_queries(llm_fn, text)
    result["queries"] = queries
    if qerr:
        notes.append(f"search queries from keywords ({qerr})")
    if private:
        result["declined"] = True
        steps.append({"name": "searching", "seconds": round(time.time() - ts, 2)})
        return
    with ThreadPoolExecutor(len(queries)) as pool:
        got = list(pool.map(lambda q: search_posts(http, q, since, until), queries))
    pages_ok = sum(ok for _, ok in got)
    posts: dict[str, dict] = {}
    found_by: dict[str, set[int]] = {}
    for qi, (ps, _) in enumerate(got):
        for p in ps:
            t = post_time(p)
            if p.get("uri") and t and since <= t <= until and embed_doc(p):
                posts.setdefault(p["uri"], p)
                found_by.setdefault(p["uri"], set()).add(qi)
    counts["fetched_posts"] = sum(len(ps) for ps, _ in got)
    counts["unique_posts"] = len(posts)
    steps.append({"name": "searching", "seconds": round(time.time() - ts, 2)})
    if pages_ok == 0:
        result["error"] = "Bluesky search did not answer (every searchPosts call failed)."
        return

    # ---- 2. grouping into narratives (embedding, relevance floor, k-means; naming overlaps step 3)
    ts = time.time()
    # embed at most EMBED_CAP posts: those more queries found first (specific hits before topic-only ones),
    # then newest first (search order)
    plist = sorted(posts.values(), key=lambda p: -len(found_by[p["uri"]]))
    docs = [embed_doc(p) for p in plist]
    keep = list(dict.fromkeys(d.lower() for d in docs if d))[:EMBED_CAP]
    kept = set(keep)
    plist, docs = zip(*[(p, d) for p, d in zip(plist, docs) if d and d.lower() in kept]) if kept else ((), ())
    counts["embedded_posts"] = len(keep)
    uniq = list(dict.fromkeys(d.lower() for d in docs if d))
    pos = {u: i for i, u in enumerate(uniq)}
    matched: list[dict] = []
    E = None
    if uniq:
        te = time.time()
        chunks = [np.asarray(embedder([QUERY_PREFIX + text]), dtype=np.float32)]
        done = 0
        while done < len(uniq) and (done < EMBED_MIN or time.time() - te < EMBED_BUDGET_S):
            chunks.append(np.asarray(embedder(uniq[done : done + EMBED_BATCH]), dtype=np.float32))
            done += EMBED_BATCH
        V = np.vstack(chunks)
        uniq = uniq[: V.shape[0] - 1]
        counts["embedded_posts"] = len(uniq)
        counts["embed_seconds"] = round(time.time() - te, 2)
        V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)
        q, E = V[0], V[1:]
        sims = E @ q
        counts["similarity_quantiles"] = {k: round(float(np.quantile(sims, v)), 3) for k, v in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9))}
        scored = [(float(sims[pos[d.lower()]]), p, d) for p, d in zip(plist, docs) if d and pos[d.lower()] < len(uniq)]

        def need(p: dict) -> float:  # topic-only hits never matched the claim's specific keywords
            return floor + TOPIC_MARGIN if len(queries) > 1 and found_by[p["uri"]] == {0} else floor

        scored = sorted((s for s in scored if s[0] >= need(s[1])), key=lambda s: -s[0])[:max_posts]
        for s, p, d in scored:
            matched.append({"post": p, "sim": s, "row": pos[d.lower()], "did": (p.get("author") or {}).get("did"), "t": post_time(p)})
    matched = [m for m in matched if m["did"]]
    result["matched_posts"] = len(matched)
    counts["relevant_posts"] = len(matched)
    if matched:
        tt = sorted(m["t"] for m in matched)
        result["window"] = {"from": tt[0], "to": tt[-1]}
    if len(matched) < cfg.MIN_MATCHES:
        steps.append({"name": "grouping into narratives", "seconds": round(time.time() - ts, 2)})
        return
    X = E[[m["row"] for m in matched]]
    te = time.time()
    labels, k, sil = choose_clusters(X)
    counts["kmeans_seconds"] = round(time.time() - te, 2)
    result["live"].update({"k": k, "silhouette": None if sil is None else round(sil, 3)})
    order = [c for c, _ in Counter(labels.tolist()).most_common()]
    nid_of = {c: f"n{i + 1}" for i, c in enumerate(order)}
    for m, lab in zip(matched, labels):
        m["nid"] = nid_of[int(lab)]
    examples: dict[str, list[str]] = {}
    for c in order:
        idx = [i for i, lab in enumerate(labels) if lab == c]
        cen = X[idx].mean(0)
        best = sorted(idx, key=lambda i: -float(X[i] @ cen))
        ex = list(dict.fromkeys(embed_doc(matched[i]["post"]) for i in best))[:6]
        examples[nid_of[c]] = ex
    naming_pool = ThreadPoolExecutor(1)
    naming = naming_pool.submit(name_clusters, llm_fn, text, examples)
    t_group = time.time() - ts

    # ---- 3. scoring accounts
    ts = time.time()
    author_basic = {}
    story_posts: dict[str, list[dict]] = {}
    for m in matched:
        author_basic.setdefault(m["did"], m["post"].get("author") or {})
        story_posts.setdefault(m["did"], []).append(m["post"])
    dids = list(story_posts)
    with ThreadPoolExecutor(2) as pool:
        f_prof = pool.submit(fetch_profiles, http, dids)
        f_hist = pool.submit(fetch_histories, http, dids, HISTORY_LIMIT)
        profiles, histories = f_prof.result(), f_hist.result()
    prof_list = [_profile_for(d, profiles, author_basic) for d in dids]
    scores = {s["did"]: s for s in scorer(prof_list, histories, story_posts)}
    p_by = {d: float(scores.get(d, {}).get("p_automated", 0.0)) for d in dids}
    counts.update({"authors": len(dids), "authors_with_profile": sum(d in profiles for d in dids), "authors_with_history": sum(bool(histories.get(d)) for d in dids)})
    flags_all: dict[str, list[bool]] = {}
    for m in matched:
        flags_all.setdefault(m["did"], []).append(p_by[m["did"]] >= cfg.HEADLINE_THRESHOLD)
    base, _, _ = share_ci(flags_all)
    result["baseline_bot_share"] = round(base, 4)
    bot_dids = {d for d in dids if p_by[d] >= cfg.HEADLINE_THRESHOLD}
    counts["likely_automated_authors"] = len(bot_dids)
    t_score = time.time() - ts

    ts = time.time()
    names = naming.result()
    naming_pool.shutdown(wait=False)
    t_wait = time.time() - ts
    counts["naming_wait_seconds"] = round(t_wait, 2)
    steps.append({"name": "grouping into narratives", "seconds": round(t_group + t_wait, 2)})
    for nid in [nid_of[c] for c in order]:
        g = [m for m in matched if m["nid"] == nid]
        flags: dict[str, list[bool]] = {}
        for m in g:
            flags.setdefault(m["did"], []).append(p_by[m["did"]] >= cfg.HEADLINE_THRESHOLD)
        share, lo, hi = share_ci(flags)
        g_sorted = sorted(g, key=lambda m: -m["sim"])
        ex, seen_txt = [], set()
        for m in g_sorted:
            tx = post_text(m["post"]) or embed_doc(m["post"])
            if tx.lower() in seen_txt:
                continue
            seen_txt.add(tx.lower())
            ref = _ref(m["did"], _profile_for(m["did"], profiles, author_basic))
            ex.append({"text": safe_example_text(tx, bool(ref["public_handle"]))[:280], "public_handle": ref["public_handle"]})
            if len(ex) == 3:
                break
        label, side = names.get(nid, (nid, "other"))
        result["narratives"].append(
            {
                "id": nid,
                "label": label,
                "side": side,
                "posts": len(g),
                "share_of_matches": round(len(g) / len(matched), 4),
                "bot_post_share": round(share, 4),
                "bot_post_share_ci": [round(lo, 4), round(hi, 4)],
                "baseline_bot_share": round(base, 4),
                "example_posts": ex,
                "evidence": [{"post_uri": m["post"]["uri"], "t": m["t"], "note": f"similarity {m['sim']:.2f}" + (", likely automated account" if m["did"] in bot_dids else "")} for m in g_sorted[:10]],
            }
        )
    result["bot_commonalities"] = commonalities(matched, bot_dids, dids, profiles, author_basic, scores)
    steps.append({"name": "scoring accounts", "seconds": round(t_score + (time.time() - ts - t_wait), 2)})

    # ---- 4. finding amplifiers
    ts = time.time()
    result["amplifiers"] = amplifiers(http, matched, p_by, profiles, histories, author_basic, scorer, assigner, t0, counts, notes)
    steps.append({"name": "finding amplifiers", "seconds": round(time.time() - ts, 2)})


def commonalities(matched, bot_dids, dids, profiles, author_basic, scores) -> list[dict]:
    out: list[dict] = []
    if len(bot_dids) < cfg.MIN_BOT_ACCOUNTS_FOR_COMMONALITY:
        return out
    month = {d: (_profile_for(d, profiles, author_basic).get("createdAt") or "")[:7] for d in dids}
    bm = Counter(month[d] for d in bot_dids if month[d])
    if bm:
        mo, n = bm.most_common(1)[0]
        share_bots = n / len(bot_dids)
        share_all = sum(1 for d in dids if month[d] == mo) / max(len(dids), 1)
        if n >= 3 and share_bots >= 2 * share_all:
            out.append({"signal": f"created in the same month ({mo})", "accounts": n})
    from src.integration import coordination

    try:
        cl = coordination.find_clusters(
            [{"did": m["did"], "uri": m["post"]["uri"], "t": m["t"], "text": post_text(m["post"]), "urls": post_urls(m["post"])} for m in matched]
        )
    except Exception:  # noqa: BLE001
        cl = []
    best = None
    for c in cl:
        members = set(c.get("dids", [])) & bot_dids
        if len(members) >= 2 and (best is None or len(members) > best[0]):
            best = (len(members), c)
    if best:
        out.append({"signal": best[1]["reasons"][0], "accounts": best[0], "evidence": best[1].get("evidence", [])[:5]})
    reasons = Counter(r for d in bot_dids for r in (scores.get(d, {}).get("reasons") or [])[:1])
    for r, k in reasons.most_common(2):
        if k >= 2:
            out.append({"signal": r, "accounts": k})
    return out


def amplifiers(http, matched, p_by, profiles, histories, author_basic, scorer, assigner, t0, counts, notes) -> dict:
    eng = {}
    for m in matched:
        p = m["post"]
        if p_by.get(m["did"], 0.0) >= cfg.AUTOMATED_MIN and (p.get("likeCount") or 0) + (p.get("repostCount") or 0) > 0:
            eng[p["uri"]] = ((p.get("likeCount") or 0) + (p.get("repostCount") or 0), m["did"])
    top = sorted(eng, key=lambda u: -eng[u][0])[:AMP_POSTS]
    counts["amplifier_posts_checked"] = len(top)
    if not top:
        return {"n_humans": 0, "archetype_mix": [], "note": "no engaged posts from likely automated accounts"}
    rows = fetch_engagers(http, top)
    actors = list(dict.fromkeys(did for uri, _, did in rows if did != eng[uri][1]))
    counts["amplifier_actors"] = len(actors)
    new = [d for d in actors if d not in p_by][:AMP_ACTOR_CAP]
    known = [d for d in actors if d in p_by]
    a_prof = fetch_profiles(http, new)
    if time.time() - t0 < BUDGET_S - 10:
        a_hist = fetch_histories(http, new, AMP_HISTORY_LIMIT)
    else:
        a_hist = {}
        notes.append("amplifiers scored from profiles only (time budget)")
    a_list = [a_prof[d] for d in new if d in a_prof]
    a_scores = {s["did"]: float(s["p_automated"]) for s in scorer(a_list, a_hist, {})} if a_list else {}
    counts["amplifier_actors_scored"] = len(a_scores) + len(known)
    p_all = {**a_scores, **{d: p_by[d] for d in known}}
    humans = [d for d in actors if d in p_all and p_all[d] < cfg.HUMAN_MAX]
    if not humans:
        return {"n_humans": 0, "archetype_mix": []}
    short = {d: (histories.get(d) or [])[:AMP_HISTORY_LIMIT] for d in p_by}
    h_prof = [a_prof.get(d) or _profile_for(d, profiles, author_basic) for d in humans]
    amp_arch = assigner(h_prof, {**short, **a_hist})
    base_h = [d for d in p_by if p_by[d] < cfg.HUMAN_MAX]
    base_arch = assigner([_profile_for(d, profiles, author_basic) for d in base_h], short) if base_h else []
    mix = Counter(a["archetype_id"] for a in amp_arch)
    base = Counter(a["archetype_id"] for a in base_arch)
    lab = {a["archetype_id"]: a["label"] for a in base_arch + amp_arch}
    out = []
    for aid, k in mix.most_common():
        share = k / len(amp_arch)
        bshare = base[aid] / len(base_arch) if base_arch else 0.0
        out.append({"id": aid, "label": lab[aid], "share": round(share, 4), "lift": round(share / bshare, 2) if bshare else None})
    return {
        "n_humans": len(humans),
        "archetype_mix": out,
        "lift_baseline": "real accounts posting about this claim in the same live sample",
    }

"""News baseline: what wire services and public broadcasters report, next to the social conversation.

Usage:
    python -m src.news.baseline label          # filter + LLM-label the Jensen headlines (cached), write story_baseline.json
    python -m src.news.baseline story          # print the per-narrative news vs social table from the cache
    python -m src.news.baseline claim --text "Was Jensen Huang's mistress a Chinese spy?"
    python -m src.news.baseline live --q "jensen huang" --days 7

Framing rule: the outlets (Reuters, AP, AFP, BBC, NPR, PBS NewsHour, DW, France24, Al Jazeera, The Guardian; see
src/ingest/news.py) are accountable, edited and comparable. They are not neutral and not "the truth". Every output says
"what these newsrooms report" and carries each outlet's funding label.

Pieces:
- load_headlines(): clean Google News titles, de-duplicate, keep story-relevant rows (required terms OR embedding
  similarity to the story text). The LLM pass then drops what is still off-topic ("r": false).
- classify_headlines(): DeepSeek chat assigns each headline the same narratives as the Bluesky posts
  (src/narratives/label.py NARRATIVES), plus secondary narratives and who the headline attributes its claim to.
  Cached in data/processed/news/headline_labels.parquet, keyed by headline id and a hash of the taxonomy, so the cache
  invalidates itself when the narratives are regenerated.
- hedging(): lexical hedge share (HEDGE_TERMS below).
- news_for_claim(): the `news` block for /claim.
- story_baseline(): the dashboard's news column.
- fetch_live_headlines(): the same outlets for any query, for the live path.

Nothing here imports torch at module level; the embedder loads lazily (or is passed in).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable

import httpx
import numpy as np
import polars as pl

RAW_PATH = Path("data/raw/news_jensen.jsonl")
NEWS_DIR = Path("data/processed/news")
LABELS_PATH = NEWS_DIR / "headline_labels.parquet"
BASELINE_JSON = NEWS_DIR / "story_baseline.json"
POSTS_PATH = Path("data/processed/posts.parquet")
POST_NARRATIVE_PATH = Path("data/processed/narratives/post_narrative.parquet")

STORY = (
    "Jensen Huang leaves Nvidia (November 2026): his affairs with employees, the woman alleged to be a Chinese spy, "
    "FBI and congressional probes, the board ouster report, his resignation, interim CEO Colette Kress, Trump and "
    "Washington politics, and Nvidia's stock"
)
STORY_TERMS = ("huang", "nvidia", "jensen", "kress")  # whole-word, case-insensitive ("Fu Shuang" does not match)
STORY_FLOOR = 0.55  # passage-to-story cosine (bge-small) that lets a headline without the terms through to the LLM
CLAIM_FLOOR = 0.62  # claim (query prefix) to headline cosine for news_for_claim: absolute minimum
CLAIM_Z = 1.5  # ...and at least mean + 1.5 sd of the claim's similarity to every story headline (when >= 20 headlines):
# every headline about one story is close to every claim about it, so an absolute floor alone matches most of them
SPY_CLAIM = "Was Jensen Huang's mistress a Chinese spy?"
SPY_RE = re.compile(r"\b(spy|spies|spying|espionage|chinese intelligence|ministry of state security|honey ?trap)\b", re.I)
SMEAR_RE = re.compile(r"\b(smear\w*|witch[- ]hunt|hit job|hit piece|slander\w*|defam\w*|fabricat\w*|hoax)\b", re.I)

# Hedging: a headline or post "hedges" when it marks a claim as unproven or attributes it to someone else.
# The list is the brief's (alleged, allegedly, suspected, reportedly, accused, claims, purported, according to,
# tied to, linked to) plus inflections of the same words. Lexical, so it over-counts "claims" used dismissively and
# misses hedges like "report says"; it is applied identically to news and social text, so the comparison is fair.
HEDGE_TERMS = (
    "alleged", "allegedly", "allegation", "allegations",
    "suspected",
    "reportedly",
    "accused", "accusation", "accusations",
    "claim", "claims", "claimed",
    "purported", "purportedly",
    "according to",
    "tied to", "linked to",
)
HEDGE_RE = re.compile(r"\b(" + "|".join(re.escape(t).replace(r"\ ", r"\s+") for t in HEDGE_TERMS) + r")\b", re.I)

NOTE = (
    "What these newsrooms report: headlines from wire services and public broadcasters, each labeled with its "
    "funding. No outlet is neutral, and their coverage is not a ruling on whether the claim is true."
)

# Google News appends " - <publisher>" to every title.
_PUBLISHER_SUFFIXES = {
    "reuters", "ap news", "ap", "the associated press", "afp", "afp.com", "bbc", "bbc news", "bbc.com", "npr",
    "pbs", "pbs newshour", "dw", "dw.com", "dw (english)", "france 24", "france24", "al jazeera", "al jazeera english",
    "the guardian", "guardian",
}
_SUFFIX_RE = re.compile(r"\s+[-–|]\s+([^-–|]{2,40})$")

Embed = Callable[[list[str], bool], np.ndarray]  # (texts, is_query) -> L2-normalized rows
Llm = Callable[[list[tuple[int, str]], dict, str], list[dict]]  # (batch, narratives, story) -> label dicts


# ---------------------------------------------------------------- embedding


_MODEL = None


def default_embed(texts: list[str], query: bool = False) -> np.ndarray:
    """bge-small, the same model and query prefix as the corpus retrieval (src/retrieval/corpus.py)."""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    return embedder_from_model(_MODEL)(texts, query)


def embedder_from_model(model) -> Embed:
    """Reuse an already loaded SentenceTransformer (e.g. Store.corpus.model) instead of loading a second copy."""
    from src.retrieval.corpus import QUERY_PREFIX

    def embed(texts: list[str], query: bool = False) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        inp = [QUERY_PREFIX + t for t in texts] if query else list(texts)
        return np.asarray(model.encode(inp, normalize_embeddings=True, batch_size=64))

    return embed


# ---------------------------------------------------------------- loading


def clean_title(title: str) -> str:
    t = re.sub(r"\s+", " ", title or "").strip()
    m = _SUFFIX_RE.search(t)
    if m and m.group(1).strip().lower() in _PUBLISHER_SUFFIXES:
        t = t[: m.start()].strip()
    return t


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _iso(published: str) -> str | None:
    if not published:
        return None
    try:
        d = parsedate_to_datetime(published)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _term_re(terms: Iterable[str]) -> re.Pattern | None:
    terms = [t for t in terms if t]
    return re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.I) if terms else None


_COLUMNS = ["hid", "source", "funding", "title", "link", "published", "summary", "via", "term_hit", "relevance"]


def frame_headlines(rows: list[dict], terms: Iterable[str] = ()) -> pl.DataFrame:
    """Clean, de-duplicate (same link, or same outlet and same normalized title; the earliest copy wins)."""
    trx = _term_re(terms)
    seen_link, seen_title, out = set(), set(), []
    for r in sorted(rows, key=lambda r: _iso(r.get("published", "")) or "9999"):
        title = clean_title(r.get("title", ""))
        if not title:
            continue
        key = (r.get("source", ""), _norm(title))
        link = r.get("link", "")
        if (link and link in seen_link) or key in seen_title:
            continue
        seen_link.add(link)
        seen_title.add(key)
        summary = re.sub(r"\s+", " ", (r.get("summary") or "").replace("&nbsp;", " ")).strip()
        if _norm(summary).startswith(_norm(title)):
            summary = ""  # Google News "summary" is the title again
        out.append(
            {
                "hid": hashlib.sha1(f"{key[0]}|{key[1]}".encode()).hexdigest()[:12],
                "source": r.get("source", ""),
                "funding": r.get("funding", ""),
                "title": title,
                "link": link,
                "published": _iso(r.get("published", "")),
                "summary": summary[:500],
                "via": r.get("via", ""),
                "term_hit": bool(trx.search(f"{title} {summary}")) if trx else False,
                "relevance": None,
            }
        )
    schema = {c: pl.Utf8 for c in _COLUMNS} | {"term_hit": pl.Boolean, "relevance": pl.Float64}
    return pl.DataFrame(out, schema=schema)


def _read_jsonl(path: str | Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_headlines(
    path: str | Path = RAW_PATH,
    story: str | None = STORY,
    terms: Iterable[str] = STORY_TERMS,
    embed: Embed | None = None,
    floor: float = STORY_FLOOR,
    after: str | None = None,
    before: str | None = None,
) -> pl.DataFrame:
    """Read the jsonl from src/ingest/news.py and keep the story's headlines.

    A row is kept when it contains one of `terms` (whole word) or, with an embedder, when its title is at least
    `floor` cosine-similar to `story`. With neither terms nor story nothing is filtered. `relevance` holds the
    similarity when an embedder was given. `after`/`before` are ISO dates on `published`.
    """
    df = frame_headlines(_read_jsonl(path), terms)
    if after:
        df = df.filter(pl.col("published") >= after)
    if before:
        df = df.filter(pl.col("published") < before)
    if df.is_empty():
        return df
    if embed is not None and story:
        q = embed([story], False)[0]
        sims = embed(df["title"].to_list(), False) @ q
        df = df.with_columns(pl.Series("relevance", sims.astype(float)))
        keep = pl.col("term_hit") | (pl.col("relevance") >= floor)
    elif list(terms):
        keep = pl.col("term_hit")
    else:
        return df
    return df.filter(keep)


# ---------------------------------------------------------------- narratives


def story_narratives() -> dict[str, str]:
    """The post taxonomy (id -> description). Imported, not copied, so regenerated labels flow through."""
    from src.narratives.label import NARRATIVES

    return dict(NARRATIVES)


def narrative_labels() -> dict[str, str]:
    try:
        from src.api.analysis import NARRATIVE_LABELS

        return {k: v[0] for k, v in NARRATIVE_LABELS.items()}
    except Exception:  # noqa: BLE001 - the API module is optional here
        return {k: v.split(":")[0] for k, v in story_narratives().items()}


def taxonomy_hash(narratives: dict, story: str) -> str:
    return hashlib.sha1((story + json.dumps(narratives, sort_keys=True)).encode()).hexdigest()[:10]


PROMPT = """You label news headlines from wire services and public broadcasters.
The story: {story}
Narratives:
{narr}
For each headline return:
- "r": true if the headline is about this story, false if it is about something else
- "n": the one narrative id that fits best (n0 if none fits)
- "also": other narrative ids the headline clearly touches (often empty)
- "a": who the headline attributes its central claim or framing to, if it names someone (e.g. "Trump", "Beijing", "sources", "Justice Department"); "" if the outlet states it in its own voice
Return only JSON: {{"labels": [{{"i": <index>, "r": true, "n": "n1", "also": [], "a": ""}}, ...]}} with one entry per headline.
Headlines:
{items}"""

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def _deepseek_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key and Path(".env").exists():
        for line in Path(".env").read_text().splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set (env or .env)")
    return key


def deepseek_llm(batch: list[tuple[int, str]], narratives: dict, story: str, client: httpx.Client | None = None) -> list[dict]:
    narr = "\n".join(f"{k}: {v}" for k, v in narratives.items())
    items = "\n".join(f"[{i}] {t}".replace("\n", " ") for i, t in batch)
    body = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": PROMPT.format(story=story, narr=narr, items=items)}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    own = client is None
    client = client or httpx.Client(timeout=120, headers={"Authorization": f"Bearer {_deepseek_key()}"})
    try:
        for attempt in range(5):
            try:
                r = client.post(DEEPSEEK_URL, json=body)
                if r.status_code == 200:
                    return json.loads(r.json()["choices"][0]["message"]["content"]).get("labels", [])
                if r.status_code not in (429, 500, 502, 503, 504):
                    break
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                pass
            time.sleep(2**attempt)
    finally:
        if own:
            client.close()
    return []


_LABEL_SCHEMA = {
    "hid": pl.Utf8,
    "taxonomy": pl.Utf8,
    "relevant": pl.Boolean,
    "narrative_id": pl.Utf8,
    "also": pl.List(pl.Utf8),
    "attributed_to": pl.Utf8,
    "labeled_at": pl.Utf8,
}


def classify_headlines(
    df: pl.DataFrame,
    llm: Llm | None = None,
    cache_path: str | Path | None = LABELS_PATH,
    story: str = STORY,
    narratives: dict | None = None,
    batch_size: int = 25,
    workers: int = 4,
    offline: bool = False,
) -> pl.DataFrame:
    """Label each headline with a narrative id (same taxonomy as the posts), secondary ids, and attribution.

    Labels are cached by (hid, taxonomy hash); only missing headlines go to the LLM. `offline=True` never calls the
    LLM (request path). Returns `df` plus relevant, narrative_id, also, attributed_to (null where unlabeled).
    """
    narratives = narratives or story_narratives()
    tax = taxonomy_hash(narratives, story)
    cache = pl.DataFrame(schema=_LABEL_SCHEMA)
    if cache_path and Path(cache_path).exists():
        cache = pl.read_parquet(cache_path)
    have = set(cache.filter(pl.col("taxonomy") == tax)["hid"].to_list())
    todo = df.filter(~pl.col("hid").is_in(list(have))) if df.height else df
    if todo.height and not offline:
        llm = llm or deepseek_llm
        texts = [f"{r['source']}: {r['title']}" + (f" ({r['summary'][:200]})" if r["summary"] else "") for r in todo.iter_rows(named=True)]
        hids = todo["hid"].to_list()
        batches = [list(enumerate(texts))[j : j + batch_size] for j in range(0, len(texts), batch_size)]
        with ThreadPoolExecutor(max(1, workers)) as pool:
            results = list(pool.map(lambda b: llm(b, narratives, story), batches))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = {}
        for batch, res in zip(batches, results):
            idx = {i for i, _ in batch}
            for o in res or []:
                try:
                    i = int(o.get("i"))
                except (TypeError, ValueError):
                    continue
                n = o.get("n")
                if i not in idx or n not in narratives:
                    continue
                also = [x for x in (o.get("also") or []) if isinstance(x, str) and x in narratives and x != n]
                rows[hids[i]] = {
                    "hid": hids[i],
                    "taxonomy": tax,
                    "relevant": bool(o.get("r", True)),
                    "narrative_id": n,
                    "also": also,
                    "attributed_to": str(o.get("a") or "").strip(),
                    "labeled_at": now,
                }
        if rows:
            new = pl.DataFrame(list(rows.values()), schema=_LABEL_SCHEMA)
            cache = pl.concat([cache.filter(~((pl.col("taxonomy") == tax) & pl.col("hid").is_in(list(rows)))), new])
            if cache_path:
                Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
                cache.write_parquet(cache_path)
    lab = cache.filter(pl.col("taxonomy") == tax).unique(subset="hid", keep="last").drop("taxonomy", "labeled_at")
    return df.join(lab, on="hid", how="left")


def story_headlines(df: pl.DataFrame) -> pl.DataFrame:
    """Headlines that count for the story: the LLM said relevant, or (unlabeled) they contain a story term."""
    if "relevant" not in df.columns:
        return df
    return df.filter(pl.col("relevant").fill_null(pl.col("term_hit")))


# ---------------------------------------------------------------- hedging


def hedge_terms(text: str) -> list[str]:
    return [m.group(1).lower() for m in HEDGE_RE.finditer(text or "")]


def is_hedged(text: str) -> bool:
    return bool(HEDGE_RE.search(text or ""))


def hedging(texts: Iterable[str]) -> float:
    """Share of texts containing at least one HEDGE_TERMS phrase (0.0 for no texts)."""
    texts = list(texts)
    return sum(map(is_hedged, texts)) / len(texts) if texts else 0.0


def _hedge_block(texts: list[str]) -> dict:
    k = sum(map(is_hedged, texts))
    return {"share": round(k / len(texts), 4) if texts else None, "hedged": k, "n": len(texts)}


# ---------------------------------------------------------------- claim and story views


@lru_cache(maxsize=4)
def load_baseline(path: str = str(RAW_PATH), labels_path: str = str(LABELS_PATH)) -> pl.DataFrame:
    """The labeled story headlines from the cache (no LLM calls, no embedder: request-path safe)."""
    df = frame_headlines(_read_jsonl(path), STORY_TERMS)  # every cleaned row; the cache decides relevance
    labeled = classify_headlines(df, cache_path=labels_path, offline=True)
    if labeled["relevant"].is_null().all():  # no cache yet: fall back to the term filter
        return labeled.filter(pl.col("term_hit"))
    return labeled.filter(pl.col("relevant").fill_null(False))


_HEMB: dict[str, np.ndarray] = {}


def _headline_emb(df: pl.DataFrame, embed: Embed) -> np.ndarray:
    missing = [(h, t) for h, t in zip(df["hid"].to_list(), df["title"].to_list()) if h not in _HEMB]
    if missing:
        for (h, _), v in zip(missing, embed([t for _, t in missing], False)):
            _HEMB[h] = v
    return np.stack([_HEMB[h] for h in df["hid"].to_list()]) if df.height else np.zeros((0, 384))


def warm(embed: Embed | None = None) -> int:
    """Load the cached baseline and embed its headlines once. Call at API startup: the first news_for_claim
    otherwise pays about 10 s of CPU embedding; later calls take about 1 s. Returns the number of headlines."""
    h = load_baseline()
    _headline_emb(h, embed or default_embed)
    return h.height


def _mentions(df: pl.DataFrame) -> dict[str, int]:
    out: dict[str, int] = {}
    if "narrative_id" not in df.columns:
        return out
    for n, also in df.select("narrative_id", "also").iter_rows():
        for x in {n, *(also or [])} - {None}:
            out[x] = out.get(x, 0) + 1
    return out


def _headline_dict(r: dict, sim: float | None = None) -> dict:
    d = {k: r.get(k) for k in ("source", "funding", "title", "link", "published")}
    if sim is not None:
        d["similarity"] = round(float(sim), 4)
    if r.get("narrative_id"):
        d["narrative_id"] = r["narrative_id"]
    if r.get("attributed_to"):
        d["attributed_to"] = r["attributed_to"]
    d["hedged"] = is_hedged(r.get("title", ""))
    return d


def news_for_claim(
    claim_text: str,
    matched_social_posts: pl.DataFrame,
    headlines: pl.DataFrame | None = None,
    embed: Embed | None = None,
    k: int = 10,
    floor: float = CLAIM_FLOOR,
    z: float = CLAIM_Z,
    min_social_share: float = 0.05,
) -> dict:
    """The `news` block for /claim.

    matched_social_posts: the claim's matched posts with `text` and (optionally) `narrative_id`.
    headlines: defaults to the cached Jensen baseline; pass fetch_live_headlines(...) for the live path.
    A headline matches when its cosine to the claim is at least max(floor, mean + z * sd) over all headlines (the
    relative part only with 20+ headlines). Every match counts for outlets, narratives and hedging; the top `k` are
    listed. A social narrative is "only on social" when it holds at least `min_social_share` of the matched posts and
    fewer than max(1, 2% of matched headlines) touch it (primary or secondary label).
    """
    labels = narrative_labels()
    headlines = load_baseline() if headlines is None else headlines
    embed = embed or default_embed
    social_texts = matched_social_posts["text"].to_list() if "text" in matched_social_posts.columns else []
    m = headlines.head(0)
    sims = np.zeros(0)
    cutoff = floor
    if headlines.height:
        q = embed([claim_text], True)[0]
        s = _headline_emb(headlines, embed) @ q
        if len(s) >= 20:
            cutoff = max(floor, float(s.mean() + z * s.std()))
        keep = np.where(s >= cutoff)[0]
        keep = keep[np.argsort(-s[keep])]
        m, sims = headlines[keep.tolist()], s[keep]
    out = {
        "headlines": [_headline_dict(r, sim) for r, sim in zip(m.head(k).iter_rows(named=True), sims[:k])],
        "n_headlines": m.height,
        "outlets": {},
        "outlet_funding": {},
        "narratives_in_news": [],
        "narratives_only_on_social": [],
        "hedging": {
            "news_share": round(hedging(m["title"].to_list()), 4) if m.height else None,
            "social_share": round(hedging(social_texts), 4) if social_texts else None,
            "n_news": m.height,
            "n_social": len(social_texts),
            "terms": list(HEDGE_TERMS),
        },
        "similarity_cutoff": round(cutoff, 4),
        "note": NOTE,
    }
    for src, fund in m.select("source", "funding").iter_rows():
        out["outlets"][src] = out["outlets"].get(src, 0) + 1
        out["outlet_funding"][src] = fund
    out["outlets"] = dict(sorted(out["outlets"].items(), key=lambda kv: -kv[1]))

    social_n: dict[str, int] = {}
    if "narrative_id" in matched_social_posts.columns:
        for n in matched_social_posts["narrative_id"].fill_null("n0").to_list():
            social_n[n] = social_n.get(n, 0) + 1
    total_social = sum(social_n.values())
    if "narrative_id" not in headlines.columns:
        out["narratives_note"] = "headlines for this story are not labeled with narratives"
        return out
    news_mentions = _mentions(m)
    story_mentions = _mentions(headlines)
    for n, c in sorted(news_mentions.items(), key=lambda kv: -kv[1]):
        out["narratives_in_news"].append(
            {
                "id": n,
                "label": labels.get(n, n),
                "news_headlines": c,
                "news_share": round(c / m.height, 4),
                "social_share": round(social_n.get(n, 0) / total_social, 4) if total_social else None,
            }
        )
    for n, c in sorted(social_n.items(), key=lambda kv: -kv[1]):
        if n == "n0" or c / total_social < min_social_share or news_mentions.get(n, 0) >= max(1, 0.02 * m.height):
            continue
        out["narratives_only_on_social"].append(
            {
                "id": n,
                "label": labels.get(n, n),
                "social_posts": c,
                "social_share": round(c / total_social, 4),
                "news_headlines_matching_claim": news_mentions.get(n, 0),
                "news_headlines_whole_story": story_mentions.get(n, 0),
            }
        )
    return out


def social_posts(posts_path: str | Path = POSTS_PATH, pn_path: str | Path = POST_NARRATIVE_PATH) -> pl.DataFrame:
    posts = pl.read_parquet(posts_path, columns=None)
    if "in_story" in posts.columns:
        posts = posts.filter(pl.col("in_story").fill_null(True))
    pn = pl.read_parquet(pn_path).select("post_id", "narrative_id")
    cols = [c for c in ("post_id", "text", "urls") if c in posts.columns]
    return posts.select(cols).join(pn, on="post_id", how="left").with_columns(pl.col("narrative_id").fill_null("n0"))


def story_baseline(
    headlines: pl.DataFrame | None = None,
    posts: pl.DataFrame | None = None,
    claim: str = SPY_CLAIM,
    gap_share: float = 0.05,
    news_floor_share: float = 0.02,
) -> dict:
    """The dashboard's news column for the story.

    headlines: labeled story headlines (default: load_baseline()). posts: post_id, text, narrative_id
    (default: posts.parquet in the story joined to post_narrative.parquet).
    """
    labels = narrative_labels()
    h = load_baseline() if headlines is None else headlines
    p = social_posts() if posts is None else posts
    nh, npo = h.height, p.height
    news_primary = dict(h.group_by("narrative_id").len().iter_rows()) if nh else {}
    news_mention = _mentions(h)
    social_n = dict(p.group_by("narrative_id").len().iter_rows()) if npo else {}
    ids = sorted(set(labels) | set(news_primary) | set(social_n), key=lambda x: (x == "n0", x))
    narratives = []
    for n in ids:
        ex = h.filter(pl.col("narrative_id") == n).sort("published", descending=True).head(3) if nh else h
        ns = news_primary.get(n, 0) / nh if nh else 0.0
        ss = social_n.get(n, 0) / npo if npo else 0.0
        narratives.append(
            {
                "id": n,
                "label": labels.get(n, n),
                "news_headlines": news_primary.get(n, 0),
                "news_share": round(ns, 4),
                "news_mentions": news_mention.get(n, 0),
                "social_posts": social_n.get(n, 0),
                "social_share": round(ss, 4),
                "only_on_social": n != "n0" and ss >= gap_share and news_mention.get(n, 0) < max(1, news_floor_share * nh),
                "example_headlines": [_headline_dict(r) for r in ex.iter_rows(named=True)],
            }
        )

    spy_news = h.filter(pl.col("title").map_elements(lambda t: bool(SPY_RE.search(t)), return_dtype=pl.Boolean)) if nh else h
    spy_p = p.filter(pl.col("text").map_elements(lambda t: bool(t and SPY_RE.search(t)), return_dtype=pl.Boolean)) if npo else p
    spy_social = spy_p["text"].to_list()
    has_link = spy_p["urls"].list.len() > 0 if "urls" in spy_p.columns else None
    uniq = list(dict.fromkeys(" ".join(t.lower().split()) for t in spy_social))
    n1_news = h.filter(pl.col("narrative_id") == "n1")["title"].to_list() if nh else []
    n1_social = p.filter(pl.col("narrative_id") == "n1")["text"].to_list() if npo else []
    hedge = {
        "claim": claim,
        "definition": "spy-related = the headline or post matches " + SPY_RE.pattern + "; hedged = contains a HEDGE_TERMS phrase",
        "news": _hedge_block(spy_news["title"].to_list()),
        "social": _hedge_block(spy_social),
        "social_unique_texts": _hedge_block(uniq),
        # posts with a link are often a shared headline; posts without one are closer to people's own words
        "social_with_link": _hedge_block(spy_p.filter(has_link)["text"].to_list()) if has_link is not None else None,
        "social_without_link": _hedge_block(spy_p.filter(~has_link)["text"].to_list()) if has_link is not None else None,
        "by_narrative_n1": {"news": _hedge_block(n1_news), "social": _hedge_block(n1_social)},
        "examples_hedged": [_headline_dict(r) for r in spy_news.filter(pl.col("title").map_elements(is_hedged, return_dtype=pl.Boolean)).head(3).iter_rows(named=True)] if spy_news.height else [],
        "examples_unhedged": [_headline_dict(r) for r in spy_news.filter(~pl.col("title").map_elements(is_hedged, return_dtype=pl.Boolean)).head(3).iter_rows(named=True)] if spy_news.height else [],
        "terms": list(HEDGE_TERMS),
    }

    smear = h.filter(pl.col("title").map_elements(lambda t: bool(SMEAR_RE.search(t)), return_dtype=pl.Boolean)) if nh else h
    social_smear = [t for t in p["text"].to_list() if t and SMEAR_RE.search(t)]
    attributed = [
        {**_headline_dict(r), "framing": SMEAR_RE.search(r["title"]).group(1).lower(), "attributed_to": r.get("attributed_to") or ""}
        for r in smear.iter_rows(named=True)
    ]
    defend = h.filter((pl.col("narrative_id") == "n6") | pl.col("also").list.contains("n6")) if nh else h
    defending = [_headline_dict(r) | {"attributed_to": r.get("attributed_to") or ""} for r in defend.iter_rows(named=True)]
    outlets = (
        h.group_by("source", "funding").len().sort("len", descending=True).rename({"len": "headlines"}).to_dicts() if nh else []
    )
    return {
        "story": STORY,
        "n_headlines": nh,
        "n_social_posts": npo,
        "outlets": outlets,
        "narratives": narratives,
        "narratives_only_on_social": [x["id"] for x in narratives if x["only_on_social"]],
        "hedging": hedge,
        "attributed_claims": {
            "framing": "smear / witch hunt / hit job / fabricated / hoax",
            "headlines": attributed,
            "headlines_attributed": sum(1 for a in attributed if a["attributed_to"]),
            "social_posts_with_framing": len(social_smear),
            "social_posts_with_framing_hedged": sum(map(is_hedged, social_smear)),
        },
        "defending_in_news": {
            "narrative": "n6",
            "headlines": defending,
            "n": len(defending),
            "attributed": sum(1 for d in defending if d["attributed_to"]),
        },
        "note": NOTE,
    }


# ---------------------------------------------------------------- live path

_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "was", "are", "were", "be", "it", "its",
         "that", "this", "with", "as", "at", "by", "from", "about", "did", "does", "do", "has", "have", "had", "who",
         "what", "why", "how", "when", "s"}


def query_terms(query: str) -> list[str]:
    return [t for t in re.findall(r"\w+", query.lower()) if t not in _STOP and len(t) > 2]


def fetch_live_headlines(
    query: str,
    days: int = 7,
    client: httpx.Client | None = None,
    workers: int = 5,
    own_rss: bool = True,
) -> pl.DataFrame:
    """Headlines about any story from the same outlets: Google News RSS site search over the last `days` days for
    every outlet, plus the outlets' own RSS feeds filtered to items containing every query term. Same columns as
    load_headlines(). Google News site search is loose (it returns an outlet's unrelated top stories), so only
    headlines containing at least half of the query's content words (whole words, title + summary) are kept.
    About 17 parallel requests, a few seconds."""
    from src.ingest.news import RSS, SOURCES, UA, parse

    terms = query_terms(query) or [t.lower() for t in re.findall(r"\w+", query)]
    own = client is None
    client = client or httpx.Client(timeout=10, headers=UA, follow_redirects=True)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def google(item):
        name, (domain, funding) = item
        q = urllib.parse.quote(f"{query} site:{domain} when:{days}d")
        try:
            r = client.get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
            items = parse(r.text) if r.status_code == 200 else []
        except httpx.HTTPError:
            items = []
        return [{"source": name, "funding": funding, "via": "google_news_rss", **it} for it in items]

    def feed(item):
        name, url = item
        try:
            r = client.get(url)
            items = parse(r.text) if r.status_code == 200 else []
        except httpx.HTTPError:
            items = []
        return [
            {"source": name, "funding": SOURCES[name][1], "via": "rss", **it}
            for it in items
            if all(t in (it["title"] + " " + it["summary"]).lower() for t in terms)
        ]

    try:
        with ThreadPoolExecutor(max(1, workers)) as pool:
            jobs = [pool.submit(google, it) for it in SOURCES.items()]
            if own_rss:
                jobs += [pool.submit(feed, it) for it in RSS.items()]
            rows = [r for j in jobs for r in j.result()]
    finally:
        if own:
            client.close()
    df = frame_headlines(rows, terms)
    need = max(1, -(-len(terms) // 2))
    word = [re.compile(r"\b" + re.escape(t) + r"\b", re.I) for t in terms]
    hits = [sum(bool(w.search(f"{t} {s}")) for w in word) for t, s in zip(df["title"].to_list(), df["summary"].to_list())]
    df = df.filter(pl.Series(hits) >= need) if df.height else df
    return df.filter(pl.col("published").is_null() | (pl.col("published") >= since)).sort("published", descending=True, nulls_last=True)


# ---------------------------------------------------------------- CLI


def _table(b: dict) -> str:
    lines = ["| Narrative | News headlines (primary) | News share | Headlines mentioning | Social posts | Social share | Only on social |", "|---|---:|---:|---:|---:|---:|---|"]
    for x in b["narratives"]:
        lines.append(
            f"| {x['id']} {x['label']} | {x['news_headlines']} | {x['news_share']:.1%} | {x['news_mentions']} | {x['social_posts']:,} | {x['social_share']:.1%} | {'yes' if x['only_on_social'] else ''} |"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lab = sub.add_parser("label", help="filter and LLM-label the story headlines, then write story_baseline.json")
    lab.add_argument("--raw", default=str(RAW_PATH))
    lab.add_argument("--no-embed", action="store_true", help="term filter only (no sentence-transformers)")
    sub.add_parser("story", help="print the per-narrative table and hedging from the cache")
    cl = sub.add_parser("claim")
    cl.add_argument("--text", default=SPY_CLAIM)
    lv = sub.add_parser("live")
    lv.add_argument("--q", required=True)
    lv.add_argument("--days", type=int, default=7)
    a = ap.parse_args()

    if a.cmd == "label":
        t0 = time.time()
        df = load_headlines(a.raw, embed=None if a.no_embed else default_embed)
        print(f"candidates after dedupe + relevance filter: {df.height} ({df['term_hit'].sum()} with a story term)")
        lab_df = classify_headlines(df)
        rel = story_headlines(lab_df)
        print(f"LLM-labeled: {lab_df['narrative_id'].is_not_null().sum()}, relevant: {rel.height}, {time.time() - t0:.0f}s")
    if a.cmd in ("label", "story"):
        load_baseline.cache_clear()
        b = story_baseline()
        NEWS_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE_JSON.write_text(json.dumps(b, indent=1, default=str))
        print(f"{b['n_headlines']} story headlines, {b['n_social_posts']:,} social posts -> {BASELINE_JSON}\n")
        print(_table(b))
        hd = b["hedging"]
        print(f"\nHedging, spy-related: news {hd['news']['hedged']}/{hd['news']['n']} = {hd['news']['share']}, social {hd['social']['hedged']}/{hd['social']['n']} = {hd['social']['share']} (unique texts {hd['social_unique_texts']['share']})")
        for key in ("social_with_link", "social_without_link"):
            if hd.get(key):
                print(f"  {key}: {hd[key]['hedged']}/{hd[key]['n']} = {hd[key]['share']}")
        dn = b["defending_in_news"]
        print(f"Defending Huang (n6) in news: {dn['n']} headlines, {dn['attributed']} attribute the defense to someone")
        for x in dn["headlines"]:
            print(f"  [{x['source']}; {x['funding']}] {x['title']}  (attributed to: {x['attributed_to'] or '-'})")
        print("Attributed 'smear' framing:")
        for x in b["attributed_claims"]["headlines"]:
            print(f"  [{x['source']}; {x['funding']}] {x['title']}  (attributed to: {x['attributed_to'] or '-'})")
    elif a.cmd == "claim":
        posts = social_posts()
        print(json.dumps(news_for_claim(a.text, posts.head(0)), indent=1, default=str))
    elif a.cmd == "live":
        df = fetch_live_headlines(a.q, a.days)
        print(df.group_by("source").len().sort("len", descending=True))
        for r in df.head(15).iter_rows(named=True):
            print(f"{r['published']} [{r['source']}] {r['title']}")


if __name__ == "__main__":
    main()

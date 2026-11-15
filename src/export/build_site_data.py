"""Export the dashboard's data file (H8): data/processed/* -> web/public/site_data.json.

    python -m src.export.build_site_data [--processed data/processed] [--out web/public/site_data.json]
                                         [--sample-out data/sample/site_data.sample.json]

Shape: README "site_data.json" plus the docs/DEMO.md additions (evidence on narratives, archetypes and clusters,
threshold_strip per narrative, challenge), and: hourly timeline with likely automated counts, the narrative ranking
recomputed without likely automated accounts and their engagement, a sampled replay graph, coordination clusters,
a news baseline and a list of plain-language findings computed from the data.

Every input is optional. A missing table gives an empty section, never a crash, because this runs on every refresh
while narratives and bot scores are being regenerated.

Privacy: every account that leaves the machine goes through src.model.schema.public_ref. Only nameable accounts
(public under the README rule, and never an undisclosed likely automated account under 5,000 followers) get a handle,
a post URI or post text. Everyone else is a salted hash with no URI and no text. @mentions of accounts that are not
nameable are masked in any text we ship.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl

from src import config as cfg
from src.model.schema import PUBLIC_FOLLOWERS, hashed_id, public_ref
from src.export.translate import CACHE_NAME, Translator, deepseek_translator, translate_challenge
from src.stats import ratio_ci, share_ci

AUTOMATED = cfg.HEADLINE_THRESHOLD  # "likely automated" for headline shares and the bots-off toggle
NODE_CAP = 1500
EDGE_CAP = 4000
PUBLIC_ACCOUNTS_CAP = 200
EVIDENCE_N = 10
EXAMPLES_N = 3
ENGAGE_TYPES = ("like", "repost", "quote")

STORY_TITLE = "Jensen Huang's exit from Nvidia, November 5 to 13, 2026"
# Event markers. Times are UTC. The first three are the DEMO markers; the two earlier ones use the time of the first
# Bluesky post reporting them in our corpus (stated in "source").
EVENTS = [
    {"t": "2026-11-05T18:45:12Z", "label": "House Republicans ask Huang for a briefing on the spy allegations",
     "source": "time of the first Bluesky post in our corpus sharing the Reuters report"},
    {"t": "2026-11-08T20:00:30Z", "label": "Huang admits the affair; Nvidia's board opens an investigation",
     "source": "time of the first Bluesky post in our corpus reporting the admission"},
    {"t": "2026-11-11T22:43:00Z", "label": "WSJ reports the board is moving to oust Huang", "source": "WSJ"},
    {"t": "2026-11-12T13:55:00Z", "label": "Huang resigns as Nvidia CEO", "source": "Nvidia announcement"},
    {"t": "2026-11-12T20:15:00Z", "label": "Washington Post reports 'online bots' defending Huang", "source": "Washington Post"},
]

FALLBACK_LABELS = {  # mirror of src/api/analysis.py NARRATIVE_LABELS, used only if that import fails
    "n1": ("Spy plot and national security", "anti_huang"),
    "n2": ("The affairs as personal misconduct", "anti_huang"),
    "n3": ("Trump and politics", "political"),
    "n4": ("Board, resignation and succession", "neutral_news"),
    "n5": ("Stock, market and lawsuits", "neutral_news"),
    "n6": ("Defending Huang", "pro_huang"),
    "n7": ("Jokes and memes", "humor"),
    "n0": ("No narrative", "other"),
}

# One definition of "spy-related" and "hedged" for the whole project: the news module's (src/news/baseline.py), so the
# dashboard, the API and the pitch quote the same numbers.
from src.news.baseline import HEDGE_TERMS, SPY_RE, is_hedged  # noqa: E402

STORY_RE = re.compile(r"huang|nvidia", re.I)  # raw-feed fallback only: the labeled headline set is already on the story
# Any @mention: Bluesky handles (@name.bsky.social, @domain.com) and other platforms' (@name on X). Only mentions of a
# nameable Bluesky account survive the export; everything else is masked, because we can't check who it is.
MENTION_RE = re.compile(r"(?<![\w.@/])@([A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?)")
MASKED_MENTION = "@[account]"


# ---------------------------------------------------------------- helpers

def _iso(s) -> str | None:
    """Any ISO-ish timestamp -> 'YYYY-MM-DDTHH:MM:SSZ' in UTC, or None. Rejects dates far outside the story."""
    if not s:
        return None
    try:
        txt = str(s).replace("Z", "+00:00")
        m = re.match(r"^(.*T\d\d:\d\d:\d\d)(\.\d+)?(.*)$", txt)
        if m:  # fromisoformat in 3.11 rejects more than 6 fractional digits
            txt = m.group(1) + (m.group(2)[:7] if m.group(2) else "") + m.group(3)
        d = datetime.fromisoformat(txt)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        d = d.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None
    lo = datetime.fromisoformat(cfg.STORY_START.replace("Z", "+00:00")) - timedelta(days=3650)
    hi = datetime.fromisoformat(cfg.STORY_END.replace("Z", "+00:00")) + timedelta(days=60)
    if not (lo <= d <= hi):
        return None
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_times(df: pl.DataFrame, col: str, out: str) -> pl.DataFrame:
    vals = df[col].unique().to_list()
    mp = {v: _iso(v) for v in vals if v is not None}
    return df.with_columns(pl.col(col).replace_strict(mp, default=None, return_dtype=pl.Utf8).alias(out))


def _r(x, n=4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)


def _read(path: Path) -> pl.DataFrame | None:
    try:
        return pl.read_parquet(path) if path.exists() else None
    except Exception as e:  # a half-written table during regeneration
        warnings.warn(f"could not read {path}: {e}")
        return None


def _first(*paths: Path) -> pl.DataFrame | None:
    for p in paths:
        df = _read(p)
        if df is not None:
            return df
    return None


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _pct1(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{100 * x:.1f}%" if x < 0.1 else f"{100 * x:.0f}%"


# ---------------------------------------------------------------- inputs

@dataclass
class Ctx:
    posts: pl.DataFrame | None = None  # post_id, account_id, t, text, engagement, narrative_id, side, p
    accounts: dict = field(default_factory=dict)  # did -> row
    scores: dict = field(default_factory=dict)  # did -> p_automated
    reasons: dict = field(default_factory=dict)
    coord_id: dict = field(default_factory=dict)
    have_scores: bool = False
    have_narratives: bool = False
    inter: pl.DataFrame | None = None  # src, dst, type, post_id, t
    arch_member: dict = field(default_factory=dict)  # did -> archetype_id
    arch_meta: pl.DataFrame | None = None  # archetypes.parquet (M5), if present
    arch_labels: dict = field(default_factory=dict)
    user_features: pl.DataFrame | None = None
    labels: dict = field(default_factory=dict)  # narrative_id -> (label, side)
    clusters: list = field(default_factory=list)
    news: list = field(default_factory=list)
    challenge: list = field(default_factory=list)
    eval_dir: Path = Path("eval")
    processed: Path = Path("data/processed")
    arch_role: dict = field(default_factory=dict)  # did -> "amplifier" | "control" (M5's matched sample)
    headlines: list = field(default_factory=list)  # story headlines: source, funding, title, link, published
    headlines_on_story: bool = False  # True when they come from the news module's labeled (story-relevant) set
    story_baseline: dict = field(default_factory=dict)  # data/processed/news/story_baseline.json (src.news.baseline)
    challenge_meta: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    # challenge post translation (src/export/translate.py): None = cached results only, never a network call
    translator: Translator | None = None
    translation: dict = field(default_factory=dict)  # summary of the last challenge translation

    # --- privacy
    def nameable(self, did: str) -> bool:
        a = self.accounts.get(did)
        if not a or not a.get("is_public") or not a.get("handle") or a["handle"] == "handle.invalid":
            return False
        p = self.scores.get(did)
        if p is not None and p >= AUTOMATED and not a.get("self_label_bot") and (a.get("followers") or 0) < PUBLIC_FOLLOWERS:
            return False  # README rule 5: undisclosed likely automated accounts under 5,000 followers are never named
        return True

    def ref(self, did: str) -> dict:
        a = self.accounts.get(did) or {}
        return public_ref(did, a.get("handle"), self.nameable(did))

    def mask(self, text: str | None, n: int = 280) -> str:
        if not text:
            return ""
        ok = self._public_handles()
        return MENTION_RE.sub(lambda m: m.group(0) if m.group(1).lower() in ok else MASKED_MENTION, text)[:n]

    _ph: set | None = None

    def _public_handles(self) -> set:
        if self._ph is None:
            self._ph = {(a.get("handle") or "").lower() for d, a in self.accounts.items() if self.nameable(d)}
        return self._ph

    def post_ev(self, did: str, uri: str | None, t: str | None, note: str, text: str | None = None) -> dict:
        """One evidence item. URI and text only for nameable authors (a post URI carries the author's DID)."""
        r = self.ref(did)
        named = r["public_handle"] is not None
        ev = {"post_uri": uri if named else None, "t": t, "note": note, "account_ref": r["ref"], "public_handle": r["public_handle"]}
        if named:
            ev["url"] = _bsky_url(r["public_handle"], uri)
            if text:
                ev["text"] = self.mask(text)
        return ev


def _bsky_url(handle: str | None, uri: str | None) -> str | None:
    if not handle or not uri or "/app.bsky.feed.post/" not in uri:
        return None
    return f"https://bsky.app/profile/{handle}/post/{uri.rsplit('/', 1)[-1]}"


def _labels() -> dict:
    try:
        from src.api.analysis import NARRATIVE_LABELS

        return dict(NARRATIVE_LABELS)
    except Exception:
        return dict(FALLBACK_LABELS)


def load(processed: str = "data/processed", raw: str = "data/raw", eval_dir: str = "eval", sample: str = "data/sample") -> Ctx:
    b, art = Path(processed), Path(processed) / "artifacts"
    c = Ctx(eval_dir=Path(eval_dir), processed=b)
    acc = _read(b / "accounts.parquet")
    if acc is not None:
        keep = [k for k in ("account_id", "handle", "is_public", "created_at", "followers", "follows", "posts_count", "self_label_bot", "bridged") if k in acc.columns]
        c.accounts = {r["account_id"]: r for r in acc.select(keep).iter_rows(named=True)}
    bs = _read(art / "bot_scores.parquet")
    if bs is not None and "p_automated" in bs.columns:
        c.have_scores = True
        c.scores = dict(zip(bs["account_id"].to_list(), [float(x) if x is not None else None for x in bs["p_automated"].to_list()]))
        if "reasons" in bs.columns:
            c.reasons = {a: list(r or []) for a, r in zip(bs["account_id"].to_list(), bs["reasons"].to_list())}
        if "coord_cluster_id" in bs.columns:
            c.coord_id = {a: x for a, x in zip(bs["account_id"].to_list(), bs["coord_cluster_id"].to_list()) if x is not None}
        c.sources["bot_model"] = (bs["model_version"][0] if "model_version" in bs.columns else bs["model"][0] if "model" in bs.columns else None) if bs.height else None
    c.labels = _labels()
    nar = _read(b / "narratives.parquet")
    if nar is not None and {"narrative_id", "label"} <= set(nar.columns):
        for r in nar.iter_rows(named=True):
            c.labels[r["narrative_id"]] = (r["label"], r.get("side") or c.labels.get(r["narrative_id"], ("", "other"))[1])
    posts = _read(b / "posts.parquet")
    if posts is not None:
        eng = [k for k in ("like_count", "repost_count", "quote_count", "reply_count") if k in posts.columns]
        posts = posts.with_columns(
            (pl.sum_horizontal([pl.col(k).fill_null(0) for k in eng]) if eng else pl.lit(0)).alias("engagement"),
            *([pl.col("like_count").fill_null(0).alias("likes")] if "like_count" in posts.columns else [pl.lit(0).alias("likes")]),
        )
        posts = posts.with_columns(
            (pl.col("urls").list.len().fill_null(0) > 0).alias("has_link") if "urls" in posts.columns else pl.lit(None, dtype=pl.Boolean).alias("has_link")
        )
        posts = _norm_times(posts, "created_at", "t").select("post_id", "account_id", "t", "text", "engagement", "likes", "has_link")
        pn = _first(b / "narratives" / "post_narrative.parquet", b / "post_narrative.parquet")
        if pn is not None and {"post_id", "narrative_id"} <= set(pn.columns):
            c.have_narratives = True
            pn = pn.sort("prob", descending=True) if "prob" in pn.columns else pn
            cols = ["post_id", "narrative_id"] + (["side"] if "side" in pn.columns else [])
            posts = posts.join(pn.unique(subset="post_id", keep="first").select(cols), on="post_id", how="left")
        if "narrative_id" not in posts.columns:
            posts = posts.with_columns(pl.lit(None, dtype=pl.Utf8).alias("narrative_id"))
        if "side" not in posts.columns:
            posts = posts.with_columns(pl.lit(None, dtype=pl.Utf8).alias("side"))
        posts = posts.with_columns(pl.col("account_id").replace_strict(c.scores, default=None, return_dtype=pl.Float64).alias("p"))
        c.posts = posts
    inter = _read(b / "interactions.parquet")
    if inter is not None and inter.height:
        inter = inter.filter(pl.col("type").is_in(list(ENGAGE_TYPES)))
        inter = _norm_times(inter, "created_at", "t0") if "created_at" in inter.columns else inter.with_columns(pl.lit(None, dtype=pl.Utf8).alias("t0"))
        if c.posts is not None:  # reposts carry no timestamp: fall back to the engaged post's time, flagged approximate
            inter = inter.join(c.posts.select("post_id", pl.col("t").alias("post_t"), "narrative_id"), on="post_id", how="left")
        else:
            inter = inter.with_columns(pl.lit(None, dtype=pl.Utf8).alias("post_t"), pl.lit(None, dtype=pl.Utf8).alias("narrative_id"))
        c.inter = inter.select(
            pl.col("src_account_id").alias("src"), pl.col("dst_account_id").alias("dst"), "type", "post_id", "narrative_id",
            pl.coalesce("t0", "post_t").alias("t"), pl.col("t0").is_null().alias("t_approx"),
        )
    ua = _first(b / "user_archetype.parquet", art / "user_archetype.parquet")
    if ua is not None and {"account_id", "archetype_id"} <= set(ua.columns):
        c.arch_member = dict(zip(ua["account_id"].to_list(), ua["archetype_id"].to_list()))
        if "role" in ua.columns:
            c.arch_role = dict(zip(ua["account_id"].to_list(), ua["role"].to_list()))
        if "label" in ua.columns:
            c.arch_labels = dict(ua.select("archetype_id", "label").unique(subset="archetype_id").iter_rows())
    c.arch_meta = _first(b / "archetypes.parquet", art / "archetypes.parquet")
    if c.arch_meta is not None and {"archetype_id", "label"} <= set(c.arch_meta.columns):
        c.arch_labels.update(dict(c.arch_meta.select("archetype_id", "label").iter_rows()))
    c.user_features = _first(b / "user_features.parquet")
    cj = art / "coord_clusters.json"
    if cj.exists():
        try:
            d = json.loads(cj.read_text())
            c.clusters = d.get("clusters", d) if isinstance(d, dict) else d
        except Exception as e:
            warnings.warn(f"could not read {cj}: {e}")
    nj = Path(raw) / "news_jensen.jsonl"
    if nj.exists():
        c.news = [json.loads(l) for l in nj.open() if l.strip()]
        labels = b / "news" / "headline_labels.parquet"
        if labels.exists():  # the news module's labeled story headlines (cache only, no LLM or embedder calls)
            try:
                from src.news.baseline import load_baseline

                h = load_baseline(str(nj), str(labels))
                c.headlines = [{k: r.get(k) for k in ("source", "funding", "title", "link", "published")} for r in h.iter_rows(named=True)]
                c.headlines_on_story = True
            except Exception as e:
                warnings.warn(f"could not load the labeled headlines ({e}); using the raw feed")
        if not c.headlines:
            seen = set()
            for r in c.news:
                title = re.sub(r"\s+-\s+[^-]{2,40}$", "", r.get("title") or "").strip()
                key = (r.get("source"), title.lower())
                if title and key not in seen:
                    seen.add(key)
                    c.headlines.append({"source": r.get("source"), "funding": r.get("funding"), "title": title, "link": r.get("link"), "published": r.get("published")})
    sbj = b / "news" / "story_baseline.json"
    if sbj.exists():
        try:
            c.story_baseline = json.loads(sbj.read_text())
        except Exception as e:
            warnings.warn(f"could not read {sbj}: {e}")
    ch = Path(sample) / "challenge.json"
    if ch.exists():
        try:
            d = json.loads(ch.read_text())
            c.challenge = d.get("accounts", d) if isinstance(d, dict) else d
            c.challenge_meta = {k: v for k, v in d.items() if k != "accounts"} if isinstance(d, dict) else {}
        except Exception as e:
            warnings.warn(f"could not read {ch}: {e}")
    mf = art / "manifest.json"
    if mf.exists():
        try:
            c.manifest = json.loads(mf.read_text())
        except Exception:
            pass
    return c


# ---------------------------------------------------------------- sections

def story(c: Ctx) -> dict:
    out = {"title": STORY_TITLE, "window": {"from": cfg.STORY_START, "to": cfg.STORY_END}, "platform": "Bluesky", "events": EVENTS}
    if c.posts is not None:
        out["posts"] = c.posts.height
        out["accounts"] = c.posts["account_id"].n_unique()
    if c.inter is not None:
        out["engagements"] = c.inter.height
    return out


def timeline(c: Ctx) -> list[dict]:
    if c.posts is None:
        return []
    p = c.posts.filter(pl.col("t").is_not_null() & (pl.col("t") >= cfg.STORY_START) & (pl.col("t") < cfg.STORY_END))
    p = p.with_columns((pl.col("t").str.slice(0, 13) + ":00:00Z").alias("hour"), (pl.col("p").fill_null(0.0) >= AUTOMATED).alias("auto"))
    total = dict(p.group_by("hour").agg(pl.len(), pl.col("auto").sum().alias("a")).select("hour", pl.struct("len", "a")).iter_rows())
    byn: dict = defaultdict(dict)
    abyn: dict = defaultdict(dict)
    for h, n, k, a in p.filter(pl.col("narrative_id").is_not_null()).group_by("hour", "narrative_id").agg(pl.len(), pl.col("auto").sum().alias("a")).iter_rows():
        byn[h][n] = k
        if a:
            abyn[h][n] = a
    eng: dict = {}
    if c.inter is not None:
        i = c.inter.filter(pl.col("t").is_not_null() & ~pl.col("t_approx") & (pl.col("t") >= cfg.STORY_START) & (pl.col("t") < cfg.STORY_END))
        eng = dict(i.group_by(pl.col("t").str.slice(0, 13) + ":00:00Z").len().iter_rows())
    start = datetime.fromisoformat(cfg.STORY_START.replace("Z", "+00:00"))
    end = datetime.fromisoformat(cfg.STORY_END.replace("Z", "+00:00"))
    out, h = [], start
    while h < end:
        key = h.strftime("%Y-%m-%dT%H:00:00Z")
        tot = total.get(key, {"len": 0, "a": 0})
        row = {"hour": key, "posts": tot["len"], "by_narrative": dict(sorted(byn.get(key, {}).items()))}
        if c.have_scores:
            row["likely_automated"] = int(tot["a"])
            row["likely_automated_by_narrative"] = dict(sorted(abyn.get(key, {}).items()))
        if c.inter is not None:
            row["engagements"] = eng.get(key, 0)
        out.append(row)
        h += timedelta(hours=1)
    return out


def _block(df: pl.DataFrame, full: bool = True) -> dict:
    """Shares for one set of post rows (account_id, p). Same fields as src.bots.narrative_shares (M4).

    Intervals come from the shared bootstrap (src.stats.share_ci). Shares shown without an interval
    (account strip; the with_bridged strip) are the same point estimate share_ci returns, computed directly
    to keep the export fast."""
    by_acct: dict[str, list[float]] = {}
    for a, p in df.select("account_id", "p").iter_rows():
        by_acct.setdefault(a, []).append(p)
    n_posts = max(df.height, 1)
    pvals = df["p"].to_list()

    def post_share(t, ci=True):
        if ci:
            return share_ci({a: [p >= t for p in ps] for a, ps in by_acct.items()})
        s = sum(p >= t for p in pvals) / n_posts
        return (s, None, None)

    def acct_share(t, ci=True):
        if ci:
            return share_ci({a: [ps[0] >= t] for a, ps in by_acct.items()})
        return (sum(ps[0] >= t for ps in by_acct.values()) / max(len(by_acct), 1), None, None)

    s, lo, hi = post_share(AUTOMATED)
    sa, alo, ahi = acct_share(AUTOMATED)
    e, elo, ehi = share_ci(by_acct) if full else (sum(pvals) / n_posts, None, None)
    strip = {str(t): (post_share(t, ci=full) if t != AUTOMATED else (s, lo, hi)) for t in cfg.STRIP_THRESHOLDS}
    return {
        "n_posts": df.height,
        "n_accounts": len(by_acct),
        "bot_post_share": _r(s),
        "bot_post_share_ci": [_r(lo), _r(hi)],
        "bot_account_share": _r(sa),
        "bot_account_share_ci": [_r(alo), _r(ahi)],
        "expected_share": _r(e),
        "expected_share_ci": [_r(elo), _r(ehi)],
        "expected_automated_posts": round(float(df["p"].sum()), 1) if df.height else 0.0,
        "threshold_strip": {k: _r(v[0]) for k, v in strip.items()},
        "threshold_strip_ci": {k: [_r(v[1]), _r(v[2])] for k, v in strip.items()},
        "threshold_strip_accounts": {str(t): _r(acct_share(t, ci=False)[0]) for t in cfg.STRIP_THRESHOLDS},
    }


def _shares(c: Ctx) -> dict:
    """Per-narrative likely automated shares. Muse's M4 module when present, the same computation here otherwise."""
    try:
        from src.bots import narrative_shares as m4  # noqa: WPS433

        pn = c.posts.filter(pl.col("narrative_id").is_not_null()).select("post_id", "narrative_id", pl.lit(1.0).alias("prob"))
        sc = {d: p for d, p in c.scores.items() if p is not None}
        bs = pl.DataFrame({"account_id": list(sc), "p_automated": list(sc.values())}, schema={"account_id": pl.Utf8, "p_automated": pl.Float64})
        acc = pl.DataFrame({"account_id": list(c.accounts), "bridged": [bool(a.get("bridged")) for a in c.accounts.values()]},
                           schema={"account_id": pl.Utf8, "bridged": pl.Boolean}) if c.accounts else None
        res = m4.narrative_shares(pn, c.posts.select("post_id", "account_id"), bs, acc)
        res["source"] = "src.bots.narrative_shares"
        return res
    except ImportError:
        pass
    df = c.posts.filter(pl.col("narrative_id").is_not_null() & pl.col("p").is_not_null())
    br = {d for d, a in c.accounts.items() if a.get("bridged")}
    df = df.with_columns(pl.col("account_id").is_in(list(br)).alias("bridged"))
    main = df.filter(~pl.col("bridged"))
    denom = "unbridged accounts (bridged fediverse accounts are in with_bridged)" if c.accounts else "all accounts (no accounts table)"
    out = {"denominator": denom, "baseline": _block(main) | {"with_bridged": _block(df, full=False)}, "narratives": [], "source": "src.export.build_site_data"}
    base = out["baseline"]["bot_post_share"]
    for nid in sorted(df["narrative_id"].unique().to_list()):
        sub_all = df.filter(pl.col("narrative_id") == nid)
        sub = sub_all.filter(~pl.col("bridged"))
        if sub.height == 0:
            continue
        row = {"id": nid} | _block(sub) | {"with_bridged": _block(sub_all, full=False)}
        row["x_baseline"] = round(row["bot_post_share"] / base, 2) if base else None
        out["narratives"].append(row)
    return out


def _without(c: Ctx) -> dict:
    """Narrative ranking with and without likely automated accounts: their posts, the engagement on those posts,
    and the engagement they gave. Volume = posts + likes, reposts and quotes."""
    p = c.posts.filter(pl.col("narrative_id").is_not_null()).with_columns((pl.col("p").fill_null(0.0) >= AUTOMATED).alias("auto"))
    posts_all = dict(p.group_by("narrative_id").len().iter_rows())
    posts_wo = dict(p.filter(~pl.col("auto")).group_by("narrative_id").len().iter_rows())
    eng_all: dict = {}
    eng_wo: dict = {}
    if c.inter is not None:
        auto_posts = set(p.filter(pl.col("auto"))["post_id"].to_list())
        auto_accts = {d for d, s in c.scores.items() if s is not None and s >= AUTOMATED}
        i = c.inter.filter(pl.col("narrative_id").is_not_null())
        eng_all = dict(i.group_by("narrative_id").len().iter_rows())
        keep = i.filter(~pl.col("post_id").is_in(list(auto_posts)) & ~pl.col("src").is_in(list(auto_accts)))
        eng_wo = dict(keep.group_by("narrative_id").len().iter_rows())
    ids = sorted(posts_all)
    vol = {n: posts_all.get(n, 0) + eng_all.get(n, 0) for n in ids}
    vol_wo = {n: posts_wo.get(n, 0) + eng_wo.get(n, 0) for n in ids}

    def ranks(d):
        order = sorted((n for n in d if n != "n0"), key=lambda n: -d[n])
        return {n: i + 1 for i, n in enumerate(order)}

    ra, rw, rpa, rpw = ranks(vol), ranks(vol_wo), ranks(posts_all), ranks(posts_wo)
    tv, tvw = sum(vol.values()) or 1, sum(vol_wo.values()) or 1
    tp, tpw = sum(posts_all.values()) or 1, sum(posts_wo.values()) or 1
    return {
        n: {
            "posts": posts_all.get(n, 0), "posts_without": posts_wo.get(n, 0),
            "engagements": eng_all.get(n, 0), "engagements_without": eng_wo.get(n, 0),
            "share": _r(posts_all.get(n, 0) / tp), "share_without": _r(posts_wo.get(n, 0) / tpw),
            "volume_share": _r(vol[n] / tv), "volume_share_without": _r(vol_wo[n] / tvw),
            "rank": ra.get(n), "rank_without": rw.get(n), "post_rank": rpa.get(n), "post_rank_without": rpw.get(n),
        }
        for n in ids
    }


def narratives(c: Ctx) -> tuple[list[dict], dict]:
    if c.posts is None or not c.have_narratives:
        return [], {}
    assigned = c.posts.filter(pl.col("narrative_id").is_not_null())
    total = assigned.height or 1
    shares = _shares(c) if c.have_scores else {"narratives": [], "baseline": {}}
    by_id = {r["id"]: r for r in shares["narratives"]}
    wo = _without(c)
    br = {d for d, a in c.accounts.items() if a.get("bridged")}
    sides = {}
    for (nid,), g in assigned.filter(pl.col("side").is_not_null()).group_by(["narrative_id"]):
        sides[nid] = Counter(g["side"].to_list()).most_common(1)[0][0]
    out = []
    for (nid,), g in sorted(assigned.group_by(["narrative_id"]), key=lambda kv: -kv[1].height):
        label, side = c.labels.get(nid, (nid, "other"))
        s = by_id.get(nid, {})
        row = {
            "id": nid, "label": label, "side": sides.get(nid, side),
            "posts": g.height, "accounts": g["account_id"].n_unique(), "share": _r(g.height / total),
        }
        for k in ("bot_post_share", "bot_post_share_ci", "bot_account_share", "bot_account_share_ci", "expected_share",
                  "expected_share_ci", "expected_automated_posts", "threshold_strip", "threshold_strip_ci", "threshold_strip_accounts", "x_baseline"):
            row[k] = s.get(k)
        if s.get("with_bridged"):
            row["with_bridged"] = {k: s["with_bridged"].get(k) for k in ("n_posts", "n_accounts", "bot_post_share", "bot_post_share_ci", "bot_account_share", "threshold_strip")}
        gb = g.filter(pl.col("account_id").is_in(list(br)))
        row["bridged"] = {
            "posts": gb.height, "accounts": gb["account_id"].n_unique(),
            "bot_post_share": _r((gb["p"].fill_null(0.0) >= AUTOMATED).mean()) if gb.height and c.have_scores else None,
        }
        row["without_automated"] = wo.get(nid, {})
        # examples: nameable authors only, unique texts, most engaged first
        ex, seen = [], set()
        for r in g.sort("engagement", descending=True).iter_rows(named=True):
            key = (r["text"] or "").strip().lower()[:120]
            if not key or key in seen or not c.nameable(r["account_id"]):
                continue
            seen.add(key)
            ex.append(r)
            if len(ex) >= EXAMPLES_N:
                break
        row["examples"] = [c.mask(r["text"]) for r in ex]
        row["example_posts"] = [c.post_ev(r["account_id"], r["post_id"], r["t"], f"{r['engagement']:,} likes, reposts, replies and quotes", r["text"]) for r in ex]
        # evidence: the likely automated posts behind the share, highest score first, then the most engaged
        ev = []
        if c.have_scores:
            auto = g.filter(pl.col("p") >= AUTOMATED).sort(["p", "engagement"], descending=True).unique(subset="account_id", keep="first", maintain_order=True)
            for r in auto.head(EVIDENCE_N).iter_rows(named=True):
                why = "; ".join((c.reasons.get(r["account_id"]) or [])[:2])
                selfbot = (c.accounts.get(r["account_id"]) or {}).get("self_label_bot")
                note = ("labels itself a bot; " if selfbot else "") + f"likely automated (score {r['p']:.2f})" + (f": {why}" if why else "")
                ev.append(c.post_ev(r["account_id"], r["post_id"], r["t"], note, r["text"]))
        row["evidence"] = ev
        out.append(row)
    base = shares.get("baseline") or {}
    meta = {
        "threshold": AUTOMATED,
        "strip_thresholds": list(cfg.STRIP_THRESHOLDS),
        "denominator": shares.get("denominator"),
        "computed_by": shares.get("source"),
        "baseline": {k: base.get(k) for k in ("n_posts", "n_accounts", "bot_post_share", "bot_post_share_ci", "bot_account_share", "bot_account_share_ci", "expected_share", "threshold_strip")} if base else {},
        "unassigned_posts": c.posts.height - assigned.height,
        "without_automated_definition": f"posts by accounts with p_automated >= {AUTOMATED}, every like, repost and quote of those posts, and every like, repost and quote those accounts gave are removed; volume = posts + likes, reposts and quotes",
    }
    return out, meta


def _first_seen(c: Ctx) -> dict:
    fs: dict = {}
    if c.posts is not None:
        for d, t in c.posts.filter(pl.col("t").is_not_null()).group_by("account_id").agg(pl.col("t").min()).iter_rows():
            fs[d] = t
    if c.inter is not None:
        for d, t in c.inter.filter(pl.col("t").is_not_null()).group_by("src").agg(pl.col("t").min()).iter_rows():
            if d not in fs or t < fs[d]:
                fs[d] = t
    return fs


def graph(c: Ctx, node_cap: int = NODE_CAP, edge_cap: int = EDGE_CAP, seed: int = 42) -> dict:
    if c.inter is None or c.inter.height == 0:
        return {"nodes": [], "edges": [], "meta": {}}
    i = c.inter.filter(pl.col("src") != pl.col("dst"))
    deg = Counter(i["src"].to_list()) + Counter(i["dst"].to_list())
    pa = lambda d: c.scores.get(d)  # noqa: E731
    auto = {d for d in deg if (pa(d) or 0.0) >= AUTOMATED}
    hi_auto = {d for d in deg if (pa(d) or 0.0) >= cfg.AUTOMATED_MIN}
    human = lambda d: (pa(d) if pa(d) is not None else 0.0) < cfg.HUMAN_MAX  # noqa: E731  unscored engagers count as human, as in the API
    amp_rows = i.filter(pl.col("dst").is_in(list(hi_auto)))
    amp_count = Counter(d for d in amp_rows["src"].to_list() if human(d))
    first_amp = dict(amp_rows.filter(pl.col("t").is_not_null()).group_by("src").agg(pl.col("t").min()).iter_rows())

    chosen: dict[str, str] = {}

    def take(ds, role, limit):
        for d in ds:
            if len(chosen) >= node_cap or limit <= 0:
                return
            if d not in chosen:
                chosen[d] = role
                limit -= 1

    take(sorted(auto, key=lambda d: -deg[d]), "likely_automated", node_cap // 2)
    take([d for d, _ in amp_count.most_common()], "amplifier", min(400, node_cap // 4))
    take(sorted((d for d in deg if c.nameable(d)), key=lambda d: -deg[d]), "public", min(200, node_cap // 8))
    rest = sorted((d for d in deg if d not in chosen), key=lambda d: -deg[d])[:3000]
    rng = random.Random(seed)
    rng.shuffle(rest)
    take(rest, "other", node_cap)
    sel = set(chosen)
    e = i.filter(pl.col("src").is_in(list(sel)) & pl.col("dst").is_in(list(sel)))
    e = e.with_columns(
        pl.when(pl.col("dst").is_in(list(auto))).then(0).when(pl.col("src").is_in(list(auto))).then(1).otherwise(2).alias("prio")
    ).sort(["prio", "t"], nulls_last=True).unique(subset=["src", "dst", "type"], keep="first", maintain_order=True).head(edge_cap)
    linked = set(e["src"].to_list()) | set(e["dst"].to_list())
    nodes_keep = [d for d in chosen if chosen[d] != "other" or d in linked]
    # node attributes
    narr: dict = {}
    if c.posts is not None:
        for d, ns in c.posts.filter(pl.col("narrative_id").is_not_null() & pl.col("account_id").is_in(nodes_keep)).group_by("account_id").agg(pl.col("narrative_id")).iter_rows():
            narr[d] = Counter(ns).most_common(1)[0][0]
    for d, ns in i.filter(pl.col("narrative_id").is_not_null() & pl.col("src").is_in(nodes_keep)).group_by("src").agg(pl.col("narrative_id")).iter_rows():
        narr.setdefault(d, Counter(ns).most_common(1)[0][0])
    nposts = Counter(c.posts.filter(pl.col("account_id").is_in(nodes_keep))["account_id"].to_list()) if c.posts is not None else Counter()
    fs = _first_seen(c)
    refs = {d: c.ref(d) for d in nodes_keep}
    nodes = []
    for d in nodes_keep:
        p = pa(d)
        nodes.append({
            "id": refs[d]["ref"], "public_handle": refs[d]["public_handle"], "role": chosen[d],
            "p_automated": _r(p, 3), "likely_automated": p is not None and p >= AUTOMATED,
            "narrative": narr.get(d), "archetype": c.arch_member.get(d), "coord_cluster": c.coord_id.get(d),
            "first_seen": fs.get(d), "first_amplified": first_amp.get(d), "posts": nposts.get(d, 0),
            "degree": deg[d], "size": round(1 + math.log1p(deg[d]), 2),
        })
    edges = [
        {"s": refs[s]["ref"], "t": refs[t]["ref"], "type": ty, "time": tm, "time_approx": ap, "narrative": nid}
        for s, t, ty, tm, ap, nid in e.select("src", "dst", "type", "t", "t_approx", "narrative_id").iter_rows()
    ]
    edges.sort(key=lambda x: (x["time"] is None, x["time"] or ""))
    # a node appears no later than its first edge in the replay
    first_edge: dict = {}
    for x in edges:
        if x["time"]:
            for k in (x["s"], x["t"]):
                first_edge.setdefault(k, x["time"])
    for n in nodes:
        fe = first_edge.get(n["id"])
        if fe and (n["first_seen"] is None or fe < n["first_seen"]):
            n["first_seen"] = fe
    nodes.sort(key=lambda n: (n["first_seen"] is None, n["first_seen"] or ""))
    # replay index: nodes and edges are time-sorted, so hour h shows nodes[:nodes] and edges[:edges]
    replay, ni, ei = [], 0, 0
    h = datetime.fromisoformat(cfg.STORY_START.replace("Z", "+00:00"))
    end = datetime.fromisoformat(cfg.STORY_END.replace("Z", "+00:00"))
    while h < end:
        h += timedelta(hours=1)
        cut = h.strftime("%Y-%m-%dT%H:%M:%SZ")
        while ni < len(nodes) and nodes[ni]["first_seen"] and nodes[ni]["first_seen"] < cut:
            ni += 1
        while ei < len(edges) and edges[ei]["time"] and edges[ei]["time"] < cut:
            ei += 1
        replay.append({"hour": (h - timedelta(hours=1)).strftime("%Y-%m-%dT%H:00:00Z"), "nodes": ni, "edges": ei})
    return {
        "nodes": nodes, "edges": edges, "replay": replay,
        "meta": {
            "node_cap": node_cap, "edge_cap": edge_cap, "accounts_with_engagement": len(deg), "engagements": i.height,
            "roles": dict(Counter(n["role"] for n in nodes)),
            "selection": f"every likely automated account (p_automated >= {AUTOMATED}) with engagement, up to half the cap by degree; then the real accounts that engaged most with posts by accounts at p_automated >= {cfg.AUTOMATED_MIN}; then the most engaged public accounts; then a seeded random sample of the 3,000 most engaged other accounts (kept only if linked). Edges among chosen accounts: engagement with likely automated accounts first, then earliest first.",
            "time_note": "edge time is the like, repost or quote time; reposts carry no timestamp, so they use the engaged post's time (time_approx true). Nodes and edges are sorted by time; replay[h] gives how many of each are visible by the end of hour h (cumulative). Engagement after the story window stays in the arrays beyond the last replay hour.",
        },
    }


def _lift_inputs(c: Ctx):
    """Interacting humans and whether each amplified a likely automated account (README definition)."""
    if c.inter is None:
        return {}, 0.0
    hi_auto = {d for d, s in c.scores.items() if s is not None and s >= cfg.AUTOMATED_MIN}
    srcs = set(c.inter["src"].unique().to_list())
    amp = set(c.inter.filter(pl.col("dst").is_in(list(hi_auto)))["src"].unique().to_list())
    humans = {d: (d in amp) for d in srcs if (c.scores.get(d) if c.scores.get(d) is not None else 0.0) < cfg.HUMAN_MAX}
    profiled = {d: f for d, f in humans.items() if d in c.arch_member}
    base = sum(profiled.values()) / len(profiled) if profiled else 0.0
    return profiled, base


def _thesis_report(c: Ctx) -> tuple[dict, str | None]:
    """Counts from Muse's matched analysis (M5): the VM run's report when it exists, else the laptop report."""
    for name in ("report-vm.md", "report.md"):
        p = c.eval_dir / "thesis" / name
        if not p.exists():
            continue
        t = p.read_text()
        out: dict = {}
        num = lambda s: int(s.replace(",", ""))  # noqa: E731
        if m := re.search(r"\*\*([\d,]+) amplifiers\.?\*\*", t):
            out["amplifiers"] = num(m.group(1))
        if m := re.search(r"unmatched[^|\n]*\|\s*([\d,]+)", t):
            out["amplifiers_unmatched"] = num(m.group(1))
        if m := re.search(r"Control pool:[^\d]*([\d,]+)", t):
            out["control_pool"] = num(m.group(1))
        if m := re.search(r"Base amplifier rate in the matched sample: ([0-9.]+)", t):
            out["base_amplifier_rate"] = float(m.group(1).rstrip("."))
        if m := re.search(r"Match rate ([0-9.]+)%", t):
            out["match_rate"] = float(m.group(1)) / 100
        if m := re.search(r"Version `([^`]+)`", t):
            out["version"] = m.group(1)
        return out, str(p)
    return {}, None


def _amp_evidence(c: Ctx, amp_ev, ds: list) -> list[dict]:
    ev = []
    if amp_ev is None:
        return ev
    sub = amp_ev.filter(pl.col("src").is_in(ds)).unique(subset="src", keep="first", maintain_order=True).head(5)
    for s, dst, ty, pid, t in sub.select("src", "dst", "type", "post_id", "t").iter_rows():
        who = c.ref(s)
        actor = f"@{who['public_handle']}" if who["public_handle"] else "a private account"
        item = c.post_ev(dst, pid, t, f"{actor} in this archetype gave a {ty} to a post by a likely automated account (score {c.scores.get(dst, 0):.2f})")
        item["actor_ref"] = who["ref"]
        ev.append(item)
    return ev


def _plain_features(feats: dict) -> dict:
    """Profile summaries with plain keys and no empty values (cards never show 'null' or raw column names)."""
    return {k: v for k, v in feats.items() if v is not None and not (isinstance(v, float) and math.isnan(v))}


def archetypes(c: Ctx) -> tuple[list[dict], dict]:
    if not c.arch_member:
        return [], {}
    members: dict = defaultdict(list)
    for d, a in c.arch_member.items():
        members[a].append(d)
    meta_rows = {r["archetype_id"]: r for r in c.arch_meta.iter_rows(named=True)} if c.arch_meta is not None and "archetype_id" in c.arch_meta.columns else {}
    hi_auto = {d for d, s in c.scores.items() if s is not None and s >= cfg.AUTOMATED_MIN}
    amp_ev = c.inter.filter(pl.col("dst").is_in(list(hi_auto))).sort("t", nulls_last=True) if c.inter is not None else None
    ok = c._public_handles()

    # Muse's matched analysis (M5): lifts against matched controls, counts from its tables. Preferred whenever present.
    if meta_rows and all(m.get("lift") is not None and m.get("n_amplifiers") is not None for m in meta_rows.values()):
        rep, rep_path = _thesis_report(c)
        out = []
        for aid, m in meta_rows.items():
            ds = members.get(aid, [])
            amps = [d for d in ds if c.arch_role.get(d, "amplifier") == "amplifier"]
            size, n_amp = int(m.get("size") or len(ds)), int(m["n_amplifiers"])
            row = {
                "id": aid, "label": m.get("label") or c.arch_labels.get(aid, aid), "size": size,
                "interacting_humans": size, "amplifiers": n_amp, "controls": size - n_amp,
                "amplifier_rate": _r(n_amp / size) if size else None,
                "lift": _r(m["lift"], 3), "lift_ci": [_r(m.get("lift_lo"), 3), _r(m.get("lift_hi"), 3)],
                "lift_basis": "matched: this archetype's amplifier rate in the matched sample (each amplifier paired with a similar account that engaged only with human posts: same narrative, 6-hour window, reach, activity and follower bucket) over the sample's base rate; bootstrap interval (src.archetypes.build)",
            }
            if m.get("description"):
                row["description"] = m["description"]
            pub = [h for h in (m.get("examples_public") or []) if h and h.lower() in ok]
            if not pub:
                pub = [c.accounts[d]["handle"] for d in sorted((d for d in ds if c.nameable(d)), key=lambda d: -(c.accounts[d].get("followers") or 0))]
            row["examples_public"] = pub[:5]
            row["evidence"] = _amp_evidence(c, amp_ev, amps)
            out.append(row)
        out.sort(key=lambda r: -r["size"])
        n_matched = sum(r["amplifiers"] for r in out)
        n_all = rep.get("amplifiers", n_matched)
        meta = {
            "source": "src.archetypes.build (archetypes.parquet)" + (f", {rep_path}" if rep_path else ""),
            "version": rep.get("version"),
            "matched": True,
            "amplifiers": n_all,
            "amplifiers_matched": n_matched,
            "amplifiers_unmatched": rep.get("amplifiers_unmatched", n_all - n_matched),
            "controls": sum(r["controls"] for r in out),
            "accounts": sum(r["size"] for r in out),
            "interacting_humans_profiled": sum(r["size"] for r in out),
            "base_amplifier_rate": rep.get("base_amplifier_rate", _r(n_matched / max(sum(r["size"] for r in out), 1))),
            "match_rate": rep.get("match_rate"),
            "matching": "one control per amplifier, without replacement: same narrative, same 6-hour window, same reach bucket of the post engaged with, same activity quintile and follower power of ten",
            "definition": f"amplifier: a real account (p_automated < {cfg.HUMAN_MAX}) that liked, reposted or quoted a story post by an account with p_automated >= {cfg.AUTOMATED_MIN}",
        }
        return out, meta

    # fallback: this export's own unmatched comparison (rate over all profiled interacting real accounts)
    flags, base = _lift_inputs(c)
    feats = c.user_features if c.user_features is not None and "account_id" in c.user_features.columns else None
    out = []
    for aid in sorted(members):
        ds = members[aid]
        f = [flags[d] for d in ds if d in flags]
        lift, lo, hi = ratio_ci(f, base) if f and base > 0 else (None, None, None)
        m = meta_rows.get(aid, {})
        row = {
            "id": aid, "label": c.arch_labels.get(aid, aid), "size": len(ds),
            "interacting_humans": len(f), "amplifiers": int(sum(f)),
            "amplifier_rate": _r(sum(f) / len(f)) if f else None,
            "lift": _r(lift, 3), "lift_ci": [_r(lo, 3), _r(hi, 3)],
            "lift_basis": "amplifier rate among this archetype's interacting real accounts over the rate among all profiled interacting real accounts (shared bootstrap)",
        }
        if m.get("description"):
            row["description"] = m["description"]
        if feats is not None:
            sub = feats.filter(pl.col("account_id").is_in(ds))
            row["features"] = _plain_features({k.replace("_", " "): _r(sub[k].mean(), 3) for k in sub.columns if k != "account_id" and sub[k].dtype.is_numeric()})
        else:
            acc = [c.accounts[d] for d in ds if d in c.accounts]
            fol = sorted((a.get("followers") or 0) for a in acc)
            pc = sorted((a.get("posts_count") or 0) for a in acc)
            ages = sorted(
                (datetime.fromisoformat(cfg.STORY_START.replace("Z", "+00:00")) - datetime.fromisoformat(t.replace("Z", "+00:00"))).days
                for t in (_iso(a.get("created_at")) for a in acc) if t
            )
            med = lambda xs: xs[len(xs) // 2] if xs else None  # noqa: E731
            row["features"] = _plain_features({
                "median followers": med(fol), "median lifetime posts": med(pc), "median account age (days)": med(ages),
                "bridged share": _r(sum(bool(a.get("bridged")) for a in acc) / len(acc)) if acc else None,
                "mean automation score": _r(sum(c.scores.get(d) or 0.0 for d in ds) / len(ds), 3) if c.have_scores else None,
            })
        pub = sorted((d for d in ds if c.nameable(d)), key=lambda d: -(c.accounts[d].get("followers") or 0))
        row["examples_public"] = [c.accounts[d]["handle"] for d in pub[:5]]
        row["evidence"] = _amp_evidence(c, amp_ev, ds)
        out.append(row)
    out.sort(key=lambda r: -r["size"])
    meta = {"matched": False, "base_amplifier_rate": _r(base), "interacting_humans_profiled": len(flags),
            "amplifiers": sum(r["amplifiers"] for r in out),
            "definition": f"amplifier: a real account (p_automated < {cfg.HUMAN_MAX}, unscored engagers counted as real) that liked, reposted or quoted a post by an account with p_automated >= {cfg.AUTOMATED_MIN}"}
    return out, meta


def coordination(c: Ctx, cap: int = 50) -> list[dict]:
    if not c.clusters:
        return []
    narr_by_acct: dict = defaultdict(Counter)
    if c.posts is not None:
        for d, n in c.posts.filter(pl.col("narrative_id").is_not_null()).select("account_id", "narrative_id").iter_rows():
            narr_by_acct[d][n] += 1
    out = []
    for cl in sorted(c.clusters, key=lambda x: -len(x.get("dids") or [])):
        dids = cl.get("dids") or []
        if not dids:
            continue
        mix = Counter()
        for d in dids:
            mix.update(narr_by_acct.get(d, {}))
        ps = [c.scores[d] for d in dids if c.scores.get(d) is not None]
        pub = [c.accounts[d]["handle"] for d in dids if c.nameable(d)]
        ev = []
        for e in (cl.get("evidence") or [])[:EVIDENCE_N]:
            uri = e.get("post_uri") or ""
            m = re.match(r"at://(did:[^/]+)/", uri)
            owner = m.group(1) if m else e.get("did")
            if owner:
                ev.append(c.post_ev(owner, uri, _iso(e.get("t")) or e.get("t"), e.get("trace") or e.get("note") or ""))
            else:
                ev.append({"post_uri": None, "t": _iso(e.get("t")), "note": e.get("trace") or "", "account_ref": None, "public_handle": None})
        out.append({
            "id": str(cl.get("cluster_id")), "size": len(dids),
            "accounts_ref": [c.ref(d)["ref"] for d in dids][:200],
            "public_handles": pub, "private_accounts": len(dids) - len(pub),
            "mean_p_automated": _r(sum(ps) / len(ps), 3) if ps else None,
            "likely_automated_accounts": sum(p >= AUTOMATED for p in ps),
            "narratives": dict(mix.most_common()),
            "reasons": [c.mask(r) for r in (cl.get("reasons") or [])],
            "evidence": ev,
        })
        if len(out) >= cap:
            break
    return out


def public_accounts(c: Ctx, cap: int = PUBLIC_ACCOUNTS_CAP) -> list[dict]:
    if c.posts is None or not c.accounts:
        return []
    pub = [d for d in c.posts["account_id"].unique().to_list() if c.nameable(d)]
    if not pub:
        return []
    recv = Counter(c.inter.filter(pl.col("dst").is_in(pub))["dst"].to_list()) if c.inter is not None else Counter()
    npost = Counter(c.posts.filter(pl.col("account_id").is_in(pub))["account_id"].to_list())
    top = sorted(pub, key=lambda d: -(npost[d] + recv[d]))[:cap]
    out = []
    pp = c.posts.filter(pl.col("account_id").is_in(top))
    by = {d: g for (d,), g in pp.group_by(["account_id"])}
    gave_by, got_by = {}, {}
    if c.inter is not None:
        gave_by = dict(c.inter.filter(pl.col("src").is_in(top)).group_by("src").agg(pl.col("dst")).iter_rows())
        got_by = dict(c.inter.filter(pl.col("dst").is_in(top)).group_by("dst").agg(pl.col("src")).iter_rows())
    for d in top:
        g = by[d]
        a = c.accounts[d]
        row = {
            "handle": a["handle"], "followers": a.get("followers"), "self_label_bot": bool(a.get("self_label_bot")),
            "bridged": bool(a.get("bridged")), "posts": g.height, "engagement_received": recv[d],
            "narratives": [n for n, _ in Counter(x for x in g["narrative_id"].to_list() if x).most_common()],
            "p_automated": _r(c.scores.get(d), 3), "reasons": (c.reasons.get(d) or [])[:3],
            "archetype": c.arch_member.get(d),
            "top_posts": [c.post_ev(d, r["post_id"], r["t"], f"{r['engagement']:,} likes, reposts, replies and quotes", r["text"])
                          for r in g.sort("engagement", descending=True).head(3).iter_rows(named=True)],
        }
        if c.inter is not None:
            gave = Counter(gave_by.get(d, []))
            got = Counter(got_by.get(d, []))
            row["amplifies"] = {"public": [c.accounts[x]["handle"] for x, _ in gave.most_common() if c.nameable(x)][:10],
                                "private_accounts": sum(1 for x in gave if not c.nameable(x))}
            row["amplified_by"] = {"public": [c.accounts[x]["handle"] for x, _ in got.most_common() if c.nameable(x)][:10],
                                   "private_accounts": sum(1 for x in got if not c.nameable(x)),
                                   "likely_automated_accounts": sum(1 for x in got if (c.scores.get(x) or 0.0) >= AUTOMATED)}
        out.append(row)
    return out


def _md_tables(text: str) -> list[dict]:
    """Markdown tables whose header has @k columns -> [{row label: {k: value}}]."""
    tables, cur, keys = [], None, None
    for line in text.splitlines():
        if not line.startswith("|"):
            cur, keys = None, None
            continue
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if keys is None:
            ks = [re.sub(r"^@", "", x) for x in cells[1:]]
            if all(re.fullmatch(r"\d+", k) for k in ks) and ks:
                keys, cur = ks, {}
                tables.append(cur)
            else:
                keys = []
            continue
        if not keys or set(cells[0]) <= set("-: "):
            continue
        try:
            cur[cells[0]] = {k: float(v.split("\u00b1")[0]) for k, v in zip(keys, cells[1:])}
            if any("\u00b1" in v for v in cells[1:]):  # "mean ± sd" cells: keep the spread beside the mean
                cur["sd::" + cells[0]] = {k: float(v.split("\u00b1")[1]) for k, v in zip(keys, cells[1:])}
        except ValueError:
            pass
    return tables


def _first_report(c: Ctx, area: str, names: tuple[str, ...]) -> Path | None:
    for n in names:
        p = c.eval_dir / area / n
        if p.exists():
            return p
    return None


def validation(c: Ctx) -> dict | None:
    """Method-view numbers, read from the evaluation reports (never typed in). The VM reports win over the laptop ones:
    the demo runs the VM's model (docs/TEAM-BRIEF.md)."""
    out: dict = {"recall_at_k": None, "recall_at_k_all_labeled": None, "baseline_recall_at_k": None, "ablation": {}, "gold_accuracy": None,
                 "narrative_llm_agreement": None, "side_llm_agreement": None, "hand_label_agreement": None,
                 "handcheck_precision": None, "bot_model": (c.manifest.get("bot_model") or {}).get("version") or c.sources.get("bot_model")}
    found = False
    rep = _first_report(c, "bots", ("report-vm.md", "report.md"))
    if rep:
        found = True
        out["bot_report"] = str(rep)
        t = rep.read_text()
        for tab in _md_tables(t):
            for k, v in tab.items():
                kl = k.lower()
                if "baseline" in kl and out["baseline_recall_at_k"] is None:
                    out["baseline_recall_at_k"] = v
                elif kl in ("behavior only", "coordination only", "both"):
                    out["ablation"][kl] = v
                elif kl.startswith("hgb") and "operator" in kl:
                    continue  # the unseen-operator test is quoted from the report, not shown as the headline recall
                elif kl.startswith("hgb") and "mean" in kl:
                    # README protocol: 20% of labeled bots held out, mean over the report's splits (the number to quote, R-09)
                    out["recall_at_k"] = v
                    out["recall_at_k_sd"] = tab.get("sd::" + k)
                    ms = re.search(r"over (\d+) splits", k)
                    out["recall_splits"] = int(ms.group(1)) if ms else None
                elif kl.startswith("hgb") and "one split" in kl:
                    out["recall_at_k_one_split"] = v
                elif kl.startswith("hgb"):
                    out["recall_at_k"] = out["recall_at_k"] or v
                elif "gradient boosting" in kl:
                    out["recall_at_k_all_labeled"] = v
        m = re.search(r"\*\*(\d+) of (\d+) \((\d+)%\)", t) or re.search(r"(\d+) of (\d+) \((\d+)%\)", t)
        if m:
            out["handcheck_precision"] = {"hits": int(m.group(1)), "n": int(m.group(2)), "share": _r(int(m.group(1)) / int(m.group(2)))}
        m = re.search(r"Model: `([^`]+)`", t)
        if m:
            out["report_model"] = m.group(1)
        if out["recall_at_k"] is None:
            out["recall_at_k"] = out["recall_at_k_all_labeled"]
    nrep = _first_report(c, "narratives", ("report-vm.md", "report.md"))
    if nrep:
        found = True
        t = nrep.read_text()
        out["narrative_report"] = str(nrep)
        # the classifier against the language-model labels; hand-label agreement only when the report says "hand"
        m = re.search(r"narrative_id:\s*held-out accuracy vs LLM labels ([0-9.]+)(?:\s*\(n=([\d,]+)\))?", t)
        if m:
            out["narrative_llm_agreement"] = _r(float(m.group(1)), 3)
            if m.group(2):
                out["narrative_llm_agreement_n"] = int(m.group(2).replace(",", ""))
        m = re.search(r"side:\s*held-out accuracy vs LLM labels ([0-9.]+)", t)
        if m:
            out["side_llm_agreement"] = _r(float(m.group(1)), 3)
        m = re.search(r"hand[- ]label[^\n]{0,60}?(?:accuracy|agreement)[^0-9\n]{0,20}([0-9]+(?:\.[0-9]+)?)\s*(%?)", t, re.I)
        if m:
            v = float(m.group(1))
            out["hand_label_agreement"] = out["gold_accuracy"] = _r(v / 100 if m.group(2) or v > 1 else v)
    rrep = _first_report(c, "retrieval", ("report-hybrid.md", "report.md"))
    if rrep:
        found = True
        t = rrep.read_text()
        r: dict = {"report": str(rrep), "tables": _md_tables(t)}
        m = re.search(r"recall@20[^\n]*?first (\d+) claims[^\n]*?\*\*([0-9.]+) at floor ([0-9.]+)\*\*", t)
        if m:
            r.update({"claims": int(m.group(1)), "recall_at_20": float(m.group(2)), "floor": float(m.group(3))})
            out["retrieval_recall_at_k"] = {"20": float(m.group(2))}
        m = re.search(r"All (\d+) claims: ([0-9]+(?:\.[0-9]+)?)", t)
        if m:
            r.update({"claims_all": int(m.group(1)), "recall_at_20_all": float(m.group(2))})
        out["retrieval"] = r
    return out if found else None


def _spy_flags(c: Ctx) -> dict:
    """Bluesky posts about the spy claim (the news module's SPY_RE), hedged or not, grouped by account for the shared
    bootstrap: all posts, posts that share a link, posts without one (people's own words)."""
    if c.posts is None:
        return {}
    sp = c.posts.filter(pl.col("text").fill_null("").str.contains("(?i)" + SPY_RE.pattern))
    groups: dict = {"all": defaultdict(list), "link": defaultdict(list), "own": defaultdict(list)}
    for d, t, link in sp.select("account_id", "text", "has_link").iter_rows():
        h = is_hedged(t or "")
        groups["all"][d].append(h)
        if link is not None:
            groups["link" if link else "own"][d].append(h)
    out = {}
    for k, g in groups.items():
        if g:
            s, lo, hi = share_ci(g)
            out[k] = {"share": s, "ci": [_r(lo), _r(hi)], "n": sum(len(v) for v in g.values()), "accounts": len(g)}
    if c.have_scores and sp.height:
        out["likely_automated_share"] = _r((sp["p"].fill_null(0.0) >= AUTOMATED).mean())
    return out


def news(c: Ctx) -> dict:
    """News baseline. Spy-related and hedged use the news module's definitions (src/news/baseline.py), and when its
    story_baseline.json exists its numbers are the ones shipped; this export adds the bootstrap intervals."""
    if not c.headlines:
        return {}
    on_story = lambda t: c.headlines_on_story or bool(STORY_RE.search(t))  # noqa: E731
    per = {}
    spy = []
    for r in c.headlines:
        t = r["title"] or ""
        s = per.setdefault(r.get("source"), {"source": r.get("source"), "name": r.get("source"), "funding": r.get("funding"),
                                             "headlines": 0, "huang_headlines": 0, "spy_headlines": 0, "spy_hedged": 0})
        s["headlines"] += 1
        if "huang" in t.lower():
            s["huang_headlines"] += 1
        if SPY_RE.search(t) and on_story(t):
            s["spy_headlines"] += 1
            s["spy_hedged"] += is_hedged(t)
            spy.append(r)
    nflags: dict = defaultdict(list)
    for r in spy:
        nflags[r.get("source")].append(is_hedged(r["title"]))
    ns, nlo, nhi = share_ci(nflags)
    sc: dict = {
        "news_headlines": len(spy), "news_hedged": sum(sum(v) for v in nflags.values()),
        "news_hedged_share": _r(ns), "news_hedged_share_ci": [_r(nlo), _r(nhi)],
        "interval_note": "news interval resamples outlets; Bluesky intervals resample accounts",
        "examples": [{"source": r.get("source"), "title": r["title"], "link": r.get("link"), "published": _iso(_rfc(r.get("published"))) or _iso(r.get("published")) or r.get("published"),
                      "hedged": is_hedged(r["title"])} for r in spy[:12]],
    }
    bf = _spy_flags(c)
    if "all" in bf:
        sc.update({"bluesky_posts": bf["all"]["n"], "bluesky_accounts": bf["all"]["accounts"], "bluesky_hedged_share": _r(bf["all"]["share"]), "bluesky_hedged_share_ci": bf["all"]["ci"]})
    if "link" in bf:
        sc.update({"bluesky_link_posts": bf["link"]["n"], "bluesky_link_hedged_share": _r(bf["link"]["share"]), "bluesky_link_hedged_share_ci": bf["link"]["ci"]})
    if "own" in bf:
        sc.update({"bluesky_own_words_posts": bf["own"]["n"], "bluesky_own_words_hedged_share": _r(bf["own"]["share"]), "bluesky_own_words_hedged_share_ci": bf["own"]["ci"]})
    if "likely_automated_share" in bf:
        sc["bluesky_likely_automated_share"] = bf["likely_automated_share"]
    # the news module's numbers are canonical; an interval computed here rides along only if it counts the same posts
    hb = (c.story_baseline or {}).get("hedging") or {}
    canon = {"news": ("news_hedged_share", "news_headlines", "news_hedged_share_ci"), "social": ("bluesky_hedged_share", "bluesky_posts", "bluesky_hedged_share_ci"),
             "social_with_link": ("bluesky_link_hedged_share", "bluesky_link_posts", "bluesky_link_hedged_share_ci"),
             "social_without_link": ("bluesky_own_words_hedged_share", "bluesky_own_words_posts", "bluesky_own_words_hedged_share_ci")}
    if hb:
        sc["source"] = "src.news.baseline (data/processed/news/story_baseline.json)"
        for key, (share_k, n_k, ci_k) in canon.items():
            blk = hb.get(key) or {}
            if blk.get("share") is None:
                continue
            if sc.get(n_k) != blk.get("n"):
                sc.pop(ci_k, None)
            sc[share_k], sc[n_k] = _r(blk["share"]), blk.get("n")
        if (hb.get("news") or {}).get("hedged") is not None:
            sc["news_hedged"] = hb["news"]["hedged"]
    outlets = sorted(per.values(), key=lambda s: -s["headlines"])
    return {
        "outlets": outlets,
        "headlines": len(c.headlines),
        "spy_claim": sc,
        "hedge_terms": list(HEDGE_TERMS),
        "method": ("spy claim: headline or post matches " + SPY_RE.pattern + (" (headlines from the news module's story-relevant set)" if c.headlines_on_story else " (headlines must also name Huang or Nvidia)")
                   + ". Hedged: uses " + ", ".join(HEDGE_TERMS[:-1]) + " or " + HEDGE_TERMS[-1] + ". Posts that share a link are often the headline itself; posts without one are closer to people's own words."),
    }


def _rfc(s):
    if not s:
        return None
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(s).isoformat()
    except Exception:
        return s


def _challenge_profiles(c: Ctx, dids: list[str]) -> dict:
    """Account age, posting rate, follows and the hour-of-day mix of its recent posts, for nameable accounts only."""
    out: dict = {}
    if not dids:
        return out
    hours: dict = {d: [0] * 24 for d in dids}
    span: dict = {}
    hp = c.processed / "history_posts.parquet"
    if hp.exists():
        try:
            h = pl.scan_parquet(hp).filter(pl.col("account_id").is_in(dids) & (pl.col("author_id") == pl.col("account_id"))).select("account_id", "t").collect()
            for d, t in h.iter_rows():
                ts = _iso(t)
                if ts:
                    hours[d][int(ts[11:13])] += 1
                    lo, hi = span.get(d, (ts, ts))
                    span[d] = (min(lo, ts), max(hi, ts))
        except Exception as e:
            warnings.warn(f"could not read {hp}: {e}")
    ref = datetime.fromisoformat(cfg.STORY_END.replace("Z", "+00:00"))
    for d in dids:
        a = c.accounts.get(d) or {}
        created = _iso(a.get("created_at"))
        age = max((ref - datetime.fromisoformat(created.replace("Z", "+00:00"))).days, 1) if created else None
        prof = {
            "account_age_days": age, "followers": a.get("followers"), "follows": a.get("follows"), "lifetime_posts": a.get("posts_count"),
            "posts_per_day": _r((a.get("posts_count") or 0) / age, 1) if age and a.get("posts_count") is not None else None,
            "self_label_bot": bool(a.get("self_label_bot")),
        }
        if sum(hours[d]):
            prof["hours_utc"] = hours[d]
            prof["hours_posts"] = sum(hours[d])
            prof["hours_span"] = {"from": span[d][0], "to": span[d][1]}
        out[d] = {k: v for k, v in prof.items() if v is not None}
    return out


def challenge(c: Ctx) -> list[dict]:
    by_handle = {(a.get("handle") or "").lower(): d for d, a in c.accounts.items() if a.get("handle")}
    rows, dids = [], []
    for a in c.challenge or []:
        handle = a.get("public_handle")
        ref = a.get("account_ref")
        if handle and ref != handle:  # a handle must only ride with its own ref
            handle = None
        did = by_handle.get(handle.lower()) if handle else None
        if handle and not did:  # not in this machine's profiles, so the README rule can't be checked here: don't name it
            handle, ref = None, hashed_id(f"handle:{handle.lower()}")
        elif handle and did and not c.nameable(did):  # never name an account the README rule doesn't allow
            handle, ref, did = None, public_ref(did, None, False)["ref"], None
        rows.append((a, ref, handle, did))
        if did:
            dids.append(did)
    prof = _challenge_profiles(c, dids)
    out = []
    for a, ref, handle, did in rows:
        item = {
            "account_ref": ref, "public_handle": handle, "tier": a.get("tier"),
            "posts": [{"t": _iso(p.get("t")) or p.get("t"), "text": c.mask(p.get("text"), 500), "kind": p.get("kind")} if isinstance(p, dict) else c.mask(str(p), 500) for p in a.get("posts", [])],
            "p_automated": a.get("p_automated"), "reasons": a.get("reasons", []), "hand_label": a.get("hand_label") or None,
        }
        if did and prof.get(did):
            item["profile"] = prof[did]
        out.append(item)
    try:  # non-English posts get lang, lang_name and text_en; a failure ships the posts untranslated
        c.translation = translate_challenge(out, c.processed / CACHE_NAME, c.translator, c.mask)
    except Exception as e:
        warnings.warn(f"challenge translation skipped: {e}")
    return out


def findings(site: dict) -> list[str]:
    """3 to 5 plain-language sentences, every number read from the computed sections (nothing hard-coded)."""
    slots: dict[str, str] = {}
    st, nm = site.get("story", {}), site.get("narratives_meta", {})
    base = nm.get("baseline") or {}
    if st.get("posts"):
        s = f"Bluesky had {st['posts']:,} posts about the story from {st['accounts']:,} accounts between Nov 5 and 13"
        if base.get("bot_post_share") is not None:
            lo, hi = base["bot_post_share_ci"]
            s += f"; {_pct1(base['bot_post_share'])} of posts ({_pct1(lo)} to {_pct1(hi)}) came from likely automated accounts (score {AUTOMATED} or higher)"
        slots["story"] = s + "."
    allnar = [n for n in site.get("narratives", []) if n["id"] != "n0"]
    wo = [n for n in allnar if (n.get("without_automated") or {}).get("rank")]
    moved = [n for n in wo if n["without_automated"]["rank"] != n["without_automated"]["rank_without"]]
    unchanged = bool(wo) and not moved and st.get("engagements") is not None
    nar = [n for n in allnar if n.get("bot_post_share") is not None and n.get("posts", 0) >= cfg.MIN_MATCHES]
    if len(nar) >= 2:
        top = max(nar, key=lambda n: n["bot_post_share"])
        low = min(nar, key=lambda n: n["bot_post_share"])
        st_top, st_low = top.get("threshold_strip") or {}, low.get("threshold_strip") or {}
        holds = bool(st_top) and all(st_top.get(k) is not None and st_low.get(k) is not None and st_top[k] >= st_low[k] for k in st_top)
        b0 = base.get("bot_post_share")
        overlap = b0 is not None and top["bot_post_share_ci"][0] <= base["bot_post_share_ci"][1]
        s = (f"Among narratives with {cfg.MIN_MATCHES}+ posts, \"{top['label']}\" has the highest point estimate of likely automated posts at {_pct1(top['bot_post_share'])} "
             f"({_pct1(top['bot_post_share_ci'][0])} to {_pct1(top['bot_post_share_ci'][1])})")
        if overlap:
            s += f"; its interval overlaps the story's {_pct1(b0)} baseline ({_pct1(base['bot_post_share_ci'][0])} to {_pct1(base['bot_post_share_ci'][1])}), so we call it suggestive, not a clear difference"
        low_clear = b0 is not None and low["bot_post_share_ci"][1] < b0
        s += f". \"{low['label']}\" is the lowest at {_pct1(low['bot_post_share'])}" + (" and clearly below the baseline" if low_clear else "")
        s += ". The order of the point estimates holds at every score cutoff from 0.3 to 0.9" if holds else ". The order changes across score cutoffs, so treat it with care"
        if unchanged:
            s += ". Removing likely automated accounts and their engagement leaves the narrative ranking unchanged"
            unchanged = False
        slots["spread"] = s + "."
        dh = next((n for n in nar if n.get("side") == "pro_huang"), None)
        if dh and base.get("bot_post_share") is not None:
            lo, hi = dh["bot_post_share_ci"]
            b = base["bot_post_share"]
            verdict = "above" if lo > b else "below" if hi < b else "not clearly different from"
            slots["wapo"] = (f"On the Washington Post's 'online bots' claim: \"{dh['label']}\" posts are {_pct1(dh['bot_post_share'])} likely automated "
                             f"({_pct1(lo)} to {_pct1(hi)}), {verdict} the story's {_pct1(b)} baseline.")
    if moved:
        big = max(moved, key=lambda n: abs(n["without_automated"]["rank"] - n["without_automated"]["rank_without"]))
        w = big["without_automated"]
        slots["without"] = (f"Removing likely automated accounts and their engagement moves \"{big['label']}\" from #{w['rank']} to #{w['rank_without']} by volume "
                            f"({_pct1(w['volume_share'])} to {_pct1(w['volume_share_without'])} of posts plus likes, reposts and quotes).")
    elif unchanged:
        slots["without"] = "Removing likely automated accounts and their engagement leaves the narrative ranking unchanged."
    am = site.get("archetypes_meta") or {}
    arch = [a for a in site.get("archetypes", []) if a.get("lift") is not None and a.get("interacting_humans", 0) >= cfg.MIN_HUMANS_FOR_AMPLIFIER_LINE]
    if arch:
        sig = [a for a in arch if a["lift_ci"][0] is not None and a["lift_ci"][0] > 1]
        if sig:
            a = max(sig, key=lambda a: a["lift"])
            who = "matched similar accounts" if am.get("matched") else "other engaged real accounts"
            slots["archetype"] = (f"Real accounts in the archetype \"{a['label']}\" were {a['lift']:.1f}x as likely as {who} to amplify "
                                  f"likely automated posts ({a['lift_ci'][0]:.1f} to {a['lift_ci'][1]:.1f}).")
        else:
            low = [a for a in arch if a["lift_ci"][1] is not None and a["lift_ci"][1] < 1]
            if low:  # say the interval-excludes-1 group instead of claiming every interval includes 1
                a = min(low, key=lambda a: a["lift"])
                tail = (f"no archetype was clearly more likely to amplify them; \"{a['label']}\" accounts were less likely "
                        f"({a['lift']:.2f}x, {a['lift_ci'][0]:.2f} to {a['lift_ci'][1]:.2f}).")
            else:
                tail = "no archetype was clearly more likely to amplify them (every lift interval includes 1)."
            if am.get("matched") and am.get("amplifiers"):
                slots["archetype"] = (f"{am['amplifiers']:,} real accounts amplified likely automated posts. Compared with similar accounts that saw the same story "
                                      f"({am.get('amplifiers_matched', 0):,} matched on narrative, time window, reach, activity and followers), " + tail)
            else:
                slots["archetype"] = "Among real accounts, " + tail
    sc = (site.get("news") or {}).get("spy_claim") or {}
    if sc.get("news_headlines") and sc.get("news_hedged_share") is not None:
        ns, link, own = sc["news_hedged_share"], sc.get("bluesky_link_hedged_share"), sc.get("bluesky_own_words_hedged_share")
        s = f"{_pct(ns)} of wire-service and public-broadcaster headlines about the spy claim hedge (\"alleged\", \"suspected\", \"claims\")"
        if link is not None and own is not None:
            if own < link and abs(link - ns) < 0.1:
                s += (f". On Bluesky, posts that share a link mostly keep the headline's wording ({_pct(link)} hedge), but posts written in "
                      f"people's own words drop it: {_pct(own)} hedge. The caution survives the share button and disappears in the retelling")
            else:
                s += f". On Bluesky, {_pct(link)} of posts that share a link hedge, and {_pct(own)} of posts in people's own words"
        elif sc.get("bluesky_hedged_share") is not None:
            s += f", against {_pct(sc['bluesky_hedged_share'])} of Bluesky posts making it"
        slots["news"] = s + "."
    keep = [k for k in ("story", "spread", "wapo", "news", "archetype", "without") if k in slots][:5]
    order = ("story", "spread", "wapo", "without", "archetype", "news")
    return [slots[k] for k in order if k in keep]


def build(processed: str = "data/processed", raw: str = "data/raw", eval_dir: str = "eval", sample: str = "data/sample",
          node_cap: int = NODE_CAP, edge_cap: int = EDGE_CAP) -> dict:
    return build_from(load(processed, raw, eval_dir, sample), node_cap, edge_cap)


def build_from(c: Ctx, node_cap: int = NODE_CAP, edge_cap: int = EDGE_CAP) -> dict:
    nar, nmeta = narratives(c)
    arch, ameta = archetypes(c)
    site = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "story": story(c),
        "timeline": timeline(c),
        "narratives": nar,
        "narratives_meta": nmeta,
        "graph": graph(c, node_cap, edge_cap),
        "archetypes": arch,
        "archetypes_meta": ameta,
        "coordination": coordination(c),
        "public_accounts": public_accounts(c),
        "validation": validation(c),
        "news": news(c),
        "challenge": challenge(c),
        "challenge_meta": (c.challenge_meta | {"accounts": len(c.challenge or []), "hand_labeled": sum(1 for a in c.challenge or [] if a.get("hand_label"))}) if c.challenge else {},
        "reddit": {"narratives": []},
        "sources": {
            "bot_model": (c.manifest.get("bot_model") or {}).get("version") or c.sources.get("bot_model"),
            "data": "Bluesky AppView public API (api.bsky.app), no login; news: wire-service and public-broadcaster RSS and Google News RSS",
            "privacy": "public accounts by handle; everyone else as a salted hash with no handle, post link or text",
        },
    }
    site["findings"] = findings(site)
    return site


def privacy_violations(site: dict, c: Ctx) -> list[str]:
    """Privacy sweep (DEMO end-to-end check 4): no DID outside a nameable author's post URI, no handle of a
    non-nameable account anywhere, and every handle field holds a nameable account."""
    did_ok = {d for d in c.accounts if c.nameable(d)}
    ok_handles = c._public_handles()
    private_handles = {(a.get("handle") or "").lower() for d, a in c.accounts.items() if a.get("handle") and not c.nameable(d)}
    private_handles.discard("handle.invalid")
    bad: list[str] = []

    def walk(x, key=None):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str):
            for m in re.finditer(r"did:[a-z]+:[A-Za-z0-9._:%-]+", x):
                did = m.group(0)
                pre = x[max(0, m.start() - 5):m.start()]
                if not (pre.endswith("at://") and did in did_ok):
                    bad.append(f"{key}: DID {did[:24]}...")
            if key in ("public_handle", "handle", "public_handles", "examples_public") and x.lower() not in ok_handles:
                bad.append(f"{key}: {x} is not a nameable account")
            if x.lower() in private_handles:
                bad.append(f"{key}: a private account's handle as a value")
            for tok in MENTION_RE.findall(x):
                if tok.lower() in private_handles:
                    bad.append(f"{key}: @mention of a private account in text")
    walk(site)
    return bad


def sample_of(site: dict, nodes: int = 150, edges: int = 300, public: int = 10) -> dict:
    """Small privacy-safe copy for data/sample (truncated graph and lists)."""
    s = json.loads(json.dumps(site))
    g = s.get("graph") or {}
    keep = g.get("nodes", [])[:0]
    roles = Counter()
    for n in sorted(g.get("nodes", []), key=lambda n: (n["role"] != "likely_automated", -n.get("degree", 0))):
        if len(keep) >= nodes:
            break
        if roles[n["role"]] < nodes // 3:
            keep.append(n)
            roles[n["role"]] += 1
    ids = {n["id"] for n in keep}
    g["nodes"] = sorted(keep, key=lambda n: n.get("first_seen") or "")
    g["edges"] = [e for e in g.get("edges", []) if e["s"] in ids and e["t"] in ids][:edges]
    g.setdefault("meta", {})["sample"] = f"truncated to {len(g['nodes'])} nodes and {len(g['edges'])} edges"
    s["public_accounts"] = s.get("public_accounts", [])[:public]
    for n in s.get("narratives", []):
        n["evidence"] = n.get("evidence", [])[:5]
    for a in s.get("archetypes", []):
        a["evidence"] = a.get("evidence", [])[:3]
    s["coordination"] = s.get("coordination", [])[:10]
    for cl in s["coordination"]:
        cl["accounts_ref"] = cl.get("accounts_ref", [])[:20]
    return s


def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--eval", default="eval")
    ap.add_argument("--sample-dir", default="data/sample", help="where challenge.json lives")
    ap.add_argument("--out", default="web/public/site_data.json")
    ap.add_argument("--sample-out", default=None, help="also write a truncated privacy-safe copy here")
    ap.add_argument("--no-translate", action="store_true", help="don't call DeepSeek for new challenge posts (cached translations still apply)")
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    c = load(a.processed, a.raw, a.eval, a.sample_dir)
    if not a.no_translate:
        c.translator = deepseek_translator
    site = build_from(c)
    if c.translation:
        print("challenge translation:", json.dumps(c.translation, ensure_ascii=False))
    bad = privacy_violations(site, c)
    if bad:
        print(f"privacy sweep FAILED ({len(bad)}), nothing written:", *bad[:20], sep="\n  ")
        raise SystemExit(1)
    print("privacy sweep: 0 violations")
    _write(Path(a.out), site)
    if a.sample_out:
        _write(Path(a.sample_out), sample_of(site))
    sizes = {k: (len(v) if isinstance(v, list) else {kk: len(vv) for kk, vv in v.items() if isinstance(vv, list)} if isinstance(v, dict) else v)
             for k, v in site.items() if k not in ("generated_at", "sources")}
    print(f"wrote {a.out} ({Path(a.out).stat().st_size / 1e6:.1f} MB)")
    print(json.dumps(sizes))
    print("findings:")
    for f in site["findings"]:
        print(" -", f)


if __name__ == "__main__":
    main()

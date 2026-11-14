"""Per-account behavior features for the bot model (M2).

Inputs are the raw shapes named in docs/DEMO.md "Module interfaces":
  profile  - one app.bsky.actor.getProfiles record
  history  - that account's compact history items (src/ingest/bluesky_history.py format)
  story    - that account's raw searchPosts records in the story, or [] / None

Excluded on purpose (README, kickoff note): the self-applied `bot` label, any bio words, the handle text,
and the bridged label. The model has to find automation from how an account behaves, not from what it
says about itself. Bio *length* is kept; bio content is not.

Every feature is computable for one account at API time, because the live path calls score_accounts directly.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone

import numpy as np

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)

_URL = re.compile(r"https?://\S+|www\.\S+")
_MENTION = re.compile(r"@[\w.\-]+")
_DIGITS = re.compile(r"\d+")
_NONWORD = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def norm_text(t: str) -> str:
    """Lowercase, strip URLs, mentions and punctuation, mask digits. Used for duplicate detection."""
    t = _URL.sub(" ", t.lower())
    t = _MENTION.sub(" ", t)
    t = _DIGITS.sub("0", t)
    t = _NONWORD.sub(" ", t)
    return _WS.sub(" ", t).strip()


def _dup_share(texts: list[str]) -> float:
    """Share of texts that repeat an earlier text from the same list."""
    if len(texts) < 2:
        return 0.0
    return 1 - len(set(texts)) / len(texts)


def _entropy(counts: Counter, n_bins: int) -> float:
    tot = sum(counts.values())
    if tot == 0:
        return float("nan")
    h = -sum((c / tot) * math.log(c / tot) for c in counts.values() if c)
    return h / math.log(n_bins)


def _domain(u: str) -> str | None:
    parts = u.split("/")
    if len(parts) < 3:
        return None
    d = parts[2].lower()
    return d[4:] if d.startswith("www.") else d


FEATURES = [
    # profile
    "log_followers",
    "log_follows",
    "follow_ratio_log",
    "log_posts_count",
    "age_days_log",
    "lifetime_ppd_log",
    "has_avatar",
    "has_banner",
    "has_display_name",
    "bio_len",
    "has_pinned",
    # history timing
    "hist_n",
    "hist_rate_log",
    "gap_cv",
    "gap_median_log",
    "burst_share",
    "hour_entropy",
    "minute_entropy",
    "on_minute_share",
    # history composition
    "repost_share",
    "reply_share",
    "quote_share",
    "link_share",
    "distinct_domains",
    "top_domain_share",
    "self_dup_rate",
    "prefix_dup_rate",
    "text_len_mean",
    "text_len_cv",
    "hashtag_rate",
    "zero_engagement_share",
    "likes_mean_log",
    "n_langs",
    "repost_top_author_share",
    # story
    "story_n_log",
    "story_dup_rate",
    "story_link_share",
    "story_share_of_history",
]


def account_features(profile: dict, history: list[dict] | None, story: list[dict] | None = None) -> dict:
    history = history or []
    story = story or []
    f: dict[str, float] = {}

    # --- profile
    followers = profile.get("followersCount") or 0
    follows = profile.get("followsCount") or 0
    posts_count = profile.get("postsCount") or 0
    created = ts(profile.get("createdAt"))
    story_times = sorted(t for t in (ts((p.get("record") or {}).get("createdAt")) for p in story) if t)
    ref_time = story_times[0] if story_times else NOW
    age_days = max((ref_time - created).total_seconds() / 86400, 1.0) if created else float("nan")
    f["log_followers"] = math.log1p(followers)
    f["log_follows"] = math.log1p(follows)
    f["follow_ratio_log"] = math.log((follows + 1) / (followers + 1))
    f["log_posts_count"] = math.log1p(posts_count)
    f["age_days_log"] = math.log(age_days) if age_days == age_days else float("nan")
    f["lifetime_ppd_log"] = math.log1p(posts_count / age_days) if age_days == age_days else float("nan")
    f["has_avatar"] = float(bool(profile.get("avatar")))
    f["has_banner"] = float(bool(profile.get("banner")))
    f["has_display_name"] = float(bool((profile.get("displayName") or "").strip()))
    f["bio_len"] = float(len(profile.get("description") or ""))
    f["has_pinned"] = float(bool(profile.get("pinnedPost")))

    # --- history timing
    times = sorted(t for t in (ts(i.get("t")) for i in history) if t)
    n = len(history)
    f["hist_n"] = float(n)
    if len(times) >= 2:
        span_days = max((times[-1] - times[0]).total_seconds() / 86400, 1 / 24)
        f["hist_rate_log"] = math.log1p(len(times) / span_days)
        gaps = np.array([(b - a).total_seconds() for a, b in zip(times, times[1:])])
        pos = gaps[gaps > 0]
        if len(pos) >= 5:
            f["gap_cv"] = float(pos.std() / pos.mean())
            f["gap_median_log"] = math.log1p(float(np.median(pos)))
        else:
            f["gap_cv"] = f["gap_median_log"] = float("nan")
        f["burst_share"] = float((gaps < 10).mean())
    else:
        f["hist_rate_log"] = f["gap_cv"] = f["gap_median_log"] = f["burst_share"] = float("nan")
    if times:
        f["hour_entropy"] = _entropy(Counter(t.hour for t in times), 24)
        f["minute_entropy"] = _entropy(Counter(t.minute for t in times), 60)
        f["on_minute_share"] = sum(1 for t in times if t.second == 0 and t.microsecond == 0) / len(times)
    else:
        f["hour_entropy"] = f["minute_entropy"] = f["on_minute_share"] = float("nan")

    # --- history composition
    kinds = Counter(i.get("kind") for i in history)
    own = [i for i in history if i.get("kind") != "repost"]
    denom = max(n, 1)
    f["repost_share"] = kinds.get("repost", 0) / denom if n else float("nan")
    f["reply_share"] = kinds.get("reply", 0) / denom if n else float("nan")
    f["quote_share"] = kinds.get("quote", 0) / denom if n else float("nan")
    if own:
        with_link = [i for i in own if i.get("urls")]
        f["link_share"] = len(with_link) / len(own)
        doms = Counter(d for i in with_link for d in {_domain(u) for u in i["urls"]} if d and d != "bsky.app")
        f["distinct_domains"] = float(len(doms))
        f["top_domain_share"] = doms.most_common(1)[0][1] / sum(doms.values()) if doms else 0.0
        texts = [norm_text(i.get("text") or "") for i in own]
        long_texts = [t for t in texts if len(t) >= 10]
        f["self_dup_rate"] = _dup_share(long_texts)
        f["prefix_dup_rate"] = _dup_share([" ".join(t.split()[:5]) for t in long_texts if len(t.split()) >= 5])
        lens = np.array([len(i.get("text") or "") for i in own], dtype=float)
        f["text_len_mean"] = float(lens.mean())
        f["text_len_cv"] = float(lens.std() / lens.mean()) if lens.mean() > 0 else 0.0
        f["hashtag_rate"] = float(np.mean([(i.get("text") or "").count("#") for i in own]))
        eng = np.array(
            [(i.get("n_like") or 0) + (i.get("n_repost") or 0) + (i.get("n_reply") or 0) + (i.get("n_quote") or 0) for i in own]
        )
        f["zero_engagement_share"] = float((eng == 0).mean())
        f["likes_mean_log"] = float(np.mean(np.log1p([i.get("n_like") or 0 for i in own])))
        f["n_langs"] = float(len({l for i in own for l in (i.get("langs") or [])}))
    else:
        for k in (
            "link_share", "distinct_domains", "top_domain_share", "self_dup_rate", "prefix_dup_rate", "text_len_mean",
            "text_len_cv", "hashtag_rate", "zero_engagement_share", "likes_mean_log", "n_langs",
        ):
            f[k] = float("nan")
    reposts = [i.get("author") for i in history if i.get("kind") == "repost" and i.get("author")]
    f["repost_top_author_share"] = Counter(reposts).most_common(1)[0][1] / len(reposts) if len(reposts) >= 3 else float("nan")

    # --- story
    f["story_n_log"] = math.log1p(len(story))
    story_texts = [norm_text((p.get("record") or {}).get("text") or "") for p in story]
    f["story_dup_rate"] = _dup_share([t for t in story_texts if len(t) >= 10])
    if story:
        def has_link(p: dict) -> bool:
            rec = p.get("record") or {}
            emb = rec.get("embed") or {}
            if (emb.get("external") or (emb.get("media") or {}).get("external")):
                return True
            return any(ft.get("uri") for fc in rec.get("facets") or [] for ft in fc.get("features") or [])

        f["story_link_share"] = sum(map(has_link, story)) / len(story)
    else:
        f["story_link_share"] = 0.0  # no story posts, no story links (an all-NaN column breaks HGB binning)
    f["story_share_of_history"] = len(story) / max(n, 1)
    return f


COORD_FEATURES = ["coord_cluster_size_log", "coord_traces_log", "coord_max_sim"]


def feature_matrix(profiles: list[dict], histories: dict, story_posts: dict | None, names: list[str] | None = None,
                   coord: dict[str, dict] | None = None) -> np.ndarray:
    """Rows = profiles, columns = names (default: behavior FEATURES). Coordination columns come from `coord`
    (src.bots.coordination.account_coord_features over the same batch); accounts with no shared traces get 0."""
    names = names or FEATURES
    story_posts = story_posts or {}
    coord = coord or {}
    zero = {k: 0.0 for k in COORD_FEATURES}
    rows = []
    for p in profiles:
        r = account_features(p, histories.get(p["did"]), story_posts.get(p["did"]))
        r.update({k: v for k, v in coord.get(p["did"], zero).items() if k in zero})
        rows.append([r.get(k, 0.0) for k in names])
    return np.array(rows, dtype=float)


def self_label_bot(profile: dict, story: list[dict] | None = None) -> bool:
    """Training label only. Never a feature."""
    labels = [l.get("val") for l in (profile.get("labels") or [])]
    for p in story or []:
        labels += [l.get("val") for l in ((p.get("author") or {}).get("labels") or [])]
    return any(l in ("bot", "!bot") for l in labels)


def bridged(profile: dict) -> bool:
    return any((l.get("val") or "").startswith("bridged-from-") for l in (profile.get("labels") or []))

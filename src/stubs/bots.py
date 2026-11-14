"""Placeholder bot scorer with Muse's interface (docs/DEMO.md, "Module interfaces").

The API imports src.bots.score when Muse's module exists and falls back to this file otherwise.
Heuristic only: a hand-weighted logistic over a few behavior features. Not trained, not evaluated.
"""
import math
import statistics
from collections import Counter
from datetime import datetime, timezone

MODEL_VERSION = "stub"
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def features(profile: dict, history: list[dict]) -> dict:
    created = _ts(profile.get("createdAt"))
    age_days = max((NOW - created).days, 1) if created else 365
    ppd = (profile.get("postsCount") or 0) / age_days
    times = sorted(t for t in (_ts(i.get("t")) for i in history) if t)
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:]) if (b - a).total_seconds() > 0]
    cv = statistics.pstdev(gaps) / statistics.mean(gaps) if len(gaps) >= 5 and statistics.mean(gaps) > 0 else 1.0
    n = max(len(history), 1)
    kinds = Counter(i.get("kind") for i in history)
    texts = [(i.get("text") or "").strip().lower() for i in history if i.get("kind") != "repost" and (i.get("text") or "").strip()]
    dup = 1 - len(set(texts)) / len(texts) if texts else 0.0
    link = sum(1 for i in history if i.get("urls")) / n
    hours = Counter(t.hour for t in times)
    ent = -sum((c / len(times)) * math.log(c / len(times), 2) for c in hours.values()) if times else 0.0
    followers, follows = profile.get("followersCount") or 0, profile.get("followsCount") or 0
    return {
        "posts_per_day": ppd,
        "gap_cv": cv,
        "repost_share": kinds.get("repost", 0) / n,
        "link_share": link,
        "dup_rate": dup,
        "hour_entropy": ent,
        "follow_ratio": (follows + 1) / (followers + 1),
        "age_days": age_days,
        "has_avatar": bool(profile.get("avatar")),
    }


REASON = {
    "posts_per_day": "posts {v:.0f} times a day on average",
    "gap_cv": "posts at unusually regular intervals",
    "link_share": "{v:.0%} of recent posts are links",
    "dup_rate": "{v:.0%} of its recent posts repeat earlier text",
    "hour_entropy": "posts around the clock",
    "has_avatar": "no profile picture",
    "age_days": "account is {v:.0f} days old",
}


def load_model(path: str | None = None) -> dict:
    return {"version": MODEL_VERSION}


def _score(f: dict) -> tuple[float, list[str]]:
    contrib = {
        "posts_per_day": 1.2 * math.log10(1 + f["posts_per_day"]) - 1.0,
        "gap_cv": 1.0 * (0.6 - min(f["gap_cv"], 2.0)),
        "link_share": 1.5 * (f["link_share"] - 0.4),
        "dup_rate": 3.0 * (f["dup_rate"] - 0.1),
        "hour_entropy": 0.6 * (f["hour_entropy"] - 3.8),
        "has_avatar": 0.0 if f["has_avatar"] else 0.8,
        "age_days": 0.5 if f["age_days"] < 60 else 0.0,
    }
    z = sum(contrib.values()) - 1.5
    p = 1 / (1 + math.exp(-z))
    top = [k for k, v in sorted(contrib.items(), key=lambda kv: -kv[1]) if v > 0.2][:3]
    return p, [REASON[k].format(v=f[k]) for k in top]


def score_accounts(model, profiles: list[dict], histories: dict[str, list[dict]], story_posts: dict | None = None) -> list[dict]:
    out = []
    for prof in profiles:
        f = features(prof, histories.get(prof["did"], []))
        p, reasons = _score(f)
        out.append({"did": prof["did"], "p_automated": round(p, 4), "reasons": reasons})
    return out

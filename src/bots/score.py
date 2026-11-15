"""Bot scorer behind the interface in docs/DEMO.md ("Module interfaces between the two halves").

    model = load_model()
    score_accounts(model, profiles, histories, story_posts) -> [{"did", "p_automated", "reasons"}]

p_automated is the positive-unlabeled estimate of P(automated | behavior) (Elkan and Noto, 2008):
the classifier learns P(self-labeled | x) and that is divided by c, the mean score of held-out labeled
bots. The labeled bots are mostly disclosed news and trend bots, so c is only an estimate; the report
states the caveat. Ranking does not depend on c.

Reasons are the top three behavior signals pushing an account toward "automated", in plain words, taken
from a linear surrogate fitted on the same features. They are observable signals only and never say who
runs an account.

If the model file is missing (no training run yet on this machine), load_model falls back to the heuristic
stub so the API keeps working, and model["version"] says "stub".
"""
from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np

from src.bots.features import COORD_FEATURES, FEATURES, feature_matrix

DEFAULT_PATH = "data/processed/artifacts/bot_model.joblib"


def load_model(path: str | None = None) -> dict:
    p = Path(path or DEFAULT_PATH)
    if not p.exists():
        warnings.warn(f"{p} not found; run `python -m src.bots.train`. Falling back to the heuristic stub.")
        from src.stubs import bots as stub

        m = stub.load_model()
        m["_stub"] = stub
        return m
    import joblib

    return joblib.load(p)


# ---------- reasons

def _secs(s: float) -> str:
    if s < 90:
        return f"{s:.0f} seconds"
    if s < 5400:
        return f"{s / 60:.0f} minutes"
    return f"{s / 3600:.1f} hours"


# feature -> (direction, phrase(f)) ; direction +1: high values look automated, -1: low values do
REASONS = {
    "lifetime_ppd_log": (+1, lambda f: f"averages {math.expm1(f['lifetime_ppd_log']):.0f} posts a day over the account's life"),
    "hist_rate_log": (+1, lambda f: f"recent pace of about {math.expm1(f['hist_rate_log']):.0f} posts a day"),
    "log_posts_count": (+1, lambda f: f"{math.expm1(f['log_posts_count']):,.0f} posts in total"),
    "gap_cv": (-1, lambda f: "posts at unusually regular intervals"),
    "gap_median_log": (-1, lambda f: f"usually posts again within {_secs(math.expm1(f['gap_median_log']))}"),
    "burst_share": (+1, lambda f: f"{f['burst_share']:.0%} of its posts come within 10 seconds of the previous one"),
    "hour_entropy": (+1, lambda f: "posts around the clock, at every hour of the day"),
    "minute_entropy": (-1, lambda f: "posts cluster on the same minutes of the hour"),
    "on_minute_share": (+1, lambda f: f"{f['on_minute_share']:.0%} of its posts are timestamped exactly on the minute"),
    "repost_share": (+1, lambda f: f"{f['repost_share']:.0%} of its recent activity is reposts"),
    "reply_share": (-1, lambda f: f"rarely replies to anyone ({f['reply_share']:.0%} of recent activity)"),
    "link_share": (+1, lambda f: f"{f['link_share']:.0%} of its posts carry a link"),
    "top_domain_share": (+1, lambda f: f"{f['top_domain_share']:.0%} of its links go to one site"),
    "self_dup_rate": (+1, lambda f: f"{f['self_dup_rate']:.0%} of its posts repeat its own earlier text"),
    "prefix_dup_rate": (+1, lambda f: f"{f['prefix_dup_rate']:.0%} of its posts open with the same words"),
    "text_len_cv": (-1, lambda f: "its posts are nearly all the same length"),
    "hashtag_rate": (+1, lambda f: f"uses {f['hashtag_rate']:.1f} hashtags per post"),
    "zero_engagement_share": (+1, lambda f: f"{f['zero_engagement_share']:.0%} of its posts get no likes, replies or reposts"),
    "repost_top_author_share": (+1, lambda f: f"{f['repost_top_author_share']:.0%} of its reposts come from one account"),
    "has_avatar": (-1, lambda f: "no profile picture"),
    "has_display_name": (-1, lambda f: "no display name"),
    "index_gap_log": (-1, lambda f: f"profile last updated {math.expm1(f['index_gap_log']) / 24:.0f} days after the account was created"),
    "bio_len": (-1, lambda f: "empty or very short bio"),
    "age_days_log": (-1, lambda f: f"account was {math.exp(f['age_days_log']):.0f} days old at its first story post"),
    "follow_ratio_log": (+1, lambda f: f"follows {math.expm1(f['log_follows']):,.0f} accounts but has {math.expm1(f['log_followers']):,.0f} followers"),
    "log_followers": (-1, lambda f: f"has only {math.expm1(f['log_followers']):,.0f} followers"),
    "story_n_log": (+1, lambda f: f"posted {math.expm1(f['story_n_log']):.0f} times about the story"),
    "story_dup_rate": (+1, lambda f: f"{f['story_dup_rate']:.0%} of its story posts repeat each other"),
    "story_link_share": (+1, lambda f: f"{f['story_link_share']:.0%} of its story posts are links"),
    "story_share_of_history": (+1, lambda f: "most of its recent posts are about this story"),
    "coord_cluster_size_log": (+1, lambda f: f"acts in step with {math.expm1(f['coord_cluster_size_log']) - 1:.0f} other accounts (same links, reposts or text within seconds)"),
    "coord_max_sim": (+1, lambda f: "shares most of its links, reposts or wording with another account"),
}
REASON_MIN_CONTRIB = 0.25


def _standardize(model: dict, X: np.ndarray) -> np.ndarray:
    Xi = np.where(np.isnan(X), model["median"], X)
    return (Xi - model["mu"]) / model["sd"]


def _names(model: dict) -> list[str]:
    return list(model.get("features") or FEATURES)


def reasons_for(model: dict, x: np.ndarray, f: dict, k: int = 3) -> list[str]:
    z = _standardize(model, x[None, :])[0]
    contrib = model["coef"] * z
    out = []
    for j in np.argsort(-contrib):
        if contrib[j] < REASON_MIN_CONTRIB or len(out) >= k:
            break
        name = _names(model)[j]
        if name not in REASONS or np.isnan(x[j]):
            continue
        direction, phrase = REASONS[name]
        if direction * z[j] <= 0:  # the phrase describes the other tail
            continue
        out.append(phrase(f))
    return out


def p_from_raw(model: dict, X: np.ndarray) -> np.ndarray:
    """P(automated | x) = P(labeled | x) / c, clipped to [0, 1]."""
    ps = model["clf"].predict_proba(X if model["kind"] == "hgb" else _standardize(model, X))[:, 1]
    return np.clip(ps / model["c"], 0.0, 1.0)


def score_accounts(model, profiles: list[dict], histories: dict[str, list[dict]], story_posts: dict[str, list[dict]] | None = None) -> list[dict]:
    if "_stub" in model:
        return model["_stub"].score_accounts(model, profiles, histories, story_posts)
    if not profiles:
        return []
    story_posts = story_posts or {}
    names = _names(model)
    coord = None
    if any(n in COORD_FEATURES for n in names):
        from src.bots.coordination import account_coord_features, posts_from_inputs

        coord = account_coord_features(posts_from_inputs(histories, story_posts))
    X = feature_matrix(profiles, histories, story_posts, names, coord)
    p = p_from_raw(model, X)
    out = []
    for i, prof in enumerate(profiles):
        f = dict(zip(names, X[i]))
        out.append({"did": prof["did"], "p_automated": round(float(p[i]), 4), "reasons": reasons_for(model, X[i], f)})
    return out


def model_version(model) -> str:
    return str(model.get("version", "unknown"))

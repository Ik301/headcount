"""Archetype features (M5): public behavior only, from each account's profile and recent history.

No demographic or sensitive guesses (README rule 4): nothing about age, gender, race, religion, health or
politics of the person. Topic mix uses only what the account posts about, via narrative centroids when they
are available.

Columns (documented here, per the README's `user_features` table):
  age_days_log           log account age in days
  lifetime_ppd_log       log1p lifetime posts per day
  hist_rate_log          log1p recent posts per day (last 50 items)
  repost_share           share of recent activity that is reposts
  reply_share            share that is replies
  quote_share            share that is quote posts
  link_share             share of own posts with a link
  follow_ratio_log       log((follows + 1) / (followers + 1))
  log_followers          log1p followers
  hour_entropy           how spread its posting is over the 24 hours (0 to 1)
  night_share_utc        share of recent posts between 04:00 and 10:00 UTC (US night)
  zero_engagement_share  share of own posts with no likes, replies or reposts
  likes_mean_log         mean log1p likes on own posts
"""
from __future__ import annotations

import math

import numpy as np

from src.bots.features import account_features, ts

ARCH_FEATURES = [
    "age_days_log",
    "lifetime_ppd_log",
    "hist_rate_log",
    "repost_share",
    "reply_share",
    "quote_share",
    "link_share",
    "follow_ratio_log",
    "log_followers",
    "hour_entropy",
    "night_share_utc",
    "zero_engagement_share",
    "likes_mean_log",
]

# plain-word description of each feature at the high and low end, for archetype labels and cards
WORDS = {
    "age_days_log": ("older accounts", "new accounts"),
    "lifetime_ppd_log": ("very prolific posters", "occasional posters"),
    "hist_rate_log": ("posting a lot this week", "posting little this week"),
    "repost_share": ("mostly reposting others", "rarely reposting"),
    "reply_share": ("mostly replying in threads", "rarely replying"),
    "quote_share": ("often quote-posting", "rarely quote-posting"),
    "link_share": ("mostly sharing links", "rarely sharing links"),
    "follow_ratio_log": ("following far more accounts than follow them", "followed more than they follow"),
    "log_followers": ("with large followings", "with small followings"),
    "hour_entropy": ("active around the clock", "active in a narrow daily window"),
    "night_share_utc": ("active during US night hours", "rarely active during US night hours"),
    "zero_engagement_share": ("whose posts get little engagement", "whose posts usually get engagement"),
    "likes_mean_log": ("whose posts get many likes", "whose posts get few likes"),
}


def arch_row(profile: dict, history: list[dict] | None) -> dict:
    f = account_features(profile, history, None)
    times = [t for t in (ts(i.get("t")) for i in history or []) if t]
    f["night_share_utc"] = sum(4 <= t.hour < 10 for t in times) / len(times) if times else float("nan")
    return {k: f[k] for k in ARCH_FEATURES}


def arch_matrix(profiles: list[dict], histories: dict) -> np.ndarray:
    return np.array([[arch_row(p, histories.get(p["did"]))[k] for k in ARCH_FEATURES] for p in profiles], dtype=float)


def describe(name: str, value: float) -> str:
    """A number in plain words for archetype cards."""
    if name == "age_days_log":
        return f"median account age {math.exp(value):.0f} days"
    if name in ("lifetime_ppd_log", "hist_rate_log"):
        return f"{math.expm1(value):.1f} posts a day" + (" recently" if name == "hist_rate_log" else "")
    if name == "log_followers":
        return f"{math.expm1(value):,.0f} followers"
    if name == "follow_ratio_log":
        return f"follows {math.exp(value):.1f}x as many accounts as follow it"
    if name == "likes_mean_log":
        return f"about {math.expm1(value):.1f} likes per post"
    if name == "hour_entropy":
        return f"hour spread {value:.2f} (1 = evenly around the clock)"
    return f"{value:.0%} " + {
        "repost_share": "reposts",
        "reply_share": "replies",
        "quote_share": "quote posts",
        "link_share": "of posts with links",
        "night_share_utc": "of posts in US night hours",
        "zero_engagement_share": "of posts with no engagement",
    }[name]

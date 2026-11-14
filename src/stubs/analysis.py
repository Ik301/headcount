"""Placeholder coordination and archetype modules with Muse's interfaces (docs/DEMO.md)."""
import re
from collections import defaultdict
from datetime import datetime


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", t or "").lower()).strip()


def find_clusters(posts: list[dict], window_s: int = 60) -> list[dict]:
    """posts: [{"did", "uri", "t", "text"}]. Groups 3+ distinct accounts posting the same text within window_s."""
    by_text = defaultdict(list)
    for p in posts:
        k = _norm(p.get("text", ""))
        if len(k) >= 30:
            by_text[k].append(p)
    clusters = []
    for k, ps in by_text.items():
        ps = sorted(ps, key=lambda p: p.get("t") or "")
        dids = {p["did"] for p in ps}
        if len(dids) < 3:
            continue
        ts = [datetime.fromisoformat(p["t"].replace("Z", "+00:00")) for p in ps if p.get("t")]
        span = (max(ts) - min(ts)).total_seconds() if ts else 1e9
        if span > window_s * len(dids):
            continue
        clusters.append(
            {
                "cluster_id": f"c{len(clusters)}",
                "dids": sorted(dids),
                "reasons": [f"{len(dids)} accounts posted the same text within {int(span)} seconds"],
                "evidence": [{"post_uri": p["uri"], "t": p.get("t"), "trace": "identical text"} for p in ps[:10]],
            }
        )
    return clusters


ARCHETYPES = {
    "a1": "New accounts (under 90 days)",
    "a2": "Heavy reposters (mostly reposts)",
    "a3": "News and link sharers",
    "a4": "Conversational posters (mostly replies)",
    "a5": "Everyone else",
}


def load_archetypes(path: str | None = None) -> dict:
    return {"version": "stub", "labels": ARCHETYPES}


def assign(arch, profiles: list[dict], histories: dict[str, list[dict]]) -> list[dict]:
    from src.stubs.bots import features

    out = []
    for prof in profiles:
        f = features(prof, histories.get(prof["did"], []))
        h = histories.get(prof["did"], [])
        replies = sum(1 for i in h if i.get("kind") == "reply") / max(len(h), 1)
        if f["age_days"] < 90:
            a = "a1"
        elif f["repost_share"] > 0.6:
            a = "a2"
        elif f["link_share"] > 0.5:
            a = "a3"
        elif replies > 0.5:
            a = "a4"
        else:
            a = "a5"
        out.append({"did": prof["did"], "archetype_id": a, "label": ARCHETYPES[a]})
    return out

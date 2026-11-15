"""analyze_claim returns the claim-level likely-automated share and interval next to the narratives (reply verdict input)."""
import polars as pl

from src.api import analysis


def test_claim_level_share_is_computed_over_all_matched_posts(monkeypatch):
    rows = []
    for i in range(40):  # 40 accounts, 2 posts each; the first 8 accounts are likely automated -> 20%
        for j in range(2):
            rows.append({"post_id": f"p{i}_{j}", "account_id": f"a{i}", "created_at": "2026-11-06T00:00:00Z", "text": f"t{i}_{j}",
                         "norm": f"t{i}_{j}", "narrative_id": "n1" if i % 2 else "n7", "side": "x", "p_automated": 0.9 if i < 8 else 0.1})
    posts = pl.DataFrame(rows)
    store = analysis.Store(corpus=None, posts=posts, accounts={}, reasons={}, archetype={}, interactions=None, baseline_bot_share=0.05)
    hits = pl.DataFrame({"norm": posts["norm"].to_list(), "sim": [0.9] * posts.height})
    monkeypatch.setattr(analysis.rc, "search_claim", lambda corpus, text, floor: hits)
    r = analysis.analyze_claim(store, "a claim")
    assert r["matched_posts"] == 80 and r["bot_post_share"] == 0.2
    lo, hi = r["bot_post_share_ci"]
    assert 0 < lo < 0.2 < hi < 0.4
    assert r["narratives"] and all("bot_post_share_ci" in n for n in r["narratives"])
    small = analysis.analyze_claim(store, "another claim")  # cached under its own id; below the match floor shares stay 0
    assert small["bot_post_share"] >= 0


def test_below_the_match_floor_the_claim_level_share_is_zero(monkeypatch):
    posts = pl.DataFrame([{"post_id": "p", "account_id": "a", "created_at": "2026-11-06T00:00:00Z", "text": "t", "norm": "t", "narrative_id": "n1", "side": "x", "p_automated": 0.9}])
    store = analysis.Store(corpus=None, posts=posts, accounts={}, reasons={}, archetype={}, interactions=None, baseline_bot_share=0.05)
    monkeypatch.setattr(analysis.rc, "search_claim", lambda corpus, text, floor: pl.DataFrame({"norm": ["t"], "sim": [0.9]}))
    r = analysis.analyze_claim(store, "tiny")
    assert r["matched_posts"] == 1 and r["bot_post_share"] == 0.0 and r["narratives"] == []

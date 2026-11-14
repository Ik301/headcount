"""M4 narrative shares on synthetic tables: shape, bridged denominators, threshold strip, kill test 3. No torch."""
import polars as pl

from src.bots.narrative_shares import kill_test_3, narrative_shares


def tables():
    # n1: 10 posts, 5 by a likely automated account; n2: 10 posts, 1 automated; one bridged automated account in n2
    posts, pn, scores, accts = [], [], [], []
    for i in range(10):
        a = "bot1" if i < 5 else f"h{i}"
        posts.append({"post_id": f"p1_{i}", "account_id": a}); pn.append({"post_id": f"p1_{i}", "narrative_id": "n1", "prob": 0.9})
    for i in range(10):
        a = "bot2" if i == 0 else ("br" if i == 1 else f"g{i}")
        posts.append({"post_id": f"p2_{i}", "account_id": a}); pn.append({"post_id": f"p2_{i}", "narrative_id": "n2", "prob": 0.8})
    pn.append({"post_id": "p2_0", "narrative_id": "n1", "prob": 0.1})  # lower-prob duplicate must be ignored
    ids = {p["account_id"] for p in posts}
    for a in ids:
        scores.append({"account_id": a, "p_automated": 0.95 if a in ("bot1", "bot2", "br") else 0.05})
        accts.append({"account_id": a, "bridged": a == "br"})
    return pl.DataFrame(pn), pl.DataFrame(posts), pl.DataFrame(scores), pl.DataFrame(accts)


def test_shares_shape_and_values():
    pn, posts, scores, accts = tables()
    res = narrative_shares(pn, posts, scores, accts, {"n1": "Spy plot"})
    by = {r["id"]: r for r in res["narratives"]}
    assert by["n1"]["bot_post_share"] == 0.5 and by["n1"]["label"] == "Spy plot"
    assert by["n2"]["n_posts"] == 9  # bridged account's post left out of the main denominator
    assert by["n2"]["with_bridged"]["n_posts"] == 10
    assert abs(by["n2"]["bot_post_share"] - 1 / 9) < 1e-3
    for r in res["narratives"]:
        assert set(r["threshold_strip"]) == {"0.3", "0.5", "0.7", "0.9"}
        lo, hi = r["bot_post_share_ci"]
        assert lo <= r["bot_post_share"] <= hi
    assert "unbridged" in res["denominator"]


def test_kill_test_3():
    pn, posts, scores, accts = tables()
    kt = kill_test_3(narrative_shares(pn, posts, scores, accts))
    assert kt["pass"] and kt["per_cutoff"]["0.5"]["most"] == "n1"

"""Reply rules from docs/DEMO.md, tested on synthetic results (no data needed)."""
from src.api import reply


def result(n=200, narratives=None):
    return {
        "claim": "test claim",
        "matched_posts": n,
        "baseline_bot_share": 0.05,
        "narratives": narratives
        if narratives is not None
        else [
            {"label": "Spy plot and national security", "share_of_matches": 0.6, "bot_post_share": 0.12, "bot_post_share_ci": [0.08, 0.16]},
            {"label": "Jokes and memes", "share_of_matches": 0.4, "bot_post_share": 0.02, "bot_post_share_ci": [0.01, 0.04]},
        ],
        "bot_commonalities": [{"signal": "created in the same month (2026-10)", "accounts": 12}],
        "amplifiers": {"n_humans": 300, "archetype_mix": [{"label": "Heavy reposters", "share": 0.4, "lift": 2.1}]},
        "dashboard_url": "http://localhost:5173/claim/abc",
    }


def test_truth_disclaimer_always_present():
    assert reply.TRUTH_LINE in reply.compose(result())
    assert reply.TRUTH_LINE in reply.compose(result(n=5))


def test_too_few_matches_reports_no_shares():
    text = reply.compose(result(n=12))
    assert "isn't enough" in text and "Likely automated" not in text


def test_uses_likely_automated_wording_and_interval():
    text = reply.compose(result())
    assert "Likely automated: 12% (8 to 16%)" in text
    assert " bots" not in text.lower()


def test_baseline_ratio_only_when_large():
    text = reply.compose(result())
    assert "2x the story's baseline" in text
    assert text.count("baseline") == 1


def test_no_operator_claims():
    r = result()
    r["bot_commonalities"] = [{"signal": "accounts run by a PR firm", "accounts": 3}]
    assert "run by" not in reply.compose(r)


def test_chart_renders():
    png = reply.chart_png(result())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

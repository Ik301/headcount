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


def test_chart_renders_with_no_narratives():
    png = reply.chart_png(result(n=0, narratives=[]))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_chart_falls_back_without_font_files(monkeypatch, tmp_path):
    monkeypatch.setattr(reply, "_FONT_DIR", tmp_path)  # no TTFs here -> DejaVu, still a PNG
    png = reply.chart_png(result())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_chart_source_line_states_the_cutoff():
    lines = reply._source_lines(result())
    assert "n=200" in lines[0] and "Bluesky" in lines[0]
    assert "likely automated" in lines[1] and "bots" not in " ".join(lines)


def test_declined_and_failed_results_keep_their_template():
    # src.api.app recomposes every result, so the live path's decline must survive compose()
    r = result(n=0, narratives=[])
    r["declined"] = True
    assert reply.compose(r) == reply.DECLINE
    r = result(n=0, narratives=[])
    r["error"] = "Bluesky search did not answer"
    assert reply.compose(r) == reply.FAILURE


def test_amplifier_line_skips_unprofiled_and_lifts_below_one():
    r = result()
    r["amplifiers"] = {"n_humans": 14, "archetype_mix": [
        {"id": "unknown", "label": "Not profiled", "share": 0.79, "lift": 0.85},
        {"id": "a2", "label": "Heavy reposters", "share": 0.07, "lift": 4.46},
    ]}
    text = reply.compose(r)
    assert "Not profiled" not in text and "Heavy reposters" not in text  # 1 profiled account is too few
    r["amplifiers"] = {"n_humans": 300, "archetype_mix": [{"id": "a1", "label": "Occasional posters", "share": 0.6, "lift": 0.9}]}
    assert "more likely" not in reply.compose(r)
    r["amplifiers"] = {"n_humans": 300, "archetype_mix": [{"id": "a2", "label": "Heavy reposters", "share": 0.6, "lift": 1.4}]}
    assert '"Heavy reposters" (1.4x more likely' in reply.compose(r)


def test_more_narratives_than_shown_are_counted():
    narrs = [{"label": f"N{i}", "share_of_matches": s, "bot_post_share": 0.0, "bot_post_share_ci": [0.0, 0.0]} for i, s in enumerate([0.3, 0.25, 0.2, 0.1, 0.1, 0.03])]
    text = reply.compose(result(narratives=narrs))
    assert "N3" in text and "N4" not in text
    assert "+ 2 smaller narratives in the full view." in text
    assert "smaller narratives" not in reply.compose(result())

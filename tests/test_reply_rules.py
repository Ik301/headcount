"""Reply rules from docs/DEMO.md, tested on synthetic results (no data needed)."""
import re

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
    assert "too few" in text and "likely automated accounts" not in text and "12" in text


def test_uses_likely_automated_wording_and_no_interval_in_the_answer():
    text = reply.compose(result())
    assert "likely automated accounts" in text and " bots" not in text.lower()
    assert " to " not in text.split("\n")[1]  # intervals live on the card, not in the first bubble


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


def test_amplifier_followup_skips_unprofiled_and_lifts_below_one():
    r = result()
    r["amplifiers"] = {"n_humans": 14, "archetype_mix": [
        {"id": "unknown", "label": "Not profiled", "share": 0.79, "lift": 0.85},
        {"id": "a2", "label": "Heavy reposters", "share": 0.07, "lift": 4.46},
    ]}
    text = reply.followup(3, r)
    assert "Not profiled" not in text and "Heavy reposters" not in text and "too few to compare" in text
    assert "more likely" not in text
    r["amplifiers"] = {"n_humans": 300, "archetype_mix": [{"id": "a1", "label": "Occasional posters", "share": 0.6, "lift": 0.9}]}
    assert "more likely" not in reply.followup(3, r) and "180 accounts" in reply.followup(3, r)
    r["amplifiers"] = {"n_humans": 300, "archetype_mix": [{"id": "a2", "label": "Heavy reposters", "share": 0.6, "lift": 1.4}]}
    assert '"Heavy reposters": 180 accounts, 1.4x more likely than similar accounts' in reply.followup(3, r)


# ---- bubble 1: the verdict

def claim_level(share, lo, hi, base=0.045, scope="corpus"):
    r = result()
    r.update(bot_post_share=share, bot_post_share_ci=[lo, hi], baseline_bot_share=base, scope=scope)
    return r


def test_verdict_above_overlapping_below_the_baseline_interval():
    assert reply.verdict(claim_level(0.12, 0.08, 0.16)) == "More automated than usual."
    assert reply.verdict(claim_level(0.05, 0.02, 0.09)) == "Mostly real people."
    assert reply.verdict(claim_level(0.016, 0.002, 0.032)) == "Mostly real people, less automation than usual."
    assert reply.verdict(claim_level(0.045, 0.045, 0.06)) == "Mostly real people."  # touching the baseline is not above it


def test_answer_bubble_is_three_short_lines_with_the_numbers():
    text = reply.compose(claim_level(0.04, 0.02, 0.07))
    lines = text.split("\n")
    assert lines == [
        "Mostly real people.",
        "4% of the 200 posts making this claim come from likely automated accounts. The story overall: 4.5%.",
        reply.TRUTH_LINE,
    ]


def test_tiny_share_is_never_shown_as_zero():
    assert "under 1% of the" in reply.compose(claim_level(0.002, 0.0, 0.01))


def test_live_search_has_no_baseline_comparison():
    r = claim_level(0.1, 0.05, 0.2, base=0.1, scope="live")
    text = reply.compose(r)
    assert "story overall" not in text and "than usual" not in text and reply.verdict(r) == "Mostly real people."
    assert reply.card_facts(r)["baseline"] is None


def test_results_without_a_claim_level_share_fall_back_to_the_narratives():
    r = result()  # no bot_post_share: 0.6 * 12% + 0.4 * 2% = 8%
    assert abs(reply.claim_level(r)[0] - 0.08) < 1e-9
    assert reply.compose(r).startswith("More automated than usual.")


def test_short_declines_failures_and_insufficient_data_keep_the_truth_rule():
    assert len(reply.DECLINE) < 110 and len(reply.FAILURE) < 90
    assert reply.TRUTH_LINE.startswith("Not a truth check")
    assert reply.compose(result(n=5)).endswith(reply.TRUTH_LINE)


# ---- bubble 3 and the intro

def test_menu_lists_the_four_follow_ups_and_the_link():
    m = reply.menu("https://demoyk.com/claim/abc")
    assert m.splitlines()[0] == "Reply with a number:"
    assert [l[:2] for l in m.splitlines()[1:5]] == ["1 ", "2 ", "3 ", "4 "]
    assert "Or text any other claim." in m and m.endswith("Full view: https://demoyk.com/claim/abc")
    assert "Full view" not in reply.menu(None)
    assert "Jensen Huang" in reply.menu(None, examples=True)


def test_intent_routing():
    for t, k in {"1": 1, "2": 2, "3.": 3, "4": 4, "narratives": 1, "Bots": 2, "show the bots": 2, "who shares it?": 3, "Who spreads it": 3, "news": 4, "NEWS!": 4,
                 "help": "help", "Menu": "help", "?": "help", "hi": "help", "Hello!": "help"}.items():
        assert reply.intent(t) == k, t
    for t in ["Was Jensen Huang's mistress a Chinese spy?", "next", "5", "news about nvidia stock tanking", "12", "did bots defend jensen huang"]:
        assert reply.intent(t) is None, t


def full_result():
    r = result()
    r.update(bot_post_share=0.04, bot_post_share_ci=[0.02, 0.07], matched_posts=443,
             bot_commonalities=[{"signal": "recent pace of about 536 posts a day", "accounts": 2}, {"signal": "created in the same month (2026-10)", "accounts": 7}],
             amplifiers={"n_humans": 300, "archetype_mix": [{"id": "a2", "label": "Heavy reposters", "share": 0.6, "lift": 1.4}]},
             news={"n_headlines": 23, "outlets": {"France24": 7, "AP": 5, "BBC": 3, "NPR": 1},
                   "hedging": {"news_share": 0.3478, "social_share": 0.1332, "n_news": 23, "n_social": 443},
                   "narratives_only_on_social": [{"id": "n7", "label": "Jokes and memes", "social_share": 0.54}]})
    return r


def test_followups_are_short_whole_percent_and_end_with_the_other_numbers():
    r = full_result()
    for k in (1, 2, 3, 4):
        text = reply.followup(k, r)
        lines = text.splitlines()
        assert 2 <= len(lines) <= 4, text
        assert lines[-1].startswith("Also:") and str(k) + " " not in lines[-1].split("Also:")[1]
        assert not re.search(r"\d\.\d+%|0\.\d{3}", lines[0]), text  # no raw decimals
        assert " bots" not in text.lower() and "run by" not in text
    assert "Spy plot and national security: 60% of posts, 12% likely automated." in reply.followup(1, r)
    assert "Recent pace of about 536 posts a day (2 accounts)" in reply.followup(2, r)
    assert "35% of the headlines hedge" in reply.followup(4, r) and "vs 13% of matching Bluesky posts" in reply.followup(4, r)


def test_followups_without_data_say_so():
    r = full_result()
    r["bot_commonalities"] = []
    assert "Not enough likely automated accounts" in reply.followup(2, r)
    r["news"] = {"error": "news baseline unavailable"}
    assert "No matching headlines" in reply.followup(4, r)
    r["amplifiers"] = {"n_humans": 0, "archetype_mix": []}
    assert "no real accounts" in reply.followup(3, r)
    assert "Text me a claim first" in reply.followup(1, result(n=5))


# ---- bubble 2: the card

def png_size(png: bytes) -> tuple[int, int]:
    import struct

    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", png[16:24])


def test_card_for_the_flagship_shape_is_a_portrait_phone_card():
    w, h = png_size(reply.chart_png(full_result()))
    assert w == 1080 and h > w
    f = reply.card_facts(full_result())
    assert f["verdict"] == "Mostly real people." and f["baseline"] == 0.05
    assert f["news"] and "35% of 23 matching headlines hedge" in f["news"] and "13% of matching Bluesky posts" in f["news"]
    assert f["common"].startswith("recent pace")


def test_card_without_news_or_commonalities():
    r = full_result()
    r.pop("news")
    r["bot_commonalities"] = []
    f = reply.card_facts(r)
    assert f["news"] is None and f["common"] is None
    assert png_size(reply.chart_png(r))[0] == 1080
    r["news"] = {"error": "x"}
    assert reply.card_facts(r)["news"] is None
    r["news"] = {"n_headlines": 3, "hedging": {"news_share": 0.0, "social_share": 0.0, "n_news": 3, "n_social": 12}}  # too few to compare
    assert reply.card_facts(r)["news"] is None
    assert "Too few headlines" in reply.followup(4, r) and "3 matching headlines" in reply.followup(4, r)


def test_card_for_a_tiny_claim():
    r = result(n=12, narratives=[])
    f = reply.card_facts(r)
    assert f["enough"] is False and f["verdict"] == "Too few posts to measure." and f["narratives"] == []
    assert png_size(reply.chart_png(r))[0] == 1080


def test_card_survives_long_labels_and_a_declined_result():
    r = full_result()
    r["claim"] = "Is it true that " + "a very long claim " * 12
    r["narratives"][0]["label"] = "An extremely long narrative label that has to wrap onto a second line and then get cut off somewhere"
    assert png_size(reply.chart_png(r))[0] == 1080
    d = result(n=0, narratives=[])
    d["declined"] = True
    assert png_size(reply.chart_png(d))[0] == 1080

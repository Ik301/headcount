"""News baseline on synthetic headlines: no torch, no network, the LLM is mocked."""
import json
import re

import httpx
import numpy as np
import polars as pl
import pytest

from src.news import baseline as nb

NARR = {
    "n1": "Spy plot and national security",
    "n2": "The affairs as personal misconduct",
    "n4": "Board, resignation and succession",
    "n7": "Jokes and memes",
    "n0": "No narrative",
}


def fake_embed(texts, query=False):
    """Bag of words hashed into 64 dims, L2-normalized: shared words -> higher cosine."""
    out = np.zeros((len(texts), 64))
    for i, t in enumerate(texts):
        for w in re.findall(r"[a-z]+", t.lower()):
            out[i, sum(map(ord, w)) % 64] += 1.0
    n = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.where(n == 0, 1, n)


ROWS = [
    {"source": "Reuters", "funding": "wire service, commercial", "via": "google_news_rss", "title": "Nvidia CEO Huang probed over alleged Chinese spy - Reuters", "link": "l1", "published": "Wed, 11 Nov 2026 10:00:00 GMT", "summary": "Nvidia CEO Huang probed over alleged Chinese spy &nbsp;&nbsp; Reuters"},
    {"source": "Reuters", "funding": "wire service, commercial", "via": "google_news_rss", "title": "Nvidia CEO Huang probed over alleged Chinese spy - Reuters", "link": "l1-copy", "published": "Wed, 11 Nov 2026 12:00:00 GMT", "summary": ""},
    {"source": "AP", "funding": "wire service, nonprofit cooperative", "via": "google_news_rss", "title": "Huang resigns as Nvidia board names interim CEO - AP News", "link": "l2", "published": "Thu, 12 Nov 2026 14:00:00 GMT", "summary": ""},
    {"source": "AP", "funding": "wire service, nonprofit cooperative", "via": "google_news_rss", "title": "Huang resigns as Nvidia board names interim CEO - AP News", "link": "l2", "published": "Thu, 12 Nov 2026 14:00:00 GMT", "summary": ""},
    {"source": "BBC", "funding": "public broadcaster, UK licence fee", "via": "rss", "title": "Political fallout from AI chip spying scandal", "link": "l3", "published": "Fri, 13 Nov 2026 09:00:00 GMT", "summary": "Questions reach the White House"},
    {"source": "DW", "funding": "public broadcaster, German state-funded", "via": "google_news_rss", "title": "Russia-Ukraine talks end with prisoner exchange - DW.com", "link": "l4", "published": "Wed, 11 Nov 2026 13:00:00 GMT", "summary": ""},
    {"source": "PBS NewsHour", "funding": "public broadcaster, US nonprofit", "via": "google_news_rss", "title": "Pandas Fu Shuang and Ping Ping debut in Atlanta - PBS", "link": "l5", "published": "Wed, 11 Nov 2026 13:00:00 GMT", "summary": ""},
]


@pytest.fixture
def raw(tmp_path):
    p = tmp_path / "news.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in ROWS) + "\nnot json\n")
    return p


def test_clean_title_strips_publisher_suffix_only():
    assert nb.clean_title("Huang resigns - AP News") == "Huang resigns"
    assert nb.clean_title("Huang resigns - DW.com") == "Huang resigns"
    assert nb.clean_title("Spy scandal - what we know") == "Spy scandal - what we know"


def test_load_headlines_dedupes_and_filters_by_terms(raw):
    df = nb.load_headlines(raw, embed=None)
    titles = df["title"].to_list()
    assert len(titles) == len(set(titles)) == 2  # duplicate link and duplicate (outlet, title) dropped
    assert all("Huang" in t for t in titles)  # "Fu Shuang" is not a whole-word match for "huang"
    assert df.filter(pl.col("source") == "Reuters")["link"].item() == "l1"  # earliest copy wins
    assert df["published"].to_list()[0] == "2026-11-11T10:00:00Z"
    assert df["summary"].to_list()[0] == ""  # Google News summary that repeats the title is dropped


def test_load_headlines_embedding_lets_related_rows_without_terms_through(raw):
    df = nb.load_headlines(raw, story="AI chip spying scandal political fallout", embed=fake_embed, floor=0.6)
    titles = df["title"].to_list()
    assert "Political fallout from AI chip spying scandal" in titles
    assert not any("Ukraine" in t for t in titles)
    assert df["relevance"].null_count() == 0


def test_load_headlines_window(raw):
    df = nb.load_headlines(raw, after="2026-11-12", before="2026-11-13")
    assert df["title"].to_list() == ["Huang resigns as Nvidia board names interim CEO"]


def _mock_llm(calls):
    def llm(batch, narratives, story):
        calls.append(len(batch))
        out = []
        for i, t in batch:
            if "spy" in t.lower():
                out.append({"i": i, "r": True, "n": "n1", "also": ["n2", "bogus"], "a": ""})
            elif "resign" in t.lower():
                out.append({"i": i, "r": True, "n": "n4", "also": [], "a": "Nvidia board"})
            else:
                out.append({"i": i, "r": False, "n": "n0", "also": [], "a": ""})
        out.append({"i": 999, "r": True, "n": "n1"})  # index outside the batch: ignored
        out.append({"i": 0, "r": True, "n": "n9"})  # unknown narrative: ignored
        return out

    return llm


def test_classify_headlines_caches_and_respects_taxonomy(raw, tmp_path):
    df = nb.load_headlines(raw, story="AI chip spying scandal political fallout", embed=fake_embed, floor=0.6)
    cache = tmp_path / "labels.parquet"
    calls = []
    out = nb.classify_headlines(df, llm=_mock_llm(calls), cache_path=cache, narratives=NARR, batch_size=2, workers=1)
    assert cache.exists() and sum(calls) == df.height
    spy = out.filter(pl.col("title").str.contains("alleged"))
    assert spy["narrative_id"].item() == "n1" and spy["also"].item().to_list() == ["n2"]
    assert out.filter(pl.col("title").str.contains("resigns"))["attributed_to"].item() == "Nvidia board"

    calls.clear()
    again = nb.classify_headlines(df, llm=_mock_llm(calls), cache_path=cache, narratives=NARR)
    assert calls == [] and again["narrative_id"].to_list() == out["narrative_id"].to_list()

    offline = nb.classify_headlines(df, llm=_mock_llm(calls), cache_path=cache, narratives=NARR | {"n3": "Trump"}, offline=True)
    assert calls == [] and offline["narrative_id"].null_count() == df.height  # new taxonomy: old labels don't apply

    nb.classify_headlines(df, llm=_mock_llm(calls), cache_path=cache, narratives=NARR | {"n3": "Trump"})
    assert sum(calls) == df.height


def test_story_headlines_drops_llm_off_topic():
    df = pl.DataFrame({"title": ["a", "b", "c"], "term_hit": [True, True, False], "relevant": [True, False, None]})
    assert nb.story_headlines(df)["title"].to_list() == ["a"]


def test_hedging_terms_and_boundaries():
    assert nb.is_hedged("Huang probed over ALLEGED spy")
    assert nb.is_hedged("woman linked\nto Beijing")
    assert nb.is_hedged("according to sources")
    assert not nb.is_hedged("the claimant disclaimed nothing")  # no partial-word matches
    assert not nb.is_hedged("Huang resigns")
    assert nb.hedging(["alleged spy", "spy", "reportedly a spy", "spy"]) == 0.5
    assert nb.hedging([]) == 0.0
    assert nb.hedge_terms("alleged spy, claims say") == ["alleged", "claims"]
    for t in ("alleged", "allegedly", "suspected", "reportedly", "accused", "claims", "purported", "according to", "tied to", "linked to"):
        assert t in nb.HEDGE_TERMS


def labeled_headlines():
    rows = [
        ("Reuters", "wire service, commercial", "Nvidia CEO Huang probed over alleged Chinese spy mistress", "n1", ["n2"], ""),
        ("AP", "wire service, nonprofit cooperative", "Chinese spy mistress case: what we know", "n1", [], ""),
        ("BBC", "public broadcaster, UK licence fee", "China dismisses spy mistress claims as a smear campaign", "n6", ["n1"], "China"),
        ("AP", "wire service, nonprofit cooperative", "Huang resigns as board names interim CEO", "n4", [], ""),
        ("NPR", "public radio, US nonprofit", "Nvidia shares fall after resignation", "n5", [], ""),
    ]
    return pl.DataFrame(
        {
            "hid": [f"h{i}" for i in range(len(rows))],
            "source": [r[0] for r in rows],
            "funding": [r[1] for r in rows],
            "title": [r[2] for r in rows],
            "link": [f"https://x/{i}" for i in range(len(rows))],
            "published": [f"2026-11-1{i}T00:00:00Z" for i in range(len(rows))],
            "summary": [""] * len(rows),
            "via": ["google_news_rss"] * len(rows),
            "term_hit": [True] * len(rows),
            "relevance": [None] * len(rows),
            "relevant": [True] * len(rows),
            "narrative_id": [r[3] for r in rows],
            "also": [r[4] for r in rows],
            "attributed_to": [r[5] for r in rows],
        },
        schema_overrides={"relevance": pl.Float64},
    )


def social():
    return pl.DataFrame(
        {
            "post_id": [f"p{i}" for i in range(10)],
            "text": ["his mistress was an alleged chinese spy"] * 2 + ["mistress chinese spy lol"] * 3 + ["leather jacket spy meme"] * 4 + ["spy"],
            "narrative_id": ["n1"] * 5 + ["n7"] * 4 + ["n0"],
            "urls": [["https://x"]] * 2 + [[]] * 8,
        }
    )


def test_news_for_claim_contract():
    nb._HEMB.clear()
    r = nb.news_for_claim("Was Huang's mistress a Chinese spy?", social(), headlines=labeled_headlines(), embed=fake_embed, floor=0.3, k=2)
    assert set(r) >= {"headlines", "outlets", "narratives_in_news", "narratives_only_on_social", "hedging", "note"}
    assert len(r["headlines"]) == 2 and r["n_headlines"] == 3
    h = r["headlines"][0]
    assert set(h) >= {"source", "funding", "title", "link", "published", "similarity"} and h["funding"]
    assert r["headlines"][0]["similarity"] >= r["headlines"][1]["similarity"]
    assert sum(r["outlets"].values()) == 3 and r["outlet_funding"]["BBC"] == "public broadcaster, UK licence fee"
    in_news = {x["id"]: x for x in r["narratives_in_news"]}
    assert in_news["n1"]["news_headlines"] == 3  # primary or secondary label
    assert in_news["n1"]["social_share"] == 0.5
    only = [x["id"] for x in r["narratives_only_on_social"]]
    assert only == ["n7"]  # jokes: 40% of posts, no headline; n0 never listed
    hd = r["hedging"]
    assert (hd["n_news"], hd["n_social"]) == (3, 10)
    assert hd["news_share"] == round(2 / 3, 4) and hd["social_share"] == 0.2
    assert "what these newsrooms report" in r["note"].lower() and "funding" in r["note"]
    assert "the truth" not in json.dumps(r).lower()


def test_news_for_claim_without_labels_or_matches():
    nb._HEMB.clear()
    plain = labeled_headlines().drop("narrative_id", "also", "attributed_to", "relevant")
    r = nb.news_for_claim("Chinese spy mistress", social(), headlines=plain, embed=fake_embed, floor=0.3)
    assert r["n_headlines"] > 0 and r["narratives_in_news"] == [] and "narratives_note" in r
    r = nb.news_for_claim("zebra quantum", social().head(0), headlines=labeled_headlines(), embed=fake_embed, floor=0.99)
    assert r["headlines"] == [] and r["hedging"]["news_share"] is None and r["hedging"]["n_social"] == 0


def test_story_baseline_shape():
    b = nb.story_baseline(headlines=labeled_headlines(), posts=social())
    by = {x["id"]: x for x in b["narratives"]}
    assert by["n1"]["news_headlines"] == 2 and by["n1"]["news_mentions"] == 3
    assert by["n7"]["only_on_social"] and not by["n1"]["only_on_social"] and not by["n0"]["only_on_social"]
    assert b["narratives_only_on_social"] == ["n7"]
    hd = b["hedging"]
    assert hd["news"] == {"share": round(2 / 3, 4), "hedged": 2, "n": 3}
    assert hd["social"]["n"] == 10 and hd["social"]["hedged"] == 2
    assert hd["social_with_link"]["share"] == 1.0 and hd["social_without_link"]["hedged"] == 0
    sm = b["attributed_claims"]["headlines"]
    assert len(sm) == 1 and sm[0]["attributed_to"] == "China" and sm[0]["framing"] == "smear"
    assert b["defending_in_news"]["n"] == 1 and b["defending_in_news"]["attributed"] == 1
    assert {o["source"] for o in b["outlets"]} == {"Reuters", "AP", "BBC", "NPR"} and all(o["funding"] for o in b["outlets"])


GN = """<?xml version="1.0"?><rss><channel>
<item><title>{t} - Reuters</title><link>https://news.google.com/a/{n}</link><pubDate>{d}</pubDate><description>{t}</description></item>
<item><title>Unrelated top story - Reuters</title><link>https://news.google.com/b/{n}</link><pubDate>{d}</pubDate><description>x</description></item>
</channel></rss>"""


def test_fetch_live_headlines_mocked():
    pytest.importorskip("defusedxml")
    from email.utils import format_datetime
    from datetime import datetime, timezone

    now = format_datetime(datetime.now(timezone.utc))
    seen = []

    def handler(req: httpx.Request):
        seen.append(str(req.url))
        if "news.google.com" in req.url.host:
            n = len(seen)
            return httpx.Response(200, text=GN.format(t="Starship booster catch succeeds", n=n, d=now))
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        df = nb.fetch_live_headlines("Starship booster catch", days=3, client=c)
    assert any("when%3A3d" in u for u in seen)
    assert df.height >= 1 and set(df["title"].to_list()) == {"Starship booster catch succeeds"}
    assert df["funding"].null_count() == 0

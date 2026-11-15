"""H8 export on tiny synthetic tables: shape, missing inputs, privacy, bots-off recompute, graph caps. No torch."""
import json
from pathlib import Path

import polars as pl
import pytest

from src.export import build_site_data as B
from src.stats import ratio_ci

PUB = "did:plc:pubhuman"  # public person, 20k followers
PUBBOT = "did:plc:pubbot"  # self-labeled bot, public
HIDDEN = "did:plc:verifiedauto"  # verified but undisclosed likely automated, 300 followers: never named
PRIV_AUTO = "did:plc:privauto"
HUMANS = [f"did:plc:human{i}" for i in range(30)]
ENGAGERS = [f"did:plc:liker{i}" for i in range(20)]  # not story authors, no score


def T(day, hour, minute=0):
    return f"2026-11-{day:02d}T{hour:02d}:{minute:02d}:00.000Z"


@pytest.fixture(autouse=True)
def salt(monkeypatch):
    monkeypatch.setenv("SALT", "test-salt")


def write_corpus(base: Path, with_scores=True, with_narratives=True, with_inter=True, with_arch=True, with_news=True, with_eval=True):
    proc, art = base / "processed", base / "processed" / "artifacts"
    (proc / "narratives").mkdir(parents=True)
    art.mkdir(parents=True)
    acc = [
        dict(account_id=PUB, handle="famous.example.com", is_public=True, followers=20000, posts_count=900, self_label_bot=False, bridged=False, created_at="2020-01-01T00:00:00Z"),
        dict(account_id=PUBBOT, handle="newsbot.example.com", is_public=True, followers=50, posts_count=90000, self_label_bot=True, bridged=False, created_at="2025-01-01T00:00:00Z"),
        dict(account_id=HIDDEN, handle="hidden-auto.bsky.social", is_public=True, followers=300, posts_count=50000, self_label_bot=False, bridged=False, created_at="2026-10-01T00:00:00Z"),
        dict(account_id=PRIV_AUTO, handle="secret-feed.bsky.social", is_public=False, followers=10, posts_count=80000, self_label_bot=False, bridged=False, created_at="2026-10-02T00:00:00Z"),
    ] + [
        dict(account_id=d, handle=f"person{i}.bsky.social", is_public=False, followers=100 + i, posts_count=500, self_label_bot=False, bridged=(i == 0), created_at="2023-05-01T00:00:00Z")
        for i, d in enumerate(HUMANS)
    ]
    pl.DataFrame(acc).write_parquet(proc / "accounts.parquet")
    posts = []

    def post(did, k, t, text, nid, likes=0):
        pid = f"at://{did}/app.bsky.feed.post/p{k}"
        posts.append(dict(post_id=pid, account_id=did, created_at=t, text=text, like_count=likes, repost_count=0, reply_count=0, quote_count=0, _n=nid))
        return pid

    bot_posts = [post(PUBBOT, i, T(12, 14, i), f"BREAKING board update {i}", "n4", 1) for i in range(6)]
    bot_posts += [post(PRIV_AUTO, i, T(12, 15, i), f"board news item {i} via @person3.bsky.social", "n4") for i in range(6)]
    bot_posts += [post(HIDDEN, i, T(11, 10, i), f"defend him {i}", "n6") for i in range(4)]
    pub_posts = [post(PUB, i, T(9, 8, i), f"my famous take {i}, cc @person1.bsky.social and @famous.example.com", "n1", 500 - i) for i in range(3)]
    for i, d in enumerate(HUMANS):
        post(d, 0, T(5 + i % 8, i % 24), f"human post {i} about the spy story", "n1" if i % 3 else "n6", 2)
        post(d, 1, T(12, 20, i), f"human joke {i}", "n7", 1)
    post(HUMANS[0], 9, "2026-11-14T08:03:21+09:00", "late post with an offset timestamp", "n7")
    nar = [dict(post_id=p["post_id"], narrative_id=p["_n"], side=None, prob=0.9) for p in posts]
    pl.DataFrame([{k: v for k, v in p.items() if k != "_n"} for p in posts]).write_parquet(proc / "posts.parquet")
    if with_narratives:
        pl.DataFrame(nar).write_parquet(proc / "narratives" / "post_narrative.parquet")
    if with_scores:
        sc = {PUB: 0.01, PUBBOT: 0.99, HIDDEN: 0.92, PRIV_AUTO: 0.95} | {d: 0.02 for d in HUMANS}
        pl.DataFrame({"account_id": list(sc), "p_automated": list(sc.values()), "reasons": [["posts 40 times a day"]] * len(sc)}).write_parquet(art / "bot_scores.parquet")
    if with_inter:
        rows = []
        for i, d in enumerate(ENGAGERS[:12]):  # 12 real engagers like automated posts
            rows.append(dict(src_account_id=d, dst_account_id=PRIV_AUTO, type="like", post_id=bot_posts[6 + i % 6], created_at=T(12, 16, i)))
        for i, d in enumerate(ENGAGERS):  # everyone likes the public account
            rows.append(dict(src_account_id=d, dst_account_id=PUB, type="like", post_id=pub_posts[0], created_at=T(9, 9, i)))
        rows.append(dict(src_account_id=PRIV_AUTO, dst_account_id=PUB, type="repost", post_id=pub_posts[1], created_at=None))  # automated engagement
        for i, d in enumerate(HUMANS[:10]):
            rows.append(dict(src_account_id=d, dst_account_id=PUBBOT, type="repost", post_id=bot_posts[i % 6], created_at=None))
        pl.DataFrame(rows, schema={"src_account_id": pl.Utf8, "dst_account_id": pl.Utf8, "type": pl.Utf8, "post_id": pl.Utf8, "created_at": pl.Utf8}).write_parquet(proc / "interactions.parquet")
    if with_arch:
        ua = {d: ("a1" if i < 15 else "a2") for i, d in enumerate(HUMANS)} | {d: ("a1" if i < 10 else "a2") for i, d in enumerate(ENGAGERS)}
        pl.DataFrame({"account_id": list(ua), "archetype_id": list(ua.values()), "label": ["Heavy reposters" if a == "a1" else "Everyone else" for a in ua.values()]}).write_parquet(art / "user_archetype.parquet")
    raw = base / "raw"
    raw.mkdir()
    if with_news:
        news = [
            {"source": "Reuters", "funding": "wire", "title": "Nvidia's Huang and the alleged Chinese spy - Reuters", "link": "https://x/1", "published": "Mon, 09 Nov 2026 10:00:00 GMT"},
            {"source": "BBC", "funding": "public", "title": "Huang spy scandal deepens - BBC", "link": "https://x/2", "published": "Tue, 10 Nov 2026 10:00:00 GMT"},
            {"source": "BBC", "funding": "public", "title": "Nvidia shares fall - BBC", "link": "https://x/3", "published": "Tue, 10 Nov 2026 11:00:00 GMT"},
        ]
        (raw / "news_jensen.jsonl").write_text("\n".join(json.dumps(n) for n in news))
    ev = base / "eval" / "bots"
    ev.mkdir(parents=True)
    if with_eval:
        (ev / "report.md").write_text(
            "Model: `v-test`\n\n| Scorer | @50 | @100 |\n|---|---|---|\n| lifetime posts per day (baseline) | 0.028 | 0.045 |\n| hgb, both | 0.26 | 0.333 |\n\n"
            "| Features | @50 | @100 |\n|---|---|---|\n| behavior only | 0.15 | 0.23 |\n| coordination only | 0.01 | 0.03 |\n| both | 0.15 | 0.24 |\n\n"
            "Precision on this sample: **45 of 50 (90%) automated**\n"
        )
    return dict(processed=str(proc), raw=str(raw), eval_dir=str(base / "eval"), sample=str(base / "sample"))


README_KEYS = {"story", "timeline", "narratives", "graph", "archetypes", "public_accounts", "validation", "challenge", "reddit", "findings", "news", "coordination"}


def test_missing_everything_gives_empty_sections(tmp_path):
    site = B.build(str(tmp_path / "nope"), str(tmp_path / "nope"), str(tmp_path / "nope"), str(tmp_path / "nope"))
    assert README_KEYS <= set(site)
    assert site["timeline"] == [] and site["narratives"] == [] and site["graph"]["nodes"] == []
    assert site["archetypes"] == [] and site["public_accounts"] == [] and site["validation"] is None
    assert site["news"] == {} and site["challenge"] == [] and site["findings"] == []
    assert [e["t"] for e in site["story"]["events"]][2:] == ["2026-11-11T22:43:00Z", "2026-11-12T13:55:00Z", "2026-11-12T20:15:00Z"]
    json.dumps(site)


@pytest.mark.parametrize("drop", ["with_scores", "with_narratives", "with_inter", "with_arch", "with_news", "with_eval"])
def test_any_single_missing_input_does_not_crash(tmp_path, drop):
    site = B.build(**write_corpus(tmp_path, **{drop: False}))
    assert README_KEYS <= set(site)
    json.dumps(site)
    if drop == "with_scores":
        assert all(n["bot_post_share"] is None for n in site["narratives"])
    if drop == "with_narratives":
        assert site["narratives"] == [] and site["timeline"][0]["by_narrative"] == {}


@pytest.fixture
def full(tmp_path):
    paths = write_corpus(tmp_path)
    c = B.load(**paths)
    return c, B.build_from(c)


def test_shape_timeline_and_strip(full):
    c, site = full
    tl = site["timeline"]
    assert len(tl) == 9 * 24 and tl[0]["hour"] == "2026-11-05T00:00:00Z"
    assert sum(r["posts"] for r in tl) == c.posts.height  # the +09:00 post lands on Nov 13 UTC, inside the window
    assert sum(sum(r["by_narrative"].values()) for r in tl) == c.posts.height
    assert sum(r["likely_automated"] for r in tl) == 16
    n4 = next(n for n in site["narratives"] if n["id"] == "n4")
    assert set(n4["threshold_strip"]) == {"0.3", "0.5", "0.7", "0.9"}
    assert n4["bot_post_share"] == 1.0 and len(n4["bot_post_share_ci"]) == 2
    assert n4["evidence"] and all(set(e) >= {"post_uri", "t", "note"} for e in n4["evidence"])
    n1 = next(n for n in site["narratives"] if n["id"] == "n1")
    assert n1["examples"] and all("famous take" in e for e in n1["examples"])  # public accounts only
    # bridged accounts are reported separately: human0 is bridged and posted twice in n7
    n7 = next(n for n in site["narratives"] if n["id"] == "n7")
    assert n7["bridged"] == {"posts": 2, "accounts": 1, "bot_post_share": 0.0}
    assert n7["with_bridged"]["n_posts"] == n7["posts"] and n7["with_bridged"]["n_posts"] == 31


def test_bots_off_removes_automated_posts_and_their_engagement(full):
    c, site = full
    n4 = next(n for n in site["narratives"] if n["id"] == "n4")["without_automated"]
    assert n4["posts"] == 12 and n4["posts_without"] == 0
    assert n4["engagements"] == 22 and n4["engagements_without"] == 0  # 12 likes + 10 reposts, all on automated posts
    n1 = next(n for n in site["narratives"] if n["id"] == "n1")["without_automated"]
    assert n1["engagements"] == 21 and n1["engagements_without"] == 20  # the automated account's repost is gone
    assert n4["rank_without"] > n4["rank"]


def test_privacy(full):
    c, site = full
    blob = json.dumps(site)
    for did in [PRIV_AUTO, HIDDEN, *HUMANS, *ENGAGERS]:
        assert did not in blob
    for h in ["secret-feed.bsky.social", "hidden-auto.bsky.social", "person1.bsky.social", "person3.bsky.social"]:
        assert h not in blob
    assert "famous.example.com" in blob and "newsbot.example.com" in blob
    assert B.privacy_violations(site, c) == []
    assert not c.nameable(HIDDEN)  # verified, but undisclosed likely automated under 5,000 followers
    bad = json.loads(blob)
    bad["graph"]["nodes"].append({"id": "x", "public_handle": "person2.bsky.social"})
    bad["narratives"][0]["evidence"].append({"post_uri": f"at://{PRIV_AUTO}/app.bsky.feed.post/p1"})
    assert len(B.privacy_violations(bad, c)) >= 2


def test_graph_caps_and_replay(tmp_path):
    c = B.load(**write_corpus(tmp_path))
    g = B.graph(c, node_cap=8, edge_cap=6)
    assert len(g["nodes"]) <= 8 and len(g["edges"]) <= 6
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["s"] in ids and e["t"] in ids for e in g["edges"])
    assert any(n["likely_automated"] for n in g["nodes"])
    assert all(set(n) >= {"id", "narrative", "archetype", "p_automated", "public_handle", "size", "first_seen"} for n in g["nodes"])
    r = g["replay"]
    assert len(r) == 216 and all(a["nodes"] <= b["nodes"] and a["edges"] <= b["edges"] for a, b in zip(r, r[1:]))
    assert any(e["time_approx"] for e in B.graph(c)["edges"] if e["type"] == "repost")


def test_archetype_lift_uses_shared_bootstrap(full):
    c, site = full
    a1 = next(a for a in site["archetypes"] if a["id"] == "a1")
    # interacting real accounts: 20 engagers + 10 humans (reposted the self-labeled bot at 0.99 >= 0.7: amplifiers)
    # a1: engagers 0-9 (all amplify: liked PRIV_AUTO) + humans 0-9 (amplify) -> 20 of 20; a2: engagers 10-19 (10, 11 amplify) -> 2 of 10
    base = 22 / 30
    lift, lo, hi = ratio_ci([True] * 20, base)
    assert a1["interacting_humans"] == 20 and a1["amplifiers"] == 20
    assert a1["lift"] == round(lift, 3) and a1["lift_ci"] == [round(lo, 3), round(hi, 3)]
    assert site["archetypes_meta"]["base_amplifier_rate"] == round(base, 4)


def test_news_validation_and_findings(full):
    c, site = full
    sc = site["news"]["spy_claim"]
    assert sc["news_headlines"] == 2 and sc["news_hedged_share"] == 0.5
    assert sc["bluesky_posts"] == 30 and sc["bluesky_hedged_share"] == 0.0
    assert {o["source"]: o["headlines"] for o in site["news"]["outlets"]} == {"BBC": 2, "Reuters": 1}
    v = site["validation"]
    assert v["recall_at_k"] == {"50": 0.26, "100": 0.333} and v["baseline_recall_at_k"]["100"] == 0.045
    assert v["ablation"]["coordination only"]["100"] == 0.03 and v["handcheck_precision"]["share"] == 0.9
    f = site["findings"]
    assert 3 <= len(f) <= 5 and all(isinstance(s, str) and s.endswith(".") for s in f)
    assert f"{c.posts.height:,} posts" in f[0]


def test_sample_is_small_and_consistent(full):
    c, site = full
    s = B.sample_of(site, nodes=5, edges=3, public=1)
    ids = {n["id"] for n in s["graph"]["nodes"]}
    assert len(ids) <= 5 and len(s["graph"]["edges"]) <= 3 and all(e["s"] in ids and e["t"] in ids for e in s["graph"]["edges"])
    assert len(s["public_accounts"]) <= 1
    assert B.privacy_violations(s, c) == []


def _story_baseline(proc: Path, news=(49, 90), social=(3152, 7239), link=(2509, 5038), own=(643, 2201)):
    blk = lambda h, n: {"share": round(h / n, 4), "hedged": h, "n": n}  # noqa: E731
    (proc / "news").mkdir(exist_ok=True)
    (proc / "news" / "story_baseline.json").write_text(json.dumps({"hedging": {
        "news": blk(*news), "social": blk(*social), "social_with_link": blk(*link), "social_without_link": blk(*own)}}))


def test_news_hedging_split_comes_from_the_news_module(tmp_path):
    paths = write_corpus(tmp_path)
    _story_baseline(Path(paths["processed"]))
    site = B.build(**paths)
    sc = site["news"]["spy_claim"]
    assert sc["news_hedged_share"] == 0.5444 and sc["news_headlines"] == 90  # story_baseline.json wins over the raw feed
    assert (sc["bluesky_link_hedged_share"], sc["bluesky_link_posts"]) == (0.498, 5038)
    assert (sc["bluesky_own_words_hedged_share"], sc["bluesky_own_words_posts"]) == (0.2921, 2201)
    assert sc["bluesky_hedged_share"] == 0.4354 and sc["bluesky_posts"] == 7239
    assert "news_hedged_share_ci" not in sc  # an interval over different headlines would not belong to these numbers
    f = next(x for x in site["findings"] if "headlines" in x and "hedge" in x)
    assert f.startswith("54% of wire-service")
    assert "(50% hedge)" in f and "29% hedge" in f and "caution survives the share button and disappears in the retelling" in f
    assert site["news"]["hedge_terms"] == list(B.HEDGE_TERMS)


def test_news_retelling_line_only_when_the_data_says_so(tmp_path):
    paths = write_corpus(tmp_path)
    _story_baseline(Path(paths["processed"]), link=(1000, 5000), own=(1500, 2000))  # own words hedge more: no retelling claim
    f = next(x for x in B.build(**paths)["findings"] if "headlines" in x and "hedge" in x)
    assert "retelling" not in f and "20% of posts that share a link hedge" in f and "75%" in f


def test_news_split_computed_with_intervals_without_story_baseline(tmp_path):
    paths = write_corpus(tmp_path)
    posts = pl.read_parquet(Path(paths["processed"]) / "posts.parquet")
    posts = posts.with_columns(pl.when(pl.col("text").str.contains("spy")).then(pl.lit(["https://x"])).otherwise(pl.lit([], dtype=pl.List(pl.Utf8))).alias("urls"))
    posts.write_parquet(Path(paths["processed"]) / "posts.parquet")
    sc = B.build(**paths)["news"]["spy_claim"]
    assert sc["bluesky_link_posts"] == 30 and sc["bluesky_link_hedged_share"] == 0.0 and len(sc["bluesky_link_hedged_share_ci"]) == 2
    assert "bluesky_own_words_posts" not in sc  # no spy post without a link here: no own-words row


def test_mentions_masked_unless_public_bluesky(full):
    c, _ = full
    out = c.mask("cc @famous.example.com @person1.bsky.social @elonmusk and @Some_X_User, mail me at a@b.com.")
    assert "@famous.example.com" in out and "@person1" not in out and "elonmusk" not in out and "Some_X_User" not in out
    assert out.count(B.MASKED_MENTION) == 3 and "a@b.com." in out


def test_matched_archetypes_use_m5_counts(tmp_path):
    paths = write_corpus(tmp_path)
    proc = Path(paths["processed"])
    pl.DataFrame({"archetype_id": ["a1", "a2"], "label": ["Heavy reposters", "Everyone else"], "size": [20, 30], "n_amplifiers": [11, 14],
                  "lift": [1.1, 0.93], "lift_lo": [0.8, 0.7], "lift_hi": [1.4, 1.2], "description": ["82% reposts; 6% replies", "1 post a day"],
                  "defining_features": [["repost_share"], ["age_days_log"]], "examples_public": [["famous.example.com", "person2.bsky.social"], []]}).write_parquet(proc / "archetypes.parquet")
    th = Path(paths["eval_dir"]) / "thesis"
    th.mkdir(parents=True)
    (th / "report-vm.md").write_text("- Amplifier: a likely human. **26 amplifiers.**\n| - | unmatched, left out of lift | 1 |\nBase amplifier rate in the matched sample: 0.50, so\n")
    site = B.build(**paths)
    am = site["archetypes_meta"]
    assert am["matched"] and am["amplifiers"] == 26 and am["amplifiers_matched"] == 25 and am["amplifiers_unmatched"] == 1 and am["base_amplifier_rate"] == 0.5
    a1 = next(a for a in site["archetypes"] if a["id"] == "a1")
    assert a1["lift"] == 1.1 and a1["lift_ci"] == [0.8, 1.4] and a1["amplifiers"] == 11 and a1["size"] == 20
    assert a1["examples_public"] == ["famous.example.com"]  # a private handle in M5's table never ships
    assert "null" not in json.dumps([a.get("features", {}) for a in site["archetypes"]]) and "defining_features" not in a1
    assert any("no archetype was clearly more likely" in f for f in site["findings"])


def test_validation_prefers_vm_reports(tmp_path):
    paths = write_corpus(tmp_path)
    ev = Path(paths["eval_dir"])
    (ev / "bots" / "report-vm.md").write_text("Model: `v-vm`\n\n| Scorer | @50 | @100 |\n|---|---|---|\n| lifetime posts per day (baseline) | 0.028 | 0.045 |\n| hgb, behavior | 0.213 | 0.272 |\n")
    (ev / "narratives").mkdir()
    (ev / "narratives" / "report.md").write_text("- narrative_id: held-out accuracy vs LLM labels 0.702 (n=8040)\n- side: held-out accuracy vs LLM labels 0.771 (n=8040)\n")
    (ev / "retrieval").mkdir()
    (ev / "retrieval" / "report-hybrid.md").write_text("recall@20 of at least 0.6 on the first 20 claims: **0.787 at floor 0.60** (0.785 with no floor) -> **pass**. All 50 claims: 0.646.\n")
    v = B.build(**paths)["validation"]
    assert v["recall_at_k"]["100"] == 0.272 and v["baseline_recall_at_k"]["100"] == 0.045 and v["report_model"] == "v-vm"
    assert v["narrative_llm_agreement"] == 0.702 and v["gold_accuracy"] is None and v["hand_label_agreement"] is None
    assert v["retrieval_recall_at_k"] == {"20": 0.787} and v["retrieval"]["recall_at_20_all"] == 0.646


def test_challenge_handle_unknown_on_this_machine_is_not_named(tmp_path):
    """A frozen challenge pick built from another machine's pull can't be checked against this machine's profiles."""
    paths = write_corpus(tmp_path)
    sample = Path(paths["sample"])
    sample.mkdir(parents=True, exist_ok=True)
    picks = [
        {"account_ref": "famous.example.com", "public_handle": "famous.example.com", "tier": "human", "posts": ["hi"], "p_automated": 0.01},
        {"account_ref": "elsewhere.example.net", "public_handle": "elsewhere.example.net", "tier": "middle", "posts": ["hello"], "p_automated": 0.3},
        {"account_ref": "secret-feed.bsky.social", "public_handle": "secret-feed.bsky.social", "tier": "automated", "posts": ["x"], "p_automated": 0.95},
    ]
    (sample / "challenge.json").write_text(json.dumps({"model_version": "v-test", "accounts": picks}))
    c = B.load(**paths)
    site = B.build_from(c)
    ch = site["challenge"]
    assert [a["public_handle"] for a in ch] == ["famous.example.com", None, None]
    blob = json.dumps(site)
    assert "elsewhere.example.net" not in blob and "secret-feed.bsky.social" not in blob
    assert len(ch[1]["account_ref"]) == 16 and ch[1]["posts"] == ["hello"]
    assert B.privacy_violations(site, c) == []


def test_archetype_finding_names_a_less_likely_group(tmp_path):
    paths = write_corpus(tmp_path)
    proc = Path(paths["processed"])
    pl.DataFrame({"archetype_id": ["a1", "a2"], "label": ["Heavy reposters", "Quote posters"], "size": [20, 30], "n_amplifiers": [11, 4],
                  "lift": [1.1, 0.46], "lift_lo": [0.8, 0.26], "lift_hi": [1.4, 0.66], "description": ["x", "y"],
                  "defining_features": [["repost_share"], ["quote_share"]], "examples_public": [[], []]}).write_parquet(proc / "archetypes.parquet")
    th = Path(paths["eval_dir"]) / "thesis"
    th.mkdir(parents=True)
    (th / "report-vm.md").write_text("- Amplifier: a likely human. **26 amplifiers.**\n| - | unmatched, left out of lift | 1 |\nBase amplifier rate in the matched sample: 0.50, so\n")
    f = [x for x in B.build(**paths)["findings"] if "amplif" in x]
    assert f and "every lift interval includes 1" not in f[0] and '"Quote posters" accounts were less likely (0.46x, 0.26 to 0.66)' in f[0]

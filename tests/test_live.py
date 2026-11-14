"""Live any-story path (src/retrieval/live.py), fully offline: fake AppView, fake LLM, fake embedder, fake
scorer and archetypes. No network, no torch."""
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.api import reply
from src.retrieval import live
from src.retrieval.corpus import QUERY_PREFIX

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
PUBLIC_HANDLE = "bignews.example"


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def make_world(n_a=40, n_b=35, n_noise=20, odd_post=None):
    """Topic A (repeal vote) and B (lawsuit) are on-claim; noise (weather) is off-topic."""
    humans = [f"did:plc:h{i}" for i in range(30)]
    bots = [f"did:plc:bot{i}" for i in range(10)]
    authors = humans + bots
    posts = []
    k = 0
    for topic, n in (("A", n_a), ("B", n_b), ("N", n_noise)):
        for i in range(n):
            did = authors[k % len(authors)]
            k += 1
            text = {"A": f"the congestion toll repeal vote is happening, take {i}", "B": f"court lawsuit over the congestion toll, filing {i}", "N": f"sunny weather today in the park {i}"}[topic]
            posts.append(
                {
                    "uri": f"at://{did}/app.bsky.feed.post/{topic}{i}",
                    "author": {"did": did, "handle": f"{did.split(':')[-1]}.example"},
                    "record": {"text": text, "createdAt": iso(NOW - timedelta(minutes=37 * k))},
                    "likeCount": 3 if "bot" in did else 0,
                    "repostCount": 1 if "bot" in did else 0,
                }
            )
    if odd_post:
        posts.append(odd_post)
    profiles = {}
    for i, d in enumerate(authors):
        profiles[d] = {
            "did": d,
            "handle": PUBLIC_HANDLE if d == "did:plc:h0" else f"{d.split(':')[-1]}.example",
            "followersCount": 6000 if d == "did:plc:h0" else 50,
            "followsCount": 100,
            "postsCount": 500,
            "createdAt": "2026-10-03T00:00:00Z" if "bot" in d else f"2023-0{1 + i % 9}-01T00:00:00Z",
        }
    profiles.pop("did:plc:h29")  # a deleted account: falls back to the post's author record
    fans = [f"did:plc:fan{i}" for i in range(15)]
    for f in fans:
        profiles[f] = {"did": f, "handle": f"{f.split(':')[-1]}.example", "followersCount": 20, "createdAt": "2022-01-01T00:00:00Z"}
    return posts, profiles, fans


class FakeAppView:
    def __init__(self, posts, profiles, fans, fail=False):
        self.posts = sorted(posts, key=lambda p: live.post_time(p), reverse=True)
        self.profiles, self.fans, self.fail = profiles, fans, fail
        self.calls: list[tuple[str, object]] = []

    def __call__(self, endpoint, params):
        self.calls.append((endpoint, params))
        if self.fail:
            return None
        if endpoint == "app.bsky.feed.searchPosts":
            got = [p for p in self.posts if params["since"] <= live.post_time(p) < params["until"]]
            return {"posts": got[: params["limit"]]}
        if endpoint == "app.bsky.actor.getProfiles":
            return {"profiles": [self.profiles[d] for _, d in params if d in self.profiles]}
        if endpoint == "app.bsky.feed.getAuthorFeed":
            did = params["actor"]
            return {"feed": [{"post": {"uri": f"at://{did}/app.bsky.feed.post/h{j}", "author": {"did": did}, "record": {"text": f"history {j}", "createdAt": iso(NOW - timedelta(hours=j))}}} for j in range(5)]}
        if endpoint == "app.bsky.feed.getRepostedBy":
            return {"repostedBy": [{"did": f} for f in self.fans[:8]] + [{"did": "did:plc:bot3"}]}
        if endpoint == "app.bsky.feed.getLikes":
            return {"likes": [{"actor": {"did": f}} for f in self.fans[5:]]}
        raise AssertionError(endpoint)

    def n(self, endpoint):
        return sum(1 for e, _ in self.calls if e == endpoint)


def fake_llm(system, user):
    if '"topic"' in system:
        return json.dumps({"topic": "congestion toll", "queries": ["toll repeal", "congestion lawsuit"], "private_individual": False})
    groups = re.findall(r"Group (n\d+):\n- ([^\n]*)", user)
    return "```json\n" + json.dumps({"narratives": [{"id": g, "label": "Repeal vote chatter about the toll today" if "repeal" in ex else "Court fight", "side": "neutral_news"} for g, ex in groups]}) + "\n```"


def fake_embedder(texts):
    out = []
    for t in texts:
        h = int(hashlib.md5(t.encode()).hexdigest()[:8], 16)
        noise = np.array([(h % 97) / 97, (h // 97 % 89) / 89]) * 0.05
        if t.startswith(QUERY_PREFIX):
            v = [1.0, 1.0, 0.0]
        elif "repeal" in t:
            v = [1.0, 0.0, 0.0]
        elif "lawsuit" in t:
            v = [0.0, 1.0, 0.0]
        else:
            v = [0.0, 0.0, 1.0]
        out.append(np.concatenate([v, noise]))
    return np.array(out)


def fake_scorer(profiles, histories, story_posts):
    return [{"did": p["did"], "p_automated": 0.9 if "bot" in p["did"] else 0.05, "reasons": ["posts at unusually regular intervals"] if "bot" in p["did"] else []} for p in profiles]


def fake_assigner(profiles, histories):
    def arch(did):
        if "fan" in did or (did.startswith("did:plc:h") and int(did[9:]) % 2 == 0):
            return ("a1", "Heavy reposters")
        return ("a2", "Everyone else")

    return [{"did": p["did"], "archetype_id": arch(p["did"])[0], "label": arch(p["did"])[1]} for p in profiles]


def run(app, llm=fake_llm, **kw):
    kw.setdefault("save_dir", None)
    kw.setdefault("use_cache", False)
    return live.analyze_live("Is the NYC congestion toll being repealed?", fake_scorer, http_get=app, llm=llm, embedder=fake_embedder, assigner=fake_assigner, now=NOW, **kw)


@pytest.fixture
def world():
    return make_world()


def test_full_result_matches_claim_contract(world):
    app = FakeAppView(*world)
    r = run(app)
    for key in ("claim_id", "claim", "scope", "matched_posts", "window", "narratives", "bot_commonalities", "amplifiers", "chart_png_url", "dashboard_url", "reply_text", "seconds", "steps"):
        assert key in r, key
    assert r["scope"] == "live"
    assert [s["name"] for s in r["steps"]] == list(live.STEP_NAMES)
    assert all(s["seconds"] >= 0 for s in r["steps"])
    assert r["matched_posts"] == 75  # the 20 off-topic posts fall under the similarity floor
    assert r["queries"] == ["congestion toll", "toll repeal", "congestion lawsuit"]
    assert len(r["narratives"]) == 2 and r["live"]["k"] == 2
    assert abs(sum(n["share_of_matches"] for n in r["narratives"]) - 1) < 1e-3
    labels = {n["label"] for n in r["narratives"]}
    assert labels == {"Repeal vote chatter about the toll", "Court fight"}  # label capped at 6 words
    for n in r["narratives"]:
        lo, hi = n["bot_post_share_ci"]
        assert 0 <= lo <= n["bot_post_share"] <= hi <= 1
        assert n["baseline_bot_share"] == r["baseline_bot_share"]
        assert {"text", "public_handle"} <= set(n["example_posts"][0])
        assert n["evidence"] and {"post_uri", "t", "note"} <= set(n["evidence"][0])
        nr_keys = {"id", "label", "side", "share_of_matches", "bot_post_share", "bot_post_share_ci", "baseline_bot_share", "example_posts", "evidence"}
        assert nr_keys <= set(n)
    assert 0 < r["baseline_bot_share"] < 1
    assert r["counts"]["authors"] == 40 and r["counts"]["likely_automated_authors"] == 10
    assert reply.TRUTH_LINE in r["reply_text"] and "(recent posts)" in r["reply_text"]
    assert "Likely automated:" in r["reply_text"]


def test_commonalities_and_amplifiers(world):
    r = run(FakeAppView(*world))
    signals = {c["signal"]: c["accounts"] for c in r["bot_commonalities"]}
    assert signals.get("created in the same month (2026-10)") == 10
    amp = r["amplifiers"]
    assert amp["n_humans"] == 15  # the 15 fans; the likely automated reposter is not a human amplifier
    top = amp["archetype_mix"][0]
    assert top["label"] == "Heavy reposters" and top["share"] == 1.0 and top["lift"] == 2.0
    assert '"Heavy reposters" (2.0x more likely' in r["reply_text"]


def test_private_handles_never_leave(world):
    r = run(FakeAppView(*world))
    blob = json.dumps(r)
    handles = set(re.findall(r"[a-z0-9]+\.example", blob))
    assert handles <= {PUBLIC_HANDLE}
    shown = [e["public_handle"] for n in r["narratives"] for e in n["example_posts"] if e["public_handle"]]
    assert set(shown) <= {PUBLIC_HANDLE}


def test_search_slides_until_and_normalizes_utc():
    odd = {
        "uri": "at://did:plc:h1/app.bsky.feed.post/odd",
        "author": {"did": "did:plc:h1"},
        "record": {"text": "the congestion toll repeal vote, offset clock", "createdAt": "2026-11-14T08:00:00-03:00"},
    }
    posts, profiles, fans = make_world(n_a=120, n_b=60, odd_post=odd)
    app = FakeAppView(posts, profiles, fans)
    got, ok = live.search_posts(app, "q", "2026-11-07T12:00:00.000Z", "2026-11-14T12:00:00.000Z")
    calls = [p for e, p in app.calls if e == "app.bsky.feed.searchPosts"]
    assert ok == len(calls) == 4  # 100 + 100 + 1, then an empty page ends the slide
    first_page_oldest = min(live.post_time(p) for p in app.posts[:100])
    assert calls[1]["until"] == first_page_oldest
    assert len(got) == len({p["uri"] for p in got}) == 201
    assert live.post_time(odd) == "2026-11-14T11:00:00.000Z"
    r = run(app)
    ts = [e["t"] for n in r["narratives"] for e in n["evidence"]]
    assert all(t.endswith("Z") for t in ts)
    assert r["window"]["to"] == iso(NOW - timedelta(minutes=37))
    assert r["matched_posts"] == 181  # 120 + 60 on-claim posts plus the offset-clock one


def test_cache_serves_repeat_claims_without_network(world, tmp_path):
    live._CACHE.clear()
    app = FakeAppView(*world)
    r1 = run(app, use_cache=True, save_dir=str(tmp_path))
    n = len(app.calls)
    r2 = run(app, use_cache=True, save_dir=str(tmp_path))
    assert r2 is r1 and len(app.calls) == n
    saved = json.loads((tmp_path / f"{r1['claim_id']}.json").read_text())
    assert saved["reply_text"] == r1["reply_text"]
    live._CACHE.clear()


def test_search_failure_returns_failure_reply_and_is_not_cached(world):
    live._CACHE.clear()
    r = run(FakeAppView(*world, fail=True), use_cache=True)
    assert r["error"] and r["reply_text"] == reply.FAILURE and r["matched_posts"] == 0
    assert r["claim_id"] not in live._CACHE


def test_too_few_matches_skips_scoring():
    posts, profiles, fans = make_world(n_a=12, n_b=5, n_noise=30)
    app = FakeAppView(posts, profiles, fans)
    r = run(app)
    assert r["matched_posts"] == 17 and r["narratives"] == []
    assert "isn't enough" in r["reply_text"] and reply.TRUTH_LINE in r["reply_text"]
    assert app.n("app.bsky.actor.getProfiles") == 0 and app.n("app.bsky.feed.getAuthorFeed") == 0


def test_private_individual_is_declined(world):
    app = FakeAppView(*world)
    r = run(app, llm=lambda s, u: json.dumps({"topic": "x", "queries": ["x y"], "private_individual": True}))
    assert r["reply_text"] == reply.DECLINE and app.n("app.bsky.feed.searchPosts") == 0


def test_llm_failure_falls_back_to_keywords_and_term_labels(world):
    def broken(system, user):
        raise RuntimeError("down")

    r = run(FakeAppView(*world), llm=broken)
    assert r["queries"] == ["nyc congestion toll repealed"]
    assert any("keywords" in n for n in r["notes"])
    assert len(r["narratives"]) == 2 and all(n["label"].startswith("Posts about") for n in r["narratives"])


def test_embedding_stops_at_time_budget(monkeypatch):
    monkeypatch.setattr(live, "EMBED_BUDGET_S", 0.0)
    monkeypatch.setattr(live, "EMBED_MIN", 64)
    posts, profiles, fans = make_world(n_a=100, n_b=80)
    r = run(FakeAppView(posts, profiles, fans))
    assert r["counts"]["unique_posts"] == 200 and r["counts"]["embedded_posts"] == 64
    assert 30 <= r["matched_posts"] <= 64


def test_choose_clusters_respects_min_cluster_size():
    rng = np.random.default_rng(0)
    a = rng.normal([5, 0], 0.1, size=(40, 2))
    b = rng.normal([0, 5], 0.1, size=(5, 2))
    labels, k, sil = live.choose_clusters(np.vstack([a, b]))
    assert k == 1 and sil is None and set(labels) == {0}
    c = rng.normal([0, 5], 0.1, size=(30, 2))
    labels, k, sil = live.choose_clusters(np.vstack([a, c]))
    assert k == 2 and sil > 0.5


def test_import_is_torch_free():
    code = "import sys, src.retrieval.live; assert 'torch' not in sys.modules and 'sentence_transformers' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)

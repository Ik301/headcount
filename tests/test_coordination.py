"""M3 coordination: traces, clusters, reasons and evidence on synthetic posts. No torch."""
from datetime import datetime, timedelta, timezone

from src.bots import coordination as C

T0 = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)


def iso(sec: float) -> str:
    return (T0 + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ring_posts():
    """5 accounts that repost the same 3 posts within seconds and share 2 links within seconds."""
    posts = []
    ring = [f"did:plc:ring{i}" for i in range(5)]
    for k, base in enumerate((0, 3600, 7200)):
        for i, d in enumerate(ring):
            posts.append({"did": d, "uri": f"at://x/post{k}", "t": iso(base + 3 * i), "kind": "repost", "repost_of": f"at://x/post{k}", "text": ""})
    for k, base in enumerate((10000, 20000)):
        for i, d in enumerate(ring):
            posts.append({"did": d, "uri": f"at://{d}/l{k}", "t": iso(base + 5 * i), "text": f"look {k}", "urls": [f"https://news.example/story{k}?utm=1"]})
    return ring, posts


def noise_posts():
    """Independent accounts: same viral link hours apart, unrelated texts."""
    out = []
    for i in range(20):
        d = f"did:plc:human{i}"
        out.append({"did": d, "uri": f"at://{d}/a", "t": iso(5000 * i), "text": f"my own take number {i} on the board vote and what it means", "urls": ["https://news.example/story0"]})
    return out


def test_ring_is_one_cluster_with_reasons_and_evidence():
    ring, posts = ring_posts()
    cl = C.find_clusters(posts + noise_posts())
    assert len(cl) == 1
    c = cl[0]
    assert c["dids"] == sorted(ring)
    assert set(c) == {"cluster_id", "dids", "reasons", "evidence"}
    assert any("reposted the same post" in r for r in c["reasons"])
    assert any("same link" in r for r in c["reasons"])
    assert all(set(e) == {"post_uri", "t", "trace"} for e in c["evidence"])
    assert 0 < len(c["evidence"]) <= C.MAX_EVIDENCE
    assert not any("bot" in r.lower() or "operat" in r.lower() for r in c["reasons"])


def test_one_shared_trace_is_not_a_cluster():
    posts = [
        {"did": "did:plc:a", "uri": "at://a/1", "t": iso(0), "text": "x", "urls": ["https://e.com/1"]},
        {"did": "did:plc:b", "uri": "at://b/1", "t": iso(5), "text": "y", "urls": ["https://e.com/1"]},
    ]
    assert C.find_clusters(posts) == []


def test_near_duplicate_text_links_accounts():
    text = "Breaking news Jensen Huang steps down as chief executive of Nvidia effective immediately sources say"
    posts = []
    for i in range(4):
        d = f"did:plc:dup{i}"
        posts.append({"did": d, "uri": f"at://{d}/1", "t": iso(i * 999), "text": text + f" {'!' * i}"})
        posts.append({"did": d, "uri": f"at://{d}/2", "t": iso(50000 + i * 999), "text": "Second template message about the Nvidia board probe and what happens next today"})
    cl = C.find_clusters(posts)
    assert len(cl) == 1 and len(cl[0]["dids"]) == 4
    assert any("near-identical text" in r for r in cl[0]["reasons"])


def test_offset_timestamps_and_empty_input():
    assert C.find_clusters([]) == []
    assert C._ts("2026-11-13T20:07:15-03:00") == C._ts("2026-11-13T23:07:15Z")


def test_account_features_cover_ring():
    ring, posts = ring_posts()
    f = C.account_coord_features(posts + noise_posts())
    assert all(f[d]["coord_cluster_id"] is not None for d in ring)
    assert all(f[d]["coord_max_sim"] > 0.9 for d in ring)

"""Abuse limits, declined-claim privacy and the free-text output guard (R-02, R-03, R-04, R-06, R-07)."""
import pytest

from src.api import limits, reply


def test_rate_limiter_sliding_window():
    rl = limits.RateLimiter(3, 60)
    assert [rl.allow("a", now=t) for t in (0, 1, 2, 3)] == [True, True, True, False]
    assert rl.allow("b", now=3) is True  # other keys are independent
    assert rl.allow("a", now=61) is True  # window slid


def test_client_key_prefers_cloudflare_and_exempts_local_poller():
    assert limits.client_key({"cf-connecting-ip": "203.0.113.9"}, "127.0.0.1") == ("203.0.113.9", False)
    assert limits.client_key({}, "127.0.0.1")[1] is True
    assert limits.client_key({}, "198.51.100.4") == ("198.51.100.4", False)


def test_gate_returns_busy_when_full():
    taken = 0
    try:
        for _ in range(3):
            limits.acquire_gate(0.01)
            taken += 1
        with pytest.raises(limits.Busy):
            limits.acquire_gate(0.01)
    finally:
        for _ in range(taken):
            limits.release_gate()


@pytest.mark.parametrize("bad", ["This claim is false.", "It was debunked last week", "that's fake news", "Yes it is true", "the story was a hoax"])
def test_guard_replaces_truth_rulings(bad):
    assert reply.guard_free_text(bad) == reply.SAFE_LINE


def test_guard_operator_words_and_clip():
    assert "linked to" in reply.guard_free_text("These accounts are run by one group")
    assert "run by" not in reply.guard_free_text("These accounts are run by one group")
    assert len(reply.guard_free_text("x" * 5000)) == 600
    assert reply.guard_free_text("12% of 40 accounts are likely automated.") == "12% of 40 accounts are likely automated."
    assert reply.guard_free_text(None) == ""


def test_thread_id_is_salted_hash(monkeypatch):
    pytest.importorskip("langchain_core")
    from src.agent import agent

    monkeypatch.setenv("SALT", "s1")
    a = agent.thread_id("+16095550123")
    assert "6095550123" not in a and len(a) == 16 and a == agent.thread_id("+16095550123")
    monkeypatch.setenv("SALT", "s2")
    assert agent.thread_id("+16095550123") != a


def _client(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from src.api import app as appmod

    monkeypatch.setattr(appmod, "CLAIMS_DIR", tmp_path)
    monkeypatch.setattr(appmod, "_RATE", limits.RateLimiter(10, 60))
    monkeypatch.setattr(appmod, "_JOIN_RATE", limits.RateLimiter(3, 3600))
    return appmod, TestClient(appmod.app)  # no `with`: skip the startup model load


def test_declined_claim_is_not_stored_or_served(monkeypatch, tmp_path):
    pytest.importorskip("polars")
    appmod, _ = _client(monkeypatch, tmp_path)
    from src.retrieval import live

    class St:
        claims: dict = {}
        accounts: dict = {}

    monkeypatch.setattr(appmod, "STORE", St())
    monkeypatch.setattr(live, "analyze_live", lambda text: {"claim_id": "abcdef123456", "claim": text, "declined": True, "queries": [text], "matched_posts": 0})
    r = appmod.run_claim("Is my coworker Dana Whitfield stealing?", "live")
    assert r["declined"] and "Dana" not in str(r) and r["reply_text"] == reply.DECLINE
    assert St.claims == {} and list(tmp_path.iterdir()) == []


def test_length_caps_and_rate_limit(monkeypatch, tmp_path):
    appmod, c = _client(monkeypatch, tmp_path)
    r = c.post("/claim", json={"text": "x" * 500})
    assert r.status_code == 422 and "too long" in r.json()["detail"] and "xxxx" not in r.text
    r = c.post("/agent", json={"sender": "s", "text": "x" * 700})
    assert r.status_code == 200 and "too long" in r.json()["reply_text"]
    h = {"CF-Connecting-IP": "203.0.113.9"}
    codes = [c.post("/claim", json={"text": "x" * 500}, headers=h).status_code for _ in range(12)]
    assert codes[:10] == [422] * 10 and codes[10:] == [429, 429]
    # loopback with no CF header (the local poller) is exempt
    from fastapi.testclient import TestClient

    local = TestClient(appmod.app, client=("127.0.0.1", 5000))
    assert all(local.post("/claim", json={"text": "x" * 500}).status_code == 422 for _ in range(15))


def test_join_limited_to_three_per_hour(monkeypatch, tmp_path):
    appmod, c = _client(monkeypatch, tmp_path)
    h = {"CF-Connecting-IP": "203.0.113.50"}
    codes = [c.post("/join", data={}, headers=h).status_code for _ in range(5)]  # 422 (missing field) still counts
    assert codes == [422, 422, 422, 429, 429]

"""Numbered follow-ups, help and greetings answer from the stored result without a model call (src/agent/agent.py)."""
import pytest

from src.agent import agent
from src.api import reply
from tests.test_reply_rules import full_result


class _Store:
    claims: dict = {}


@pytest.fixture(autouse=True)
def bound(monkeypatch):
    st = _Store()
    st.claims = {"abc": {**full_result(), "claim_id": "abc"}}
    monkeypatch.setattr(agent, "_STORE", st)
    monkeypatch.setattr(agent, "_LAST", {})
    monkeypatch.setattr(agent, "agent", lambda: pytest.fail("the model must not run for follow-ups"))
    monkeypatch.delenv("DASHBOARD_BASE", raising=False)


def test_numbered_follow_ups_use_the_senders_last_claim():
    agent._LAST["isaac"] = "abc"
    for text, kind in {"1": 1, "2": 2, "3": 3, "4": 4, "show the bots": 2, "who shares it": 3, "news": 4, "narratives": 1}.items():
        out = agent.run("isaac", text)
        assert out["reply_text"] == reply.followup(kind, agent._STORE.claims["abc"])
        assert out["chart_png_url"] is None and out["claim_id"] == "abc" and out.get("menu_text") is None


def test_follow_up_without_a_claim_says_to_text_one_first():
    out = agent.run("new person", "2")
    assert out["reply_text"].startswith("Text me a claim first") and out["claim_id"] is None


def test_help_returns_intro_and_menu_with_examples(monkeypatch):
    for t in ("help", "menu", "?", "hi", "Hello!"):
        out = agent.run("x", t)
        assert out["reply_text"].startswith("I'm Headcount") and "automated" in out["reply_text"]
        assert out["menu_text"].startswith("Reply with a number:") and "Jensen Huang" in out["menu_text"]
    monkeypatch.setenv("DASHBOARD_BASE", "https://demoyk.com")
    assert agent.run("x", "help")["menu_text"].endswith("Full view: https://demoyk.com")


def test_a_claim_is_not_routed():
    assert agent.route("x", "Was Jensen Huang's mistress a Chinese spy?") is None
    assert agent.route("x", "did bots defend jensen huang") is None

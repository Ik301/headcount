"""The deepagent behind the text line (LangChain deepagents, DeepSeek model, LangSmith tracing via env).

Tools wrap src.api.analysis so every number comes from computed results. POST /agent in src/api/app.py
calls run(sender, text); the sender id is the conversation thread, so follow-ups keep context.
"""
import json
import os

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from src.api import analysis, reply

SYSTEM = """You answer text messages for a tool that shows who is pushing a claim on Bluesky, about the week Jensen Huang left Nvidia (Nov 5 to 13, 2026).

For a new claim: call search_claim with the claim as the user wrote it, then reply with exactly the reply_text that compose_reply returns for that claim_id. Do not change its numbers or add new ones.
For follow-ups about the last claim:
- "show the bots" or similar: call coordination_evidence and summarize it in 2 to 4 short lines.
- "who shares it" or similar: call amplifier_archetypes and summarize in 2 to 4 short lines.
- "next": call narratives_for and describe the next narrative not yet discussed, using its numbers.
- "help" or a greeting: explain in 2 lines that they can text any claim about the Jensen Huang story.
Rules, always: never say whether a claim is true; never say who runs or operates any account; never name accounts except the public handles a tool returns; say "likely automated", not "bots", for accounts that don't label themselves; if a claim targets a private person by name, decline politely. Plain text only, no markdown, short lines suitable for a text message."""

_STORE: analysis.Store | None = None
_LAST: dict[str, str] = {}


def bind(store: analysis.Store) -> None:
    global _STORE
    _STORE = store


def _get(claim_id: str) -> dict:
    r = _STORE.claims.get(claim_id) if _STORE else None
    if not r:
        raise ValueError(f"unknown claim_id {claim_id}; call search_claim first")
    return r


@tool
def search_claim(claim: str) -> str:
    """Find posts making this claim in the Jensen Huang corpus and compute narratives, likely-automated shares and amplifiers. Returns claim_id and a summary."""
    r = analysis.analyze_claim(_STORE, claim, dashboard_base=os.environ.get("DASHBOARD_BASE", "http://localhost:5173"))
    r["reply_text"] = reply.compose(r)
    return json.dumps({"claim_id": r["claim_id"], "matched_posts": r["matched_posts"], "narratives": [{"id": n["id"], "label": n["label"], "share": n["share_of_matches"]} for n in r["narratives"]]})


@tool
def compose_reply(claim_id: str) -> str:
    """The rule-checked reply text for a claim. Send it verbatim for a new claim."""
    return _get(claim_id)["reply_text"]


@tool
def narratives_for(claim_id: str) -> str:
    """All narratives for a claim with share of matches, likely-automated share, interval and baseline."""
    return json.dumps([{k: n[k] for k in ("id", "label", "side", "share_of_matches", "bot_post_share", "bot_post_share_ci", "baseline_bot_share")} for n in _get(claim_id)["narratives"]])


@tool
def bot_share(claim_id: str, narrative_id: str) -> str:
    """Likely-automated share for one narrative of a claim, with interval and example posts (public handles only)."""
    for n in _get(claim_id)["narratives"]:
        if n["id"] == narrative_id:
            return json.dumps({k: n[k] for k in ("label", "bot_post_share", "bot_post_share_ci", "baseline_bot_share", "example_posts")})
    return json.dumps({"error": "narrative not found for this claim"})


@tool
def amplifier_archetypes(claim_id: str) -> str:
    """Which archetypes of real accounts amplified likely-automated posts for this claim, with lift."""
    return json.dumps(_get(claim_id)["amplifiers"])


@tool
def coordination_evidence(claim_id: str) -> str:
    """What the likely-automated accounts behind this claim have in common (observable signals only)."""
    return json.dumps(_get(claim_id)["bot_commonalities"])


_AGENT = None


def agent():
    global _AGENT
    if _AGENT is None:
        from deepagents import create_deep_agent

        model = ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com", api_key=os.environ["DEEPSEEK_API_KEY"], temperature=0)
        _AGENT = create_deep_agent(
            model=model,
            tools=[search_claim, compose_reply, narratives_for, bot_share, amplifier_archetypes, coordination_evidence],
            system_prompt=SYSTEM,
            checkpointer=MemorySaver(),
            name="claim-checker",
        )
    return _AGENT


def run(sender: str, text: str) -> dict:
    out = agent().invoke({"messages": [{"role": "user", "content": text}]}, config={"configurable": {"thread_id": sender}, "run_name": "claim-checker", "tags": ["hackprinceton"]})
    msg = out["messages"][-1].content
    claim_id = None
    for m in out["messages"]:
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") in ("compose_reply", "narratives_for", "amplifier_archetypes", "coordination_evidence", "bot_share"):
                claim_id = tc["args"].get("claim_id", claim_id)
    if claim_id:
        _LAST[sender] = claim_id
    cid = claim_id or _LAST.get(sender)
    r = _STORE.claims.get(cid) if cid else None
    return {"reply_text": msg, "claim_id": cid, "chart_png_url": r["chart_png_url"] if r and claim_id else None, "dashboard_url": r["dashboard_url"] if r and claim_id else None}

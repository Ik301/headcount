"""The deepagent behind the text line (LangChain deepagents, DeepSeek model, LangSmith tracing via env).

Tools wrap src.api.analysis so every number comes from computed results. POST /agent in src/api/app.py
calls run(sender, text); the sender id is the conversation thread, so follow-ups keep context.
"""
import json
import os
import re

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from src.api import analysis, reply

SYSTEM = """You answer text messages for a tool that shows who is pushing a claim on Bluesky. It knows the week Jensen Huang left Nvidia (Nov 5 to 13, 2026) in depth and can search any other story live.

For a new claim (about the Jensen Huang story or any other story): call search_claim with the claim as the user wrote it, then reply with exactly the reply_text that compose_reply returns for that claim_id. Do not change its numbers or add new ones. Always call search_claim for a new claim before deciding anything else: search_claim runs the private-person check itself and compose_reply then returns the decline text, so you never need to decline a claim on your own judgment.
Claims about public figures and news stories are always checked, including claims about the people around them, named or unnamed (for example "Was Jensen Huang's mistress a Chinese spy?", "Did Nvidia's board push Huang out?", "Did bots defend Jensen Huang?"). Only if the message plainly asks about a named private individual (a neighbor, coworker, classmate, ex) and you are certain, reply with exactly: "I can't run checks on claims about a private person. I can check claims about public stories, like the Jensen Huang week."
For follow-ups about the last claim:
- "show the bots" or similar: call coordination_evidence and summarize it in 2 to 4 short lines.
- "who shares it" or similar: call amplifier_archetypes and summarize in 2 to 4 short lines. Report each group's lift only with its account count, and when the tool says the sample is small, say so instead of calling any group "more likely".
- "next": call narratives_for and describe the next narrative not yet discussed, using its numbers as whole percentages (never raw decimals like 0.5267).
- "help" or a greeting: explain in 2 lines that they can text any claim or story they heard about.
Rules, always: never say whether a claim is true; never say who runs or operates any account; never name accounts except the public handles a tool returns; say "likely automated", not "bots", for accounts that don't label themselves. Plain text only, no markdown, short lines suitable for a text message."""

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
    """Find posts making this claim (the Jensen Huang corpus, or a live Bluesky search for any other story) and compute narratives, likely-automated shares and amplifiers. Returns claim_id and a summary."""
    from src.api.app import run_claim  # corpus or live, plus news and the privacy scrub

    r = run_claim(claim, "auto")
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
    """Which archetypes of real accounts amplified likely-automated posts for this claim, with lift and account counts."""
    amp = _get(claim_id)["amplifiers"]
    n = amp.get("n_humans", 0) or 0
    groups, unprofiled = [], 0
    for a in amp.get("archetype_mix", []):
        k = round(n * a.get("share", 0))
        if reply._unprofiled(a):  # missing profile data, not a kind of account
            unprofiled += k
            continue
        groups.append({"label": a["label"], "accounts": k, "share": a.get("share"), "lift": a.get("lift")})
    profiled = sum(g["accounts"] for g in groups)
    out = {"n_humans": n, "profiled_accounts": profiled, "not_profiled_accounts": unprofiled, "groups": groups}
    if profiled < 10:
        out["note"] = f"Only {profiled} amplifying accounts could be profiled, too few to say any group is more likely to amplify. Report counts, not lifts."
    return json.dumps(out)


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


def _searched(messages) -> bool:
    return any(tc.get("name") == "search_claim" for m in messages for tc in (getattr(m, "tool_calls", None) or []))


def run(sender: str, text: str) -> dict:
    # The last claim_id rides along with each message, so follow-ups work even when the claim was answered by the
    # safety net below (outside the model's own tool calls).
    content = text if sender not in _LAST else f"{text}\n\n(Context for tools, not from the user: the last claim_id for this sender is {_LAST[sender]}.)"
    out = agent().invoke({"messages": [{"role": "user", "content": content}]}, config={"configurable": {"thread_id": sender}, "run_name": "claim-checker", "tags": ["hackprinceton"]})
    msgs = out["messages"]
    # out["messages"] is the whole thread (checkpointer); only this turn's messages count below, otherwise an old
    # claim_id or search from earlier in the conversation leaks into this reply (e.g. a chart sent with a decline).
    start = max((i for i, m in enumerate(msgs) if getattr(m, "type", "") == "human"), default=0)
    turn = msgs[start:]
    msg = msgs[-1].content
    claim_id = None
    for m in turn:
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") in ("compose_reply", "narratives_for", "amplifier_archetypes", "coordination_evidence", "bot_share"):
                claim_id = tc["args"].get("claim_id", claim_id)
        if claim_id is None and getattr(m, "type", "") == "tool" and getattr(m, "name", "") == "search_claim":
            try:  # the model searched but wrote the reply without compose_reply: still attach the claim
                claim_id = json.loads(m.content).get("claim_id")
            except (ValueError, TypeError, AttributeError):
                pass
    new_claim = _searched(turn)
    # Safety net: the model once declined "Was Jensen Huang's mistress a Chinese spy?" as a private-person claim
    # without searching. A decline must come from the API's own check, so when the model declines on its own,
    # run the claim through the API and send whatever it composes (its decline, or the real answer).
    if not new_claim and re.search(r"private (person|individual)", msg or "", re.I):
        from src.api.app import run_claim

        r = run_claim(text, "auto")
        msg = r["reply_text"]
        claim_id = None if r.get("declined") else r["claim_id"]
        new_claim = True
    if (msg or "").strip() == reply.DECLINE:  # never send the previous claim's chart or link with a decline
        return {"reply_text": msg, "claim_id": None, "chart_png_url": None, "dashboard_url": None}
    if claim_id:
        _LAST[sender] = claim_id
    cid = claim_id or _LAST.get(sender)
    r = _STORE.claims.get(cid) if cid else None
    attach = bool(r and claim_id and new_claim)  # chart and link go with a new answer, not with every follow-up
    chart = r["chart_png_url"] if (attach and r) else None
    link = r["dashboard_url"] if (attach and r) else None
    return {"reply_text": msg, "claim_id": cid, "chart_png_url": chart, "dashboard_url": link}

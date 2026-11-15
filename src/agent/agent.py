"""The deepagent behind the text line (LangChain deepagents, DeepSeek model, LangSmith tracing via env).

Tools wrap src.api.analysis so every number comes from computed results. POST /agent in src/api/app.py
calls run(sender, text); the sender id is the conversation thread, so follow-ups keep context.
"""
import hashlib
import json
import os
import re

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from src import config as cfg
from src.api import analysis, limits, reply

SYSTEM = """You answer text messages for a tool that shows who is pushing a claim on Bluesky. It knows the week Jensen Huang left Nvidia (Nov 5 to 13, 2026) in depth and can search any other story live.

For a new claim (about the Jensen Huang story or any other story): call search_claim with the claim as the user wrote it, then reply with exactly the reply_text that compose_reply returns for that claim_id. Do not change its numbers or add new ones. Always call search_claim for a new claim before deciding anything else: search_claim runs the private-person check itself and compose_reply then returns the decline text, so you never need to decline a claim on your own judgment.
Claims about public figures and news stories are always checked, including claims about the people around them, named or unnamed (for example "Was Jensen Huang's mistress a Chinese spy?", "Did Nvidia's board push Huang out?", "Did bots defend Jensen Huang?"). Only if the message plainly asks about a named private individual (a neighbor, coworker, classmate, ex) and you are certain, reply with exactly: "__DECLINE__"
The numbered follow-ups (1 to 4 and their word forms: narratives, bots, who shares it, news) and help or a greeting are answered by code before you see them, so you only get new claims and free-form questions. For a free-form question about the last claim:
- about the automated accounts: call coordination_evidence and summarize it in 2 to 4 short lines.
- about who spreads it: call amplifier_archetypes and summarize in 2 to 4 short lines. Report each group's lift only with its account count, and when the tool says the sample is small, say so instead of calling any group "more likely".
- "next": call narratives_for and describe the next narrative not yet discussed, using its numbers as whole percentages (never raw decimals like 0.5267).
Rules, always: never say whether a claim is true; never say who runs or operates any account; never name accounts except the public handles a tool returns; say "likely automated", not "bots", for accounts that don't label themselves. Plain text only, no markdown, short lines suitable for a text message.""".replace("__DECLINE__", reply.DECLINE)

_STORE: analysis.Store | None = None
_LAST: dict[str, str] = {}


def thread_id(sender: str) -> str:
    """Salted hash of the sender (a phone number or Apple ID) for LangSmith: traces never carry the raw id."""
    return hashlib.sha256((os.environ.get("SALT") or "dev-salt").encode() + b":" + sender.encode()).hexdigest()[:16]


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

    try:
        r = run_claim(claim, "auto")
    except limits.Busy:
        return json.dumps({"error": "busy", "instruction": "Tell the user the checker is busy and to try again in a minute."})
    if r.get("declined"):  # nothing was stored for a private-person claim, so there is no claim_id to compose from
        return json.dumps({"declined": True, "instruction": f"Reply with exactly: {reply.DECLINE}"})
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


def _plain(text: str, claim_id: str | None = None, menu_text: str | None = None, dashboard_url: str | None = None) -> dict:
    return {"reply_text": text, "claim_id": claim_id, "chart_png_url": None, "dashboard_url": dashboard_url, "menu_text": menu_text}


def route(sender: str, text: str) -> dict | None:
    """Deterministic replies, no model call: help or a greeting, and the numbered follow-ups 1 to 4 (and their word
    forms) answered from the stored result of the sender's last claim. None means a claim or a free-form question."""
    kind = reply.intent(text)
    if kind is None:
        return None
    if kind == "help":
        base = os.environ.get("DASHBOARD_BASE")
        return _plain(reply.intro(), menu_text=reply.menu(base, examples=True), dashboard_url=base)
    cid = _LAST.get(sender)
    r = _STORE.claims.get(cid) if (cid and _STORE) else None
    if not r:
        return _plain(reply.no_claim_yet())
    return _plain(reply.followup(kind, r), claim_id=cid)


def run(sender: str, text: str) -> dict:
    routed = route(sender, text)
    if routed is not None:
        return routed
    # The last claim_id rides along with each message, so follow-ups work even when the claim was answered by the
    # safety net below (outside the model's own tool calls).
    content = text if sender not in _LAST else f"{text}\n\n(Context for tools, not from the user: the last claim_id for this sender is {_LAST[sender]}.)"
    tid = thread_id(sender)  # _LAST stays keyed by the raw sender: it is in-memory only and never traced
    out = agent().invoke({"messages": [{"role": "user", "content": content}]}, config={"configurable": {"thread_id": tid}, "run_name": "claim-checker", "tags": ["hackprinceton"], "metadata": {"sender": tid}})
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
    for m in turn:  # search_claim declined a private-person claim: nothing was stored, send the fixed decline
        if getattr(m, "type", "") == "tool" and getattr(m, "name", "") == "search_claim" and '"declined": true' in str(m.content):
            return _plain(reply.DECLINE)
    # Safety net: the model once declined "Was Jensen Huang's mistress a Chinese spy?" as a private-person claim
    # without searching. A decline must come from the API's own check, so when the model declines on its own,
    # run the claim through the API and send whatever it composes (its decline, or the real answer).
    if not new_claim and re.search(r"private (person|individual)", msg or "", re.I):
        from src.api.app import run_claim

        r = run_claim(text, "auto")
        msg = r["reply_text"]
        if r.get("declined"):  # nothing stored for a decline
            return _plain(reply.DECLINE)
        claim_id = r["claim_id"]
        new_claim = True
    if (msg or "").strip() == reply.DECLINE:  # never send the previous claim's chart or link with a decline
        return _plain(msg)
    if claim_id:
        _LAST[sender] = claim_id
    cid = claim_id or _LAST.get(sender)
    r = _STORE.claims.get(cid) if cid else None
    attach = bool(r and claim_id and new_claim)  # chart and link go with a new answer, not with every follow-up
    chart = r["chart_png_url"] if (attach and r) else None
    link = r["dashboard_url"] if (attach and r) else None
    if attach and r and r.get("reply_text") and not r.get("declined"):
        msg = r["reply_text"]  # the rule-checked bubble 1, never the model's paraphrase
    if not (attach and r and r.get("reply_text")):  # free-form turn: the output guard applies (templated bubble 1 is already rule-checked)
        msg = reply.guard_free_text(msg)
    menu_text = reply.menu(link) if (attach and r and r.get("matched_posts", 0) >= cfg.MIN_MATCHES and not r.get("error")) else None
    return {"reply_text": msg, "claim_id": cid, "chart_png_url": chart, "dashboard_url": link, "menu_text": menu_text}

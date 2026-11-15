"""Analysis API.

Run: .venv/bin/uvicorn src.api.app:app --host 127.0.0.1 --port 8000
Contracts: docs/DEMO.md ("API contracts").

/claim modes: "corpus" (the Jensen Huang story on disk), "live" (any story, searched on Bluesky now, src.retrieval.live),
"auto" (corpus when it has at least config.MIN_MATCHES matching posts, live otherwise). Every response gets a `news`
block (src.news.baseline) and passes through `scrub` so no private account's DID leaves the server.
Results are kept in memory and written to data/processed/claims/<claim_id>.json, so shared links survive restarts.
"""
import json
import os
import re
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from src import config as cfg
from src.api import analysis, reply
from src.api.health import bot_model_version
from src.integration import versions
from src.model.schema import hashed_id

load_dotenv()
app = FastAPI(title="socialnet-bot-tracker")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
STORE: analysis.Store | None = None
CLAIMS_DIR = Path(os.environ.get("DATA_DIR", "data/processed")) / "claims"
DID_RE = re.compile(r"at://(did:[a-z]+:[A-Za-z0-9._:-]+)/")
_WARM = {"live": False, "news": False}


def store() -> analysis.Store:
    global STORE
    if STORE is None:
        STORE = analysis.Store.load(os.environ.get("DATA_DIR", "data/processed"))
    return STORE


def _public(did: str) -> bool:
    a = STORE.accounts.get(did) if STORE else None
    return bool(a and a.get("is_public"))


def scrub(obj):
    """Replace any post URI from a non-public account with an account ref (privacy rule 4)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and k in ("post_uri", "uri", "post_id") and (m := DID_RE.match(v)) and not _public(m.group(1)):
                out[k] = None
                out.setdefault("account_ref", hashed_id(m.group(1)))
            else:
                out[k] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, str) and "did:plc:" in obj:
        return DID_RE.sub(lambda m: m.group(0) if _public(m.group(1)) else "at://acct-" + hashed_id(m.group(1)) + "/", obj)
    return obj


def _save(r: dict) -> None:
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CLAIMS_DIR / f"{r['claim_id']}.json.tmp"
    tmp.write_text(json.dumps(r))
    os.replace(tmp, CLAIMS_DIR / f"{r['claim_id']}.json")


def _lookup(claim_id: str) -> dict | None:
    if not re.fullmatch(r"[0-9a-f]{6,64}", claim_id):
        return None
    r = store().claims.get(claim_id)
    if r is None:
        from src.retrieval import live

        r = live.cached(claim_id)
    if r is None and (CLAIMS_DIR / f"{claim_id}.json").exists():
        r = json.loads((CLAIMS_DIR / f"{claim_id}.json").read_text())
        store().claims[claim_id] = r
    return r


def _news(text: str, r: dict) -> dict | None:
    try:
        from src.news import baseline as nb

        embed = nb.embedder_from_model(store().corpus.model)
        if r.get("scope") == "live":
            heads = nb.fetch_live_headlines(text)
            return nb.news_for_claim(text, _live_posts(r), headlines=heads, embed=embed)
        m = store().matched.get(r["claim_id"])
        if m is None:
            return None
        return nb.news_for_claim(text, m, embed=embed)
    except Exception as e:  # the news block is additive; never fail the claim over it
        return {"error": f"news baseline unavailable: {type(e).__name__}"}


def _live_posts(r: dict):
    import polars as pl

    rows = [{"text": ex["text"], "narrative_id": n["id"]} for n in r.get("narratives", []) for ex in n.get("example_posts", [])]
    return pl.DataFrame(rows, schema={"text": pl.Utf8, "narrative_id": pl.Utf8})


def _warm_background() -> None:
    try:
        from src.retrieval import live

        live.warm()
        _WARM["live"] = True
        from src.news import baseline as nb

        nb.warm(nb.embedder_from_model(store().corpus.model))
        _WARM["news"] = True
    except Exception as e:
        print(f"warm-up failed: {e}", flush=True)


class ClaimIn(BaseModel):
    text: str
    mode: str = "auto"


@app.on_event("startup")
def _startup() -> None:
    store()
    threading.Thread(target=_warm_background, daemon=True).start()


@app.get("/health")
def health() -> dict:
    v = versions()
    return {"ok": True, "artifacts_loaded": STORE is not None, "bot_model": bot_model_version(), "modules": v, "warm": _WARM}


def run_claim(text: str, mode: str = "auto") -> dict:
    """The /claim pipeline, shared with the agent's search_claim tool."""
    base = os.environ.get("DASHBOARD_BASE", "http://localhost:5173")
    r = None
    if mode in ("auto", "corpus"):
        r = analysis.analyze_claim(store(), text, dashboard_base=base)
        if mode == "auto" and r["matched_posts"] < cfg.MIN_MATCHES:
            r = None
    if r is None:
        from src.retrieval import live

        r = live.analyze_live(text)
        r.setdefault("dashboard_url", f"{base}/claim/{r['claim_id']}")
        r.setdefault("chart_png_url", f"/claim/{r['claim_id']}/chart.png")
    if "news" not in r:
        r["news"] = _news(text, r)
    r["reply_text"] = reply.compose(r)
    r = scrub(r)
    store().claims[r["claim_id"]] = r
    _save(r)
    return r


@app.post("/claim")
def claim(body: ClaimIn) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "empty claim")
    if body.mode not in ("auto", "corpus", "live"):
        raise HTTPException(400, "mode must be auto, corpus or live")
    return run_claim(text, body.mode)


@app.get("/claim/{claim_id}")
def get_claim(claim_id: str) -> dict:
    r = _lookup(claim_id)
    if not r:
        raise HTTPException(404, "unknown claim id")
    return r


@app.get("/claim/{claim_id}/chart.png")
def chart(claim_id: str) -> Response:
    r = _lookup(claim_id)
    if not r:
        raise HTTPException(404, "unknown claim id")
    return Response(reply.chart_png(r), media_type="image/png")


class AgentIn(BaseModel):
    sender: str
    text: str


@app.post("/agent")
def agent_reply(body: AgentIn) -> dict:
    """Messaging service entry point: one inbound text from one sender -> the deepagent's reply."""
    from src.agent import agent as ag

    ag.bind(store())
    return scrub(ag.run(body.sender, body.text.strip()))


@app.get("/join", response_class=HTMLResponse)
def join_form() -> str:
    from src.messaging import join

    return join.page()


@app.post("/join", response_class=HTMLResponse)
def join_submit(handle: str = Form(...)) -> str:
    from src.messaging import join

    return join.join(handle)

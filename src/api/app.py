"""Analysis API.

Run: .venv/bin/uvicorn src.api.app:app --host 127.0.0.1 --port 8000
Contracts: docs/DEMO.md ("API contracts").
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from src.api import analysis, reply
from src.integration import versions

load_dotenv()
app = FastAPI(title="socialnet-bot-tracker")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
STORE: analysis.Store | None = None


def store() -> analysis.Store:
    global STORE
    if STORE is None:
        STORE = analysis.Store.load(os.environ.get("DATA_DIR", "data/processed"))
    return STORE


class ClaimIn(BaseModel):
    text: str
    mode: str = "auto"


@app.on_event("startup")
def _warm() -> None:
    store()


@app.get("/health")
def health() -> dict:
    v = versions()
    return {"ok": True, "artifacts_loaded": STORE is not None, "bot_model": "stub" if "stubs" in v["bots"] else v["bots"], "modules": v}


@app.post("/claim")
def claim(body: ClaimIn) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "empty claim")
    if body.mode == "live":
        raise HTTPException(501, "live mode not built yet")
    r = analysis.analyze_claim(store(), text, dashboard_base=os.environ.get("DASHBOARD_BASE", "http://localhost:5173"))
    r["reply_text"] = reply.compose(r)
    return r


@app.get("/claim/{claim_id}")
def get_claim(claim_id: str) -> dict:
    r = store().claims.get(claim_id)
    if not r:
        raise HTTPException(404, "unknown claim id")
    return r


@app.get("/claim/{claim_id}/chart.png")
def chart(claim_id: str) -> Response:
    r = store().claims.get(claim_id)
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
    return ag.run(body.sender, body.text.strip())


@app.get("/join", response_class=HTMLResponse)
def join_form() -> str:
    from src.messaging import join

    return join.page()


@app.post("/join", response_class=HTMLResponse)
def join_submit(handle: str = Form(...)) -> str:
    from src.messaging import join

    return join.join(handle)

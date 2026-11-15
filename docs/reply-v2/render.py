"""Regenerate docs/reply-v2: cards and the three-bubble exchanges from stored results.
Run from the repo root: PYTHONPATH=. .venv/bin/python docs/reply-v2/render.py
The flagship result predates the claim-level field, so it is merged in from a real recompute (analysis.analyze_claim)."""
import json
import os
from pathlib import Path

from src.agent import agent
from src.api import reply

OUT = Path("docs/reply-v2")
BASE = "https://demoyk.com"  # illustrative; the live link comes from DASHBOARD_BASE
FLAGSHIP_CLAIM_LEVEL = {"bot_post_share": 0.0158, "bot_post_share_ci": [0.0023, 0.0318]}  # analyze_claim on data/processed, 443 posts


def load(cid: str, extra: dict | None = None) -> dict:
    path = next(Path("data/processed").glob(f"claims*/{cid}.json"))  # claims/ is rotated by reruns; claims_old_* keep copies
    r = json.loads(path.read_text())
    r.update(extra or {})
    r["dashboard_url"] = f"{BASE}/claim/{cid}"
    r["reply_text"] = reply.compose(r)
    return r


def bubbles(r: dict) -> list[str]:
    return ["[bubble 1 · text]\n" + r["reply_text"], f"[bubble 2 · image] {r['claim_id']}.png (1080 px wide card)", "[bubble 3 · text]\n" + reply.menu(r["dashboard_url"])]


def main() -> None:
    os.environ["DASHBOARD_BASE"] = BASE
    flagship = load("b61ff2f2ead5", FLAGSHIP_CLAIM_LEVEL)
    live = load("1e6f9f5ec7c2")
    (OUT / "flagship.png").write_bytes(reply.chart_png(flagship))
    (OUT / "live.png").write_bytes(reply.chart_png(live))
    tiny = {"claim": "Is the moon made of Wi-Fi?", "claim_id": "tiny", "scope": "live", "matched_posts": 12, "narratives": [], "dashboard_url": f"{BASE}/claim/tiny"}
    (OUT / "tiny.png").write_bytes(reply.chart_png(tiny))
    agent._STORE = type("S", (), {"claims": {flagship["claim_id"]: flagship}})()
    agent._LAST.clear()
    agent._LAST["demo"] = flagship["claim_id"]
    parts = ["=== texter: " + flagship["claim"], "[bubble 0 · text, sent at once]\nChecking who is pushing that. About 20 seconds.", *bubbles(flagship)]
    for t in ("2", "3", "4"):
        parts += ["", f"=== texter: {t}", "[1 bubble · text]\n" + agent.run("demo", t)["reply_text"]]
    agent._LAST.clear()
    out = agent.run("fresh", "help")
    parts += ["", "=== texter: help", "[bubble 1 · text]\n" + out["reply_text"], "[bubble 2 · text]\n" + out["menu_text"]]
    out = agent.run("fresh", "2")
    parts += ["", "=== texter: 2 (before any claim)", "[1 bubble · text]\n" + out["reply_text"]]
    parts += ["", "=== live-style result (St. Patrick's parade, live Bluesky search, no story baseline)", *bubbles(live)]
    (OUT / "exchange.txt").write_text("\n\n".join(p if not p.startswith("\n") else p for p in parts).replace("\n\n\n", "\n\n") + "\n")


if __name__ == "__main__":
    main()

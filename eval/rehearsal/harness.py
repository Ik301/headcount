"""Rehearsal harness (docs/rehearsal.md): hits the public API, records latency, reply, number checks and a privacy sweep.
Usage: .venv/bin/python eval/rehearsal/harness.py claims <out.json> '[{"text": "..."}]'
       .venv/bin/python eval/rehearsal/harness.py agent <out.json> '[{"sender": "test-1", "turns": ["...", "show the bots"]}]'
Use test sender ids, never phone numbers. API_BASE overrides the API URL. Output stays local (scratch), never commit it.
"""
import json, os, re, sys, time, urllib.request, urllib.error  # noqa: E401
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(os.environ.get("TMPDIR", "/tmp")) / "rehearsal_raw"

sys.path.insert(0, str(ROOT))
import polars as pl
from src.api import reply as R

API = os.environ.get("API_BASE", "https://antivirus-checked-insight-chi.trycloudflare.com")


def req(method, path, body=None, timeout=150):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json", "User-Agent": "rehearsal"})
    t = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw, code = resp.read(), resp.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    except Exception as e:  # noqa
        raw, code = str(e).encode(), -1
    return code, raw, round(time.time() - t, 2)


a = pl.read_parquet(ROOT / "data/processed/accounts.parquet").select("account_id", "handle", "is_public")
PRIV_H = {h.lower() for h in a.filter(~pl.col("is_public"))["handle"].to_list() if h}
PRIV_D = set(a.filter(~pl.col("is_public"))["account_id"].to_list())
DID_RE = re.compile(r"did:(?:plc|web):[A-Za-z0-9._:-]+")


def privacy(raw: str) -> dict:
    low = raw.lower()
    dids = set(DID_RE.findall(raw))
    toks = set(re.findall(r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+", low))
    return {
        "dids_total": len(dids),
        "private_dids": sorted(d for d in dids if d in PRIV_D),
        "noncorpus_dids": sorted(d for d in dids if d not in PRIV_D and d not in set(a["account_id"].to_list()))[:10],
        "private_handles": sorted(t for t in toks if t in PRIV_H),
        "mentions": sorted(set(re.findall(r"@([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+)", low))),
    }


def json_numbers(r: dict) -> set:
    """Every number a reply could legitimately quote, rendered the ways reply.py renders them."""
    s = set()
    def add(x):
        s.add(str(x))
    n = r.get("matched_posts", 0)
    add(n); add(f"{n:,}"); add(30)
    base = r.get("baseline_bot_share") or 0
    for nr in r.get("narratives", []):
        for k in ("share_of_matches", "bot_post_share", "baseline_bot_share"):
            add(f"{nr[k]*100:.0f}"); add(f"{nr[k]*100:.1f}")
        for v in nr["bot_post_share_ci"]:
            add(f"{v*100:.0f}"); add(f"{v*100:.1f}")
        if base:
            add(f"{nr['bot_post_share']/base:.0f}"); add(f"{nr['bot_post_share']/base:.1f}")
        add(nr.get("posts", ""))
    for c in r.get("bot_commonalities", []):
        add(c.get("accounts")); [add(x) for x in re.findall(r"\d+(?:[.,]\d+)?", c.get("signal", ""))]
    amp = r.get("amplifiers", {})
    add(amp.get("n_humans"))
    for m in amp.get("archetype_mix", []):
        add(f"{(m.get('lift') or 0):.1f}"); add(f"{(m.get('lift') or 0):.2f}"); add(f"{m['share']*100:.0f}")
        [add(x) for x in re.findall(r"\d+(?:\.\d+)?", m.get("label", ""))]
    for nr in r.get("narratives", []):
        [add(x) for x in re.findall(r"\d+(?:\.\d+)?", nr["label"])]
    for x in ("5", "13", "2026", "2", "3", "4", "1"):  # window words, list numbering
        add(x)
    return s


def reply_numbers(text: str) -> list:
    t = re.sub(r"https?://\S+", "", text)
    return re.findall(r"\d[\d,]*(?:\.\d+)?", t)


def check_claim(text, mode="auto"):
    code, raw, secs = req("POST", "/claim", {"text": text, "mode": mode})
    out = {"claim": text, "mode": mode, "http": code, "latency_s": secs}
    try:
        r = json.loads(raw)
    except Exception:
        out["error"] = raw[:300].decode(errors="replace")
        return out
    if "claim_id" not in r:
        out["error"] = r
        return out
    out.update({k: r.get(k) for k in ("claim_id", "scope", "matched_posts", "seconds", "reply_text", "declined", "error", "queries", "notes", "counts", "steps")})
    out["narratives"] = [{k: n.get(k) for k in ("id", "label", "side", "posts", "share_of_matches", "bot_post_share", "bot_post_share_ci")} for n in r.get("narratives", [])]
    out["bot_commonalities"] = [{k: c.get(k) for k in ("signal", "accounts")} for c in r.get("bot_commonalities", [])]
    out["amplifiers"] = {"n_humans": r.get("amplifiers", {}).get("n_humans"), "mix": r.get("amplifiers", {}).get("archetype_mix")}
    out["baseline_bot_share"] = r.get("baseline_bot_share")
    out["news_present"] = bool(r.get("news")) and "error" not in (r.get("news") or {})
    out["news_error"] = (r.get("news") or {}).get("error") if isinstance(r.get("news"), dict) else None
    # numbers: strict recompose + loose number set
    try:
        expected = R.compose(r)
    except Exception as e:  # noqa
        expected = f"<compose failed: {e}>"
    out["reply_equals_recompose"] = expected == r.get("reply_text")
    nums = json_numbers(r)
    out["reply_numbers_unmatched"] = [x for x in reply_numbers(r.get("reply_text") or "") if x not in nums and x.replace(",", "") not in nums]
    # GET round trip and chart
    c2, raw2, s2 = req("GET", f"/claim/{r['claim_id']}")
    out["get_http"], out["get_latency_s"] = c2, s2
    try:
        r2 = json.loads(raw2)
        out["get_same_numbers"] = [(n["share_of_matches"], n["bot_post_share"], n["bot_post_share_ci"]) for n in r2.get("narratives", [])] == [(n["share_of_matches"], n["bot_post_share"], n["bot_post_share_ci"]) for n in r.get("narratives", [])] and r2.get("reply_text") == r.get("reply_text")
    except Exception:
        out["get_same_numbers"] = False
    c3, raw3, s3 = req("GET", f"/claim/{r['claim_id']}/chart.png")
    out["chart_http"], out["chart_bytes"], out["chart_png"], out["chart_latency_s"] = c3, len(raw3), raw3[:4] == b"\x89PNG", s3
    out["privacy"] = privacy(raw.decode(errors="replace"))
    out["public_handles_shown"] = sorted({e.get("public_handle") for n in r.get("narratives", []) for e in n.get("example_posts", []) if e.get("public_handle")})
    out["evidence_uris_shown"] = sum(1 for n in r.get("narratives", []) for e in n.get("evidence", []) if e.get("post_uri"))
    out["evidence_uris_scrubbed"] = sum(1 for n in r.get("narratives", []) for e in n.get("evidence", []) if not e.get("post_uri"))
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{r['claim_id']}.json").write_bytes(raw)
    return out


def agent_turn(sender, text):
    code, raw, secs = req("POST", "/agent", {"sender": sender, "text": text}, timeout=180)
    out = {"sender": sender, "text": text, "http": code, "latency_s": secs}
    try:
        r = json.loads(raw)
    except Exception:
        out["error"] = raw[:300].decode(errors="replace")
        return out
    out.update(r)
    out["privacy"] = privacy(raw.decode(errors="replace"))
    return out


if __name__ == "__main__":
    kind, path = sys.argv[1], sys.argv[2]
    items = json.loads(sys.argv[3])
    res = []
    if kind == "claims":
        for it in items:
            res.append(check_claim(it["text"], it.get("mode", "auto")))
            print(json.dumps({k: res[-1].get(k) for k in ("claim", "scope", "http", "latency_s", "matched_posts", "reply_equals_recompose", "reply_numbers_unmatched")}), flush=True)
    else:
        for conv in items:
            for t in conv["turns"]:
                res.append(agent_turn(conv["sender"], t))
                print(json.dumps({k: res[-1].get(k) for k in ("sender", "text", "http", "latency_s", "claim_id")}), flush=True)
    Path(path).write_text(json.dumps(res, indent=1, default=str))

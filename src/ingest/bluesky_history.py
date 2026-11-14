"""Pull recent post history for every account in the story (compact fields only).

Usage:
    python -m src.ingest.bluesky_history --profiles data/raw/profiles.jsonl --out data/raw/history.jsonl --limit 50

One app.bsky.feed.getAuthorFeed call per account (unauthenticated AppView). Resumable.
Each output line: {"did", "items": [{"uri","t","text","kind","reply_parent","quote","repost_of","langs","n_like","n_repost","n_reply","n_quote","urls"}]}
kind is "post", "reply", "quote" or "repost" (repost = the account reposted someone else's post at time t).
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

API = "https://api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"


def compact(item: dict, did: str) -> dict:
    post = item.get("post", {})
    rec = post.get("record", {}) or {}
    reason = item.get("reason") or {}
    is_repost = reason.get("$type", "").endswith("reasonRepost")
    embed = rec.get("embed") or {}
    quote = None
    if "record" in embed.get("$type", ""):
        r = embed.get("record", {})
        quote = r.get("uri") or (r.get("record") or {}).get("uri")
    urls = []
    for facet in rec.get("facets") or []:
        for feat in facet.get("features") or []:
            if feat.get("uri"):
                urls.append(feat["uri"])
    ext = (embed.get("external") or (embed.get("media") or {}).get("external") or {}).get("uri")
    if ext:
        urls.append(ext)
    reply = (rec.get("reply") or {}).get("parent", {}).get("uri")
    kind = "repost" if is_repost else ("reply" if reply else ("quote" if quote else "post"))
    return {
        "uri": post.get("uri"),
        "author": (post.get("author") or {}).get("did"),
        "t": reason.get("indexedAt") if is_repost else rec.get("createdAt"),
        "text": (rec.get("text") or "")[:1000],
        "kind": kind,
        "reply_parent": reply,
        "quote": quote,
        "langs": rec.get("langs"),
        "n_like": post.get("likeCount"),
        "n_repost": post.get("repostCount"),
        "n_reply": post.get("replyCount"),
        "n_quote": post.get("quoteCount"),
        "urls": urls,
    }


def fetch(client: httpx.Client, did: str, limit: int) -> dict:
    for attempt in range(6):
        try:
            r = client.get(API, params={"actor": did, "limit": limit})
        except httpx.HTTPError:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            return {"did": did, "items": [compact(i, did) for i in r.json().get("feed", [])]}
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        return {"did": did, "items": [], "error": r.status_code}
    return {"did": did, "items": [], "error": "retries"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    dids = [json.loads(l)["did"] for l in open(a.profiles) if l.strip()]
    out = Path(a.out)
    done = set()
    if out.exists():
        done = {json.loads(l)["did"] for l in open(out) if l.strip()}
    todo = [d for d in dids if d not in done]
    print(f"{len(dids)} accounts, {len(done)} done, {len(todo)} to fetch", flush=True)
    t0 = time.time()
    with httpx.Client(timeout=30, headers={"User-Agent": "socialnet-bot-tracker (HackPrinceton research)"}) as client, open(
        out, "a"
    ) as fo, ThreadPoolExecutor(a.workers) as pool:
        for i, row in enumerate(pool.map(lambda d: fetch(client, d, a.limit), todo)):
            fo.write(json.dumps(row) + "\n")
            if i % 500 == 0:
                fo.flush()
                print(f"{i}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    print(f"done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

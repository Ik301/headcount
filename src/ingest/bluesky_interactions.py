"""Pull who liked, reposted and quoted each story post.

Usage:
    python -m src.ingest.bluesky_interactions --posts data/processed/posts.parquet --out data/raw/interactions.jsonl

One page (up to 100) per post and type from the unauthenticated AppView: getLikes (has createdAt),
getRepostedBy (no timestamps), getQuotes (quote posts carry createdAt). Only posts with a nonzero count are
queried. Resumable by (post, type). Output lines: {"post_id", "type", "actors": [{"did", "handle", "t"}], "total"}
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import polars as pl

BASE = "https://api.bsky.app/xrpc/"
ENDPOINT = {"like": ("app.bsky.feed.getLikes", "likes"), "repost": ("app.bsky.feed.getRepostedBy", "repostedBy"), "quote": ("app.bsky.feed.getQuotes", "posts")}


def fetch(client: httpx.Client, post_id: str, kind: str) -> dict:
    ep, key = ENDPOINT[kind]
    for attempt in range(6):
        try:
            r = client.get(BASE + ep, params={"uri": post_id, "limit": 100})
        except httpx.HTTPError:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            items = r.json().get(key, [])
            actors = []
            for it in items:
                if kind == "like":
                    a = it.get("actor", {})
                    actors.append({"did": a.get("did"), "handle": a.get("handle"), "t": it.get("createdAt")})
                elif kind == "repost":
                    actors.append({"did": it.get("did"), "handle": it.get("handle"), "t": None})
                else:
                    a = it.get("author", {})
                    actors.append({"did": a.get("did"), "handle": a.get("handle"), "t": (it.get("record") or {}).get("createdAt"), "uri": it.get("uri")})
            return {"post_id": post_id, "type": kind, "actors": actors}
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        return {"post_id": post_id, "type": kind, "actors": [], "error": r.status_code}
    return {"post_id": post_id, "type": kind, "actors": [], "error": "retries"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--posts", default="data/processed/posts.parquet")
    ap.add_argument("--out", default="data/raw/interactions.jsonl")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    p = pl.read_parquet(a.posts)
    jobs = []
    for kind, col in (("like", "like_count"), ("repost", "repost_count"), ("quote", "quote_count")):
        sub = p.filter(pl.col(col) > 0).sort(col, descending=True)
        jobs += [(pid, kind, n) for pid, n in zip(sub["post_id"].to_list(), sub[col].to_list())]
    out = Path(a.out)
    done = set()
    if out.exists():
        done = {(d["post_id"], d["type"]) for d in map(json.loads, open(out)) if "error" not in d}
    todo = [j for j in jobs if (j[0], j[1]) not in done]
    print(f"{len(jobs)} jobs, {len(done)} done, {len(todo)} to fetch", flush=True)
    t0 = time.time()
    with httpx.Client(timeout=30, headers={"User-Agent": "socialnet-bot-tracker (HackPrinceton research)"}) as client, open(
        out, "a"
    ) as fo, ThreadPoolExecutor(a.workers) as pool:
        for i, row in enumerate(pool.map(lambda j: {**fetch(client, j[0], j[1]), "total": j[2]}, todo)):
            fo.write(json.dumps(row) + "\n")
            if i % 1000 == 0:
                fo.flush()
                print(f"{i}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    print(f"done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

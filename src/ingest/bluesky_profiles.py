"""Pull Bluesky profiles for every account in the story posts file.

Usage:
    python -m src.ingest.bluesky_profiles --posts data/raw/bsky_jensen_nov5_13.jsonl --out data/raw/profiles.jsonl

Reads public data from the unauthenticated AppView (app.bsky.actor.getProfiles, 25 actors per call).
Resumable: skips DIDs already present in the output file.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

API = "https://api.bsky.app/xrpc/app.bsky.actor.getProfiles"


def fetch(client: httpx.Client, dids: list[str]) -> list[dict]:
    for attempt in range(6):
        r = client.get(API, params=[("actors", d) for d in dids])
        if r.status_code == 200:
            return r.json().get("profiles", [])
        if r.status_code in (429, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 400 and len(dids) > 1:
            # one bad actor fails the batch; split it
            mid = len(dids) // 2
            return fetch(client, dids[:mid]) + fetch(client, dids[mid:])
        return []
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--posts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    dids: list[str] = []
    seen = set()
    with open(a.posts) as f:
        for line in f:
            did = json.loads(line)["author"]["did"]
            if did not in seen:
                seen.add(did)
                dids.append(did)

    out = Path(a.out)
    done = set()
    if out.exists():
        with open(out) as f:
            done = {json.loads(l)["did"] for l in f if l.strip()}
    todo = [d for d in dids if d not in done]
    batches = [todo[i : i + 25] for i in range(0, len(todo), 25)]
    print(f"{len(dids)} accounts, {len(done)} done, {len(batches)} batches to fetch", flush=True)

    t0 = time.time()
    n = 0
    with httpx.Client(timeout=30, headers={"User-Agent": "socialnet-bot-tracker (HackPrinceton research)"}) as client, open(
        out, "a"
    ) as fo, ThreadPoolExecutor(a.workers) as pool:
        for i, profiles in enumerate(pool.map(lambda b: fetch(client, b), batches)):
            for p in profiles:
                fo.write(json.dumps(p) + "\n")
                n += 1
            if i % 50 == 0:
                fo.flush()
                print(f"batch {i}/{len(batches)} profiles {n} {time.time() - t0:.0f}s", flush=True)
    print(f"done: {n} profiles in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

"""Re-pull the story posts from Bluesky search.

Usage:
    python -m src.ingest.bluesky_search --q "jensen huang" --since 2026-11-05T00:00:00Z \
        --until 2026-11-14T00:00:00Z --out data/raw/bsky_jensen_nov5_13.jsonl

Uses app.bsky.feed.searchPosts on the unauthenticated AppView with sort=latest. Cursor paging returns 403
on this endpoint, so it slides `until` back to the oldest createdAt seen on each page. Writes raw post
records (one JSON object per line), de-duplicated by URI. Resumable: restarts from the oldest post on disk.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

API = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def utc(t: str | None) -> str | None:
    """Normalize an ISO timestamp to UTC 'Z' form so string comparison is time comparison.

    createdAt is client-supplied: some posts carry offsets like -03:00 or no zone at all. Comparing those
    as raw strings picks the wrong oldest post and stalls the `until` pager after a few pages.
    """
    if not t:
        return None
    try:
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def post_time(p: dict) -> str | None:
    return utc(p.get("record", {}).get("createdAt")) or utc(p.get("indexedAt"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pages", type=int, default=5000)
    a = ap.parse_args()

    out = Path(a.out)
    seen: set[str] = set()
    a.since, a.until = utc(a.since), utc(a.until)
    until = a.until
    if out.exists():
        oldest = None
        for line in open(out):
            d = json.loads(line)
            seen.add(d["uri"])
            t = post_time(d)
            if t and a.since <= t and (oldest is None or t < oldest):
                oldest = t
        if oldest:
            until = oldest
    print(f"{len(seen)} posts on disk; paging back from {until}", flush=True)

    t0 = time.time()
    with httpx.Client(timeout=30, headers={"User-Agent": "socialnet-bot-tracker (HackPrinceton research)"}) as client, open(
        out, "a"
    ) as fo:
        for page in range(a.max_pages):
            params = {"q": a.q, "sort": "latest", "limit": 100, "since": a.since, "until": until}
            r = None
            for attempt in range(6):
                r = client.get(API, params=params)
                if r.status_code == 200:
                    break
                time.sleep(2 ** attempt)
            else:
                print(f"giving up at page {page}: HTTP {r.status_code if r else 'none'}", flush=True)
                break
            posts = r.json().get("posts", [])
            new = [p for p in posts if p["uri"] not in seen]
            for p in new:
                seen.add(p["uri"])
                fo.write(json.dumps(p) + "\n")
            # ignore backdated createdAt values outside the window, so one bad clock can't skip days
            times = [t for t in (post_time(p) for p in posts) if t and a.since <= t <= until]
            if not posts or not times:
                break
            oldest = min(times)
            if oldest >= until and not new:
                break  # no progress
            until = oldest
            if page % 25 == 0:
                fo.flush()
                print(f"page {page}: {len(seen)} posts, until={until} ({time.time() - t0:.0f}s)", flush=True)
    print(f"done: {len(seen)} posts in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

"""Pull profiles and histories for audience accounts that are not story authors (M5 input).

Usage:
    python -m src.archetypes.pull_audience --max-controls 6000

Likers, reposters and quoters of story posts are often not authors of story posts, so the story pull has no
profile or history for them. This pulls them, prioritized as the README asks: every account that engaged
with a likely automated post first (amplifier candidates), then a random sample of accounts that engaged
only with human posts (control candidates). Reuses the ingest fetchers (read-only AppView, backoff on 429).
Resumable; writes data/raw/audience_profiles.jsonl and data/raw/audience_history.jsonl.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import polars as pl

from src.config import AUTOMATED_MIN, HUMAN_MAX
from src.ingest.bluesky_history import fetch as fetch_history
from src.ingest.bluesky_profiles import fetch as fetch_profiles

UA = {"User-Agent": "socialnet-bot-tracker (HackPrinceton research)"}


def done_dids(path: Path) -> set[str]:
    return {json.loads(l)["did"] for l in open(path) if l.strip()} if path.exists() else set()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--interactions", default="data/processed/interactions.parquet")
    ap.add_argument("--scores", default="data/processed/artifacts/bot_scores.parquet")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--max-controls", type=int, default=6000)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    raw = Path(a.raw)
    inter = pl.read_parquet(a.interactions)
    scores = pl.read_parquet(a.scores).select("account_id", "p_automated")
    known = set(scores["account_id"].to_list())
    p_by = dict(scores.iter_rows())

    inter = inter.with_columns(pl.col("dst_account_id").replace_strict(p_by, default=None, return_dtype=pl.Float64).alias("p_dst"))
    bot_eng = set(inter.filter(pl.col("p_dst") >= AUTOMATED_MIN)["src_account_id"].to_list())
    human_eng = set(inter.filter(pl.col("p_dst") < HUMAN_MAX)["src_account_id"].to_list())
    amp_c = sorted(bot_eng - known)
    ctl_c = sorted(human_eng - bot_eng - known)
    random.Random(42).shuffle(ctl_c)
    todo = amp_c + ctl_c[: a.max_controls]
    print(f"audience: {len(bot_eng):,} engaged a likely automated post ({len(amp_c):,} not profiled); "
          f"{len(human_eng - bot_eng):,} engaged only human posts ({len(ctl_c):,} not profiled); pulling {len(todo):,}", flush=True)

    t0 = time.time()
    prof_out, hist_out = raw / "audience_profiles.jsonl", raw / "audience_history.jsonl"
    have = done_dids(prof_out)
    batches = [b for b in (todo[i : i + 25] for i in range(0, len(todo), 25)) if any(d not in have for d in b)]
    with httpx.Client(timeout=30, headers=UA) as client, open(prof_out, "a") as fo, ThreadPoolExecutor(4) as pool:
        for i, profs in enumerate(pool.map(lambda b: fetch_profiles(client, b), batches)):
            for p in profs:
                fo.write(json.dumps(p) + "\n")
            if i % 50 == 0:
                fo.flush()
                print(f"profiles batch {i}/{len(batches)} {time.time() - t0:.0f}s", flush=True)

    dids = [d for d in (json.loads(l)["did"] for l in open(prof_out) if l.strip())]
    have_h = done_dids(hist_out)
    left = [d for d in dids if d not in have_h]
    with httpx.Client(timeout=30, headers=UA) as client, open(hist_out, "a") as fo, ThreadPoolExecutor(a.workers) as pool:
        for i, row in enumerate(pool.map(lambda d: fetch_history(client, d, a.limit), left)):
            fo.write(json.dumps(row) + "\n")
            if i % 500 == 0:
                fo.flush()
                print(f"histories {i}/{len(left)} {time.time() - t0:.0f}s", flush=True)
    print(f"done: {len(dids):,} audience profiles with histories in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

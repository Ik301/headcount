"""Score every story account with the trained bot model (M2 batch entry point, run by Hermes on the VM).

Usage:
    python -m src.bots.score_corpus --raw data/raw --out data/processed/artifacts

Writes bot_scores.parquet (README table: account_id, p_automated, coord_cluster_id, reasons, model_version)
to a temp file and renames it, so a crash never leaves a half-written table. Also writes coord_clusters.json
(clusters with plain-language reasons and evidence, from src.bots.coordination.find_clusters). Local tables keep DIDs as account_id; hashing happens at export.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import polars as pl

from src.bots.coordination import find_clusters, posts_from_inputs
from src.bots.score import load_model, model_version, score_accounts
from src.bots.train import load_raw


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--posts-file", default="bsky_jensen_nov5_13.jsonl")
    ap.add_argument("--model", default=None, help="default data/processed/artifacts/bot_model.joblib")
    ap.add_argument("--out", default="data/processed/artifacts")
    a = ap.parse_args()
    t0 = time.time()
    profiles, histories, story = load_raw(Path(a.raw), a.posts_file)
    model = load_model(a.model)
    scores = score_accounts(model, profiles, histories, story)
    v = model_version(model)
    cposts = posts_from_inputs(histories, story)
    clusters = find_clusters(cposts)
    cid = {d: c["cluster_id"] for c in clusters for d in c["dids"]}
    df = pl.DataFrame(
        {
            "account_id": [s["did"] for s in scores],
            "p_automated": [float(s["p_automated"]) for s in scores],
            "coord_cluster_id": pl.Series([cid.get(s["did"]) for s in scores], dtype=pl.Utf8),
            "reasons": [s["reasons"] for s in scores],
            "model_version": [v] * len(scores),
        }
    )
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "bot_scores.parquet.tmp"
    df.write_parquet(tmp)
    os.replace(tmp, out / "bot_scores.parquet")
    # clusters with reasons and evidence for the evidence drawer and "show the bots" (local: holds DIDs)
    tmp = out / "coord_clusters.json.tmp"
    tmp.write_text(json.dumps({"model_version": v, "clusters": clusters}))
    os.replace(tmp, out / "coord_clusters.json")
    print(
        f"scored {df.height:,} accounts with {v} in {time.time() - t0:.0f}s; {len(clusters)} coordination clusters; "
        + ", ".join(f"p>={t}: {(df['p_automated'] >= t).mean():.1%}" for t in (0.3, 0.5, 0.7, 0.9))
    )


if __name__ == "__main__":
    main()

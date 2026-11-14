"""Score every story account with the current bot model and archetype module (Muse's or the stubs).

Usage:
    python -m src.pipeline.corpus_scores --raw data/raw --out data/processed/artifacts

Writes bot_scores.parquet (account_id, p_automated, reasons, model) and user_archetype.parquet
(account_id, archetype_id, label), and prints recall@k on self-labeled bots as a sanity check
(the labeled bots are not held out here; Muse's eval report is the real number).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from src.integration import archetypes, bots, versions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/processed/artifacts")
    ap.add_argument("--posts-file", default="bsky_jensen_nov5_13.jsonl")
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    profiles = [json.loads(l) for l in open(raw / "profiles.jsonl") if l.strip()]
    histories = {}
    for l in open(raw / "history.jsonl"):
        d = json.loads(l)
        histories[d["did"]] = d.get("items", [])
    story = {}
    labeled = set()
    for l in open(raw / a.posts_file):
        d = json.loads(l)
        story.setdefault(d["author"]["did"], []).append(d)
        if any(x.get("val") in ("bot", "!bot") for x in (d["author"].get("labels") or [])):
            labeled.add(d["author"]["did"])

    model = bots.load_model()
    scores = bots.score_accounts(model, profiles, histories, story)
    v = versions()
    bs = pl.DataFrame(
        {
            "account_id": [s["did"] for s in scores],
            "p_automated": [float(s["p_automated"]) for s in scores],
            "reasons": [s["reasons"] for s in scores],
            "model": [v["bots"]] * len(scores),
        }
    )
    bs.write_parquet(out / "bot_scores.parquet")

    arch = archetypes.load_archetypes()
    asg = archetypes.assign(arch, profiles, histories)
    pl.DataFrame(asg).rename({"did": "account_id"}).write_parquet(out / "user_archetype.parquet")

    y = np.array([d in labeled for d in bs["account_id"].to_list()])
    o = np.argsort(-bs["p_automated"].to_numpy())
    print(f"modules: {v}")
    print(f"accounts scored: {bs.height}; labeled bots: {y.sum()}; share p>=0.5: {(bs['p_automated'] >= 0.5).mean():.3f}")
    for k in (50, 100, 200, 500):
        print(f"recall@{k} on labeled bots (not held out): {y[o[:k]].sum() / max(y.sum(), 1):.3f}")


if __name__ == "__main__":
    main()

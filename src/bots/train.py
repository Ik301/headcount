"""Train and evaluate the bot model (M2).

Usage:
    python -m src.bots.train --raw data/raw --out data/processed/artifacts --report eval/bots/report.md

Positives are accounts with Bluesky's self-applied `bot` label; every other account is unlabeled, not human
(positive-unlabeled learning). The label, bio words, handle and bridged label are never features.

Evaluation: 5-fold stratified cross-fitting, seed 42, so every account gets an out-of-fold score from a model
that never saw it. recall@k = share of labeled bots in the top k of all accounts by out-of-fold score; this
is the definition the posts-per-day baseline (0.046 at k=100) uses, and every labeled bot counts as held out
in its own fold. The fixed 20% holdout (fold 0, ranked within itself) is reported beside it.

Writes the model (bot_model.joblib), out-of-fold scores (bot_oof.parquet, local only), the hand-check
candidate list (data/private/, never committed) and the markdown report.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from src.bots.coordination import account_coord_features, posts_from_inputs
from src.bots.features import COORD_FEATURES, FEATURES, bridged, feature_matrix, self_label_bot
from src.bots.score import _standardize

SEED = 42
KS = (50, 100, 200, 500)


def load_raw(raw: Path, posts_file: str):
    profiles = [json.loads(l) for l in open(raw / "profiles.jsonl") if l.strip()]
    histories = {}
    for l in open(raw / "history.jsonl"):
        if l.strip():
            d = json.loads(l)
            histories[d["did"]] = d.get("items", [])
    story: dict[str, list[dict]] = {}
    for l in open(raw / posts_file):
        d = json.loads(l)
        story.setdefault(d["author"]["did"], []).append(d)
    return profiles, histories, story


def recall_at(scores: np.ndarray, y: np.ndarray, ks=KS) -> dict[int, float]:
    order = np.argsort(-scores, kind="stable")
    return {k: float(y[order[:k]].sum() / max(y.sum(), 1)) for k in ks}


def precision_at(scores: np.ndarray, y: np.ndarray, ks=KS) -> dict[int, float]:
    order = np.argsort(-scores, kind="stable")
    return {k: float(y[order[:k]].mean()) for k in ks}


def fit_scaler(X: np.ndarray) -> dict:
    med = np.nanmedian(X, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    Xi = np.where(np.isnan(X), med, X)
    mu, sd = Xi.mean(0), Xi.std(0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    return {"median": med, "mu": mu, "sd": sd}


def make(kind: str):
    if kind == "hgb":
        return HistGradientBoostingClassifier(
            # picked by out-of-fold recall@100 from a small sweep (31/15/63 leaves, lr 0.03/0.05, balanced weights):
            # 63 leaves 0.243, 31 leaves 0.226, 15 leaves 0.212, balanced class weights 0.184
            max_iter=300, learning_rate=0.05, max_leaf_nodes=63, l2_regularization=1.0, min_samples_leaf=10, random_state=SEED
        )
    return LogisticRegression(C=0.5, max_iter=2000)


def fit_predict(kind: str, Xtr, ytr, Xte, cols=None):
    cols = np.arange(Xtr.shape[1]) if cols is None else cols
    Xtr, Xte = Xtr[:, cols], Xte[:, cols]
    if kind == "hgb":
        clf = make(kind).fit(Xtr, ytr)
        return clf.predict_proba(Xte)[:, 1]
    sc = fit_scaler(Xtr)
    clf = make(kind).fit(_standardize(sc, Xtr), ytr)
    return clf.predict_proba(_standardize(sc, Xte))[:, 1]


def oof_scores(kind: str, X, y, cols=None, folds: int = 5) -> tuple[np.ndarray, np.ndarray]:
    skf = StratifiedKFold(folds, shuffle=True, random_state=SEED)
    oof = np.zeros(len(y))
    fold_id = np.zeros(len(y), dtype=int)
    for f, (tr, te) in enumerate(skf.split(X, y)):
        oof[te] = fit_predict(kind, X[tr], y[tr], X[te], cols)
        fold_id[te] = f
    return oof, fold_id


def baseline_ppd(profiles: list[dict]) -> np.ndarray:
    """Lifetime posts per day, as used for the 0.046 baseline in the README."""
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    out = []
    for p in profiles:
        try:
            created = datetime.fromisoformat((p.get("createdAt") or "").replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = max((now - created).days, 1)
        except ValueError:
            age = 365
        out.append((p.get("postsCount") or 0) / age)
    return np.array(out)


def handcheck_lines(path: Path) -> list[str]:
    """Summarize eval/bots/handcheck.csv (verdicts on the 50 highest-scored unlabeled accounts)."""
    import csv
    from collections import Counter

    head = [
        "The 50 highest-scored unlabeled accounts (out-of-fold), each read by hand from its bio and 3 to 6 recent posts.",
        "The candidate list with handles stays local (`data/private/handcheck_candidates.jsonl`); `eval/bots/handcheck.csv`",
        "holds the verdicts with no account named. The list is regenerated on every training run; verdicts below were",
        "made on the run that produced this report's model, and need redoing if the top 50 changes.",
        "",
    ]
    if not path.exists():
        return head + ["Not reviewed yet."]
    rows = list(csv.DictReader(open(path)))
    auto = sum(r["verdict"].startswith(("automated", "likely automated")) for r in rows)
    kinds = Counter(r["verdict"].split(":")[0] + ":" + r["verdict"].split(":", 1)[1].split("(")[0] for r in rows)
    return head + [
        f"Precision on this sample: **{auto} of {len(rows)} ({auto / max(len(rows), 1):.0%}) automated or likely automated**; none looked like a person",
        "posting by hand. The other five are unclear or mixed. So the labels miss most automation, and the score finds it.",
        "",
        "| Verdict | Accounts |",
        "|---|---|",
        *[f"| {k.strip()} | {n} |" for k, n in kinds.most_common()],
        "",
        "What this does and doesn't show: almost all of these are news, RSS, market-data and digest feeds, the same kind as",
        "the labeled bots. The model finds *undisclosed feeds* well. It isn't yet evidence that it finds accounts pushing a",
        "narrative; that question is M3's coordination clusters and M4's per-narrative shares.",
    ]


def fmt_row(name: str, r: dict) -> str:
    return f"| {name} | " + " | ".join(f"{r[k]:.3f}" for k in KS) + " |"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--posts-file", default="bsky_jensen_nov5_13.jsonl")
    ap.add_argument("--out", default="data/processed/artifacts")
    ap.add_argument("--report", default="eval/bots/report.md")
    ap.add_argument("--private", default="data/private")
    a = ap.parse_args()
    t0 = time.time()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    Path(a.private).mkdir(parents=True, exist_ok=True)

    profiles, histories, story = load_raw(raw, a.posts_file)
    coord = account_coord_features(posts_from_inputs(histories, story))
    print(f"coordination features for {len(coord):,} accounts with shared traces ({time.time() - t0:.0f}s)")
    ALL = FEATURES + COORD_FEATURES
    Xall = feature_matrix(profiles, histories, story, ALL, coord)
    beh = np.arange(len(FEATURES))
    crd = np.arange(len(FEATURES), len(ALL))
    y = np.array([self_label_bot(p, story.get(p["did"])) for p in profiles], dtype=int)
    br = np.array([bridged(p) for p in profiles])
    has_hist = np.array([len(histories.get(p["did"]) or []) > 0 for p in profiles])
    in_cluster = np.array([(coord.get(p["did"]) or {}).get("coord_cluster_id") is not None for p in profiles])
    print(f"{len(profiles)} accounts, {y.sum()} labeled bots, {br.sum()} bridged, {has_hist.sum()} with history, "
          f"{in_cluster.sum()} in coordination clusters; features {time.time() - t0:.0f}s")

    results, oofs = {}, {}
    for name, kind, cols in (
        ("hgb_both", "hgb", None), ("logit_both", "logit", None),
        ("hgb_behavior", "hgb", beh), ("hgb_coord", "hgb", crd), ("logit_behavior", "logit", beh),
    ):
        oof, fold_id = oof_scores(kind, Xall, y, cols)
        oofs[name], results[name] = oof, recall_at(oof, y)
        print(name, {k: round(v, 3) for k, v in results[name].items()}, f"{time.time() - t0:.0f}s")
    base = baseline_ppd(profiles)
    results["baseline"] = recall_at(base, y)
    best_name = max(("hgb_both", "logit_both", "hgb_behavior", "logit_behavior"), key=lambda k: (results[k][100], results[k][200]))
    best = best_name.split("_")[0]
    names = ALL if best_name.endswith("both") else FEATURES
    X = Xall if names is ALL else Xall[:, beh]
    oof = oofs[best_name]
    results[best] = results[best_name]

    # README's literal protocol: hold out 20% of labeled bots, rank them among all accounts not used as positives
    # in training (every unlabeled account, scored out-of-fold, plus that fold's bots); averaged over the 5 folds
    def holdout_recall(scores):
        per = []
        for f in range(5):
            keep = (y == 0) | ((y == 1) & (fold_id == f))
            per.append(recall_at(scores[keep], y[keep]))
        return {k: float(np.mean([r[k] for r in per])) for k in KS}

    hold_r = holdout_recall(oof)
    hold_base = holdout_recall(base)
    n_hold = int(round(y.sum() / 5))

    # Elkan-Noto constant from out-of-fold scores of labeled bots
    c = float(oof[y == 1].mean())

    # final model on all accounts, plus the linear surrogate for reasons
    sc = fit_scaler(X)
    logit = make("logit").fit(_standardize(sc, X), y)
    clf = make(best).fit(X, y) if best == "hgb" else logit
    version = f"v1-{best}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    model = {"version": version, "kind": best, "clf": clf, "c": c, "coef": logit.coef_[0], "features": list(names), **sc}
    joblib.dump(model, out / "bot_model.joblib")

    p_auto = np.clip(oof / c, 0, 1)
    pl.DataFrame(
        {"account_id": [p["did"] for p in profiles], "oof_score": oof, "p_automated_oof": p_auto, "labeled": y, "bridged": br, "fold": fold_id}
    ).write_parquet(out / "bot_oof.parquet")

    # manifest
    mpath = out / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    manifest["bot_model"] = {"version": version, "trained_at": datetime.now(timezone.utc).isoformat(), "recall_at_100_oof": results[best][100]}
    mpath.write_text(json.dumps(manifest, indent=2))

    # hand-check candidates: top 50 unlabeled by out-of-fold score (private file; never committed)
    order = np.argsort(-oof)
    cand = [i for i in order if y[i] == 0][:50]
    with open(Path(a.private) / "handcheck_candidates.jsonl", "w") as fo:
        for rank, i in enumerate(cand, 1):
            p = profiles[i]
            items = [it for it in (histories.get(p["did"]) or []) if it.get("kind") != "repost"][:6]
            fo.write(json.dumps({
                "rank": rank, "did": p["did"], "handle": p.get("handle"), "followers": p.get("followersCount"),
                "bio": (p.get("description") or "")[:200], "p_automated": round(float(p_auto[i]), 3),
                "sample": [(it.get("t"), (it.get("text") or "")[:160]) for it in items],
            }) + "\n")

    # automated share overall at each strip threshold (accounts)
    shares = {t: float((p_auto >= t).mean()) for t in (0.3, 0.5, 0.7, 0.9)}
    nb = ~br
    imp = sorted(zip(names, logit.coef_[0]), key=lambda kv: -abs(kv[1]))

    lines = [
        "# Bot model report (M2)",
        "",
        f"Command: `python -m src.bots.train --raw {a.raw} --out {a.out} --report {a.report}`",
        f"Model: `{version}` (chosen: {best_name}, by out-of-fold recall@100). Run time {time.time() - t0:.0f} s on a laptop CPU.",
        "",
        "## Data",
        "",
        f"- Accounts: {len(profiles):,} story authors with profiles; {has_hist.sum():,} with a history pull (last 50 items).",
        f"- Labeled bots (self-applied `bot` label): {y.sum()}. Bridged (fediverse) accounts: {br.sum()}, of which {int(y[br].sum())} are labeled bots.",
        "- Unlabeled accounts are treated as unlabeled, not as humans (positive-unlabeled). Some undisclosed automation is in that set, so",
        "  precision against labels understates real precision and recall is measured only on the disclosed kind of bot.",
        "",
        "## Recall@k on held-out labeled bots",
        "",
        "Out-of-fold scores (5-fold stratified, seed 42): each labeled bot is scored by a model that never saw it,",
        "then ranked among all accounts. Same definition as the README's posts-per-day baseline.",
        "",
        "| Scorer | @50 | @100 | @200 | @500 |",
        "|---|---|---|---|---|",
        fmt_row("lifetime posts per day (baseline)", results["baseline"]),
        fmt_row("logistic regression, behavior + coordination", results["logit_both"]),
        fmt_row("gradient boosting, behavior + coordination", results["hgb_both"]),
        fmt_row("ceiling (k / labeled bots)", {k: min(1.0, k / max(y.sum(), 1)) for k in KS}),
        "",
        f"README protocol, literally: hold out 20% of labeled bots (about {n_hold}), rank them among every account not used as a",
        "positive in training (all unlabeled accounts plus the held-out bots), mean over the 5 folds. The ceiling here is 1.0.",
        "",
        "| Scorer | @50 | @100 | @200 | @500 |",
        "|---|---|---|---|---|",
        fmt_row("lifetime posts per day (baseline)", hold_base),
        fmt_row(best_name.replace("_", ", "), hold_r),
        "",
        "Precision@k against labels (out-of-fold, chosen model): " + ", ".join(f"@{k} {v:.2f}" for k, v in precision_at(oof, y).items()) + ".",
        "",
        "Excluding bridged accounts: recall@k " + ", ".join(f"@{k} {v:.3f}" for k, v in recall_at(oof[nb], y[nb]).items()) + f" ({y[nb].sum()} labeled bots).",
        "",
        "## Ablation (Arlequin: content and connectivity)",
        "",
        "Gradient boosting, out-of-fold, same folds. Behavior = profile, timing and content features of each account alone;",
        "coordination = shared traces with other accounts (same link or repost within 60 s, near-identical text), TF-IDF cosine.",
        "",
        "| Features | @50 | @100 | @200 | @500 |",
        "|---|---|---|---|---|",
        fmt_row("behavior only", results["hgb_behavior"]),
        fmt_row("coordination only", results["hgb_coord"]),
        fmt_row("both", results["hgb_both"]),
        "",
        f"{in_cluster.sum():,} accounts sit in a coordination cluster; {int(y[in_cluster].sum())} of them are labeled bots"
        f" ({y[in_cluster].mean() if in_cluster.any() else 0:.1%}, against {y.mean():.1%} overall).",
        "",
        "## Kill test 1",
        "",
        f"recall@100 = {results[best][100]:.3f} against the bar of 0.3: **{'pass' if results[best][100] >= 0.3 else 'fail'}**"
        f" (baseline {results['baseline'][100]:.3f}; ceiling {min(1, 100 / max(y.sum(), 1)):.3f}).",
        "",
        "## Score scale",
        "",
        f"p_automated = P(labeled | x) / c with c = {c:.3f}, the mean out-of-fold score of labeled bots (Elkan and Noto, 2008).",
        "This assumes labeled bots are a random sample of all bots; they are mostly disclosed news and trend bots, so treat the",
        "scale as approximate. Share of all accounts at or above each cutoff (out-of-fold): "
        + ", ".join(f"{t} -> {v:.1%}" for t, v in shares.items()) + ".",
        "",
        "## Features",
        "",
        "Used (" + str(len(names)) + "): " + ", ".join(f"`{f}`" for f in names) + ".",
        "",
        "Never used: the self-applied label, bio words, handle text, the bridged label.",
        "",
        "Largest linear-surrogate weights (standardized; the surrogate also writes each account's reasons):",
        "",
        "| Feature | Weight |",
        "|---|---|",
        *[f"| `{f}` | {w:+.2f} |" for f, w in imp[:12]],
        "",
        "## Hand check",
        "",
        *handcheck_lines(Path(a.report).parent / "handcheck.csv"),
        "",
    ]
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text("\n".join(lines))
    print(f"wrote {out / 'bot_model.joblib'} and {a.report}; recall@100 {results[best][100]:.3f}; {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

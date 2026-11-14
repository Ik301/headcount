"""Label posts with a fixed narrative taxonomy and side, then extend the labels to every post.

Usage:
    python -m src.narratives.label --dir data/processed/narratives --sample 4000

Step 1: an LLM (DeepSeek chat, OpenAI-compatible API, key in DEEPSEEK_API_KEY) labels a stratified sample of
unique posts, 25 per call. Step 2: a multinomial logistic regression on the bge-small embeddings learns those
labels and labels everything else (cheap: no LLM call per post). Held-out accuracy against the LLM labels is
written to eval/narratives/report.md. Isaac's hand labels are scored separately by eval_hand.py.

Outputs in --dir: llm_labels.parquet, post_narrative.parquet (post_id, narrative_id, side, prob, source).
"""
import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import polars as pl

NARRATIVES = {
    "n1": "Spy plot and national security: the alleged Chinese intelligence link, FBI or congressional probes of the spy angle, chips reaching China",
    "n2": "The affairs as personal misconduct: reports of the affairs with employees, his admission, workplace conduct",
    "n3": "Trump administration and politics: Trump, Lutnick, Commerce, Congress, partisan blame, Trump suggesting Tim Cook",
    "n4": "Board, resignation and succession: board probe, ouster report, resignation, interim CEO Colette Kress, who replaces him",
    "n5": "Stock, market and lawsuits: share price, market value, AI bubble, investor class actions",
    "n6": "Defending Huang: smear campaign, witch hunt, he is vital to the AI race, private life is irrelevant, sympathy",
    "n7": "Jokes and memes: humor about the affairs, the leather jacket, puns",
    "n0": "No narrative: bare links, trending-word lists, unrelated or unclear",
}
SIDES = ["pro_huang", "anti_huang", "neutral_news", "humor", "other"]

PROMPT = """You label Bluesky posts about Jensen Huang leaving Nvidia (Nov 2026). Posts may be in any language.
Narratives:
{narr}
Sides: pro_huang (defends or sympathizes with Huang), anti_huang (criticizes or condemns him), neutral_news (reports without taking a side), humor (mainly a joke), other.
Return only JSON: {{"labels": [{{"i": <index>, "n": "<narrative id>", "s": "<side>"}}, ...]}} with one entry per post.
Posts:
{posts}"""


def call(client: httpx.Client, batch: list[tuple[int, str]]) -> list[dict]:
    narr = "\n".join(f"{k}: {v}" for k, v in NARRATIVES.items())
    posts = "\n".join(f"[{i}] {t[:400]}".replace("\n", " ") for i, t in batch)
    body = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": PROMPT.format(narr=narr, posts=posts)}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(5):
        try:
            r = client.post("https://api.deepseek.com/chat/completions", json=body)
            if r.status_code == 200:
                out = json.loads(r.json()["choices"][0]["message"]["content"])["labels"]
                return [o for o in out if o.get("n") in NARRATIVES and o.get("s") in SIDES]
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            pass
        time.sleep(2 ** attempt)
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/processed/narratives")
    ap.add_argument("--sample", type=int, default=4000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--llm-only", action="store_true", help="only write llm_labels.parquet")
    ap.add_argument("--all", action="store_true", help="LLM-label every unique text not yet labeled (the classifier then only fills gaps)")
    a = ap.parse_args()
    d = Path(a.dir)
    full = pl.read_parquet(d / "posts_clusters.parquet").with_columns(
        pl.col("text").str.replace_all(r"https?://\S+", "").str.to_lowercase().str.strip_chars().alias("norm")
    )
    order = pl.read_parquet(d / "embed_index.parquet")  # eidx, norm, text in embedding row order
    order = order.join(full.unique(subset="norm").select("norm", "cluster"), on="norm", how="left")

    llm_path = d / "llm_labels.parquet"
    lab = pl.read_parquet(llm_path) if llm_path.exists() else pl.DataFrame(schema={"eidx": pl.Int64, "narrative_id": pl.Utf8, "side": pl.Utf8})
    if a.all:
        picks = [i for i in order["eidx"].to_list() if i not in set(lab["eidx"].to_list())]
    elif lab.height == 0:
        rng = np.random.default_rng(0)
        per = max(1, a.sample // max(1, order["cluster"].n_unique()))
        picks = []
        for c in order["cluster"].unique().to_list():
            sub = order.filter(pl.col("cluster") == c)
            k = min(sub.height, per if c != -1 else per * 4)
            picks += sub["eidx"].to_list() if sub.height <= k else rng.choice(sub["eidx"].to_numpy(), k, replace=False).tolist()
        picks = picks[: a.sample]
    else:
        picks = []
    if picks:
        texts = dict(zip(order["eidx"].to_list(), order["text"].to_list()))
        batches = [[(i, texts[i]) for i in picks[j : j + 25]] for j in range(0, len(picks), 25)]
        key = os.environ["DEEPSEEK_API_KEY"]
        t0 = time.time()
        rows = []
        with httpx.Client(timeout=120, headers={"Authorization": f"Bearer {key}"}) as client, ThreadPoolExecutor(a.workers) as pool:
            def save() -> None:
                nonlocal lab
                new = pl.DataFrame(rows, schema={"eidx": pl.Int64, "narrative_id": pl.Utf8, "side": pl.Utf8}).filter(pl.col("eidx").is_in(picks))
                merged = pl.concat([lab.cast({"eidx": pl.Int64}), new]).unique(subset="eidx", keep="first")
                merged.write_parquet(str(llm_path) + ".tmp")
                os.replace(str(llm_path) + ".tmp", llm_path)

            for k, res in enumerate(pool.map(lambda b: call(client, b), batches)):
                rows += [{"eidx": int(o["i"]), "narrative_id": o["n"], "side": o["s"]} for o in res]
                if k % 50 == 0:
                    print(f"batch {k}/{len(batches)} labels {len(rows)} {time.time() - t0:.0f}s", flush=True)
                    save()  # incremental, so a killed run keeps its labels
            save()
        lab = pl.read_parquet(llm_path)
        print(f"LLM labels now: {lab.height} ({len(rows)} new in {time.time() - t0:.0f}s)", flush=True)

    if a.llm_only:
        return
    emb = np.load(d / "embeddings.npy")
    if order.height != emb.shape[0]:
        raise SystemExit(f"embedding rows {emb.shape[0]} != embed_index rows {order.height}")
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    X = emb[lab["eidx"].to_numpy()]
    report = ["# Narrative labeling report\n", f"LLM-labeled sample: {lab.height} unique posts (DeepSeek chat, 25 per call).\n"]
    preds = {}
    for col in ("narrative_id", "side"):
        y = lab[col].to_numpy()
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
        clf = LogisticRegression(max_iter=2000, C=4.0).fit(Xtr, ytr)
        acc = (clf.predict(Xte) == yte).mean()
        report.append(f"- {col}: held-out accuracy vs LLM labels {acc:.3f} (n={len(yte)})")
        clf = LogisticRegression(max_iter=2000, C=4.0).fit(X, y)
        proba = clf.predict_proba(emb)
        preds[col] = (clf.classes_[proba.argmax(1)], proba.max(1))
    order = order.with_columns(
        pl.Series("narrative_id", preds["narrative_id"][0]),
        pl.Series("prob", preds["narrative_id"][1]),
        pl.Series("side", preds["side"][0]),
    )
    # LLM label wins where we have one
    order = order.join(lab.rename({"narrative_id": "n_llm", "side": "s_llm"}), on="eidx", how="left").with_columns(
        pl.when(pl.col("n_llm").is_not_null()).then(pl.col("n_llm")).otherwise(pl.col("narrative_id")).alias("narrative_id"),
        pl.when(pl.col("s_llm").is_not_null()).then(pl.col("s_llm")).otherwise(pl.col("side")).alias("side"),
        pl.when(pl.col("n_llm").is_not_null()).then(pl.lit("llm")).otherwise(pl.lit("classifier")).alias("source"),
    )
    pn = full.join(order.select("norm", "narrative_id", "side", "prob", "source"), on="norm", how="left").select(
        pl.col("uri").alias("post_id"), "narrative_id", "side", "prob", "source"
    )
    pn.write_parquet(d / "post_narrative.parquet")
    counts = pn.group_by("narrative_id").len().sort("len", descending=True)
    report.append("\nPosts per narrative (all 44k text posts):\n")
    for nid, n in counts.iter_rows():
        report.append(f"- {nid} ({NARRATIVES.get(nid, '?').split(':')[0]}): {n}")
    sides = pn.group_by("side").len().sort("len", descending=True)
    report.append("\nPosts per side:\n")
    for s, n in sides.iter_rows():
        report.append(f"- {s}: {n}")
    out = Path("eval/narratives")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()

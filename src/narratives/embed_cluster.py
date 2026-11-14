"""Embed story posts and cluster them into candidate narratives.

Usage:
    python -m src.narratives.embed_cluster --posts data/raw/bsky_jensen_nov5_13.jsonl --outdir data/processed/narratives

Steps: dedupe exact repeats, embed with BAAI/bge-small-en-v1.5 (CPU), UMAP to 10 dims, HDBSCAN.
Writes embeddings.npy, posts_clusters.parquet (uri, cluster, text, created_at, author_did) and
clusters.md (size, top terms, sample posts per cluster) for a person to name.
"""
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
import polars as pl

STOP = set(
    "the a an and or of to in on for is are was were be been it its this that with as at by from has have had not but "
    "he she they his her their them you your i we our us my me so if just about what who will would can could do does did "
    "jensen huang nvidia nvda ceo https http www com amp rt more than all also into out up over after now new he's it's".split()
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--posts", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--min-cluster", type=int, default=150)
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for line in open(a.posts):
        d = json.loads(line)
        rec = d.get("record", {})
        text = (rec.get("text") or "").strip()
        if len(text) < 15:
            continue
        rows.append({"uri": d["uri"], "author_did": d["author"]["did"], "created_at": rec.get("createdAt"), "text": text})
    df = pl.DataFrame(rows)
    df = df.with_columns(pl.col("text").str.replace_all(r"https?://\S+", "").str.to_lowercase().str.strip_chars().alias("norm"))
    uniq = df.unique(subset="norm", keep="first")
    print(f"{len(df)} posts, {len(uniq)} unique texts", flush=True)

    from sentence_transformers import SentenceTransformer

    t0 = time.time()
    model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    emb = model.encode(uniq["text"].to_list(), batch_size=128, normalize_embeddings=True, show_progress_bar=False)
    np.save(out / "embeddings.npy", emb)
    print(f"embedded in {time.time() - t0:.0f}s", flush=True)

    import umap
    from sklearn.cluster import HDBSCAN

    t0 = time.time()
    red = umap.UMAP(n_components=10, n_neighbors=30, min_dist=0.0, metric="cosine", random_state=0).fit_transform(emb)
    labels = HDBSCAN(min_cluster_size=a.min_cluster, min_samples=20).fit_predict(red)
    print(f"clustered in {time.time() - t0:.0f}s: {len(set(labels)) - (1 if -1 in labels else 0)} clusters, "
          f"{(labels == -1).mean():.0%} unassigned", flush=True)

    uniq = uniq.with_columns(pl.Series("cluster", labels))
    full = df.join(uniq.select("norm", "cluster"), on="norm", how="left")
    full.drop("norm").write_parquet(out / "posts_clusters.parquet")

    lines = ["# Candidate narratives (for naming)\n"]
    sizes = Counter(full["cluster"].to_list())
    for c, n in sizes.most_common():
        sub = full.filter(pl.col("cluster") == c)
        words = Counter(w for t in sub["text"].to_list() for w in re.findall(r"[a-z][a-z']{2,}", t.lower()) if w not in STOP)
        lines.append(f"## cluster {c}: {n} posts\n")
        lines.append("top terms: " + ", ".join(w for w, _ in words.most_common(15)) + "\n")
        for t in sub.unique(subset="text").sample(min(6, sub.height), seed=0)["text"].to_list():
            lines.append("- " + t.replace("\n", " ")[:220])
        lines.append("")
    (out / "clusters.md").write_text("\n".join(lines))
    print("wrote", out / "clusters.md", flush=True)


if __name__ == "__main__":
    main()

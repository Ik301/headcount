"""Claim retrieval evaluation (M6): score any retriever against the rule-checked claim set.

Usage:
    python -m src.evaluation.retrieval --claims eval/retrieval/claims.csv --report eval/retrieval/report.md

The claim set (eval/retrieval/claims.csv) gives each claim a regex rule (`all_of`: groups joined by `&&`, all
must match). The posts that truly match a claim are the unique story texts its rule matches, in Hermes's
normalization (URLs stripped, lowercased, stripped: src/narratives/embed_cluster.py), so gold items and
retrieved items are the same unit. The gold texts are rebuilt locally from the rules and written to
data/private/ only: post URIs carry account DIDs, so no gold IDs are committed.

Retriever under test: anything returning a ranked list of (norm, sim) for a claim. By default this wraps
src.retrieval.corpus.search_claim (bge-small, query prefix, cosine) over Hermes's embeddings if they exist,
else over a local index built with the same model and the same normalization.

Metrics, per claim then averaged:
  recall@k     |gold ∩ top k| / min(k, |gold|)   (capped, because many claims have hundreds of matches)
  precision@k  |gold ∩ top k| / k
  set metrics  for the matched set the API would report (top 300 with sim >= floor): precision, recall
               against min(300, |gold|), F1; the floor with the best mean F1 is recommended.
"""
from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path

import numpy as np
import polars as pl

KS = (10, 20, 50)
FLOORS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85)
TOP = 300


def norm_frame(posts: pl.DataFrame) -> pl.DataFrame:
    """Hermes's normalization, kept identical so gold and retrieved texts line up."""
    df = posts.with_columns(pl.col("text").str.replace_all(r"https?://\S+", "").str.to_lowercase().str.strip_chars().alias("norm"))
    return df.filter(pl.col("norm").str.len_chars() > 0).unique(subset="norm", keep="first", maintain_order=True)


def load_claims(path: str) -> list[dict]:
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        r["rules"] = [re.compile(g.strip()) for g in r["all_of"].split("&&")]
    return rows


def gold_sets(claims: list[dict], norms: list[str]) -> dict[str, set[str]]:
    return {c["claim_id"]: {t for t in norms if all(g.search(t) for g in c["rules"])} for c in claims}


def default_retriever(posts: pl.DataFrame, cache: Path):
    """Hermes's search_claim over his embeddings if present, else over a local index with the same model."""
    from src.retrieval import corpus as C

    hermes = Path("data/processed/narratives")
    if (hermes / "embeddings.npy").exists():
        corp = C.load(str(hermes))
        source = "Hermes's embeddings (data/processed/narratives)"
    else:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
        cache.mkdir(parents=True, exist_ok=True)
        if (cache / "embeddings.npy").exists():
            emb = np.load(cache / "embeddings.npy")
            index = pl.read_parquet(cache / "embed_index.parquet")
        else:
            uniq = norm_frame(posts).select("norm", "text").with_row_index("eidx")
            t0 = time.time()
            emb = model.encode(uniq["text"].to_list(), batch_size=128, normalize_embeddings=True, show_progress_bar=False)
            np.save(cache / "embeddings.npy", emb)
            uniq.write_parquet(cache / "embed_index.parquet")
            index = uniq
            print(f"embedded {len(uniq):,} unique texts in {time.time() - t0:.0f}s")
        corp = C.Corpus(emb=emb, index=index, model=model)
        source = f"local bge-small index ({cache})"

    def search(text: str) -> list[tuple[str, float]]:
        r = C.search_claim(corp, text, k=TOP, floor=-1.0)
        return list(zip(r["norm"].to_list(), r["sim"].to_list()))

    search.corpus = corp
    return search, source


def variants(corp, claims, gold) -> list[tuple[str, float, float]]:
    """recall@20 (first 20 claims, all 50) for retriever variants H5 could adopt. Diagnostic, not a referee change."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    from src.retrieval.corpus import QUERY_PREFIX

    norms = corp.index["norm"].to_list()
    E = corp.emb
    Q = corp.model.encode([QUERY_PREFIX + c["claim"] for c in claims], normalize_embeddings=True)
    mu = E.mean(0)
    Ec = E - mu
    Ec /= np.linalg.norm(Ec, axis=1, keepdims=True)
    tf = TfidfVectorizer(sublinear_tf=True, min_df=2, stop_words="english", ngram_range=(1, 2)).fit(norms)
    D, T = tf.transform(norms), tf.transform([c["claim"].lower() for c in claims])

    def tfidf(i):
        return (D @ T[i].T).toarray().ravel()

    def centered(i):
        q = Q[i] - mu
        return Ec @ (q / np.linalg.norm(q))

    fns = [
        ("embedding cosine (current `search_claim`)", lambda i: E @ Q[i]),
        ("embedding, mean-centered", centered),
        ("TF-IDF only (word 1-2 grams)", tfidf),
        ("hybrid 0.7 embedding + 0.3 TF-IDF", lambda i: 0.7 * (E @ Q[i]) + 0.3 * tfidf(i)),
        ("hybrid 0.5 embedding + 0.5 TF-IDF", lambda i: 0.5 * (E @ Q[i]) + 0.5 * tfidf(i)),
        ("hybrid 0.3 embedding + 0.7 TF-IDF", lambda i: 0.3 * (E @ Q[i]) + 0.7 * tfidf(i)),
    ]
    out = []
    for name, fn in fns:
        r = []
        for i, c in enumerate(claims):
            g = gold[c["claim_id"]]
            top = np.argsort(-fn(i))[:20]
            r.append(len(g & {norms[j] for j in top}) / min(20, len(g)) if g else np.nan)
        r = np.array(r)
        out.append((name, float(np.nanmean(r[:20])), float(np.nanmean(r))))
    return out


def evaluate(claims, gold, search) -> dict:
    per = []
    for c in claims:
        g = gold[c["claim_id"]]
        t0 = time.time()
        res = search(c["claim"])
        dt = time.time() - t0
        row = {"claim_id": c["claim_id"], "n_gold": len(g), "seconds": dt}
        for f in FLOORS:
            kept = [n for n, s in res if s >= f]
            for k in KS:
                hit = len(g & set(kept[:k]))
                row[f"r{k}@{f}"] = hit / min(k, len(g)) if g else np.nan
                row[f"p{k}@{f}"] = hit / k
            hit = len(g & set(kept))
            prec = hit / len(kept) if kept else 0.0
            rec = hit / min(TOP, len(g)) if g else np.nan
            row[f"setp@{f}"], row[f"setr@{f}"] = prec, rec
            row[f"f1@{f}"] = 2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
            row[f"n@{f}"] = len(kept)
        # with no floor (pure ranking)
        for k in KS:
            hit = len(g & {n for n, _ in res[:k]})
            row[f"r{k}"] = hit / min(k, len(g)) if g else np.nan
        per.append(row)
    return per


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--claims", default="eval/retrieval/claims.csv")
    ap.add_argument("--posts", default="data/processed/posts.parquet")
    ap.add_argument("--report", default="eval/retrieval/report.md")
    ap.add_argument("--cache", default="data/processed/eval_retrieval")
    ap.add_argument("--private", default="data/private")
    a = ap.parse_args()
    t0 = time.time()

    posts = pl.read_parquet(a.posts)
    uniq = norm_frame(posts)
    norms = uniq["norm"].to_list()
    claims = load_claims(a.claims)
    gold = gold_sets(claims, norms)
    Path(a.private).mkdir(parents=True, exist_ok=True)
    pl.DataFrame([{"claim_id": c, "norm": n} for c, s in gold.items() for n in sorted(s)]).write_parquet(Path(a.private) / "retrieval_gold.parquet")

    search, source = default_retriever(posts, Path(a.cache))
    per = pl.DataFrame(evaluate(claims, gold, search))
    first20 = per.head(20)

    def m(df, col):
        return float(df[col].drop_nans().mean())

    top_f1 = max(m(per, f"f1@{f}") for f in FLOORS)
    # highest floor whose F1 is within 0.01 of the best: near-ties go to precision (fewer unrelated posts counted)
    best = max(f for f in FLOORS if m(per, f"f1@{f}") >= top_f1 - 0.01)
    var = variants(search.corpus, claims, gold)
    lines = [
        "# Claim retrieval evaluation (M6)",
        "",
        f"Command: `python -m src.evaluation.retrieval --claims {a.claims} --report {a.report}`",
        f"Retriever: `src.retrieval.corpus.search_claim` (bge-small-en-v1.5 with the query prefix, cosine, top {TOP}) over {source}.",
        f"Corpus: {len(norms):,} unique story texts (Hermes's normalization). Run time {time.time() - t0:.0f} s.",
        "",
        "## The claim set",
        "",
        f"50 claims written from reading the story posts (`eval/retrieval/claims.csv`), not from the narrative labels."
        " Each has a regex rule; its true matches are the unique texts the rule matches (median"
        f" {int(per['n_gold'].median())}, range {per['n_gold'].min()} to {per['n_gold'].max()}).",
        "Rule check: 4 random matches per claim were read by hand (200 in all); **163 of 200 (82%) make the claim**. Six loose",
        "rules were tightened or replaced after a first pass. Rules miss paraphrases, so a retriever that finds a true",
        "paraphrase is scored as wrong; treat precision as a lower bound.",
        "",
        "Gold texts are rebuilt from the rules on each run and kept in `data/private/` (they come from private accounts).",
        "The retriever's builder must not edit this file; corrections go through COMMS (build spec).",
        "",
        "## Recall@k (capped: hits / min(k, matches)), all 50 claims",
        "",
        "| Floor | @10 | @20 | @50 | precision@20 | mean matched (of 300) |",
        "|---|---|---|---|---|---|",
        f"| none (ranking only) | {m(per, 'r10'):.3f} | {m(per, 'r20'):.3f} | {m(per, 'r50'):.3f} | | |",
        *[
            f"| {f:.2f} | {m(per, f'r10@{f}'):.3f} | {m(per, f'r20@{f}'):.3f} | {m(per, f'r50@{f}'):.3f} | {m(per, f'p20@{f}'):.3f} | {m(per, f'n@{f}'):.0f} |"
            for f in FLOORS
        ],
        "",
        "## Choosing the similarity floor",
        "",
        "The API reports shares over the matched set (top 300 above the floor), so the floor trades how much of the claim",
        "is found against how much unrelated text gets counted. Mean over claims:",
        "",
        "| Floor | set precision | set recall | F1 |",
        "|---|---|---|---|",
        *[f"| {f:.2f} | {m(per, f'setp@{f}'):.3f} | {m(per, f'setr@{f}'):.3f} | {m(per, f'f1@{f}'):.3f} |" for f in FLOORS],
        "",
        f"**Recommended floor: {best:.2f}**: the highest floor whose mean F1 is within 0.01 of the best ({top_f1:.3f}); F1 is"
        " nearly flat from 0.50 to 0.70, so the tie goes to precision. bge-small similarities sit high on this corpus (every"
        " post is about Huang), so floors under 0.65 filter almost nothing. `src/config.py` has `SIMILARITY_FLOOR = 0.70`; changing it is a"
        " `[contract]` pull request citing this report.",
        "",
        "## Kill test 4",
        "",
        f"recall@20 of at least 0.6 on the first 20 claims: **{m(first20, f'r20@{best}'):.3f} at floor {best:.2f}**"
        f" ({m(first20, 'r20'):.3f} with no floor) -> **{'pass' if m(first20, f'r20@{best}') >= 0.6 else 'fail'}**."
        f" All 50 claims: {m(per, f'r20@{best}'):.3f}.",
        "",
        f"Latency: median {per['seconds'].median() * 1000:.0f} ms per claim on a laptop CPU (embedding plus search).",
        "",
        "## Why it misses, and a fix for H5 to consider",
        "",
        "Broad claims (resignation, interim CEO, stock drop, board probe) retrieve well. Specific ones fail (blackmail, payout,"
        " Musk's job offer, shorting the stock): every post is about Jensen Huang, so the shared topic dominates the cosine and the"
        " specific words don't move the ranking. Adding a keyword signal fixes most of it:",
        "",
        "| Retriever | recall@20, first 20 claims | recall@20, all 50 |",
        "|---|---|---|",
        *[f"| {n} | {a:.3f} | {b:.3f} |" for n, a, b in var],
        "",
        "Caveats: the gold sets come from keyword rules, which favors TF-IDF, so part of this gain is the referee's own bias;"
        " three weights were tried on these same 50 claims, so expect the best one to do a little worse on new claims. The"
        " 0.5/0.5 hybrid is still the recommendation, and with it kill test 4 would pass. A second, independently written claim"
        " set would settle how much of the gain is real. This is a suggestion for H5 (Hermes owns `src/retrieval/`); the claim set does not change.",
        "",
        "## Per claim (floor " + f"{best:.2f})",
        "",
        "| Claim | Matches | recall@20 | matched set precision |",
        "|---|---|---|---|",
        *[
            f"| {c['claim_id']} {c['claim']} | {r['n_gold']} | {r[f'r20@{best}']:.2f} | {r[f'setp@{best}']:.2f} |"
            for c, r in zip(claims, per.iter_rows(named=True))
        ],
        "",
    ]
    Path(a.report).write_text("\n".join(lines))
    print(f"wrote {a.report}: best floor {best}, recall@20 first-20 {m(first20, f'r20@{best}'):.3f}, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

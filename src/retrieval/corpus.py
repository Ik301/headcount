"""Claim retrieval over the story corpus.

search_claim(text) ranks unique story texts by a hybrid score: 0.5 x embedding cosine (bge-small, query prefix)
+ 0.5 x TF-IDF cosine (word 1-2 grams). This is the recommendation in Muse's retrieval evaluation
(eval/retrieval/report.md): recall@20 on the first 20 claims rises from 0.577 to 0.785. The gold rules are lexical,
so part of that gain is the referee's own bias. Embedding cosine alone is dominated by the shared topic (every post
is about Huang); the keyword signal lets specific claims (blackmail, payout, the email to employees) rank their own
posts first.

Matched set: the top k by hybrid score whose embedding cosine clears the floor (config.SIMILARITY_FLOOR, chosen in
the same report) and which share at least one weighted term with the claim. A negative floor means "ranking only"
(used by the evaluation script): no floor and no term requirement.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from src import config as cfg

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DEFAULT_FLOOR = cfg.SIMILARITY_FLOOR
EMB_WEIGHT = 0.5


@dataclass
class Corpus:
    emb: np.ndarray  # (n_unique, 384), normalized
    index: pl.DataFrame  # eidx, norm, text
    model: Any
    tfidf: Any = None
    tf_matrix: Any = None


def fit_tfidf(norms: list[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer

    tf = TfidfVectorizer(sublinear_tf=True, min_df=2, stop_words="english", ngram_range=(1, 2))
    return tf, tf.fit_transform(norms)


def load(d: str = "data/processed/narratives", model=None) -> Corpus:
    p = Path(d)
    emb = np.load(p / "embeddings.npy")
    index = pl.read_parquet(p / "embed_index.parquet")
    if model is None:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    tf, m = fit_tfidf(index["norm"].to_list())
    return Corpus(emb=emb, index=index, model=model, tfidf=tf, tf_matrix=m)


def search_claim(corpus: Corpus, text: str, k: int = 300, floor: float = DEFAULT_FLOOR) -> pl.DataFrame:
    """Returns eidx, norm, text, sim (embedding cosine) and score (hybrid) for the matched set, best first."""
    q = corpus.model.encode([QUERY_PREFIX + text], normalize_embeddings=True)[0]
    cos = corpus.emb @ q
    if corpus.tfidf is not None:
        qv = corpus.tfidf.transform([" ".join(text.lower().split())])
        lex = np.asarray((corpus.tf_matrix @ qv.T).todense()).ravel()
        score = EMB_WEIGHT * cos + (1 - EMB_WEIGHT) * lex
    else:
        lex, score = None, cos
    if floor < 0:
        cand = np.arange(len(cos))
    else:
        keep = cos >= floor
        if lex is not None:
            keep &= lex > 0
        cand = np.where(keep)[0]
    top = cand[np.argsort(-score[cand])][:k]
    return corpus.index[top.tolist()].with_columns(pl.Series("sim", cos[top].astype(float)), pl.Series("score", score[top].astype(float)))

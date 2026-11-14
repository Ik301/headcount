"""Claim retrieval over the story corpus.

search_claim(text) embeds the claim with bge-small (query prefix), takes cosine top-k over the corpus
embeddings and returns matching unique texts with similarity. The similarity floor is a placeholder until
Muse's retrieval eval (M6) reports the best value.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DEFAULT_FLOOR = 0.70


@dataclass
class Corpus:
    emb: np.ndarray  # (n_unique, 384), normalized
    index: pl.DataFrame  # eidx, norm, text
    model: object


def load(d: str = "data/processed/narratives") -> Corpus:
    from sentence_transformers import SentenceTransformer

    p = Path(d)
    emb = np.load(p / "embeddings.npy")
    index = pl.read_parquet(p / "embed_index.parquet")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    return Corpus(emb=emb, index=index, model=model)


def search_claim(corpus: Corpus, text: str, k: int = 300, floor: float = DEFAULT_FLOOR) -> pl.DataFrame:
    """Returns eidx, norm, text, sim for the top-k unique texts with sim >= floor, best first."""
    q = corpus.model.encode([QUERY_PREFIX + text], normalize_embeddings=True)[0]
    sims = corpus.emb @ q
    top = np.argsort(-sims)[:k]
    top = top[sims[top] >= floor]
    return corpus.index[top.tolist()].with_columns(pl.Series("sim", sims[top].astype(float)))

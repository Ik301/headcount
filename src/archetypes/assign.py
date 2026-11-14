"""Assign accounts to archetypes (M5), behind the interface in docs/DEMO.md:

    arch = load_archetypes()
    assign(arch, profiles, histories) -> [{"did", "archetype_id", "label"}]

Nearest centroid in the standardized archetype feature space; the scaler ships inside the artifact because
this runs at API time (live path, /xray). Falls back to the stub when no artifact exists yet.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np

from src.archetypes.features import arch_matrix

DEFAULT_PATH = "data/processed/artifacts/archetypes.joblib"


def load_archetypes(path: str | None = None) -> dict:
    p = Path(path or DEFAULT_PATH)
    if not p.exists():
        warnings.warn(f"{p} not found; run `python -m src.archetypes.build`. Falling back to the stub archetypes.")
        from src.stubs import analysis as stub

        a = stub.load_archetypes()
        a["_stub"] = stub
        return a
    import joblib

    return joblib.load(p)


def standardize(arch: dict, X: np.ndarray) -> np.ndarray:
    Xi = np.where(np.isnan(X), arch["median"], X)
    return (Xi - arch["mu"]) / arch["sd"]


def assign(arch, profiles: list[dict], histories: dict[str, list[dict]]) -> list[dict]:
    if "_stub" in arch:
        return arch["_stub"].assign(arch, profiles, histories)
    if not profiles:
        return []
    Z = standardize(arch, arch_matrix(profiles, histories))
    d = ((Z[:, None, :] - arch["centroids"][None, :, :]) ** 2).sum(-1)
    k = d.argmin(1)
    ids, labels = arch["ids"], arch["labels"]
    return [{"did": p["did"], "archetype_id": ids[j], "label": labels[j]} for p, j in zip(profiles, k)]

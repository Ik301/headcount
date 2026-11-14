"""The one shared bootstrap (docs/DEMO.md, Build specification): over accounts, 1,000 resamples, seed 42."""
import numpy as np

RESAMPLES = 1000
SEED = 42


def share_ci(flags_by_account: dict[str, list[bool]], resamples: int = RESAMPLES, seed: int = SEED) -> tuple[float, float, float]:
    """Share of True flags with a 95% interval, resampling accounts (posts stay grouped by account).

    Returns (share, lo, hi)."""
    accts = list(flags_by_account)
    if not accts:
        return (0.0, 0.0, 0.0)
    tot = np.array([len(flags_by_account[a]) for a in accts], dtype=float)
    pos = np.array([sum(flags_by_account[a]) for a in accts], dtype=float)
    share = float(pos.sum() / max(tot.sum(), 1))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(accts), size=(resamples, len(accts)))
    boot = pos[idx].sum(1) / np.maximum(tot[idx].sum(1), 1)
    return (share, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))


def ratio_ci(num_flags: list[bool], base_rate: float, resamples: int = RESAMPLES, seed: int = SEED) -> tuple[float, float, float]:
    """Lift of a group's rate over a base rate, with a bootstrap interval over the group's members."""
    x = np.array(num_flags, dtype=float)
    if len(x) == 0 or base_rate <= 0:
        return (0.0, 0.0, 0.0)
    rng = np.random.default_rng(seed)
    boot = x[rng.integers(0, len(x), size=(resamples, len(x)))].mean(1) / base_rate
    return (float(x.mean() / base_rate), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))

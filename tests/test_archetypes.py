"""M5 archetypes: interface shape, labels in plain behavioral words, regression helper. No torch."""
import numpy as np

from src.archetypes import assign as A
from src.archetypes import build as B
from src.archetypes.features import ARCH_FEATURES, WORDS, arch_row, describe

BANNED = ("gender", "race", "religio", "age group", "old people", "young people", "women", "men ", "democrat", "republican", "liberal", "conservative")


def prof(i, followers=100):
    return {"did": f"did:plc:a{i}", "createdAt": "2025-01-01T00:00:00Z", "followersCount": followers, "followsCount": 50, "postsCount": 500}


def test_every_feature_has_plain_words_and_no_sensitive_terms():
    assert set(WORDS) == set(ARCH_FEATURES)
    for hi, lo in WORDS.values():
        assert not any(b in (hi + lo).lower() for b in BANNED)


def test_arch_row_handles_empty_history():
    r = arch_row(prof(1), [])
    assert set(r) == set(ARCH_FEATURES)


def test_label_centroid_is_unique_and_readable():
    z = np.zeros(len(ARCH_FEATURES))
    z[ARCH_FEATURES.index("repost_share")] = 2.0
    z[ARCH_FEATURES.index("age_days_log")] = -1.5
    lab, feats = B.label_centroid(z, set())
    assert lab.startswith("Mostly reposting others") and "new accounts" in lab
    lab2, _ = B.label_centroid(z, {lab})
    assert lab2 != lab


def test_describe_formats():
    assert "days" in describe("age_days_log", np.log(45))
    assert describe("repost_share", 0.7).startswith("70%")


def test_logit_fit_recovers_sign():
    rng = np.random.default_rng(0)
    x = rng.normal(size=2000)
    y = (rng.random(2000) < 1 / (1 + np.exp(-(0.5 + 1.5 * x)))).astype(float)
    b, se = B.logit_fit(np.column_stack([np.ones_like(x), x]), y)
    assert abs(b[1] - 1.5) < 0.3 and se[1] > 0


def test_assign_with_artifact_and_stub(tmp_path):
    import joblib

    k = len(ARCH_FEATURES)
    arch = {"version": "t", "ids": ["a1", "a2"], "labels": ["L1", "L2"], "centroids": np.array([np.zeros(k), np.ones(k) * 5]),
            "median": np.zeros(k), "mu": np.zeros(k), "sd": np.ones(k), "features": ARCH_FEATURES}
    p = tmp_path / "arch.joblib"
    joblib.dump(arch, p)
    out = A.assign(A.load_archetypes(str(p)), [prof(1), prof(2)], {})
    assert [set(o) for o in out] == [{"did", "archetype_id", "label"}] * 2
    stub = A.load_archetypes(str(tmp_path / "missing.joblib"))
    assert stub["version"] == "stub" and len(A.assign(stub, [prof(3)], {})) == 1

"""M2 bot model: interface shape, feature exclusions, and a tiny end-to-end train on synthetic accounts. No torch."""
import math
from datetime import datetime, timedelta, timezone

import numpy as np

from src.bots import features as F
from src.bots import score as S


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def make_account(i: int, bot: bool):
    t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
    prof = {
        "did": f"did:plc:test{i}",
        "handle": f"user{i}.bsky.social",
        "createdAt": _iso(t0 - timedelta(days=20 if bot else 900)),
        "followersCount": 3 if bot else 400,
        "followsCount": 2 if bot else 300,
        "postsCount": 20000 if bot else 900,
        "avatar": None if bot else "x",
        "description": "I am a bot that posts news" if bot else "hi",
        "labels": [{"val": "bot"}] if bot else [],
    }
    if bot:
        items = [{"uri": f"at://{i}/{k}", "t": _iso(t0 + timedelta(minutes=10 * k)), "text": f"BREAKING market update {k} https://news.example/a",
                  "kind": "post", "urls": ["https://news.example/a"], "n_like": 0, "n_repost": 0, "n_reply": 0, "n_quote": 0} for k in range(50)]
    else:
        rng = np.random.default_rng(i)
        ts = np.cumsum(rng.exponential(5000, 50))
        kinds = ["post", "reply", "repost", "post", "reply"]
        items = [{"uri": f"at://{i}/{k}", "author": f"did:plc:other{k % 7}", "t": _iso(t0 + timedelta(seconds=float(ts[k]))),
                  "text": f"thought number {rng.integers(1e9)} about things {k}", "kind": kinds[k % 5], "urls": [],
                  "n_like": int(rng.integers(0, 20)), "n_repost": 0, "n_reply": 1, "n_quote": 0} for k in range(50)]
    return prof, items


def test_features_exclude_label_and_bio_words():
    for name in F.FEATURES:
        assert "label" not in name and "bridged" not in name and "handle" not in name
    p_bot, h = make_account(1, True)
    p_clean = dict(p_bot, labels=[], description="x" * len(p_bot["description"]))
    a, b = F.account_features(p_bot, h), F.account_features(p_clean, h)
    assert all((math.isnan(a[k]) and math.isnan(b[k])) or a[k] == b[k] for k in F.FEATURES)


def test_timestamps_with_offsets_parse():
    assert F.ts("2026-11-13T20:07:15-03:00") == datetime(2026, 11, 13, 23, 7, 15, tzinfo=timezone.utc)
    assert F.ts("garbage") is None


def test_empty_history_is_safe():
    prof, _ = make_account(2, False)
    f = F.account_features(prof, [], None)
    assert set(f) == set(F.FEATURES)


def test_train_and_score_interface():
    from src.bots.train import fit_scaler, make

    accts = [make_account(i, i % 10 == 0) for i in range(120)]
    profiles = [a[0] for a in accts]
    hist = {a[0]["did"]: a[1] for a in accts}
    X = F.feature_matrix(profiles, hist, None)
    y = np.array([F.self_label_bot(p) for p in profiles], dtype=int)
    sc = fit_scaler(X)
    logit = make("logit").fit(S._standardize(sc, X), y)
    clf = make("hgb").fit(X, y)
    model = {"version": "test", "kind": "hgb", "clf": clf, "c": 0.8, "coef": logit.coef_[0], "features": F.FEATURES, **sc}

    out = S.score_accounts(model, profiles, hist, None)
    assert len(out) == len(profiles)
    for r in out:
        assert set(r) == {"did", "p_automated", "reasons"}
        assert 0.0 <= r["p_automated"] <= 1.0
        assert len(r["reasons"]) <= 3 and all(isinstance(s, str) for s in r["reasons"])
    bots = [r["p_automated"] for r, p in zip(out, profiles) if F.self_label_bot(p)]
    humans = [r["p_automated"] for r, p in zip(out, profiles) if not F.self_label_bot(p)]
    assert min(bots) > max(humans)
    top_bot = next(r for r, p in zip(out, profiles) if F.self_label_bot(p))
    assert top_bot["reasons"], "a clearly automated account should get reasons"
    assert not any("bot" in s.lower() for s in top_bot["reasons"]), "reasons never call an account a bot"
    assert S.score_accounts(model, [], {}, None) == []


def test_missing_model_falls_back_to_stub(tmp_path):
    m = S.load_model(str(tmp_path / "nope.joblib"))
    assert m["version"] == "stub"
    prof, items = make_account(3, False)
    out = S.score_accounts(m, [prof], {prof["did"]: items})
    assert out[0]["did"] == prof["did"]

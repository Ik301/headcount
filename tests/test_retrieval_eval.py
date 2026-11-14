"""M6 retrieval evaluation: claim file parses, rules compile, metrics behave. No torch, no data files."""
import polars as pl

from src.evaluation import retrieval as R


def test_claim_file_is_complete_and_compiles():
    claims = R.load_claims("eval/retrieval/claims.csv")
    assert len(claims) == 50
    assert len({c["claim_id"] for c in claims}) == 50
    assert all(c["claim"] and c["rules"] for c in claims)


def test_normalization_matches_hermes():
    df = pl.DataFrame({"text": ["Huang RESIGNS https://x.com/a ", "huang resigns", "  "]})
    out = R.norm_frame(df)
    assert out["norm"].to_list() == ["huang resigns"]


def test_metrics_with_fake_retriever():
    claims = [{"claim_id": "x", "claim": "spy", "rules": [__import__("re").compile(r"\bspy\b")]}]
    norms = ["a spy story", "spy again", "nothing here", "more spy talk"]
    gold = R.gold_sets(claims, norms)
    assert gold["x"] == {"a spy story", "spy again", "more spy talk"}

    def search(text):
        return [("a spy story", 0.9), ("nothing here", 0.8), ("spy again", 0.6), ("more spy talk", 0.4)]

    row = R.evaluate(claims, gold, search)[0]
    assert row["r10"] == 1.0  # all 3 gold in top 10, capped denominator min(10, 3)
    assert abs(row["r10@0.7"] - 1 / 3) < 1e-9  # floor 0.7 keeps 2 items, 1 is gold
    assert abs(row["setp@0.5"] - 2 / 3) < 1e-9

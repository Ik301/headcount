"""Likely automated share per narrative, with the threshold strip (M4). Called by H8's export.

    narrative_shares(post_narrative, posts, bot_scores, accounts=None) -> {"baseline": {...}, "narratives": [...]}

Inputs are the README tables (polars DataFrames): post_narrative (post_id, narrative_id, prob; the highest-prob
narrative per post is used), posts (post_id, account_id), bot_scores (account_id, p_automated) and optionally
accounts (account_id, bridged).

Per narrative, at HEADLINE_THRESHOLD and at each STRIP_THRESHOLDS cutoff:
  bot_post_share      share of the narrative's posts whose author has p_automated >= cutoff
  bot_account_share   share of its distinct authors with p_automated >= cutoff
  expected_share      mean p_automated over its posts, so the headline doesn't hinge on one cutoff
Every interval is the shared bootstrap (src.stats.share_ci: over accounts, 1,000 resamples, seed 42).

Bridged (fediverse) accounts: the build spec says the export carries both denominators and the dashboard shows the
unbridged one. So the top-level numbers exclude bridged accounts and "with_bridged" holds the same numbers on
everyone. Without an accounts table, nothing is excluded and that is stated in "denominator".

    python -m src.bots.narrative_shares   # writes artifacts/narrative_shares.json and eval/bots/narrative_shares.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from src.config import HEADLINE_THRESHOLD, STRIP_THRESHOLDS
from src.stats import share_ci


POST_NARRATIVE_PATHS = ("data/processed/narratives/post_narrative.parquet", "data/processed/post_narrative.parquet")


def find_post_narrative(paths=POST_NARRATIVE_PATHS) -> Path | None:
    """H3 writes data/processed/narratives/post_narrative.parquet; the README table path is accepted too."""
    return next((Path(x) for x in paths if Path(x).exists()), None)


def narrative_labels() -> dict[str, str]:
    """Display labels from the API's table (H3), so the report and the dashboard use the same names."""
    try:
        from src.api.analysis import NARRATIVE_LABELS

        return {k: (v[0] if isinstance(v, (tuple, list)) else str(v)) for k, v in NARRATIVE_LABELS.items()}
    except Exception:
        return {}


def _assign(post_narrative: pl.DataFrame) -> pl.DataFrame:
    return post_narrative.sort("prob", descending=True).unique(subset="post_id", keep="first").select("post_id", "narrative_id")


def _block(df: pl.DataFrame) -> dict:
    """Shares for one set of (account_id, p) post rows."""
    by_acct: dict[str, list[float]] = {}
    for a, p in df.select("account_id", "p_automated").iter_rows():
        by_acct.setdefault(a, []).append(p)
    one = {a: [ps[0]] for a, ps in by_acct.items()}  # one row per account for account shares

    def post_share(t):
        return share_ci({a: [p >= t for p in ps] for a, ps in by_acct.items()})

    def acct_share(t):
        return share_ci({a: [ps[0] >= t] for a, ps in one.items()})

    s, lo, hi = post_share(HEADLINE_THRESHOLD)
    sa, alo, ahi = acct_share(HEADLINE_THRESHOLD)
    e, elo, ehi = share_ci(by_acct)  # floats: mean p_automated over posts
    return {
        "n_posts": df.height,
        "n_accounts": len(by_acct),
        "bot_post_share": round(s, 4),
        "bot_post_share_ci": [round(lo, 4), round(hi, 4)],
        "bot_account_share": round(sa, 4),
        "bot_account_share_ci": [round(alo, 4), round(ahi, 4)],
        "expected_share": round(e, 4),
        "expected_share_ci": [round(elo, 4), round(ehi, 4)],
        "expected_automated_posts": round(float(df["p_automated"].sum()), 1),
        "threshold_strip": {str(t): round(post_share(t)[0], 4) for t in STRIP_THRESHOLDS},
        "threshold_strip_ci": {str(t): [round(x, 4) for x in post_share(t)[1:]] for t in STRIP_THRESHOLDS},
        "threshold_strip_accounts": {str(t): round(acct_share(t)[0], 4) for t in STRIP_THRESHOLDS},
    }


def narrative_shares(post_narrative: pl.DataFrame, posts: pl.DataFrame, bot_scores: pl.DataFrame,
                     accounts: pl.DataFrame | None = None, labels: dict[str, str] | None = None) -> dict:
    df = (
        posts.select("post_id", "account_id")
        .join(_assign(post_narrative), on="post_id", how="inner")
        .join(bot_scores.select("account_id", "p_automated"), on="account_id", how="inner")
    )
    if accounts is not None and "bridged" in accounts.columns:
        df = df.join(accounts.select("account_id", "bridged"), on="account_id", how="left").with_columns(pl.col("bridged").fill_null(False))
        denom = "unbridged accounts (bridged fediverse accounts are in with_bridged)"
    else:
        df = df.with_columns(pl.lit(False).alias("bridged"))
        denom = "all accounts (no accounts table, so bridged accounts could not be separated)"
    main = df.filter(~pl.col("bridged"))
    out = {"denominator": denom, "baseline": _block(main) | {"with_bridged": _block(df)}, "narratives": []}
    for nid in sorted(df["narrative_id"].unique().to_list()):
        sub_all = df.filter(pl.col("narrative_id") == nid)
        sub = sub_all.filter(~pl.col("bridged"))
        if sub.height == 0:
            continue
        row = {"id": nid, "label": (labels or {}).get(nid, "")} | _block(sub) | {"with_bridged": _block(sub_all)}
        base = out["baseline"]["bot_post_share"]
        row["x_baseline"] = round(row["bot_post_share"] / base, 2) if base > 0 else None
        out["narratives"].append(row)
    out["narratives"].sort(key=lambda r: -r["n_posts"])
    return out


def kill_test_3(res: dict, exclude: tuple[str, ...] = ("n0",)) -> dict:
    """Most automated narrative's share at least twice the least automated one's, at every strip cutoff."""
    rows = [r for r in res["narratives"] if r["id"] not in exclude]
    per = {}
    for t in map(str, STRIP_THRESHOLDS):
        vals = {r["id"]: r["threshold_strip"][t] for r in rows}
        hi, lo = max(vals, key=vals.get), min(vals, key=vals.get)
        ratio = vals[hi] / vals[lo] if vals[lo] > 0 else float("inf")
        per[t] = {"most": hi, "least": lo, "ratio": round(ratio, 2), "pass": ratio >= 2}
    return {"per_cutoff": per, "pass": all(v["pass"] for v in per.values())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--post-narrative", default=None, help="default: the first of " + ", ".join(POST_NARRATIVE_PATHS) + " that exists")
    ap.add_argument("--out", default="data/processed/artifacts/narrative_shares.json")
    ap.add_argument("--report", default="eval/bots/narrative_shares.md")
    a = ap.parse_args()
    proc = Path(a.processed)
    pn_path = Path(a.post_narrative) if a.post_narrative else find_post_narrative()
    if pn_path is None or not pn_path.exists():
        raise SystemExit(f"no post_narrative.parquet found (looked in {', '.join(POST_NARRATIVE_PATHS)}); H3 writes it")
    pn = pl.read_parquet(pn_path)
    labels = narrative_labels()
    res = narrative_shares(pn, pl.read_parquet(proc / "posts.parquet"), pl.read_parquet(proc / "artifacts/bot_scores.parquet"),
                           pl.read_parquet(proc / "accounts.parquet"), labels)
    kt = kill_test_3(res)
    res["kill_test_3"] = kt
    Path(a.out).write_text(json.dumps(res, indent=1))
    b = res["baseline"]
    lines = [
        "# Likely automated share per narrative (M4)",
        "",
        f"Command: `python -m src.bots.narrative_shares` (post_narrative: `{pn_path}`)",
        f"Denominator: {res['denominator']}. Intervals: shared bootstrap over accounts (1,000 resamples, seed 42).",
        "",
        f"Story baseline: {b['bot_post_share']:.1%} of posts ({b['bot_post_share_ci'][0]:.1%} to {b['bot_post_share_ci'][1]:.1%}) and"
        f" {b['bot_account_share']:.1%} of accounts are likely automated (p >= {HEADLINE_THRESHOLD}); expected share {b['expected_share']:.1%}.",
        "",
        "| Narrative | Posts | Likely automated posts (95% CI) | x baseline | Accounts | Expected | " + " | ".join(f"@{t}" for t in STRIP_THRESHOLDS) + " |",
        "|---|---|---|---|---|---|" + "---|" * len(STRIP_THRESHOLDS),
        *[
            f"| {r['id']} {r['label']} | {r['n_posts']:,} | {r['bot_post_share']:.1%} ({r['bot_post_share_ci'][0]:.1%} to {r['bot_post_share_ci'][1]:.1%})"
            f" | {r['x_baseline']} | {r['bot_account_share']:.1%} | {r['expected_share']:.1%} | "
            + " | ".join(f"{r['threshold_strip'][str(t)]:.1%}" for t in STRIP_THRESHOLDS) + " |"
            for r in res["narratives"]
        ],
        "",
        "## Kill test 3",
        "",
        "Most automated narrative's share at least twice the least automated one's, at every cutoff (n0, no narrative, excluded):",
        "",
        *[f"- @{t}: {v['most']} vs {v['least']}, ratio {v['ratio']} -> {'pass' if v['pass'] else 'fail'}" for t, v in kt["per_cutoff"].items()],
        "",
        f"**{'Pass' if kt['pass'] else 'Fail'}.**" + ("" if kt["pass"] else
          " Per DEMO.md the headline becomes: automation is spread evenly, and the bots-defending-Huang claim does not show on Bluesky."),
        "",
    ]
    Path(a.report).write_text("\n".join(lines))
    print(f"wrote {a.out} and {a.report}; kill test 3 {'pass' if kt['pass'] else 'fail'}")


if __name__ == "__main__":
    main()

"""Quick story-level numbers: likely-automated share per narrative (unbridged), with intervals and the cutoff strip.

Usage: python -m src.pipeline.story_numbers
"""
import polars as pl

from src import config as cfg
from src.api.analysis import NARRATIVE_LABELS
from src.stats import share_ci


def main() -> None:
    p = pl.read_parquet("data/processed/posts.parquet").select("post_id", "account_id")
    pn = pl.read_parquet("data/processed/narratives/post_narrative.parquet")
    bs = pl.read_parquet("data/processed/artifacts/bot_scores.parquet").select("account_id", "p_automated")
    acc = pl.read_parquet("data/processed/accounts.parquet").select("account_id", "bridged")
    d = (
        p.join(pn, on="post_id")
        .join(bs, on="account_id", how="left")
        .join(acc, on="account_id", how="left")
        .with_columns(pl.col("p_automated").fill_null(0.0))
        .filter(~pl.col("bridged").fill_null(False))
    )
    base = float((d["p_automated"] >= cfg.HEADLINE_THRESHOLD).mean())
    print(f"posts {d.height} (bridged excluded); baseline likely automated {base:.3%}")
    rows = []
    for nid in sorted(d["narrative_id"].unique().to_list()):
        g = d.filter(pl.col("narrative_id") == nid)
        flags: dict[str, list[bool]] = {}
        for a, pp in g.select("account_id", "p_automated").iter_rows():
            flags.setdefault(a, []).append(pp >= cfg.HEADLINE_THRESHOLD)
        s, lo, hi = share_ci(flags)
        strip = [float((g["p_automated"] >= t).mean()) for t in cfg.STRIP_THRESHOLDS]
        rows.append((NARRATIVE_LABELS.get(nid, (nid,))[0], g.height, g["account_id"].n_unique(), s, lo, hi, strip))
    for name, n, na, s, lo, hi, strip in sorted(rows, key=lambda r: -r[3]):
        print(f"{name:40s} posts {n:6d} accts {na:6d}  automated {s:6.1%} ({lo:.1%} to {hi:.1%})  x{s / base if base else 0:.1f}  strip " + " / ".join(f"{x:.1%}" for x in strip))


if __name__ == "__main__":
    main()

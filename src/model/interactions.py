"""Convert data/raw/interactions.jsonl into data/processed/interactions.parquet.

Usage: python -m src.model.interactions
Columns: src_account_id (the actor), dst_account_id (author of the post), type (like, repost, quote), post_id, created_at.
"""
import json
from pathlib import Path

import polars as pl


def main(raw: str = "data/raw/interactions.jsonl", posts: str = "data/processed/posts.parquet", out: str = "data/processed/interactions.parquet") -> None:
    author = dict(pl.read_parquet(posts).select("post_id", "account_id").iter_rows())
    rows = []
    for line in open(raw):
        d = json.loads(line)
        dst = author.get(d["post_id"])
        for a in d.get("actors", []):
            if a.get("did"):
                rows.append({"src_account_id": a["did"], "dst_account_id": dst, "type": d["type"], "post_id": d["post_id"], "created_at": a.get("t")})
    df = pl.DataFrame(rows, schema={"src_account_id": pl.Utf8, "dst_account_id": pl.Utf8, "type": pl.Utf8, "post_id": pl.Utf8, "created_at": pl.Utf8})
    df.write_parquet(out)
    print("interactions", df.height, df.group_by("type").len().to_dicts())


if __name__ == "__main__":
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    main()

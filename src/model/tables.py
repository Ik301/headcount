"""Build the local Parquet tables from the raw pulls.

Usage:
    python -m src.model.tables --raw data/raw --out data/processed

Inputs (from the ingest scripts): bsky_jensen_nov5_13.jsonl (story posts), profiles.jsonl, history.jsonl.
Outputs: accounts.parquet, posts.parquet, history_posts.parquet.

Local tables keep Bluesky DIDs as account_id (data/processed is gitignored). Hashing happens at export,
in src.model.schema.public_ref, before anything reaches the dashboard, a reply or the repo.
"""
import argparse
import json
from pathlib import Path

import polars as pl

from src.model.schema import is_public


def story_posts(path: Path) -> pl.DataFrame:
    rows = []
    for line in open(path):
        d = json.loads(line)
        rec = d.get("record", {}) or {}
        embed = rec.get("embed") or {}
        quote = None
        if "record" in embed.get("$type", ""):
            r = embed.get("record", {})
            quote = r.get("uri") or (r.get("record") or {}).get("uri")
        reply = rec.get("reply") or {}
        urls = []
        for facet in rec.get("facets") or []:
            for feat in facet.get("features") or []:
                if feat.get("uri"):
                    urls.append(feat["uri"])
        ext = (embed.get("external") or (embed.get("media") or {}).get("external") or {}).get("uri")
        if ext:
            urls.append(ext)
        rows.append(
            {
                "post_id": d["uri"],
                "platform": "bluesky",
                "account_id": d["author"]["did"],
                "created_at": rec.get("createdAt"),
                "text": rec.get("text") or "",
                "lang": (rec.get("langs") or [None])[0],
                "parent_post_id": (reply.get("parent") or {}).get("uri"),
                "root_post_id": (reply.get("root") or {}).get("uri"),
                "quoted_post_id": quote,
                "urls": urls,
                "domains": [u.split("/")[2] for u in urls if u.count("/") >= 2],
                "like_count": d.get("likeCount", 0),
                "repost_count": d.get("repostCount", 0),
                "reply_count": d.get("replyCount", 0),
                "quote_count": d.get("quoteCount", 0),
                "in_story": True,
            }
        )
    return pl.DataFrame(rows).unique(subset="post_id")


def accounts(path: Path, story_authors: dict[str, list[str]]) -> pl.DataFrame:
    rows = []
    for line in open(path):
        p = json.loads(line)
        labels = [l.get("val") for l in (p.get("labels") or [])] + story_authors.get(p["did"], [])
        rows.append(
            {
                "account_id": p["did"],
                "platform": "bluesky",
                "handle": p.get("handle"),
                "display_name": p.get("displayName"),
                "is_public": is_public(p),
                "created_at": p.get("createdAt"),
                "followers": p.get("followersCount", 0),
                "follows": p.get("followsCount", 0),
                "posts_count": p.get("postsCount", 0),
                "has_avatar": bool(p.get("avatar")),
                "bio": p.get("description") or "",
                "bio_len": len(p.get("description") or ""),
                "labels": sorted(set(l for l in labels if l)),
                "self_label_bot": any(l in ("bot", "!bot") for l in labels),
                "bridged": any((l or "").startswith("bridged-from-") for l in labels),
            }
        )
    return pl.DataFrame(rows).unique(subset="account_id")


def history(path: Path) -> pl.DataFrame:
    rows = []
    for line in open(path):
        d = json.loads(line)
        for it in d.get("items", []):
            rows.append(
                {
                    "account_id": d["did"],
                    "post_id": it.get("uri"),
                    "author_id": it.get("author"),
                    "t": it.get("t"),
                    "kind": it.get("kind"),
                    "text": it.get("text") or "",
                    "reply_parent": it.get("reply_parent"),
                    "quote": it.get("quote"),
                    "urls": it.get("urls") or [],
                    "n_like": it.get("n_like") or 0,
                    "n_repost": it.get("n_repost") or 0,
                    "n_reply": it.get("n_reply") or 0,
                    "n_quote": it.get("n_quote") or 0,
                }
            )
    return pl.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--posts-file", default="bsky_jensen_nov5_13.jsonl")
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    story_labels: dict[str, list[str]] = {}
    for line in open(raw / a.posts_file):
        au = json.loads(line)["author"]
        story_labels.setdefault(au["did"], [])
        story_labels[au["did"]] += [l.get("val") for l in (au.get("labels") or [])]

    p = story_posts(raw / a.posts_file)
    p.write_parquet(out / "posts.parquet")
    print("posts", p.height)
    acc = accounts(raw / "profiles.jsonl", story_labels)
    acc.write_parquet(out / "accounts.parquet")
    print("accounts", acc.height, "self-labeled bots", acc["self_label_bot"].sum(), "public", acc["is_public"].sum())
    if (raw / "history.jsonl").exists():
        h = history(raw / "history.jsonl")
        h.write_parquet(out / "history_posts.parquet")
        print("history_posts", h.height)


if __name__ == "__main__":
    main()

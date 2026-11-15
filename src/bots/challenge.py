"""Challenge set (M7): 20 frozen accounts for challenge mode and the post-pitch table activity.

Usage:
    python -m src.bots.challenge --out data/sample/challenge.json

Picks 5 clearly automated (self-labeled, one per operator domain; no unlabeled high scorer is public), 5 clearly human and 10 from the uncertain middle of the score
range. Only public accounts under the README rule (5,000+ followers, verified, or self-labeled bot), because this
file is committed and shows handles and post text. Scores are out-of-fold (from bot_oof.parquet), so a labeled
bot's score comes from a model that never saw it; reasons come from the deployed model.

hand_label: "automated" or "human" where a person has checked it (pass --labels with a JSON {handle: label}),
"" where Isaac's label is still needed (the middle 10). Each entry also carries "tier" (automated, human, middle).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import polars as pl

from src.bots.score import load_model, score_accounts
from src.bots.train import load_raw
from src.model.schema import is_public

SEED = 42
ADULT = {"porn", "sexual", "nudity", "graphic-media", "gore", "sexual-figurative"}


PROFANE = re.compile(r"fuck|shit|bitch|cunt|asshole|motherf|urinat", re.I)


def demo_safe(p: dict, items: list[dict]) -> bool:
    """Judges see this at the table: skip adult or graphic labels, government or office accounts (not one person
    posting by hand), and accounts whose displayed posts contain profanity."""
    if any((l.get("val") or "") in ADULT for l in p.get("labels") or []):
        return False
    if (p.get("handle") or "").endswith(".gov"):
        return False
    return not any(PROFANE.search(x["text"]) or PROFANE.search(p.get("handle") or "") for x in own_posts(items))


MENTION = re.compile(r"@([a-z0-9][a-z0-9.\-]*\.[a-z]{2,})", re.I)
PUBLIC_HANDLES: set[str] = set()  # filled in main(); mentions of anyone else are masked


FEDI_MENTION = re.compile(r"@[\w.-]+@[\w.-]+\.[a-z]{2,}", re.I)  # fediverse @user@instance: never a story account


def mask_mentions(text: str) -> str:
    """Posts may @mention private accounts; their handles never go into a committed file. Fediverse mentions
    (@user@instance) are masked whole, or the user part would survive the domain match."""
    text = FEDI_MENTION.sub("@[a private account]", text)
    return MENTION.sub(lambda m: m.group(0) if m.group(1).lower() in PUBLIC_HANDLES else "@[a private account]", text)


def own_posts(items: list[dict], n: int = 5) -> list[dict]:
    own = [i for i in items if i.get("kind") != "repost" and (i.get("text") or "").strip()]
    own.sort(key=lambda i: i.get("t") or "", reverse=True)
    return [{"t": i.get("t"), "text": mask_mentions((i.get("text") or "")[:280]), "kind": i.get("kind")} for i in own[:n]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--oof", default="data/processed/artifacts/bot_oof.parquet")
    ap.add_argument("--out", default="data/sample/challenge.json")
    ap.add_argument("--labels", default="data/sample/challenge_labels.json", help="JSON {handle: 'automated'|'human'} from the hand check")
    ap.add_argument("--exclude", default="data/private/challenge_exclude.json",
                    help="JSON list of handles skipped after the hand check (kept local: it names accounts)")
    a = ap.parse_args()

    profiles, histories, story = load_raw(Path(a.raw), "bsky_jensen_nov5_13.jsonl")
    prof = {p["did"]: p for p in profiles}
    PUBLIC_HANDLES.update((p.get("handle") or "").lower() for p in profiles if is_public(p))
    oof = pl.read_parquet(a.oof)
    excl = set(json.load(open(a.exclude))) if a.exclude and Path(a.exclude).exists() else set()
    pub = oof.filter(pl.col("account_id").map_elements(lambda d: is_public(prof[d]) and demo_safe(prof[d], histories.get(d, [])), return_dtype=pl.Boolean))
    pub = pub.filter(pl.col("account_id").map_elements(lambda d: len(own_posts(histories.get(d, []))) >= 3, return_dtype=pl.Boolean))

    rng = np.random.default_rng(SEED)
    # Clearly automated: unlabeled high scorers are all under 5,000 followers (not public), so this tier is
    # self-labeled bots, one per operator domain so the round isn't five copies of one mirror network.
    lab_ids, seen_dom = [], set()
    for d in pub.filter(pl.col("labeled") == 1).sort("oof_score", descending=True)["account_id"].to_list():
        if prof[d]["handle"] in excl:
            continue
        dom = ".".join(prof[d]["handle"].split(".")[-3:])
        if dom not in seen_dom:
            seen_dom.add(dom)
            lab_ids.append(d)
        if len(lab_ids) == 5:
            break
    auto_ids = pub.filter((pl.col("labeled") == 0) & (pl.col("p_automated_oof") >= 0.7)).sort("oof_score", descending=True).head(5 - len(lab_ids))["account_id"].to_list()
    hum_pool = pub.filter((pl.col("labeled") == 0) & (pl.col("p_automated_oof") < 0.01)).sort("account_id")
    # stable draw: a fixed permutation of the pool, so excluding one account doesn't reshuffle the others
    perm = np.random.default_rng(SEED).permutation(hum_pool.height)
    hum_ids = [d for d in (hum_pool["account_id"][int(i)] for i in perm) if prof[d]["handle"] not in excl][:5]
    mid_pool = pub.filter((pl.col("p_automated_oof") >= 0.15) & (pl.col("p_automated_oof") < 0.85)).sort("p_automated_oof")
    mid = mid_pool[np.linspace(0, mid_pool.height - 1, 10).round().astype(int).tolist()]

    picks = [(d, "automated") for d in lab_ids + auto_ids]
    picks += [(d, "human") for d in hum_ids] + [(d, "middle") for d in mid["account_id"].to_list()]
    p_oof = dict(oof.select("account_id", "p_automated_oof").iter_rows())
    model = load_model()
    sc = {s["did"]: s for s in score_accounts(model, [prof[d] for d, _ in picks], {d: histories.get(d, []) for d, _ in picks},
                                              {d: story.get(d, []) for d, _ in picks})}
    labels = json.load(open(a.labels)) if a.labels and Path(a.labels).exists() else {}
    out = []
    for d, tier in picks:
        h = prof[d]["handle"]
        out.append({
            "account_ref": h,
            "public_handle": h,
            "tier": tier,
            "posts": own_posts(histories.get(d, [])),
            "p_automated": round(float(p_oof[d]), 3),
            "reasons": sc[d]["reasons"],
            "hand_label": labels.get(h, ""),
        })
    order = rng.permutation(len(out))  # shuffle so the quiz doesn't run in tier order
    out = [out[i] for i in order]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"model_version": model.get("version"), "accounts": out}, indent=1, ensure_ascii=False))
    print(f"wrote {a.out}: {len(out)} accounts ({sum(o['tier'] == 'middle' for o in out)} middle need Isaac's label)")


if __name__ == "__main__":
    main()

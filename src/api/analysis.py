"""Claim analysis: the computation behind /claim and the agent's tools.

State is loaded once (Store.load). analyze_claim() returns the /claim contract in docs/DEMO.md.
"""
import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl

from src import config as cfg
from src.integration import coordination, versions
from src.model.schema import public_ref
from src.retrieval import corpus as rc
from src.stats import share_ci

NARRATIVE_LABELS = {
    "n1": ("Spy plot and national security", "anti_huang"),
    "n2": ("The affairs as personal misconduct", "anti_huang"),
    "n3": ("Trump and politics", "political"),
    "n4": ("Board, resignation and succession", "neutral_news"),
    "n5": ("Stock, market and lawsuits", "neutral_news"),
    "n6": ("Defending Huang", "pro_huang"),
    "n7": ("Jokes and memes", "humor"),
    "n0": ("No narrative", "other"),
}
AUTOMATED = cfg.HEADLINE_THRESHOLD
HUMAN = cfg.HUMAN_MAX
MIN_MATCHES = cfg.MIN_MATCHES


@dataclass
class Store:
    corpus: rc.Corpus
    posts: pl.DataFrame  # post_id, account_id, created_at, text, norm, narrative_id, side, p_automated
    accounts: dict  # did -> {handle, is_public, created_at}
    reasons: dict  # did -> [str]
    archetype: dict  # did -> (archetype_id, label)
    interactions: pl.DataFrame | None
    baseline_bot_share: float
    claims: dict = field(default_factory=dict)

    @classmethod
    def load(cls, base: str = "data/processed") -> "Store":
        b = Path(base)
        posts = pl.read_parquet(b / "posts.parquet").with_columns(
            pl.col("text").str.replace_all(r"https?://\S+", "").str.to_lowercase().str.strip_chars().alias("norm")
        )
        pn = pl.read_parquet(b / "narratives/post_narrative.parquet")
        bs = pl.read_parquet(b / "artifacts/bot_scores.parquet")
        posts = posts.join(pn.select("post_id", "narrative_id", "side"), on="post_id", how="left").join(
            bs.select(pl.col("account_id"), "p_automated"), on="account_id", how="left"
        ).with_columns(pl.col("p_automated").fill_null(0.0), pl.col("narrative_id").fill_null("n0"))
        acc = pl.read_parquet(b / "accounts.parquet")
        accounts = {r["account_id"]: r for r in acc.select("account_id", "handle", "is_public", "created_at", "self_label_bot").iter_rows(named=True)}
        reasons = dict(zip(bs["account_id"].to_list(), bs["reasons"].to_list()))
        ua = pl.read_parquet(b / "artifacts/user_archetype.parquet")
        archetype = {r[0]: (r[1], r[2]) for r in ua.select("account_id", "archetype_id", "label").iter_rows()}
        inter = pl.read_parquet(b / "interactions.parquet") if (b / "interactions.parquet").exists() else None
        base_share = float((posts["p_automated"] >= AUTOMATED).mean())
        return cls(rc.load(str(b / "narratives")), posts, accounts, reasons, archetype, inter, base_share)

    def ref(self, did: str) -> dict:
        a = self.accounts.get(did, {})
        return public_ref(did, a.get("handle"), bool(a.get("is_public")))


def analyze_claim(store: Store, text: str, floor: float = cfg.SIMILARITY_FLOOR, mode: str = "corpus", dashboard_base: str = "http://localhost:5173") -> dict:
    t0 = time.time()
    norm_claim = " ".join(text.lower().split())
    claim_id = hashlib.sha256((norm_claim + mode).encode()).hexdigest()[:12]
    if claim_id in store.claims:
        return store.claims[claim_id]
    hits = rc.search_claim(store.corpus, text, floor=floor)
    sims = dict(zip(hits["norm"].to_list(), hits["sim"].to_list()))
    m = store.posts.filter(pl.col("norm").is_in(list(sims))).with_columns(pl.col("norm").replace_strict(sims, default=0.0).alias("sim"))
    result = {
        "claim_id": claim_id,
        "claim": text,
        "scope": "corpus",
        "matched_posts": m.height,
        "window": {"from": m["created_at"].min() if m.height else None, "to": m["created_at"].max() if m.height else None},
        "narratives": [],
        "bot_commonalities": [],
        "amplifiers": {"n_humans": 0, "archetype_mix": []},
        "baseline_bot_share": round(store.baseline_bot_share, 4),
        "modules": versions(),
        "chart_png_url": f"/claim/{claim_id}/chart.png",
        "dashboard_url": f"{dashboard_base}/claim/{claim_id}",
    }
    if m.height >= MIN_MATCHES:
        for nid, g in sorted(m.group_by("narrative_id"), key=lambda kv: -kv[1].height):
            nid = nid[0] if isinstance(nid, tuple) else nid
            if nid == "n0" and g.height < 0.2 * m.height:
                continue
            flags: dict[str, list[bool]] = {}
            for did, p in g.select("account_id", "p_automated").iter_rows():
                flags.setdefault(did, []).append(p >= AUTOMATED)
            share, lo, hi = share_ci(flags)
            ex = g.sort("sim", descending=True).unique(subset="norm", maintain_order=True).head(3)
            label, side = NARRATIVE_LABELS.get(nid, (nid, "other"))
            result["narratives"].append(
                {
                    "id": nid,
                    "label": label,
                    "side": side,
                    "posts": g.height,
                    "share_of_matches": round(g.height / m.height, 4),
                    "bot_post_share": round(share, 4),
                    "bot_post_share_ci": [round(lo, 4), round(hi, 4)],
                    "baseline_bot_share": round(store.baseline_bot_share, 4),
                    "example_posts": [{"text": r["text"][:280], "public_handle": store.ref(r["account_id"])["public_handle"]} for r in ex.iter_rows(named=True)],
                    "evidence": [{"post_uri": r["post_id"], "t": r["created_at"], "note": f"similarity {r['sim']:.2f}"} for r in g.sort("sim", descending=True).head(10).iter_rows(named=True)],
                }
            )
        result["bot_commonalities"] = commonalities(store, m)
        result["amplifiers"] = amplifiers(store, m)
    result["seconds"] = round(time.time() - t0, 2)
    store.claims[claim_id] = result
    return result


def commonalities(store: Store, m: pl.DataFrame) -> list[dict]:
    bots = m.filter(pl.col("p_automated") >= AUTOMATED)
    dids = bots["account_id"].unique().to_list()
    out = []
    if len(dids) < cfg.MIN_BOT_ACCOUNTS_FOR_COMMONALITY:
        return out
    weeks = Counter((store.accounts.get(d, {}).get("created_at") or "")[:7] for d in dids)
    month, n = weeks.most_common(1)[0]
    if month and n >= 3:
        out.append({"signal": f"created in the same month ({month})", "accounts": n})
    cl = coordination.find_clusters(
        [{"did": r["account_id"], "uri": r["post_id"], "t": r["created_at"], "text": r["text"]} for r in m.iter_rows(named=True)]
    )
    if cl:
        big = max(cl, key=lambda c: len(c["dids"]))
        out.append({"signal": big["reasons"][0], "accounts": len(big["dids"]), "evidence": big["evidence"][:5]})
    reasons = Counter(r for d in dids for r in (store.reasons.get(d) or [])[:1])
    for r, k in reasons.most_common(2):
        if k >= 2:
            out.append({"signal": r, "accounts": k})
    return out


def amplifiers(store: Store, m: pl.DataFrame) -> dict:
    if store.interactions is None:
        return {"n_humans": 0, "archetype_mix": [], "note": "interactions not loaded yet"}
    bot_posts = m.filter(pl.col("p_automated") >= cfg.AUTOMATED_MIN)["post_id"].to_list()
    if not bot_posts:
        return {"n_humans": 0, "archetype_mix": []}
    p_by = dict(store.posts.select("account_id", "p_automated").unique(subset="account_id").iter_rows())
    inter = store.interactions.filter(pl.col("post_id").is_in(bot_posts))
    humans = [d for d in inter["src_account_id"].unique().to_list() if p_by.get(d, 0.0) < HUMAN]
    all_h = [d for d in store.interactions["src_account_id"].unique().to_list() if p_by.get(d, 0.0) < HUMAN]
    mix = Counter(store.archetype.get(d, ("unknown", "Not profiled"))[0] for d in humans)
    base = Counter(store.archetype.get(d, ("unknown", "Not profiled"))[0] for d in all_h)
    labels = {aid: lab for aid, lab in store.archetype.values()}
    out = []
    for aid, k in mix.most_common():
        share = k / max(len(humans), 1)
        bshare = base[aid] / max(len(all_h), 1)
        out.append({"id": aid, "label": labels.get(aid, "Not profiled"), "share": round(share, 4), "lift": round(share / bshare, 2) if bshare else None})
    return {"n_humans": len(humans), "archetype_mix": out}

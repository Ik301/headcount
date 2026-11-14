"""Archetypes and the thesis test (M5).

Usage:
    python -m src.archetypes.build

Amplifier: a human account (p_automated < HUMAN_MAX) that liked, reposted or quoted a story post whose author is
likely automated (p_automated >= AUTOMATED_MIN). Reply stance is cut (build spec), so replies don't count.

Matched control, one per amplifier, without replacement: a human account that engaged only with human-authored
story posts, at least one of them in the same narrative, the same 6-hour window and the same reach bucket as
the amplifier's first likely-automated post, and with the same activity bucket (lifetime posts per day,
quintiles) and follower bucket (powers of ten). Where no exact match exists, the reach bucket is dropped, then
the window widens to the day; every match records its level and the report gives the match rate per level.
Unmatched amplifiers are left out of lift and counted.

Archetypes: amplifiers and controls clustered together on public-behavior features (src/archetypes/features.py),
standardized, k-means with k in 4..8 by silhouette. Labels are plain words from each centroid's most distinctive
features. Lift = amplifier rate inside an archetype / amplifier rate overall, with the shared bootstrap
(src/stats.py). A logistic regression adds follower count, activity, narrative and hour.

Writes to data/processed/: user_features, archetypes, user_archetype, amplification (README tables), and
artifacts/archetypes.joblib for src.archetypes.assign; plus eval/thesis/report.md.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from src.archetypes.features import ARCH_FEATURES, WORDS, arch_matrix, describe
from src.bots.train import load_raw
from src.config import AUTOMATED_MIN, HUMAN_MAX
from src.stats import ratio_ci

SEED = 42
WINDOW_H = 6


def _t(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def load_jsonl(path: Path, key: str = "did") -> list[dict]:
    return [json.loads(l) for l in open(path) if l.strip()] if path.exists() else []


def logit_fit(X: np.ndarray, y: np.ndarray, iters: int = 50, ridge: float = 1e-6):
    """Newton-Raphson logistic regression with standard errors from the inverse Hessian."""
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p))
        b += step
        if np.abs(step).max() < 1e-8:
            break
    p = 1 / (1 + np.exp(-X @ b))
    H = X.T @ (X * (p * (1 - p))[:, None]) + ridge * np.eye(X.shape[1])
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return b, se


def label_centroid(z: np.ndarray, taken: set[str]) -> tuple[str, list[str]]:
    order = np.argsort(-np.abs(z))
    parts = []
    for j in order:
        hi, lo = WORDS[ARCH_FEATURES[j]]
        parts.append(hi if z[j] > 0 else lo)
        lab = parts[0][0].upper() + parts[0][1:] + ("" if len(parts) == 1 else ", " + ", ".join(parts[1:]))
        if len(parts) >= 2 and lab not in taken:
            return lab, [ARCH_FEATURES[i] for i in order[: len(parts)]]
    return lab, [ARCH_FEATURES[i] for i in order[:3]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--report", default="eval/thesis/report.md")
    a = ap.parse_args()
    t0 = time.time()
    raw, proc = Path(a.raw), Path(a.processed)
    art = proc / "artifacts"

    # ---- accounts, histories, scores
    profiles, histories, story = load_raw(raw, "bsky_jensen_nov5_13.jsonl")
    aud_p = load_jsonl(raw / "audience_profiles.jsonl")
    for d in load_jsonl(raw / "audience_history.jsonl"):
        histories.setdefault(d["did"], d.get("items", []))
    prof_by = {p["did"]: p for p in profiles}
    for p in aud_p:
        prof_by.setdefault(p["did"], p)
    scores = dict(pl.read_parquet(art / "bot_scores.parquet").select("account_id", "p_automated").iter_rows())
    new = [p for p in aud_p if p["did"] not in scores]
    if new:
        from src.bots.score import load_model, score_accounts

        for s in score_accounts(load_model(), new, {p["did"]: histories.get(p["did"], []) for p in new}, None):
            scores[s["did"]] = s["p_automated"]
    print(f"{len(prof_by):,} profiled accounts ({len(aud_p):,} from the audience pull), {len(scores):,} scored ({time.time() - t0:.0f}s)")

    # ---- posts, narratives, interactions
    posts = pl.read_parquet(proc / "posts.parquet").select("post_id", "account_id", "created_at", "like_count", "repost_count", "quote_count")
    pn_path = proc / "post_narrative.parquet"
    have_narr = pn_path.exists()
    if have_narr:
        pn = pl.read_parquet(pn_path).sort("prob", descending=True).unique(subset="post_id", keep="first").select("post_id", "narrative_id")
        posts = posts.join(pn, on="post_id", how="left").with_columns(pl.col("narrative_id").fill_null("n0"))
    else:
        posts = posts.with_columns(pl.lit("all").alias("narrative_id"))
    pinfo = {
        r["post_id"]: (r["account_id"], _t(r["created_at"]), r["narrative_id"],
                       int(math.log2(1 + (r["like_count"] or 0) + (r["repost_count"] or 0) + (r["quote_count"] or 0))))
        for r in posts.iter_rows(named=True)
    }
    inter = pl.read_parquet(proc / "interactions.parquet").filter(pl.col("type").is_in(["like", "repost", "quote"]))
    rows = []
    for r in inter.iter_rows(named=True):
        info = pinfo.get(r["post_id"])
        if not info:
            continue
        src, (dst, pt, narr, reach) = r["src_account_id"], info
        ps, pd = scores.get(src), scores.get(dst)
        if ps is None or pd is None or src == dst or src not in prof_by:
            continue
        rows.append((src, r["post_id"], dst, ps, pd, _t(r["created_at"]) or pt, pt, narr, reach, r["type"]))
    print(f"{len(rows):,} usable interactions of {inter.height:,} (both ends scored, actor profiled)")

    # ---- amplifiers and control pool
    by_src: dict[str, list] = {}
    for x in rows:
        by_src.setdefault(x[0], []).append(x)
    amps, pool = {}, {}
    for src, xs in by_src.items():
        if scores[src] >= HUMAN_MAX:
            continue
        bot = [x for x in xs if x[4] >= AUTOMATED_MIN]
        hum = [x for x in xs if x[4] < HUMAN_MAX]
        if bot:
            amps[src] = {"first": min(bot, key=lambda x: x[5] or 0), "n_bot": len({x[1] for x in bot}), "n_hum": len({x[1] for x in hum})}
        elif hum:
            pool[src] = hum
    print(f"amplifiers {len(amps):,}; control pool {len(pool):,}")

    def activity(did):
        p = prof_by[did]
        try:
            age = max((datetime(2026, 11, 14, tzinfo=timezone.utc) - datetime.fromisoformat(p["createdAt"].replace("Z", "+00:00"))).days, 1)
        except Exception:
            age = 365
        return (p.get("postsCount") or 0) / age

    ppd_all = np.array([activity(d) for d in list(amps) + list(pool)])
    qs = np.quantile(ppd_all, [0.2, 0.4, 0.6, 0.8]) if len(ppd_all) else np.array([0, 0, 0, 0])

    def act_b(did):
        return int(np.searchsorted(qs, activity(did)))

    def fol_b(did):
        return int(math.log10(1 + (prof_by[did].get("followersCount") or 0)))

    def keys(narr, pt, reach, did, level):
        w = int((pt or 0) // (3600 * (WINDOW_H if level < 2 else 24)))
        base = (narr, w, act_b(did), fol_b(did))
        return base + ((reach,) if level == 0 else ())

    rng = np.random.default_rng(SEED)
    matches, level_of, used, ctl_post = {}, {}, set(), {}
    remaining = list(amps)
    rng.shuffle(remaining)
    for level in (0, 1, 2):
        idx: dict[tuple, list[str]] = {}
        for c, hs in pool.items():
            if c in used:
                continue
            for x in hs:
                idx.setdefault(keys(x[7], x[6], x[8], c, level), []).append((c, x))
        left = []
        for amp in remaining:
            f = amps[amp]["first"]
            cands = [cx for cx in idx.get(keys(f[7], f[6], f[8], amp, level), []) if cx[0] not in used]
            if cands:
                c, x = cands[int(rng.integers(len(cands)))]
                used.add(c)
                matches[amp], level_of[amp], ctl_post[c] = c, level, x
            else:
                left.append(amp)
        remaining = left
    unmatched = len(remaining)
    lvl = Counter(level_of.values())
    print(f"matched {len(matches):,} of {len(amps):,} amplifiers (exact {lvl[0]}, no reach {lvl[1]}, day window {lvl[2]}); unmatched {unmatched}")

    # ---- features, clustering
    members = list(matches) + list(matches.values())
    role = ["amplifier"] * len(matches) + ["control"] * len(matches)
    y = np.array([1] * len(matches) + [0] * len(matches))
    plist = [prof_by[d] for d in members]
    X = arch_matrix(plist, histories)
    med = np.nanmedian(X, 0)
    med = np.where(np.isnan(med), 0, med)
    Xi = np.where(np.isnan(X), med, X)
    mu, sd = Xi.mean(0), Xi.std(0)
    sd = np.where(sd < 1e-9, 1, sd)
    Z = (Xi - mu) / sd
    sil = {}
    sample = rng.choice(len(Z), min(4000, len(Z)), replace=False) if len(Z) else np.array([], dtype=int)
    for k in range(4, 9):
        km = KMeans(k, n_init=10, random_state=SEED).fit(Z)
        sil[k] = float(silhouette_score(Z[sample], km.labels_[sample])) if len(set(km.labels_[sample])) > 1 else -1
    best_k = max(sil, key=sil.get)
    k_note = f"k = {best_k} by silhouette ({', '.join(f'{k}: {v:.3f}' for k, v in sil.items())})"
    if max(sil.values()) < 0.05:
        best_k, k_note = 4, k_note + "; every silhouette is under 0.05, so k = 4 per the build spec and the clusters are weak"
    km = KMeans(best_k, n_init=10, random_state=SEED).fit(Z)
    lab = km.labels_
    order = np.argsort(-np.bincount(lab))
    ids, labels, defining = [], [], []
    taken: set[str] = set()
    remap = {}
    for rank, c in enumerate(order):
        aid = f"a{rank + 1}"
        l, feats = label_centroid(km.cluster_centers_[c], taken)
        taken.add(l)
        ids.append(aid), labels.append(l), defining.append(feats)
        remap[c] = rank
    lab = np.array([remap[c] for c in lab])
    cents = km.cluster_centers_[order]

    # ---- lift with the shared bootstrap
    base = float(y.mean()) if len(y) else 0.0
    arch_rows = []
    for j, aid in enumerate(ids):
        m = lab == j
        lift, lo, hi = ratio_ci(list(y[m].astype(bool)), base)
        feats = defining[j][:3]
        med_raw = {f: float(np.nanmedian(X[m, ARCH_FEATURES.index(f)])) for f in feats}
        examples = [prof_by[d].get("handle") for d, mm in zip(members, m) if mm and _is_public(prof_by[d])][:5]
        arch_rows.append({
            "archetype_id": aid, "label": labels[j], "size": int(m.sum()), "n_amplifiers": int(y[m].sum()),
            "lift": round(lift, 3), "lift_lo": round(lo, 3), "lift_hi": round(hi, 3),
            "description": "; ".join(describe(f, v) for f, v in med_raw.items()),
            "defining_features": feats, "examples_public": examples,
        })

    # ---- regression: amplified ~ archetype + log(followers) + posts_per_day + narrative + hour
    # each control carries the human post it was matched on, so narrative and hour line up with its amplifier
    key_post = {**{d: amps[d]["first"] for d in matches}, **ctl_post}
    narr = [key_post[d][7] for d in members]
    hours = [_hour(key_post[d][6]) for d in members]
    ref = 0
    cols, names = [np.ones(len(y))], ["intercept"]
    for j in range(1, len(ids)):
        cols.append((lab == j).astype(float)), names.append(f"archetype {ids[j]} (vs {ids[ref]})")
    cols.append(np.log1p([prof_by[d].get("followersCount") or 0 for d in members])), names.append("log(followers)")
    cols.append(np.log1p([activity(d) for d in members])), names.append("log(1 + posts per day)")
    nar_levels = sorted(set(narr))
    for n in nar_levels[1:]:
        cols.append(np.array([x == n for x in narr], dtype=float)), names.append(f"narrative {n} (vs {nar_levels[0]})")
    hr = np.array(hours, dtype=float)
    cols.append(np.sin(2 * np.pi * hr / 24)), names.append("hour (sin)")
    cols.append(np.cos(2 * np.pi * hr / 24)), names.append("hour (cos)")
    Xr = np.column_stack(cols)
    coef, se = logit_fit(Xr, y.astype(float)) if len(y) else (np.zeros(len(names)), np.zeros(len(names)))
    zv = coef / np.where(se > 0, se, 1)
    pv = [math.erfc(abs(z) / math.sqrt(2)) for z in zv]

    # ---- write tables and artifact
    version = f"v0-k{best_k}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    pl.DataFrame(arch_rows).write_parquet(proc / "archetypes.parquet")
    pl.DataFrame({"account_id": members, "archetype_id": [ids[j] for j in lab], "role": role}).write_parquet(proc / "user_archetype.parquet")
    pl.DataFrame({"account_id": members, **{f: X[:, i] for i, f in enumerate(ARCH_FEATURES)}}).write_parquet(proc / "user_features.parquet")
    pl.DataFrame([
        {"account_id": d, "n_bot_posts_amplified": v["n_bot"], "n_human_posts_amplified": v["n_hum"],
         "first_bot_contact_at": datetime.fromtimestamp(v["first"][5], timezone.utc).isoformat() if v["first"][5] else None,
         "matched_control_id": matches.get(d), "match_level": level_of.get(d), "adopted_bot_narrative": None}
        for d, v in amps.items()
    ]).write_parquet(proc / "amplification.parquet")
    joblib.dump({"version": version, "ids": ids, "labels": labels, "centroids": cents, "median": med, "mu": mu, "sd": sd,
                 "features": ARCH_FEATURES}, art / "archetypes.joblib")
    mpath = art / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    manifest["archetypes"] = {"version": version, "k": best_k, "built_at": datetime.now(timezone.utc).isoformat()}
    mpath.write_text(json.dumps(manifest, indent=2))

    # ---- report
    any_sig = any(r["lift_lo"] > 1 or r["lift_hi"] < 1 for r in arch_rows)
    lines = [
        "# Archetypes and the thesis test (M5)",
        "",
        "Command: `python -m src.archetypes.pull_audience && python -m src.archetypes.build`",
        f"Version `{version}`; run time {time.time() - t0:.0f} s. Platform: Bluesky only.",
        "",
        "## Who counts",
        "",
        f"- Amplifier: a likely human (p_automated < {HUMAN_MAX}) who liked, reposted or quoted a story post by a likely automated"
        f" author (p_automated >= {AUTOMATED_MIN}). **{len(amps):,} amplifiers.**",
        f"- Control pool: likely humans who engaged only with human-authored story posts: {len(pool):,}.",
        f"- Usable interactions: {len(rows):,} of {inter.height:,} (both ends scored and the actor profiled).",
        "- What this measures is amplification, not belief: \"more likely to amplify\", never \"more easily fooled\".",
        "",
        "## Matching",
        "",
        f"One control per amplifier, without replacement: same narrative, same {WINDOW_H}-hour window, same reach bucket"
        " (log2 engagement) of the post engaged with, same activity quintile and follower power of ten.",
        "",
        "| Level | Rule | Amplifiers matched |",
        "|---|---|---|",
        f"| 0 | exact | {lvl[0]:,} |",
        f"| 1 | reach bucket dropped | {lvl[1]:,} |",
        f"| 2 | window widened to the day, reach dropped | {lvl[2]:,} |",
        f"| - | unmatched, left out of lift | {unmatched:,} |",
        "",
        f"Match rate {len(matches) / max(len(amps), 1):.0%}."
        + ("" if have_narr else " **Narratives were not available yet** (`post_narrative.parquet` from H3), so every post counts as one"
           " narrative; rerun once H3 lands and matching gains the narrative key."),
        "",
        "## Archetypes",
        "",
        f"{len(members):,} accounts (amplifiers and controls together), {len(ARCH_FEATURES)} public-behavior features, standardized; {k_note}.",
        f"Base amplifier rate in the matched sample: {base:.2f}, so a lift of 1 means \"as likely as similar accounts\".",
        "",
        "| Archetype | Label | Size | Amplifiers | Lift (95% CI) | Typical |",
        "|---|---|---|---|---|---|",
        *[f"| {r['archetype_id']} | {r['label']} | {r['size']:,} | {r['n_amplifiers']:,} | {r['lift']:.2f} ({r['lift_lo']:.2f} to {r['lift_hi']:.2f}) | {r['description']} |" for r in arch_rows],
        "",
        ("At least one archetype's interval excludes 1: some kinds of accounts are measurably more (or less) likely to amplify"
         " likely automated posts than matched accounts that saw the same story." if any_sig else
         "**Null result:** no archetype's interval excludes 1. After matching, no kind of account stands out as more likely to"
         " amplify likely automated posts than similar accounts that saw the same story."),
        "",
        "## Logistic regression",
        "",
        "`amplified_bot ~ archetype + log(followers) + posts_per_day + narrative + hour`, Newton-Raphson, standard errors from the",
        "inverse Hessian, on the matched sample.",
        "",
        "| Term | Coefficient | SE | z | p |",
        "|---|---|---|---|---|",
        *[f"| {n} | {c:+.3f} | {s:.3f} | {z:+.2f} | {p:.3g} |" for n, c, s, z, p in zip(names, coef, se, zv, pv)],
        "",
        "## Caveats",
        "",
        "- The hour terms describe the post, not the person: amplifiers and controls share a 6-hour window, but inside it likely"
        " automated posts go out at different hours than human posts. A significant hour term means automated posts are timed"
        " differently, not that some people amplify at certain hours.",
        "- Likes have timestamps; reposts don't (getRepostedBy), so a repost's time is the post's time.",
        f"- Small sample: only {len(amps):,} likely humans engaged with a likely automated post, because those posts get little"
        " engagement. Intervals are wide; a lift has to be large to show.",
        "- One page (up to 100) of likers, reposters and quoters per post, so very popular posts are undersampled.",
        "- Features are public behavior only; no demographic or sensitive traits. Example accounts on cards are public ones only.",
        "",
    ]
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text("\n".join(lines))
    print(f"wrote {a.report}; {best_k} archetypes; {time.time() - t0:.0f}s")


def _is_public(p: dict) -> bool:
    from src.model.schema import is_public

    return is_public(p)


def _hour(ts: float | None) -> int:
    return datetime.fromtimestamp(ts, timezone.utc).hour if ts else 12



if __name__ == "__main__":
    main()

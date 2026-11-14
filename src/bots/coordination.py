"""Coordination clusters (M3), after Pacheco et al., ICWSM 2021.

    find_clusters(posts, window_s=60) -> [{"cluster_id", "dids", "reasons", "evidence": [{"post_uri", "t", "trace"}]}]

posts: [{"did", "uri", "t", "text"}] (what the API passes), optionally with "urls" (list), "kind" and
"repost_of" (the URI of the reposted post, for kind == "repost").

Traces (behavior two accounts can share):
  link   - the same URL posted by 2+ accounts within window_s of each other (one burst = one trace)
  repost - the same post reposted by 2+ accounts within window_s of each other
  text   - near-duplicate text (MinHash on word 3-grams, estimated Jaccard >= 0.8), any time

Accounts x traces is weighted with TF-IDF; accounts whose cosine similarity is >= SIM_THRESHOLD and who share
at least MIN_SHARED traces are linked; connected components of 2+ accounts are clusters. Reasons are plain
words about observable behavior only, never who runs the accounts.
"""
from __future__ import annotations

import math
import re
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

from src.bots.features import norm_text

SIM_THRESHOLD = 0.6
MIN_SHARED = 2  # one shared link or repost is coincidence; two is a pattern
MIN_TEXT_CHARS = 40  # normalized length below which "duplicate text" is too common to mean anything
N_PERM, BANDS = 64, 8  # LSH: 8 bands of 8 rows, candidate threshold about 0.77
DUP_JACCARD = 0.8
MAX_EVIDENCE = 20

_P = (1 << 61) - 1
_rng = np.random.default_rng(42)
_A = _rng.integers(1, _P, N_PERM, dtype=np.uint64)
_B = _rng.integers(0, _P, N_PERM, dtype=np.uint64)
_URL_TAIL = re.compile(r"[?#].*$")


def _ts(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _norm_url(u: str) -> str | None:
    u = _URL_TAIL.sub("", u.strip().lower()).rstrip("/")
    u = re.sub(r"^https?://(www\.)?", "", u)
    if not u or u.startswith("bsky.app/profile") and "/post/" not in u:
        return None
    return u


def minhash(text: str) -> np.ndarray | None:
    toks = text.split()
    if len(toks) < 3:
        return None
    sh = np.array([zlib.crc32(" ".join(toks[i : i + 3]).encode()) for i in range(len(toks) - 2)], dtype=np.uint64)
    # (a * h + b) mod p, with the multiply kept below 2**64 by using 32-bit shingle hashes and 29-bit a
    v = ((_A[:, None] >> np.uint64(32)) * sh[None, :] + _B[:, None]) % np.uint64(_P)
    return v.min(axis=1)


def _bursts(events: list[tuple[float, str, dict]], window_s: int) -> list[list[tuple[float, str, dict]]]:
    """Split time-sorted (t, did, post) into runs where consecutive events are <= window_s apart."""
    events.sort(key=lambda e: e[0])
    runs, cur = [], [events[0]]
    for e in events[1:]:
        if e[0] - cur[-1][0] <= window_s:
            cur.append(e)
        else:
            runs.append(cur)
            cur = [e]
    runs.append(cur)
    return [r for r in runs if len({d for _, d, _ in r}) >= 2]


def build_traces(posts: list[dict], window_s: int = 60):
    """Returns (traces, trace_kind, trace_posts): traces[trace_id] = set of dids."""
    traces: dict[str, set[str]] = {}
    kind: dict[str, str] = {}
    tposts: dict[str, list[dict]] = {}

    by_url: dict[str, list] = defaultdict(list)
    by_repost: dict[str, list] = defaultdict(list)
    for p in posts:
        t = _ts(p.get("t"))
        if t is None or not p.get("did"):
            continue
        if p.get("kind") == "repost" and p.get("repost_of"):
            by_repost[p["repost_of"]].append((t, p["did"], p))
            continue
        for u in {x for x in (_norm_url(u) for u in p.get("urls") or []) if x}:
            by_url[u].append((t, p["did"], p))

    for label, groups in (("link", by_url), ("repost", by_repost)):
        for key, ev in groups.items():
            if len({d for _, d, _ in ev}) < 2:
                continue
            for i, run in enumerate(_bursts(ev, window_s)):
                tid = f"{label}:{key}:{i}"
                traces[tid] = {d for _, d, _ in run}
                kind[tid] = label
                tposts[tid] = [p for _, _, p in run]

    # near-duplicate text via MinHash LSH; union within verified buckets
    sigs, owners = [], []
    for p in posts:
        if p.get("kind") == "repost":
            continue
        txt = norm_text(p.get("text") or "")
        if len(txt) < MIN_TEXT_CHARS:
            continue
        s = minhash(txt)
        if s is not None:
            sigs.append(s)
            owners.append(p)
    if sigs:
        S = np.vstack(sigs)
        parent = list(range(len(S)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        rows = N_PERM // BANDS
        for b in range(BANDS):
            buckets: dict[bytes, list[int]] = defaultdict(list)
            band = S[:, b * rows : (b + 1) * rows]
            for i in range(len(S)):
                buckets[band[i].tobytes()].append(i)
            for idx in buckets.values():
                if len(idx) < 2:
                    continue
                head = idx[0]
                for j in idx[1:]:
                    if find(j) != find(head) and (S[head] == S[j]).mean() >= DUP_JACCARD:
                        parent[find(j)] = find(head)
        groups: dict[int, list[int]] = defaultdict(list)
        for i in range(len(S)):
            groups[find(i)].append(i)
        for g, idx in groups.items():
            dids = {owners[i]["did"] for i in idx}
            if len(dids) < 2:
                continue
            tid = f"text:{g}"
            traces[tid] = dids
            kind[tid] = "text"
            tposts[tid] = [owners[i] for i in idx]
    return traces, kind, tposts


def account_similarity(traces: dict[str, set[str]]):
    """TF-IDF weighted account x trace matrix and cosine similarity (sparse). Returns (dids, sim csr, shared csr)."""
    from scipy.sparse import csr_matrix

    dids = sorted({d for s in traces.values() for d in s})
    if not dids:
        return dids, None, None
    di = {d: i for i, d in enumerate(dids)}
    tids = list(traces)
    rows, cols = [], []
    for j, t in enumerate(tids):
        for d in traces[t]:
            rows.append(di[d])
            cols.append(j)
    M = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(dids), len(tids)))
    df = np.asarray(M.sum(0)).ravel()
    idf = np.log(len(dids) / df) + 1.0
    W = M.multiply(idf[None, :]).tocsr()
    norms = np.sqrt(np.asarray(W.multiply(W).sum(1)).ravel())
    norms[norms == 0] = 1
    from scipy.sparse import diags

    Wn = diags(1 / norms) @ W
    sim = (Wn @ Wn.T).tocsr()
    shared = (M @ M.T).tocsr()
    return dids, sim, shared


def _components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    comp: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        comp[find(i)].append(i)
    return [c for c in comp.values() if len(c) >= 2]


def _gap(ps: list[dict]) -> float:
    """Median gap in seconds between consecutive posts of one trace (bursts chain gaps up to window_s)."""
    ts = sorted(t for t in (_ts(p.get("t")) for p in ps) if t is not None)
    return float(np.median(np.diff(ts))) if len(ts) >= 2 else 0.0


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _reasons(members: set[str], traces, kind, tposts) -> list[str]:
    inside = [t for t, ds in traces.items() if len(ds & members) >= 2]
    by_kind = Counter(kind[t] for t in inside)
    out = []
    n = len(members)
    if by_kind["repost"]:
        gaps = [_gap([p for p in tposts[t] if p["did"] in members]) for t in inside if kind[t] == "repost"]
        out.append(f"{n} accounts reposted the same post seconds apart (typically {max(1, round(np.median(gaps)))} s), {_plural(by_kind['repost'], 'time')}")
    if by_kind["link"]:
        gaps = [_gap([p for p in tposts[t] if p["did"] in members]) for t in inside if kind[t] == "link"]
        out.append(f"{n} accounts shared the same link seconds apart (typically {max(1, round(np.median(gaps)))} s), {_plural(by_kind['link'], 'time')}")
    if by_kind["text"]:
        k = sum(1 for t in inside if kind[t] == "text" for p in tposts[t] if p["did"] in members)
        out.append(f"{n} accounts posted near-identical text ({_plural(k, 'post')} in {_plural(by_kind['text'], 'group')})")
    return out


TRACE_WORDS = {"link": "same link within a minute", "repost": "reposted the same post within a minute", "text": "near-identical text"}


def find_clusters(posts: list[dict], window_s: int = 60) -> list[dict]:
    traces, kind, tposts = build_traces(posts, window_s)
    dids, sim, shared = account_similarity(traces)
    if not dids:
        return []
    sim = sim.tocoo()
    sh = shared.tocsr()
    edges = [(i, j) for i, j, v in zip(sim.row, sim.col, sim.data) if i < j and v >= SIM_THRESHOLD and sh[i, j] >= MIN_SHARED]
    comps = sorted(_components(len(dids), edges), key=len, reverse=True)
    out = []
    for c in comps:
        members = {dids[i] for i in c}
        ev = []
        for t, ds in traces.items():
            if len(ds & members) >= 2:
                for p in tposts[t]:
                    if p["did"] in members:
                        ev.append({"post_uri": p.get("uri"), "t": p.get("t"), "trace": TRACE_WORDS[kind[t]]})
        ev.sort(key=lambda e: e["t"] or "")
        out.append({"cluster_id": f"c{len(out)}", "dids": sorted(members), "reasons": _reasons(members, traces, kind, tposts), "evidence": ev[:MAX_EVIDENCE]})
    return out


def account_coord_features(posts: list[dict], window_s: int = 60) -> dict[str, dict]:
    """Per-account coordination features for the bot model: cluster size, shared traces, max similarity."""
    traces, kind, tposts = build_traces(posts, window_s)
    dids, sim, shared = account_similarity(traces)
    if not dids:
        return {}
    n_traces = Counter(d for s in traces.values() for d in s)
    sim = sim.tolil()
    sim.setdiag(0)
    sim = sim.tocsr()
    max_sim = np.asarray(sim.max(1).todense()).ravel()
    clusters = find_clusters(posts, window_s)
    size = {d: len(c["dids"]) for c in clusters for d in c["dids"]}
    cid = {d: c["cluster_id"] for c in clusters for d in c["dids"]}
    return {
        d: {"coord_cluster_size_log": math.log1p(size.get(d, 0)), "coord_traces_log": math.log1p(n_traces[d]),
            "coord_max_sim": float(max_sim[i]), "coord_cluster_id": cid.get(d)}
        for i, d in enumerate(dids)
    }


def posts_from_inputs(histories: dict[str, list[dict]], story_posts: dict[str, list[dict]] | None = None) -> list[dict]:
    """Flatten score_accounts inputs into find_clusters posts: story posts plus history items (with reposts)."""
    out, seen = [], set()
    for did, items in (story_posts or {}).items():
        for d in items:
            r = d.get("record") or {}
            urls = [ft["uri"] for fc in r.get("facets") or [] for ft in fc.get("features") or [] if ft.get("uri")]
            e = r.get("embed") or {}
            x = (e.get("external") or (e.get("media") or {}).get("external") or {}).get("uri")
            if x:
                urls.append(x)
            seen.add((did, d.get("uri")))
            out.append({"did": did, "uri": d.get("uri"), "t": r.get("createdAt"), "text": r.get("text") or "", "urls": urls})
    for did, items in histories.items():
        for it in items or []:
            if it.get("kind") == "repost":
                out.append({"did": did, "uri": it.get("uri"), "t": it.get("t"), "kind": "repost", "repost_of": it.get("uri"), "text": ""})
            elif (did, it.get("uri")) not in seen:
                out.append({"did": did, "uri": it.get("uri"), "t": it.get("t"), "text": it.get("text") or "", "urls": it.get("urls") or []})
    return out


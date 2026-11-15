import { useEffect, useMemo, useRef, useState } from "react";
import type { ClaimNarrative } from "../api/types";
import { fmtInt, pct } from "../lib/format";
import { narrativeColor, narrativeHex } from "../lib/narrativeColor";

/* "Volume vs. voices": one dot per matching post, sorted in four steps.
 *   1 Volume       every post in one grey cloud: what a reader sees
 *   2 Narratives   the dots sort into one column per way of telling the claim
 *   3 Automated    posts from likely automated accounts settle to the bottom of each column. The interval is
 *                  drawn, not hidden: solid red is its low end, ringed dots are the rest of the range it allows
 *   4 Without them the point estimate drops out, the columns re-settle and re-rank
 * Every count comes from the /claim JSON (narratives[].posts or share_of_matches, bot_post_share and its
 * interval). Above a cap one dot stands for several posts, and the caption says how many. */

const SIGNAL = "#D9472B";
const PAPER = "#F7F5F0";
const GREY = "#8A8F99";
const STEPS = ["Volume", "Narratives", "Likely automated", "Without them"] as const;
const DUR = 950; // ms per transition
const DWELL = 2100; // ms per step while autoplaying

interface Col {
  id: string;
  label: string;
  color: string;
  swatch: string;
  posts: number; // real posts
  n: number; // dots
  lo: number;
  a: number;
  hi: number;
  bot: number;
  ci?: [number, number];
}
interface Dot {
  col: number;
  k: number; // index inside its column, 0 = bottom (automated first)
  g: number; // shuffled global index for the cloud
  seed: number;
}
interface P {
  x: number;
  y: number;
  r: number;
  o: number; // opacity
}

function rng(seed: number) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const ordinal = (n: number) => `${n}${n % 10 === 1 && n !== 11 ? "st" : n % 10 === 2 && n !== 12 ? "nd" : n % 10 === 3 && n !== 13 ? "rd" : "th"}`;

export function VoiceSorter({ narr, matched, subject = "claim" }: { narr: ClaimNarrative[]; matched: number; subject?: "claim" | "story" }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [W, setW] = useState(900);
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const fixed = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("stage") : null;
  const [stage, setStage] = useState(fixed != null ? Math.max(0, Math.min(3, +fixed - 1)) : reduced ? 2 : 0);
  const [auto, setAuto] = useState(false);
  const played = useRef(fixed != null || !!reduced);
  // Label room depends on how narrow the columns get: wide columns take name + counts on two lines, narrow ones
  // wrap to four, and very narrow ones (compact) show a swatch and one number, with the names in a legend below.
  const k = Math.max(1, narr.length);
  const perCol = (W - 20 * (k - 1)) / k;
  const compact = perCol < 90;
  const LABEL_H = compact ? 44 : perCol < 170 ? 98 : W < 600 ? 96 : 58;
  const H = (W < 600 ? 280 : 300) + LABEL_H;
  const plotH = H - LABEL_H;

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(300, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* columns and dots */
  const { cols, dots, unit, total } = useMemo(() => {
    const raw = narr
      .map((n, i) => ({ n, i, posts: n.posts ?? Math.round(n.share_of_matches * matched) }))
      .filter((x) => x.posts > 0)
      .sort((a, b) => b.posts - a.posts);
    const total = raw.reduce((s, x) => s + x.posts, 0);
    const cap = W < 600 ? 900 : 2000;
    const unit = Math.max(1, Math.ceil(total / cap));
    const cols: Col[] = raw.map(({ n, i, posts }) => {
      const d = Math.max(1, Math.round(posts / unit));
      const ci = n.bot_post_share_ci;
      const a = Math.round(d * n.bot_post_share);
      return {
        id: n.id,
        label: n.label,
        color: narrativeHex(n.id, i),
        swatch: narrativeColor(n.id, i),
        posts,
        n: d,
        a,
        lo: ci ? Math.min(a, Math.round(d * ci[0])) : a,
        hi: ci ? Math.max(a, Math.round(d * ci[1])) : a,
        bot: n.bot_post_share,
        ci,
      };
    });
    const N = cols.reduce((s, c) => s + c.n, 0);
    const r = rng(N * 7919 + cols.length);
    const perm = Array.from({ length: N }, (_, i) => i);
    for (let i = N - 1; i > 0; i--) {
      const j = Math.floor(r() * (i + 1));
      [perm[i], perm[j]] = [perm[j], perm[i]];
    }
    const dots: Dot[] = [];
    let g = 0;
    cols.forEach((c, ci) => {
      for (let k = 0; k < c.n; k++) dots.push({ col: ci, k, g: perm[g++], seed: r() });
    });
    return { cols, dots, unit, total };
  }, [narr, matched, W]);

  /* geometry: one cell size for every column step, so dots keep their size while they move */
  const geo = useMemo(() => {
    const k = cols.length;
    const gap = W < 600 ? 14 : 28;
    const colW = Math.min(W < 600 ? 120 : 190, (W - gap * (k - 1)) / Math.max(1, k));
    const left = (W - (colW * k + gap * (k - 1))) / 2;
    const nmax = Math.max(1, ...cols.map((c) => c.n));
    let s = 11;
    while (s > 2.5 && Math.ceil(nmax / Math.max(1, Math.floor(colW / s))) * s > plotH - 8) s -= 0.25;
    const per = Math.max(1, Math.floor(colW / s));
    const base = plotH - 2;
    const colX = (slot: number) => left + slot * (colW + gap);
    const cell = (slot: number, k: number): { x: number; y: number } => ({
      x: colX(slot) + (colW - per * s) / 2 + (k % per) * s + s / 2,
      y: base - Math.floor(k / per) * s - s / 2,
    });
    // cloud: a sunflower spiral, sized so the dots fill a disc
    const N = dots.length;
    const R = Math.min(W * 0.42, plotH * 0.48);
    const c = R / Math.sqrt(Math.max(1, N));
    const cloud = (g: number) => {
      const th = g * 2.39996323;
      const rr = c * Math.sqrt(g + 0.5);
      return { x: W / 2 + rr * Math.cos(th), y: plotH / 2 + rr * Math.sin(th) };
    };
    const order0 = cols.map((_, i) => i);
    const rest = cols.map((c) => c.n - c.a);
    const order3 = [...order0].sort((a, b) => rest[b] - rest[a]);
    const slot0 = new Map(order0.map((c, i) => [c, i]));
    const slot3 = new Map(order3.map((c, i) => [c, i]));
    return { s, per, colW, colX, cell, cloud, cloudR: Math.max(1.2, c * 0.42), slot0, slot3, base };
  }, [cols, dots.length, W, plotH]);

  const target = (d: Dot, st: number): P => {
    const dr = Math.max(1, geo.s * 0.36);
    if (st === 0) {
      const p = geo.cloud(d.g);
      return { ...p, r: Math.min(dr, geo.cloudR), o: 0.75 };
    }
    const c = cols[d.col];
    if (st < 3) return { ...geo.cell(geo.slot0.get(d.col)!, d.k), r: dr, o: 1 };
    if (d.k < c.a) {
      const p = geo.cell(geo.slot3.get(d.col)!, d.k);
      return { x: p.x, y: geo.base + 36 + d.seed * 30, r: dr * 0.7, o: 0 };
    }
    return { ...geo.cell(geo.slot3.get(d.col)!, d.k - c.a), r: dr, o: 1 };
  };

  /* animation state lives outside React: positions now, the step we are heading to, when it started */
  const anim = useRef<{ from: P[]; to: P[]; cur: P[]; t0: number; st: number; prev: number; raf: number }>({ from: [], to: [], cur: [], t0: 0, st: -1, prev: 0, raf: 0 });

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = W * dpr;
    cv.height = plotH * dpr;
    cv.style.width = `${W}px`;
    cv.style.height = `${plotH}px`;
    const ctx = cv.getContext("2d")!;
    const A = anim.current;
    const to = dots.map((d) => target(d, stage));
    const sameLen = A.cur.length === dots.length;
    A.from = sameLen ? A.cur.map((p) => ({ ...p })) : to.map((p) => ({ ...p }));
    A.to = to;
    A.cur = A.from.map((p) => ({ ...p }));
    // only a change of step animates; a resize or new data just redraws in place
    const instant = reduced || !sameLen || A.st === -1 || A.st === stage;
    A.t0 = performance.now() - (instant ? DUR * 3 : 0);
    A.prev = A.st < 0 ? stage : A.st;
    A.st = stage;

    const color = (d: Dot, st: number) => {
      if (st === 0) return { fill: GREY, ring: false };
      const c = cols[d.col];
      if (st >= 2 && d.k < c.lo) return { fill: SIGNAL, ring: false };
      if (st >= 2 && d.k < c.hi) return { fill: SIGNAL, ring: true };
      return { fill: c.color, ring: false };
    };

    const frame = (now: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, plotH);
      let busy = false;
      // baseline rule under the columns
      if (stage > 0) {
        ctx.strokeStyle = "#E3DFD6";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, geo.base + 0.5);
        ctx.lineTo(W, geo.base + 0.5);
        ctx.stroke();
      }
      for (let i = 0; i < dots.length; i++) {
        const d = dots[i];
        const delay = d.seed * 0.35 * DUR;
        const t = Math.max(0, Math.min(1, (now - A.t0 - delay) / DUR));
        if (t < 1) busy = true;
        const e = ease(t);
        const f = A.from[i], g = A.to[i];
        const p = (A.cur[i] = { x: f.x + (g.x - f.x) * e, y: f.y + (g.y - f.y) * e, r: f.r + (g.r - f.r) * e, o: f.o + (g.o - f.o) * e });
        if (p.o <= 0.01) continue;
        // colour switches halfway through each dot's own move
        const col = color(d, t > 0.5 ? stage : A.prev);
        ctx.globalAlpha = p.o;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        if (col.ring) {
          ctx.fillStyle = PAPER;
          ctx.fill();
          ctx.strokeStyle = col.fill;
          ctx.lineWidth = Math.max(0.8, p.r * 0.45);
          ctx.stroke();
        } else {
          ctx.fillStyle = col.fill;
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      if (busy) A.raf = requestAnimationFrame(frame);
    };
    cancelAnimationFrame(A.raf);
    A.raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(A.raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, dots, geo, W, plotH]);

  /* play once, the first time the figure is mostly on screen */
  useEffect(() => {
    const el = wrap.current;
    if (!el || played.current) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.intersectionRatio >= 0.55 && !played.current) {
          played.current = true;
          setAuto(true);
          io.disconnect();
        }
      },
      { threshold: [0.55] },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  useEffect(() => {
    if (!auto) return;
    if (stage >= 3) {
      setAuto(false);
      return;
    }
    const id = setTimeout(() => setStage((s) => s + 1), stage === 0 ? 1200 : DWELL);
    return () => clearTimeout(id);
  }, [auto, stage]);

  const go = (s: number) => {
    setAuto(false);
    setStage(Math.max(0, Math.min(3, s)));
  };

  /* the words for each step, all from the same counts the dots use */
  const A = cols.reduce((s, c) => s + c.posts * c.bot, 0);
  const LO = cols.reduce((s, c) => s + c.posts * (c.ci?.[0] ?? c.bot), 0);
  const HI = cols.reduce((s, c) => s + c.posts * (c.ci?.[1] ?? c.bot), 0);
  const restPosts = cols.map((c) => c.posts * (1 - c.bot));
  const order3 = cols.map((_, i) => i).sort((a, b) => restPosts[b] - restPosts[a]);
  const moved = order3.map((c, i) => ({ c, from: c + 1, to: i + 1 })).filter((m) => m.from !== m.to);
  const round = (x: number) => (x >= 100 ? Math.round(x / 10) * 10 : Math.round(x));
  const top = cols[0];

  const lines: [string, string][] = [
    [
      subject === "claim" ? `${fmtInt(matched)} posts make this claim.` : `${fmtInt(matched)} posts told the story one of these ways.`,
      `Each dot is ${unit > 1 ? `${unit} posts` : "one post"}. This is the volume a reader scrolls past: it looks like everyone is saying it.`,
    ],
    [
      cols.length === 1 ? "They all tell it one way." : `They tell it ${cols.length} ways.`,
      top ? `“${top.label}” is the biggest, with ${pct(top.posts / Math.max(1, total))} of the posts. Each column is one narrative.` : "",
    ],
    [
      `About ${fmtInt(round(A))} came from likely automated accounts.`,
      `The interval runs from ${fmtInt(round(LO))} to ${fmtInt(round(HI))} posts. Solid red is its low end; ringed dots are the rest of the range it allows. They sit at the bottom of each column.`,
    ],
    [
      `Without them, about ${fmtInt(round(total - A))} posts remain.`,
      moved.length
        ? moved
            .slice(0, 2)
            .map((m) => `“${cols[m.c].label}” moves from ${ordinal(m.from)} to ${ordinal(m.to)}`)
            .join("; ") + "."
        : `The order of the narratives doesn’t change. Ringed dots stay: within the interval, they may still be automated.`,
    ],
  ];

  const slotOf = stage === 3 ? geo.slot3 : geo.slot0;

  return (
    <section className="blk sorter" aria-labelledby="sorter-h">
      <div className="sorter-head">
        <div>
          <h2 id="sorter-h">Volume vs. voices</h2>
          <p className="sub">{subject === "claim" ? "How much of the volume is likely automated, post by post." : "Every post in a narrative, sorted: how much of the volume was likely automated."}</p>
        </div>
        <div className="sorter-steps" role="group" aria-label="Steps">
          {STEPS.map((s, i) => (
            <button key={s} type="button" aria-pressed={stage === i} className={stage === i ? "on" : i < stage ? "past" : ""} onClick={() => go(i)}>
              <span className="n">{i + 1}</span>
              <span className="t">{s}</span>
            </button>
          ))}
          <button type="button" className="sorter-replay" onClick={() => (setStage(0), setAuto(true))} aria-label="Play all four steps">
            Play
          </button>
        </div>
      </div>
      <div className="sorter-read" aria-live="polite">
        <p className="sorter-big">{lines[stage][0]}</p>
        <p className="sorter-small">{lines[stage][1]}</p>
      </div>
      <div
        className="sorter-fig"
        ref={wrap}
        tabIndex={0}
        aria-label="Post sorter. Use 1 to 4 or the arrow keys to change step."
        onKeyDown={(e) => {
          if (/^[1-4]$/.test(e.key)) go(+e.key - 1);
          if (e.key === "ArrowRight") go(stage + 1);
          if (e.key === "ArrowLeft") go(stage - 1);
        }}
        style={{ height: H }}
      >
        <canvas ref={canvas} aria-hidden="true" />
        <div className={`sorter-labels${stage === 0 ? " off" : ""}`} aria-hidden={stage === 0}>
          {cols.map((c, i) => {
            const slot = slotOf.get(i) ?? i;
            return (
              <div key={c.id} className={`sorter-lab${compact ? " is-compact" : perCol < 170 ? " is-narrow" : ""}`} style={{ left: geo.colX(slot), width: geo.colW, top: plotH + 8 }} title={c.label}>
                <span className="nm">
                  <i className="sw" style={{ background: c.swatch }} />
                  {!compact && c.label}
                </span>
                {compact ? (
                  <span className="ct">{stage === 2 ? <b>{pct(c.bot)}</b> : stage === 3 ? <b>−{fmtInt(Math.round(c.posts * c.bot))}</b> : fmtInt(c.posts)}</span>
                ) : (
                  <span className="ct">
                    {stage === 3 ? <>{fmtInt(round(c.posts * (1 - c.bot)))} left</> : <>{fmtInt(c.posts)} posts</>}
                    {stage === 2 && <b> · {pct(c.bot)} auto.</b>}
                    {stage === 3 && <b> · {fmtInt(Math.round(c.posts * c.bot))} out</b>}
                  </span>
                )}
              </div>
            );
          })}
        </div>
        <span className={`sorter-cloud-cap${stage === 0 ? "" : " off"}`} style={{ top: plotH + 12 }}>
          {fmtInt(matched)} posts, unsorted
        </span>
      </div>
      {compact && (
        <ul className="sorter-legend" aria-label="Narratives">
          {cols.map((c) => (
            <li key={c.id}>
              <i className="sw" style={{ background: c.swatch }} />
              <span className="nm">{c.label}</span>
              <span className="ct">
                {fmtInt(c.posts)} posts · <b>{pct(c.bot)} auto.</b>
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="sorter-key">
        <span className={stage < 2 ? "dim" : ""}>
          <i className="k-solid" /> likely automated, low end of the interval
        </span>
        <span className={stage < 2 ? "dim" : ""}>
          <i className="k-ring" /> rest of the interval
        </span>
        <span className="sorter-note">Counts use the 0.5 score cutoff and each narrative’s 95% interval{unit > 1 ? `; 1 dot = ${unit} posts` : ""}.</span>
      </p>
    </section>
  );
}

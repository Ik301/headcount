import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Narr } from "../model";
import { pc, type Arch, type HedgeRow } from "./data";
import { Receipt } from "../../components/Receipt";

/* The guided story's charts. One visual grammar throughout: a dot for the best estimate, a line for the
 * 95% interval, a dashed rule for the comparison value. Red is reserved for likely automated. */

export const C = { signal: "#D9472B", signalInk: "#B3371E", human: "#2F6F8F", ink: "#16181D", ink2: "#4A4F5A", cap: "#6B707A", rule: "#E3DFD6", panel: "#EBE7DF" };

export function useWidth<T extends HTMLElement>(fallback = 800): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.getBoundingClientRect().width || fallback);
    const ro = new ResizeObserver(([e]) => setW(Math.max(200, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [fallback]);
  return [ref, w];
}

/** Hatching for an interval: the engineering-drawing convention for "somewhere in this range". */
function Hatch({ id, color }: { id: string; color: string }) {
  return (
    <defs>
      <pattern id={id} patternUnits="userSpaceOnUse" width={4} height={4} patternTransform="rotate(45)">
        <rect width={1.6} height={4} fill={color} fillOpacity={0.75} />
      </pattern>
    </defs>
  );
}
const safeId = (s: string) => s.replace(/[^a-zA-Z0-9_-]/g, "");

/** An inline term, defined in the sentence that follows it the first time it appears. */
export function Term({ children }: { children: ReactNode }) {
  return <dfn className="g-term">{children}</dfn>;
}

/* ---------------- 100 squares: the share of posts ---------------- */

export function Waffle({ share, cols }: { share: number; cols: number }) {
  const red = Math.round(share * 100);
  const rows = Math.ceil(100 / cols);
  const s = 100 / cols;
  return (
    <svg className="g-waffle" viewBox={`0 0 ${cols * s} ${rows * s}`} role="img" aria-label={`${red} of every 100 posts came from likely automated accounts`}>
      {Array.from({ length: 100 }, (_, i) => {
        const x = (i % cols) * s, y = Math.floor(i / cols) * s;
        return <rect key={i} x={x + s * 0.09} y={y + s * 0.09} width={s * 0.82} height={s * 0.82} rx={s * 0.08} fill={i < red ? C.signal : C.panel} />;
      })}
    </svg>
  );
}

/* ---------------- one estimate with its interval on a 0..max scale ---------------- */

export function EstimateBar({ value, ci, max, color = C.signal, label }: { value: number; ci?: [number, number]; max: number; color?: string; label: string }) {
  const [ref, w] = useWidth<HTMLDivElement>(600);
  const hid = safeId(useId());
  const L = 6, R = 6, H = 46;
  const x = (v: number) => L + (Math.min(v, max) / max) * (w - L - R);
  const ticks = niceTicks(max);
  return (
    <div ref={ref} className="g-estimate">
      <svg width={w} height={H} role="img" aria-label={label}>
        <line x1={L} x2={w - R} y1={16} y2={16} stroke={C.rule} strokeWidth={6} strokeLinecap="round" />
        <Hatch id={hid} color={color} />
        {ci && <rect x={x(ci[0])} y={10} width={Math.max(2, x(ci[1]) - x(ci[0]))} height={12} rx={1.5} fill={`url(#${hid})`} stroke={color} strokeOpacity={0.45} />}
        {ci && [ci[0], ci[1]].map((v, i) => <line key={i} x1={x(v)} x2={x(v)} y1={9} y2={23} stroke={color} strokeWidth={1.5} />)}
        <circle cx={x(value)} cy={16} r={6.5} fill={color} stroke="#fff" strokeWidth={2} />
        {ticks.map((t, i) => (
          <text key={t} x={x(t)} y={41} textAnchor={i === 0 ? "start" : i === ticks.length - 1 ? "end" : "middle"} className="g-ax">
            {Math.round(t * 100)}%
          </text>
        ))}
      </svg>
    </div>
  );
}

function niceTicks(max: number): number[] {
  const step = max <= 0.1 ? 0.02 : max <= 0.2 ? 0.05 : max <= 0.5 ? 0.1 : 0.25;
  const out: number[] = [];
  for (let v = 0; v <= max + 1e-9; v += step) out.push(Math.round(v * 1000) / 1000);
  return out;
}

/* ---------------- likely automated share by narrative ---------------- */

export function NarrativeRows({ narr, baseline, note }: { narr: Narr[]; baseline?: number; note?: Record<string, string> }) {
  const [ref, w] = useWidth<HTMLDivElement>(560);
  const hid = safeId(useId());
  const max = Math.max(0.05, ...narr.map((n) => n.ci?.[1] ?? n.bot), (baseline ?? 0) * 1.4) * 1.08;
  const L = 8, R = 8, H = 34;
  const x = (v: number) => L + (v / max) * (w - L - R);
  const ticks = niceTicks(max).filter((t) => t <= max);
  return (
    <div className="g-rows" role="table" aria-label="Share of posts from likely automated accounts, by narrative, with 95% intervals">
      {narr.map((n) => {
        // Reuters-style: the verdict is drawn, not left to the reader. Solid when the interval clears the
        // whole-story line, hollow and lighter when it doesn't, and the words say which.
        const v = baseline != null && n.ci ? (n.ci[0] > baseline ? "above" : n.ci[1] < baseline ? "below" : "same") : null;
        const solid = v !== "same";
        return (
          <div key={n.id} className={`g-row is-${v ?? "na"}`} role="row">
            <div className="g-row-label" role="rowheader">
              <span className="g-row-name">{n.label}</span>
              {note?.[n.id] && <span className="g-row-note">{note[n.id]}</span>}
            </div>
            <div className="g-row-chart" ref={n === narr[0] ? ref : undefined} role="cell" aria-label={`${pc(n.bot)}${n.ci ? `, interval ${pc(n.ci[0])} to ${pc(n.ci[1])}` : ""}`}>
              <svg width={w} height={H} aria-hidden="true">
                {baseline != null && <line x1={x(baseline)} x2={x(baseline)} y1={0} y2={H} stroke={C.ink2} strokeDasharray="3 3" />}
                <Hatch id={`${hid}${n.id}`} color={C.signal} />
                {n.ci && <rect x={x(n.ci[0])} y={H / 2 - 5} width={Math.max(2, x(n.ci[1]) - x(n.ci[0]))} height={10} rx={1.5} fill={`url(#${hid}${n.id})`} stroke={C.signal} strokeOpacity={solid ? 0.5 : 0.25} opacity={solid ? 1 : 0.6} />}
                <circle cx={x(n.bot)} cy={H / 2} r={6} fill={solid ? C.signal : "#fff"} stroke={solid ? "#fff" : C.signal} strokeWidth={2} />
              </svg>
            </div>
            <div className="g-row-val" role="cell">
              <Receipt
                align="right"
                title={`Receipt · ${n.label}`}
                lines={[
                  ["Posts", n.posts.toLocaleString("en-US")],
                  ["From likely automated", n.botPosts ? `about ${Math.round(n.botPosts).toLocaleString("en-US")}` : pc(n.bot)],
                  ["Counted as automated", "account score ≥ 0.5"],
                  ["Estimate", pc(n.bot)],
                  n.ci && ["95% interval", `${pc(n.ci[0])} to ${pc(n.ci[1])}`],
                  baseline != null && ["Whole story", pc(baseline)],
                  ["Narrative labels", "language model, one per post"],
                  ["Interval method", "bootstrap over accounts"],
                ]}
              >
                {pc(n.bot)}
              </Receipt>
              {v && <span className="g-verdict">{v === "above" ? "above the story" : v === "below" ? "below the story" : "not clearly different"}</span>}
            </div>
          </div>
        );
      })}
      <div className="g-row g-row-axis" aria-hidden="true">
        <div className="g-row-label" />
        <div className="g-row-chart">
          <svg width={w} height={30}>
            {ticks.map((t, i) => (
              <text key={t} x={x(t)} y={14} textAnchor={i === 0 ? "start" : "middle"} className="g-ax">
                {Math.round(t * 100)}%
              </text>
            ))}
            {baseline != null && (
              <text x={x(baseline)} y={28} textAnchor="middle" className="g-ax g-ax-strong">
                whole story {pc(baseline)}
              </text>
            )}
          </svg>
        </div>
        <div className="g-row-val" />
      </div>
    </div>
  );
}

/* ---------------- the ranking with and without likely automated accounts ---------------- */

export function RankBars({ narr, removed }: { narr: Narr[]; removed: boolean }) {
  const val = (n: Narr) => (removed ? n.volumeShareWithout ?? n.shareWithout : n.volumeShare ?? n.share);
  const order = [...narr].sort((a, b) => val(b) - val(a));
  const pos = new Map(order.map((n, i) => [n.id, i]));
  const max = Math.max(...narr.map((n) => Math.max(n.volumeShare ?? n.share, n.volumeShareWithout ?? n.shareWithout)));
  const RH = 48;
  return (
    <ol className="g-rank" style={{ height: narr.length * RH }} aria-label={removed ? "Narratives ranked without likely automated accounts" : "Narratives ranked by share of the conversation"}>
      {narr.map((n) => (
        <li key={n.id} style={{ transform: `translateY(${(pos.get(n.id) ?? 0) * RH}px)` }}>
          <span className="g-rank-n">{(pos.get(n.id) ?? 0) + 1}</span>
          <span className="g-rank-body">
            <span className="g-rank-name">{n.label}</span>
            <span className="g-rank-bar">
              <i style={{ width: `${(val(n) / max) * 100}%` }} />
            </span>
          </span>
          <span className="g-rank-v">{pc(val(n))}</span>
        </li>
      ))}
    </ol>
  );
}

/* ---------------- hedging: newsrooms vs Bluesky ---------------- */

export function HedgeBars({ rows }: { rows: HedgeRow[] }) {
  const [ref, w] = useWidth<HTMLDivElement>(560);
  const H = 36, L = 2, R = 8;
  const x = (v: number) => L + v * (w - L - R);
  return (
    <div className="g-rows g-hedge" role="table" aria-label="Share that hedge, with 95% intervals">
      {rows.map((r, i) => (
        <div key={r.id} className={`g-row${r.tone === "news" ? " is-news" : ""}`} role="row">
          <div className="g-row-label" role="rowheader">
            <span className="g-row-name">{r.label}</span>
            <span className="g-row-note">
              {r.n != null ? `${r.n.toLocaleString("en-US")} ${r.tone === "news" ? "headlines" : "posts"}` : ""}
              {r.note ? `${r.n != null ? ", " : ""}${r.note}` : ""}
            </span>
          </div>
          <div className="g-row-chart" ref={i === 0 ? ref : undefined} role="cell" aria-label={`${pc(r.share)} hedge${r.ci ? `, interval ${pc(r.ci[0])} to ${pc(r.ci[1])}` : ""}`}>
            <svg width={w} height={H} aria-hidden="true">
              <rect x={L} y={4} width={w - L - R} height={16} rx={2} fill={C.panel} />
              <rect x={L} y={4} width={Math.max(0, x(r.share) - L)} height={16} rx={2} fill={r.tone === "news" ? C.ink : C.human} />
              {r.ci && (
                <g stroke={C.ink2} strokeWidth={1.5}>
                  <line x1={x(r.ci[0])} x2={x(r.ci[1])} y1={28} y2={28} />
                  <line x1={x(r.ci[0])} x2={x(r.ci[0])} y1={24} y2={32} />
                  <line x1={x(r.ci[1])} x2={x(r.ci[1])} y1={24} y2={32} />
                </g>
              )}
            </svg>
          </div>
          <div className="g-row-val" role="cell">
            {pc(r.share)}
          </div>
        </div>
      ))}
      <div className="g-row g-row-axis" aria-hidden="true">
        <div className="g-row-label" />
        <div className="g-row-chart">
          <svg width={w} height={18}>
            {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
              <text key={t} x={x(t)} y={14} textAnchor={i === 0 ? "start" : i === 4 ? "end" : "middle"} className="g-ax">
                {t * 100}%
              </text>
            ))}
          </svg>
        </div>
        <div className="g-row-val" />
      </div>
    </div>
  );
}

/* ---------------- archetype lift, log scale centred on 1 ---------------- */

export function LiftRows({ arch }: { arch: Arch[] }) {
  const [ref, w] = useWidth<HTMLDivElement>(560);
  const hid = safeId(useId());
  // A small group's interval can start at 0 (no amplifiers in some resamples). log(0) is -Infinity, so the
  // axis is clamped to 1/4..4 and an interval that runs past the edge is drawn open-ended with an arrow.
  const MIN = 0.25, MAX = 4;
  const ok = (v: number | undefined) => v != null && isFinite(v) && v > 0;
  const ends = arch.flatMap((a) => [a.lift, ...(a.ci ?? [])]).filter(ok) as number[];
  const lo = Math.max(MIN, Math.min(0.67, ...ends) * 0.95);
  const hi = Math.min(MAX, Math.max(1.5, ...ends) * 1.05);
  const span = Math.max(Math.log(1 / lo), Math.log(hi));
  const L = 10, R = 10, H = 34;
  const clamp = (v: number) => Math.min(Math.exp(span), Math.max(Math.exp(-span), ok(v) ? v : Math.exp(-span)));
  const x = (v: number) => L + ((Math.log(clamp(v)) + span) / (2 * span)) * (w - L - R);
  const ticks = [0.25, 0.5, 0.67, 1, 1.5, 2, 3, 4].filter((t) => Math.abs(Math.log(t)) <= span + 1e-9);
  const tickLabel = (t: number) => (t === 0.67 ? "⅔" : t === 0.25 ? "¼" : t === 0.5 ? "½" : String(t)) + "×";
  return (
    <div className="g-rows g-lift" role="table" aria-label="How likely each group was to amplify likely automated accounts, compared with all real accounts, with 95% intervals">
      {arch.map((a, i) => {
        const clear = a.ci ? a.ci[0] > 1 || a.ci[1] < 1 : false;
        const cutLo = a.ci ? !ok(a.ci[0]) || a.ci[0] < Math.exp(-span) : false;
        const cutHi = a.ci ? a.ci[1] > Math.exp(span) : false;
        const y = H / 2;
        return (
          <div key={a.id} className={`g-row${clear ? " is-clear" : " is-same"}`} role="row">
            <div className="g-row-label" role="rowheader">
              <span className="g-row-name">{a.label}</span>
              <span className="g-row-note">{a.size.toLocaleString("en-US")} accounts</span>
            </div>
            <div className="g-row-chart" ref={i === 0 ? ref : undefined} role="cell" aria-label={`${a.lift.toFixed(2)} times${a.ci ? `, interval ${a.ci[0].toFixed(2)} to ${a.ci[1].toFixed(2)}` : ""}`}>
              <svg width={w} height={H} aria-hidden="true">
                <line x1={x(1)} x2={x(1)} y1={0} y2={H} stroke={C.ink2} strokeDasharray="3 3" />
                <Hatch id={`${hid}${a.id}`} color={C.human} />
                {a.ci && (
                  <rect
                    x={x(a.ci[0]) + (cutLo ? 6 : 0)}
                    y={y - 5}
                    width={Math.max(2, x(a.ci[1]) - (cutHi ? 6 : 0) - (x(a.ci[0]) + (cutLo ? 6 : 0)))}
                    height={10}
                    rx={1.5}
                    fill={`url(#${hid}${a.id})`}
                    stroke={C.human}
                    strokeOpacity={clear ? 0.5 : 0.25}
                    opacity={clear ? 1 : 0.6}
                  />
                )}
                {cutLo && <path d={`M${x(a.ci![0]) + 7} ${y - 5} L${x(a.ci![0])} ${y} L${x(a.ci![0]) + 7} ${y + 5}`} fill="none" stroke={C.human} strokeOpacity={0.6} strokeWidth={1.6} />}
                {cutHi && <path d={`M${x(a.ci![1]) - 7} ${y - 5} L${x(a.ci![1])} ${y} L${x(a.ci![1]) - 7} ${y + 5}`} fill="none" stroke={C.human} strokeOpacity={0.6} strokeWidth={1.6} />}
                <circle cx={x(a.lift)} cy={y} r={6} fill={clear ? C.human : "#fff"} stroke={clear ? "#fff" : C.human} strokeWidth={2} />
              </svg>
            </div>
            <div className="g-row-val" role="cell">
              {a.lift.toFixed(1)}×<span className="g-verdict">{!a.ci ? "" : a.ci[0] > 1 ? "more likely" : a.ci[1] < 1 ? "less likely" : "no clear difference"}</span>
            </div>
          </div>
        );
      })}
      <div className="g-row g-row-axis" aria-hidden="true">
        <div className="g-row-label" />
        <div className="g-row-chart">
          <svg width={w} height={34}>
            {ticks.map((t) => (
              <text key={t} x={x(t)} y={14} textAnchor="middle" className={`g-ax${t === 1 ? " g-ax-strong" : ""}`}>
                {tickLabel(t)}
              </text>
            ))}
            <text x={L} y={30} className="g-ax">
              ← less likely
            </text>
            <text x={x(1)} y={30} textAnchor="middle" className="g-ax g-ax-strong">
              no difference
            </text>
            <text x={w - R} y={30} textAnchor="end" className="g-ax">
              more likely →
            </text>
          </svg>
        </div>
        <div className="g-row-val" />
      </div>
    </div>
  );
}

/* ---------------- hand check: n squares, hits filled ---------------- */

export function CheckGrid({ hits, n, cols }: { hits: number; n: number; cols: number }) {
  const rows = Math.ceil(n / cols);
  const s = 20;
  return (
    <svg className="g-check" viewBox={`0 0 ${cols * s} ${rows * s}`} role="img" aria-label={`${hits} of ${n} hand-checked accounts were clearly automated`}>
      {Array.from({ length: n }, (_, i) => {
        const x = (i % cols) * s, y = Math.floor(i / cols) * s;
        const hit = i < hits;
        return <rect key={i} x={x + 2} y={y + 2} width={s - 4} height={s - 4} rx={2} fill={hit ? C.signal : "#fff"} stroke={hit ? "none" : C.ink2} strokeWidth={1.2} />;
      })}
    </svg>
  );
}

/* ---------------- recall@k: model vs posting rate alone ---------------- */

export function RecallChart({ rows }: { rows: { k: string; model: number; base?: number }[] }) {
  const [ref, w] = useWidth<HTMLDivElement>(520);
  const H = 170, L = 34, R = 12, T = 12, B = 30;
  const x = (i: number) => L + (rows.length > 1 ? i / (rows.length - 1) : 0.5) * (w - L - R);
  const y = (v: number) => T + (1 - v) * (H - T - B);
  const line = (vals: (number | undefined)[]) => vals.map((v, i) => (v == null ? "" : `${i ? "L" : "M"}${x(i)},${y(v)}`)).join("");
  const hasBase = rows.some((r) => r.base != null);
  return (
    <div ref={ref} className="g-recall">
      <svg width={w} height={H} role="img" aria-label="Share of hidden labeled bots found in the model's top k accounts, against posting rate alone">
        {[0, 0.5, 1].map((g) => (
          <g key={g}>
            <line x1={L} x2={w - R} y1={y(g)} y2={y(g)} stroke={C.rule} />
            <text x={L - 6} y={y(g) + 4} textAnchor="end" className="g-ax">
              {g * 100}%
            </text>
          </g>
        ))}
        <path d={line(rows.map((r) => r.model))} fill="none" stroke={C.signal} strokeWidth={2} />
        {hasBase && <path d={line(rows.map((r) => r.base))} fill="none" stroke={C.ink2} strokeWidth={1.5} strokeDasharray="4 3" />}
        {rows.map((r, i) => (
          <g key={r.k}>
            <circle cx={x(i)} cy={y(r.model)} r={3.5} fill={C.signal} />
            <text x={x(i)} y={H - 10} textAnchor="middle" className="g-ax">
              top {r.k}
            </text>
          </g>
        ))}
        <text x={x(rows.length - 1) - 4} y={y(rows[rows.length - 1].model) - 9} textAnchor="end" className="g-ax g-ax-strong">
          our model
        </text>
        {hasBase && (
          <text x={x(rows.length - 1) - 4} y={y(rows[rows.length - 1].base ?? 0) - 8} textAnchor="end" className="g-ax">
            posting rate alone
          </text>
        )}
      </svg>
    </div>
  );
}

/* ---------------- score cutoff strip ---------------- */

export function CutoffStrip({ strip, current = "0.5" }: { strip: Record<string, number>; current?: string }) {
  const keys = Object.keys(strip).sort((a, b) => +a - +b);
  const max = Math.max(...keys.map((k) => strip[k])) || 1;
  return (
    <ul className="g-cuts">
      {keys.map((k) => (
        <li key={k} className={k === current ? "is-current" : ""}>
          <span className="g-cut-k">score {k}+</span>
          <span className="g-cut-bar">
            <i style={{ width: `${(strip[k] / max) * 100}%` }} />
          </span>
          <span className="g-cut-v">{pc(strip[k])}</span>
        </li>
      ))}
    </ul>
  );
}

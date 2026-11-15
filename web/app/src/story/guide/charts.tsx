import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Narr } from "../model";
import { pc, type Arch, type HedgeRow } from "./data";

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
  const L = 6, R = 6, H = 46;
  const x = (v: number) => L + (Math.min(v, max) / max) * (w - L - R);
  const ticks = niceTicks(max);
  return (
    <div ref={ref} className="g-estimate">
      <svg width={w} height={H} role="img" aria-label={label}>
        <line x1={L} x2={w - R} y1={16} y2={16} stroke={C.rule} strokeWidth={6} strokeLinecap="round" />
        {ci && <line x1={x(ci[0])} x2={x(ci[1])} y1={16} y2={16} stroke={color} strokeOpacity={0.35} strokeWidth={6} strokeLinecap="round" />}
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
  const max = Math.max(0.05, ...narr.map((n) => n.ci?.[1] ?? n.bot), (baseline ?? 0) * 1.4) * 1.08;
  const L = 8, R = 8, H = 34;
  const x = (v: number) => L + (v / max) * (w - L - R);
  const ticks = niceTicks(max).filter((t) => t <= max);
  return (
    <div className="g-rows" role="table" aria-label="Share of posts from likely automated accounts, by narrative, with 95% intervals">
      {narr.map((n) => (
        <div key={n.id} className="g-row" role="row">
          <div className="g-row-label" role="rowheader">
            <span className="g-row-name">{n.label}</span>
            {note?.[n.id] && <span className="g-row-note">{note[n.id]}</span>}
          </div>
          <div className="g-row-chart" ref={n === narr[0] ? ref : undefined} role="cell" aria-label={`${pc(n.bot)}${n.ci ? `, interval ${pc(n.ci[0])} to ${pc(n.ci[1])}` : ""}`}>
            <svg width={w} height={H} aria-hidden="true">
              {baseline != null && <line x1={x(baseline)} x2={x(baseline)} y1={0} y2={H} stroke={C.ink2} strokeDasharray="3 3" />}
              {n.ci && <line x1={x(n.ci[0])} x2={x(n.ci[1])} y1={H / 2} y2={H / 2} stroke={C.signal} strokeOpacity={0.45} strokeWidth={5} strokeLinecap="round" />}
              <circle cx={x(n.bot)} cy={H / 2} r={6} fill={C.signal} stroke="#fff" strokeWidth={2} />
            </svg>
          </div>
          <div className="g-row-val" role="cell">
            {pc(n.bot)}
          </div>
        </div>
      ))}
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
  const lo = Math.min(0.67, ...arch.map((a) => a.ci?.[0] ?? a.lift)) * 0.95;
  const hi = Math.max(1.5, ...arch.map((a) => a.ci?.[1] ?? a.lift)) * 1.05;
  const span = Math.max(Math.log(1 / lo), Math.log(hi));
  const L = 8, R = 8, H = 34;
  const x = (v: number) => L + ((Math.log(v) + span) / (2 * span)) * (w - L - R);
  const ticks = [0.5, 0.67, 0.8, 1, 1.25, 1.5, 2].filter((t) => Math.abs(Math.log(t)) <= span);
  return (
    <div className="g-rows g-lift" role="table" aria-label="How likely each group was to amplify likely automated accounts, compared with all real accounts, with 95% intervals">
      {arch.map((a, i) => (
        <div key={a.id} className="g-row" role="row">
          <div className="g-row-label" role="rowheader">
            <span className="g-row-name">{a.label}</span>
            <span className="g-row-note">{a.size.toLocaleString("en-US")} accounts</span>
          </div>
          <div className="g-row-chart" ref={i === 0 ? ref : undefined} role="cell" aria-label={`${a.lift.toFixed(2)} times${a.ci ? `, interval ${a.ci[0].toFixed(2)} to ${a.ci[1].toFixed(2)}` : ""}`}>
            <svg width={w} height={H} aria-hidden="true">
              <line x1={x(1)} x2={x(1)} y1={0} y2={H} stroke={C.ink2} strokeDasharray="3 3" />
              {a.ci && <line x1={x(a.ci[0])} x2={x(a.ci[1])} y1={H / 2} y2={H / 2} stroke={C.human} strokeOpacity={0.5} strokeWidth={5} strokeLinecap="round" />}
              <circle cx={x(a.lift)} cy={H / 2} r={6} fill={C.human} stroke="#fff" strokeWidth={2} />
            </svg>
          </div>
          <div className="g-row-val" role="cell">
            {a.lift.toFixed(1)}×
          </div>
        </div>
      ))}
      <div className="g-row g-row-axis" aria-hidden="true">
        <div className="g-row-label" />
        <div className="g-row-chart">
          <svg width={w} height={34}>
            {ticks.map((t) => (
              <text key={t} x={x(t)} y={14} textAnchor="middle" className="g-ax">
                {t}×
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

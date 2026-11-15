import { useEffect, useMemo, useRef, useState } from "react";
import { fmtInt, utcLabel } from "../lib/format";
import type { Model } from "./model";

const L = 46, R = 14, TOP = 46, BOT = 26;

/** Stacked narrative river (SVG) with event markers and a draggable playhead. It is the scrubber:
 *  pointer drag, click, or arrow keys (shift = one day). */
export function River({ m, T, onScrub }: { m: Model; T: number; onScrub: (h: number) => void }) {
  const ref = useRef<SVGSVGElement>(null);
  const [W, setW] = useState(1200);
  const HH = 244;
  const drag = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(400, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const iw = W - L - R, ih = HH - TOP - BOT;
  const smooth = (a: number[]) => a.map((v, i) => (a[Math.max(0, i - 1)] + v * 2 + a[Math.min(a.length - 1, i + 1)]) / 4);
  const geo = useMemo(() => {
    const H = m.hours;
    const layers = m.river.map((r) => ({ id: r.id, p: smooth(r.posts), a: smooth(r.bots) }));
    const tot = Array.from({ length: H }, (_, h) => layers.reduce((s, l) => s + (l.p[h] ?? 0), 0));
    const raw = Math.max(1, ...tot);
    const step = raw > 1000 ? 500 : raw > 400 ? 200 : raw > 100 ? 50 : 10;
    const ymax = Math.ceil(raw / step) * step;
    const xs = (h: number) => L + (h / H) * iw;
    const ys = (v: number) => TOP + ih - (v / ymax) * ih;
    const base = new Array(H).fill(0);
    const path = (lo: number[], hi: number[]) => {
      let d = "";
      for (let h = 0; h < H; h++) d += `${h ? "L" : "M"}${xs(h + 0.5).toFixed(1)},${ys(hi[h]).toFixed(1)}`;
      for (let h = H - 1; h >= 0; h--) d += `L${xs(h + 0.5).toFixed(1)},${ys(lo[h]).toFixed(1)}`;
      return d + "Z";
    };
    const bands = layers.map((l) => {
      const lo = base.slice(), mid = base.map((b, h) => b + Math.min(l.a[h], l.p[h])), hi = base.map((b, h) => b + l.p[h]);
      for (let h = 0; h < H; h++) base[h] = hi[h];
      return { id: l.id, top: path(mid, hi), auto: path(lo, mid) };
    });
    const days: { x: number; label: string }[] = [];
    for (let h = 0; h <= H; h++) {
      const d = new Date(m.start + h * 3_600_000);
      if (d.getUTCHours() === 0 && xs(h) < W - R - 36) days.push({ x: xs(h), label: `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getUTCMonth()]} ${d.getUTCDate()}` });
    }
    return { xs, ys, ymax, bands, days };
  }, [m, iw, ih]);

  const color = new Map(m.narratives.map((n) => [n.id, n.hex]));
  const fromEv = (ev: React.PointerEvent) => {
    const b = ref.current!.getBoundingClientRect();
    return ((ev.clientX - b.left - L) / (b.width - L - R)) * m.hours;
  };
  const x = geo.xs(T);
  return (
    <svg
      ref={ref}
      className="river"
      viewBox={`0 0 ${W} ${HH}`}
      tabIndex={0}
      role="slider"
      aria-label="Replay time"
      aria-valuemin={0}
      aria-valuemax={m.hours}
      aria-valuenow={Number(T.toFixed(1))}
      aria-valuetext={`${utcLabel(new Date(m.start + T * 3_600_000))} UTC`}
      onPointerDown={(ev) => {
        drag.current = true;
        (ev.target as Element).setPointerCapture?.(ev.pointerId);
        onScrub(fromEv(ev));
      }}
      onPointerMove={(ev) => drag.current && onScrub(fromEv(ev))}
      onPointerUp={() => (drag.current = false)}
      onKeyDown={(ev) => {
        if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") {
          ev.preventDefault();
          onScrub(T + (ev.key === "ArrowRight" ? 1 : -1) * (ev.shiftKey ? 24 : 1));
        }
        if (ev.key === "Home") onScrub(0);
        if (ev.key === "End") onScrub(m.hours);
      }}
    >
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}>
          <line x1={L} x2={W - R} y1={geo.ys(geo.ymax * f)} y2={geo.ys(geo.ymax * f)} stroke="#DCE0D5" />
          <text x={L - 8} y={geo.ys(geo.ymax * f) + 4} textAnchor="end" className="ax">
            {fmtInt(geo.ymax * f)}
          </text>
        </g>
      ))}
      <text x={4} y={TOP - 18} className="ax sans">
        posts / h
      </text>
      <g>
        {geo.bands.map((b) => (
          <g key={b.id}>
            <path d={b.top} fill={color.get(b.id) ?? "#7C867F"} fillOpacity={0.82} />
            <path d={b.auto} fill="#C81E66" />
          </g>
        ))}
      </g>
      {geo.days.map((d) => (
        <g key={d.x}>
          <line x1={d.x} x2={d.x} y1={TOP + ih} y2={TOP + ih + 5} stroke="#7C867F" />
          <text x={d.x + 4} y={TOP + ih + 17} className="ax">
            {d.label}
          </text>
        </g>
      ))}
      <line x1={L} x2={W - R} y1={TOP + ih} y2={TOP + ih} stroke="#7C867F" />
      {/* Events are numbered on the chart and spelled out in the list under it (RiverEvents), so labels never
          collide however close the events are. Major events get a solid line, the rest a dotted one. */}
      {m.events.map((e, i) => {
        const ex = geo.xs(e.h);
        const past = e.h <= T;
        return (
          <g key={e.t}>
            <title>{`${i + 1}. ${e.label}, ${utcLabel(new Date(e.t))} UTC`}</title>
            <line x1={ex} x2={ex} y1={TOP - 12} y2={TOP + ih} stroke={e.major ? "#111814" : "#7C867F"} strokeDasharray={e.major ? undefined : "2 3"} />
            <circle cx={ex} cy={TOP - 22} r={9} fill={past ? "#111814" : "#F9FAF6"} stroke="#111814" strokeWidth={1.2} />
            <text x={ex} y={TOP - 18.5} textAnchor="middle" className="ev-n" fill={past ? "#F9FAF6" : "#111814"}>
              {i + 1}
            </text>
          </g>
        );
      })}
      <rect x={x} y={TOP - 2} width={Math.max(0, W - R - x)} height={ih + 2} fill="#F9FAF6" fillOpacity={0.72} pointerEvents="none" />
      <g transform={`translate(${x},0)`} pointerEvents="none">
        <line y1={TOP - 4} y2={TOP + ih + 4} stroke="#111814" strokeWidth={1.5} />
        <rect x={-5} y={TOP + ih - 4} width={10} height={10} rx={2} fill="#111814" />
      </g>
    </svg>
  );
}

/** The numbered events under the river: time and label, click to jump there. */
export function RiverEvents({ m, T, onScrub }: { m: Model; T: number; onScrub: (h: number) => void }) {
  if (!m.events.length) return null;
  return (
    <ol className="river-evs">
      {m.events.map((e, i) => (
        <li key={e.t} className={e.h <= T ? "is-past" : ""}>
          <button onClick={() => onScrub(e.h + 0.4)}>
            <span className="river-ev-n">{i + 1}</span>
            <span className="river-ev-t">{utcLabel(new Date(e.t))} UTC</span>
            <span className="river-ev-l">{e.label}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

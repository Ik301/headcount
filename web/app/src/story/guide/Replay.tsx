import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../../components/Icons";
import { handle } from "../../lib/format";
import type { Model } from "../model";
import { C, useWidth } from "./charts";
import { dayLabel, replayCast, timeLabel, type GNode, type GuideData } from "./data";

const SEEN_KEY = "sbt.replaySeen.v1";
const WEEK_SECONDS = 14; // a full replay of the window takes about this long

/** Chapter 1's figure: the accounts that matter, appearing hour by hour, over a posts-per-hour strip that
 *  doubles as the scrubber. Plays once on a visitor's first view; after that it opens on the full week. */
export function ReplayFigure({ m, g, still }: { m: Model; g: GuideData; still: boolean }) {
  const end = m.hours - 0.01;
  const firstView = useMemo(() => {
    if (still) return false;
    try {
      if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;
      return localStorage.getItem(SEEN_KEY) !== "1";
    } catch {
      return false;
    }
  }, [still]);
  const [T, setT] = useState(firstView ? 0 : end);
  const [playing, setPlaying] = useState(firstView);
  const raf = useRef(0);

  useEffect(() => {
    if (!playing) return;
    try {
      localStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* private mode */
    }
    let last = 0;
    const speed = m.hours / WEEK_SECONDS;
    const tick = (ts: number) => {
      const dt = last ? Math.min(0.1, (ts - last) / 1000) : 0;
      last = ts;
      let done = false;
      setT((t) => {
        const nt = t + dt * speed;
        if (nt >= end) return (done = true), end;
        return nt;
      });
      if (done) setPlaying(false);
      else raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, m.hours, end]);

  const scrub = useCallback((h: number) => {
    setPlaying(false);
    setT(Math.max(0, Math.min(end, h)));
  }, [end]);

  const toggle = () => {
    if (playing) return setPlaying(false);
    if (T >= end - 0.5) setT(0);
    setPlaying(true);
  };

  return (
    <div className="g-replay">
      <div className="g-replay-bar">
        <button className="g-play" onClick={toggle} aria-label={playing ? "Pause the replay" : "Play the week"}>
          <Icon name={playing ? "pause" : "play"} />
          <span>{playing ? "Pause" : T >= end - 0.5 ? "Replay the week" : "Play"}</span>
        </button>
        <span className="g-clock" aria-live="off">
          {timeLabel(new Date(m.start + Math.min(T, end) * 3_600_000)).replace(/:\d\d UTC$/, ":00 UTC")}
        </span>
      </div>
      <Network m={m} T={T} />
      <Timeline g={g} m={m} T={T} onScrub={scrub} />
    </div>
  );
}

function Network({ m, T }: { m: Model; T: number }) {
  const [wrap, w] = useWidth<HTMLDivElement>(1000);
  const canvas = useRef<HTMLCanvasElement>(null);
  const narrow = w < 640;
  const H = narrow ? Math.round(w * 0.95) : Math.round(Math.min(420, Math.max(320, w * 0.38)));
  // layout in a fixed frame per aspect, then scale: stable positions while resizing
  const frame = narrow ? { W: 600, H: 570 } : { W: 1000, H: 420 };
  const cast = useMemo(() => replayCast(m, frame.W, frame.H), [m, frame.W, frame.H]);
  const [tip, setTip] = useState<{ x: number; y: number; n: GNode } | null>(null);
  const sc = Math.min(w / frame.W, H / frame.H);
  const ox = (w - frame.W * sc) / 2, oy = (H - frame.H * sc) / 2;

  // the public accounts worth naming: largest first, never overlapping
  const named = useMemo(() => [...cast.nodes].filter((n) => n.handle).sort((a, b) => b.weight - a.weight), [cast]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = w * dpr;
    cv.height = H * dpr;
    const g = cv.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, H);
    const X = (x: number) => ox + x * sc, Y = (y: number) => oy + y * sc;
    for (const e of cast.edges) {
      if (e.t > T) continue;
      g.beginPath();
      g.moveTo(X(e.a.x), Y(e.a.y));
      g.lineTo(X(e.b.x), Y(e.b.y));
      g.strokeStyle = e.amp ? "rgba(47,111,143,.22)" : e.a.role === "auto" && e.b.role === "auto" ? "rgba(217,71,43,.35)" : "rgba(160,154,142,.22)";
      g.lineWidth = 0.8;
      g.stroke();
    }
    const order = { amp: 0, public: 1, auto: 2 } as const;
    const vis = cast.nodes.filter((n) => n.t <= T).sort((a, b) => order[a.role] - order[b.role]);
    const rs = Math.max(0.75, Math.min(1.2, sc * 1.1));
    for (const n of vis) {
      g.beginPath();
      g.arc(X(n.x), Y(n.y), n.r * rs, 0, Math.PI * 2);
      if (n.role === "auto") {
        g.fillStyle = C.signal;
        g.fill();
      } else if (n.role === "amp") {
        g.fillStyle = C.human;
        g.fill();
      } else {
        g.fillStyle = "#fff";
        g.fill();
        g.strokeStyle = C.ink;
        g.lineWidth = 1.4;
        g.stroke();
      }
    }
    // labels: up to 6 (3 on phones), skipping any that would collide
    const boxes: [number, number, number, number][] = [];
    g.font = "500 11.5px 'IBM Plex Mono', monospace";
    g.textBaseline = "middle";
    let count = 0;
    for (const n of named) {
      if (count >= (narrow ? 3 : 6)) break;
      if (n.t > T) continue;
      const text = handle(n.handle)!;
      const tw = g.measureText(text).width;
      let tx = X(n.x) + n.r * rs + 5;
      if (tx + tw > w - 4) tx = X(n.x) - n.r * rs - 5 - tw;
      const ty = Y(n.y);
      const b: [number, number, number, number] = [tx - 3, ty - 9, tx + tw + 3, ty + 9];
      if (boxes.some((o) => !(b[2] < o[0] || b[0] > o[2] || b[3] < o[1] || b[1] > o[3]))) continue;
      boxes.push(b);
      count++;
      g.lineWidth = 4;
      g.strokeStyle = "rgba(247,245,240,.95)";
      g.strokeText(text, tx, ty);
      g.fillStyle = C.ink;
      g.fillText(text, tx, ty);
    }
  }, [cast, T, w, H, sc, ox, oy, named, narrow]);

  const pick = (ev: React.MouseEvent) => {
    const b = canvas.current!.getBoundingClientRect();
    const x = (ev.clientX - b.left - ox) / sc, y = (ev.clientY - b.top - oy) / sc;
    let best: GNode | null = null, bd = 10 / sc;
    for (const n of cast.nodes) {
      if (n.t > T) continue;
      const d = Math.hypot(n.x - x, n.y - y);
      if (d < bd) (bd = d), (best = n);
    }
    return best;
  };
  const vis = cast.nodes.filter((n) => n.t <= T);
  const count = (r: GNode["role"]) => vis.filter((n) => n.role === r).length;

  return (
    <figure className="g-net">
      <ul className="g-legend" aria-label="Legend">
        <li>
          <i className="g-dot is-auto" aria-hidden="true" />
          <span>
            <b>{count("auto").toLocaleString("en-US")}</b> likely automated accounts
          </span>
        </li>
        <li>
          <i className="g-dot is-amp" aria-hidden="true" />
          <span>
            <b>{count("amp").toLocaleString("en-US")}</b> real accounts that liked, reposted or quoted them
          </span>
        </li>
        <li>
          <i className="g-dot is-public" aria-hidden="true" />
          <span>
            <b>{count("public").toLocaleString("en-US")}</b> public accounts, named
          </span>
        </li>
      </ul>
      <div ref={wrap} className="g-net-canvas">
        <canvas
          ref={canvas}
          style={{ width: w, height: H }}
          role="img"
          aria-label={`Network replay at ${timeLabel(new Date(m.start + T * 3_600_000))}: ${count("auto")} likely automated accounts, ${count("amp")} real accounts amplifying them, ${count("public")} public accounts.`}
          onMouseMove={(ev) => {
            const n = pick(ev);
            setTip(n ? { x: ev.clientX, y: ev.clientY, n } : null);
          }}
          onMouseLeave={() => setTip(null)}
        />
        {tip && (
          <div className="g-tip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
            {tip.n.handle ? <span className="mono">{handle(tip.n.handle)}</span> : <span>A private account, not named</span>}
            <br />
            <span className="g-tip-s">{tip.n.role === "auto" ? "Likely automated" : tip.n.role === "amp" ? "Real account that amplified a likely automated one" : "Public account"}</span>
          </div>
        )}
      </div>
    </figure>
  );
}

function Timeline({ g, m, T, onScrub }: { g: GuideData; m: Model; T: number; onScrub: (h: number) => void }) {
  const [ref, w] = useWidth<HTMLDivElement>(1000);
  // stagger event markers that would touch (several events can land within hours of each other)
  const rowsOf = useMemo(() => {
    const out: number[] = [];
    const lastX: number[] = [];
    g.events.forEach((e) => {
      const ex = (e.h / m.hours) * w;
      let row = 0;
      while (lastX[row] != null && ex - lastX[row] < 20) row++;
      lastX[row] = ex;
      out.push(row);
    });
    return out;
  }, [g.events, m.hours, w]);
  const rows = Math.max(0, ...rowsOf) + 1;
  const H = (w < 640 ? 110 : 128) + (rows - 1) * 20;
  const L = 0, R = 0, TOP = 24 + (rows - 1) * 20, BOT = 22;
  const ih = H - TOP - BOT;
  const drag = useRef(false);
  const smooth = (a: number[]) => a.map((v, i) => (a[Math.max(0, i - 1)] + v * 2 + a[Math.min(a.length - 1, i + 1)]) / 4);
  const geo = useMemo(() => {
    const p = smooth(g.postsPerHour), a = smooth(g.autoPerHour);
    const max = Math.max(1, ...p);
    const xs = (h: number) => L + (h / m.hours) * (w - L - R);
    const ys = (v: number) => TOP + ih - (v / max) * ih;
    const area = (vals: number[]) => {
      let d = `M${xs(0)},${ys(0)}`;
      vals.forEach((v, h) => (d += `L${xs(h + 0.5).toFixed(1)},${ys(v).toFixed(1)}`));
      return d + `L${xs(m.hours)},${ys(0)}Z`;
    };
    const days: { x: number; label: string }[] = [];
    for (let h = 0; h < m.hours; h += 24) days.push({ x: xs(h), label: dayLabel(new Date(m.start + h * 3_600_000)) });
    return { xs, total: area(p), auto: area(a), days };
  }, [g, m, w, ih]);
  const fromEv = (ev: React.PointerEvent) => {
    const b = ref.current!.getBoundingClientRect();
    return ((ev.clientX - b.left) / b.width) * m.hours;
  };
  const x = geo.xs(T);
  const narrow = w < 640;
  return (
    <div className="g-timeline">
      <div ref={ref} className="g-tl-svg">
        <svg
          width={w}
          height={H}
          tabIndex={0}
          role="slider"
          aria-label="Replay time"
          aria-valuemin={0}
          aria-valuemax={Math.round(m.hours)}
          aria-valuenow={Math.round(T)}
          aria-valuetext={timeLabel(new Date(m.start + T * 3_600_000))}
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
              ev.stopPropagation();
              onScrub(T + (ev.key === "ArrowRight" ? 1 : -1) * (ev.shiftKey ? 24 : 3));
            }
            if (ev.key === "Home") onScrub(0);
            if (ev.key === "End") onScrub(m.hours);
          }}
        >
          <path d={geo.total} fill="#CFC9BD" />
          <path d={geo.auto} fill={C.signal} />
          <line x1={0} x2={w} y1={TOP + ih} y2={TOP + ih} stroke="#A9A397" />
          {geo.days.map((d, i) => (
            <g key={d.x}>
              <line x1={d.x} x2={d.x} y1={TOP + ih} y2={TOP + ih + 4} stroke="#A9A397" />
              {(!narrow || i % 2 === 0) && (
                <text x={d.x + 3} y={H - 6} className="g-ax">
                  {d.label}
                </text>
              )}
            </g>
          ))}
          {g.events.map((e, i) => {
            const ex = geo.xs(e.h);
            const cy = TOP - 13 - rowsOf[i] * 20;
            return (
              <g key={e.t}>
                <line x1={ex} x2={ex} y1={cy + 8} y2={TOP + ih} stroke={C.ink} strokeOpacity={0.55} />
                <circle cx={ex} cy={cy} r={8.5} fill={T >= e.h ? C.ink : "#fff"} stroke={C.ink} strokeWidth={1.2} />
                <text x={ex} y={cy + 3.5} textAnchor="middle" className="g-ev-n" fill={T >= e.h ? "#fff" : C.ink}>
                  {i + 1}
                </text>
              </g>
            );
          })}
          <rect x={x} y={TOP - 2} width={Math.max(0, w - x)} height={ih + 2} fill="#F7F5F0" fillOpacity={0.75} pointerEvents="none" />
          <line x1={x} x2={x} y1={TOP - 2} y2={TOP + ih + 2} stroke={C.ink} strokeWidth={2} pointerEvents="none" />
        </svg>
      </div>
      <p className="g-tl-key">
        Posts per hour. <span className="g-key-auto">Red</span>: from likely automated accounts. Drag to move through the week.
      </p>
      <ol className="g-events">
        {g.events.map((e) => (
          <li key={e.t} className={T >= e.h ? "is-past" : ""}>
            <button type="button" onClick={() => onScrub(e.h + 0.5)}>
              <span className="g-ev-time">{timeLabel(new Date(e.t))}</span>
              <span className="g-ev-label">{e.label}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

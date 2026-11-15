import { useEffect, useMemo, useRef, useState } from "react";
import { acctRef, handle } from "../lib/format";
import { AUTOMATED, GH, GW, HUMAN_MAX, clusterCenter, type Model, type Node } from "./model";

/* Canvas 2D network. Chosen over sigma.js/WebGL because it renders the export's capped graph
 * (<= 3,000 nodes) at 60 fps, prints in headless screenshots without GPU flags, and keeps the
 * node styling (rings, dashed self-labels) in plain code a designer can edit. */

const C = { signal: "#D9472B", human: "#2F6F8F", ink: "#16181D", ink3: "#8A8F99", rule: "#CFCAC0", label: "#4A4F5A" };

export function Network({ m, T, onCluster }: { m: Model; T: number; onCluster: (narrativeId: string) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [w, setW] = useState(900);
  const [tip, setTip] = useState<{ x: number; y: number; n: Node } | null>(null);
  const H = Math.round(Math.min(380, Math.max(260, w * 0.34)));
  const scale = Math.min(w / GW, H / GH);
  const ox = (w - GW * scale) / 2, oy = (H - GH * scale) / 2;

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const labels = useMemo(
    () => m.narratives.map((n) => ({ n, c: clusterCenter(m.nodes, n.id) })).filter((x) => x.c),
    [m],
  );

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = w * dpr;
    cv.height = H * dpr;
    const g = cv.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, H);
    const X = (x: number) => ox + x * scale, Y = (y: number) => oy + y * scale;

    for (const e of m.edges) {
      if (e.t > T) continue;
      g.beginPath();
      g.moveTo(X(e.a.x), Y(e.a.y));
      g.lineTo(X(e.b.x), Y(e.b.y));
      g.strokeStyle = e.kind === "co" ? "rgba(217,71,43,.5)" : e.kind === "amp" ? "rgba(47,111,143,.38)" : "rgba(207,202,192,.75)";
      g.lineWidth = e.kind === "gen" ? 0.7 : 1;
      g.stroke();
    }
    const order = (n: Node) => (n.handle ? 4 : n.selfLabel ? 3 : n.p >= AUTOMATED ? 2 : n.ampT <= T ? 1 : 0);
    const vis = m.nodes.filter((n) => n.t <= T).sort((a, b) => order(a) - order(b));
    const hexOf = new Map(m.narratives.map((n) => [n.id, n.hex]));
    for (const n of vis) {
      const r = n.r * Math.max(0.8, scale);
      g.beginPath();
      g.arc(X(n.x), Y(n.y), r, 0, Math.PI * 2);
      g.setLineDash([]);
      if (n.handle && !n.selfLabel) {
        g.fillStyle = "#fff";
        g.fill();
        g.strokeStyle = C.ink;
        g.lineWidth = 1.6;
        g.stroke();
      } else if (n.selfLabel) {
        g.fillStyle = "#fff";
        g.fill();
        g.setLineDash([2.4, 1.8]);
        g.strokeStyle = C.ink3;
        g.lineWidth = 1.6;
        g.stroke();
        g.setLineDash([]);
      } else if (n.p >= AUTOMATED) {
        g.fillStyle = C.signal;
        g.fill();
      } else if (n.ampT <= T && n.p < HUMAN_MAX) {
        g.fillStyle = C.human;
        g.fill();
        g.strokeStyle = "#fff";
        g.lineWidth = 1.2;
        g.stroke();
      } else {
        g.globalAlpha = 0.78;
        g.fillStyle = hexOf.get(n.narrative) ?? C.ink3;
        g.fill();
        g.globalAlpha = 1;
      }
    }
    g.font = "11px 'IBM Plex Mono', monospace";
    g.textBaseline = "middle";
    // name only the largest public accounts, and never on top of another label
    const boxes: number[][] = [];
    const named = vis.filter((n) => n.handle).sort((a, b) => b.size - a.size || b.degree - a.degree);
    for (const n of named) {
      if (boxes.length >= 12) break;
      const t = handle(n.handle)!;
      const tw = g.measureText(t).width;
      const left = X(n.x) + n.r * scale + 5 + tw > w - 4;
      const tx = left ? X(n.x) - n.r * scale - 5 : X(n.x) + n.r * scale + 5;
      const b = left ? [tx - tw - 2, Y(n.y) - 8, tx + 2, Y(n.y) + 8] : [tx - 2, Y(n.y) - 8, tx + tw + 2, Y(n.y) + 8];
      if (boxes.some((o) => !(b[2] < o[0] || b[0] > o[2] || b[3] < o[1] || b[1] > o[3]))) continue;
      boxes.push(b);
      g.textAlign = left ? "end" : "start";
      g.lineWidth = 3;
      g.strokeStyle = "#fff";
      g.strokeText(t, tx, Y(n.y));
      g.fillStyle = C.ink;
      g.fillText(t, tx, Y(n.y));
    }
    g.textAlign = "start";
    g.font = "500 12px 'IBM Plex Sans', sans-serif";
    g.textAlign = "center";
    for (const { n, c } of labels) {
      g.lineWidth = 4;
      g.strokeStyle = "#fff";
      g.strokeText(n.label, X(c!.x), Math.max(10, Y(c!.top) - 9));
      g.fillStyle = C.label;
      g.fillText(n.label, X(c!.x), Math.max(10, Y(c!.top) - 9));
    }
    g.textAlign = "start";
  }, [m, T, w, H, scale, ox, oy, labels]);

  const pick = (ev: React.MouseEvent) => {
    const b = canvas.current!.getBoundingClientRect();
    const x = (ev.clientX - b.left - ox) / scale, y = (ev.clientY - b.top - oy) / scale;
    let best: Node | null = null, bd = 14 / scale;
    for (const n of m.nodes) {
      if (n.t > T) continue;
      const d = Math.hypot(n.x - x, n.y - y);
      if (d < bd) {
        bd = d;
        best = n;
      }
    }
    return best;
  };

  const tipText = (n: Node) => {
    const nar = m.narratives.find((x) => x.id === n.narrative)?.label ?? "";
    if (n.handle) return { h: handle(n.handle)!, s: n.selfLabel ? "Self-labeled bot · public" : `Public account · ${nar}` };
    if (n.p >= AUTOMATED) return { h: "Likely automated", s: `score ${n.p.toFixed(2)} · ${acctRef(n.id)} · ${nar}` };
    if (n.ampT <= T) return { h: "Real account", s: `amplifying likely automated posts · ${acctRef(n.id)} · private, not named` };
    return { h: nar || "Account", s: `${acctRef(n.id)} · private, not named` };
  };

  return (
    <div ref={wrap} className="netwrap">
      <canvas
        ref={canvas}
        style={{ width: w, height: H }}
        role="img"
        aria-label={`Account network clustered by narrative, ${m.nodes.filter((n) => n.t <= T).length} accounts visible`}
        onMouseMove={(ev) => {
          const n = pick(ev);
          setTip(n ? { x: ev.clientX, y: ev.clientY, n } : null);
          (ev.target as HTMLCanvasElement).style.cursor = n ? "pointer" : "default";
        }}
        onMouseLeave={() => setTip(null)}
        onClick={(ev) => {
          const n = pick(ev);
          if (n) onCluster(n.narrative);
        }}
      />
      {tip && (
        <div className="tip on" style={{ left: tip.x + 14, top: tip.y + 14 }}>
          <b>{tipText(tip.n).h}</b>
          <br />
          <span className="mono">{tipText(tip.n).s}</span>
        </div>
      )}
    </div>
  );
}

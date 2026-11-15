import { useEffect, useRef, useState } from "react";
import { getSiteData } from "../api/client";
import type { GraphEdge, GraphNode } from "../api/types";

/* The checker's hero: the real Jensen Huang story network (site_data.json graph: the accounts the replay
 * draws and who engaged with whom) on a slowly turning globe. Likely automated accounts (score 0.5+) glow
 * red; everything else is a quiet grey point. Positions on the sphere are arbitrary; the caption says so.
 * mode "scan" (while a check runs) turns faster and sweeps a band across the globe. It never turns anything
 * red during a scan: that would suggest results the check hasn't returned. No handles are drawn. */

const RED = "#FF5A3C";
const DOT = "rgba(222,226,233,";
const EDGE_AUTO = "rgba(255,90,60,";
const EDGE = "rgba(170,178,190,";

interface N3 {
  x: number;
  y: number;
  z: number;
  auto: boolean;
  w: number;
}

export function NetworkGlobe({ mode = "idle" }: { mode?: "idle" | "scan" }) {
  const box = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);
  const [graph, setGraph] = useState<{ nodes: N3[]; edges: [number, number, boolean][]; autoN: number; n: number } | null>(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  useEffect(() => {
    let live = true;
    getSiteData()
      .then((d) => {
        const nodes: GraphNode[] = d.graph?.nodes ?? [];
        const edges: GraphEdge[] = d.graph?.edges ?? [];
        if (!live || nodes.length < 10) return;
        const idx = new Map(nodes.map((n, i) => [n.id, i]));
        const N = nodes.length;
        // Fibonacci sphere, ordered so connected nodes sit near each other: sort by degree, then by narrative
        const order = nodes.map((_, i) => i).sort((a, b) => (nodes[a].narrative ?? "").localeCompare(nodes[b].narrative ?? "") || (nodes[b].degree ?? 0) - (nodes[a].degree ?? 0));
        const pos: N3[] = new Array(N);
        order.forEach((ni, k) => {
          const y = 1 - (2 * (k + 0.5)) / N;
          const r = Math.sqrt(1 - y * y);
          const th = k * 2.39996323;
          const n = nodes[ni];
          pos[ni] = { x: r * Math.cos(th), y, z: r * Math.sin(th), auto: (n.p_automated ?? 0) >= 0.5 || n.role === "likely_automated", w: Math.min(1, Math.log1p(n.degree ?? n.size ?? 1) / 6) };
        });
        const E: [number, number, boolean][] = [];
        for (const e of edges) {
          const a = idx.get(e.s), b = idx.get(e.t);
          if (a == null || b == null || a === b) continue;
          E.push([a, b, pos[a].auto || pos[b].auto]);
        }
        setGraph({ nodes: pos, edges: E, autoN: pos.filter((p) => p.auto).length, n: N });
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    const c = cv.current, el = box.current;
    if (!c || !el || !graph) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    let W = 0, H = 0;
    const size = () => {
      const b = el.getBoundingClientRect();
      W = b.width;
      H = b.height;
      c.width = W * dpr;
      c.height = H * dpr;
      c.style.width = `${W}px`;
      c.style.height = `${H}px`;
    };
    size();
    const ro = new ResizeObserver(size);
    ro.observe(el);
    const ctx = c.getContext("2d")!;
    let raf = 0, angle = 0.6, last = performance.now(), speed = 0.07;
    const tilt = 0.38;
    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const scan = modeRef.current === "scan";
      speed += ((scan ? 0.42 : 0.07) - speed) * Math.min(1, dt * 2.5);
      if (!reduced) angle += speed * dt;
      const R = Math.min(W, H) * 0.42;
      const cx = W / 2, cy = H / 2;
      const ca = Math.cos(angle), sa = Math.sin(angle), ct = Math.cos(tilt), st = Math.sin(tilt);
      const P = graph.nodes.map((p) => {
        const x1 = p.x * ca + p.z * sa;
        const z1 = -p.x * sa + p.z * ca;
        const y2 = p.y * ct - z1 * st;
        const z2 = p.y * st + z1 * ct;
        const k = 1 / (1.9 - z2 * 0.55); // gentle perspective
        return { sx: cx + x1 * R * k * 1.75, sy: cy + y2 * R * k * 1.75, z: z2, auto: p.auto, w: p.w };
      });
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      // faint rim
      ctx.strokeStyle = "rgba(170,178,190,0.10)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, R * 1.04, 0, Math.PI * 2);
      ctx.stroke();
      // scan band position (0..1 top to bottom), only in scan mode
      const band = scan ? ((now / 1600) % 1.3) - 0.15 : -9;
      const bandY = cy - R + band * 2 * R;
      for (const [a, b, auto] of graph.edges) {
        const A = P[a], B = P[b];
        const depth = (A.z + B.z + 2) / 4;
        ctx.strokeStyle = (auto ? EDGE_AUTO : EDGE) + (auto ? 0.1 + depth * 0.35 : 0.04 + depth * 0.16) + ")";
        ctx.lineWidth = auto ? 0.9 : 0.6;
        ctx.beginPath();
        ctx.moveTo(A.sx, A.sy);
        ctx.lineTo(B.sx, B.sy);
        ctx.stroke();
      }
      const sorted = P.map((_, i) => i).sort((i, j) => P[i].z - P[j].z);
      for (const i of sorted) {
        const p = P[i];
        const depth = (p.z + 1) / 2;
        const near = scan ? Math.max(0, 1 - Math.abs(p.sy - bandY) / 26) : 0;
        const r = (1.1 + p.w * 2.4) * (0.6 + depth * 0.6) + near * 1.2;
        if (p.auto) {
          ctx.shadowColor = RED;
          ctx.shadowBlur = 10 * depth + 2;
          ctx.fillStyle = RED;
          ctx.globalAlpha = 0.35 + depth * 0.65;
        } else {
          ctx.shadowBlur = near ? 8 : 0;
          ctx.shadowColor = "rgba(222,226,233,0.9)";
          ctx.fillStyle = DOT + (0.18 + depth * 0.55 + near * 0.3) + ")";
          ctx.globalAlpha = 1;
        }
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;
      if (scan) {
        const g = ctx.createLinearGradient(0, bandY - 30, 0, bandY + 30);
        g.addColorStop(0, "rgba(222,226,233,0)");
        g.addColorStop(0.5, "rgba(222,226,233,0.07)");
        g.addColorStop(1, "rgba(222,226,233,0)");
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, R * 1.04, 0, Math.PI * 2);
        ctx.clip();
        ctx.fillStyle = g;
        ctx.fillRect(cx - R * 1.1, bandY - 30, R * 2.2, 60);
        ctx.restore();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    const onVis = () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else {
        last = performance.now();
        raf = requestAnimationFrame(draw);
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [graph]);

  return (
    <figure className="globe" aria-label={graph ? `${graph.n} accounts from the Jensen Huang story network; ${graph.autoN} likely automated, shown in red` : undefined}>
      <div className="globe-box" ref={box}>
        <canvas ref={cv} aria-hidden="true" />
      </div>
      {graph && (
        <figcaption className="globe-cap">
          <span>
            <i className="globe-dot" /> {graph.autoN} likely automated
          </span>
          <span>
            <i className="globe-dot grey" /> {graph.n - graph.autoN} other accounts
          </span>
          <span className="globe-src globe-src-short">Picked around likely automated accounts, so red is over-represented. Position means nothing.</span>
          <span className="globe-src globe-src-long">
            Real accounts from the Jensen Huang week and who engaged with whom: the {graph.n} the story replay draws, picked around the likely automated ones, so red is over-represented here (it is about 1 in 20 posts story-wide). Position on the globe means nothing.
          </span>
        </figcaption>
      )}
    </figure>
  );
}

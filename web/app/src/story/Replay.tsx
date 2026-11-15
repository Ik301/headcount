import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../components/Icons";
import { fmtInt, pct, utcLabel } from "../lib/format";
import type { DrawerContent } from "./Drawer";
import { narrativeDrawer } from "./drawers";
import { FindingBar } from "./FindingBar";
import type { Model } from "./model";
import { Network } from "./Network";
import { River, RiverEvents } from "./River";

const SPEED = 18; // story hours per second of playback

export function Replay({ m, openDrawer }: { m: Model; openDrawer: (c: DrawerContent) => void }) {
  const lastMajor = [...m.events].reverse().find((e) => e.major);
  const [T, setT] = useState(() => Math.min(m.hours - 0.01, (lastMajor?.h ?? m.hours * 0.85) + 2.25));
  const [playing, setPlaying] = useState(false);
  const raf = useRef(0);

  useEffect(() => {
    if (!playing) return;
    let last = 0;
    const tick = (ts: number) => {
      const dt = last ? (ts - last) / 1000 : 0;
      last = ts;
      let done = false;
      setT((t) => {
        const nt = t + dt * SPEED;
        if (nt >= m.hours - 0.01) {
          done = true;
          return m.hours - 0.01;
        }
        return nt;
      });
      if (done) setPlaying(false);
      else raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, m.hours]);

  const scrub = useCallback((h: number) => {
    setPlaying(false);
    setT(Math.max(0, Math.min(m.hours - 0.01, h)));
  }, [m.hours]);

  const stats = useMemo(() => {
    const cum = (arr: number[], t: number) => {
      let s = 0;
      const f = Math.floor(t);
      for (let i = 0; i < f && i < arr.length; i++) s += arr[i];
      if (f < arr.length) s += arr[f] * (t - f);
      return s;
    };
    let P = 0, A = 0, p6 = 0, a6 = 0;
    const rows = m.river.map((r) => {
      const p = cum(r.posts, T), a = cum(r.bots, T);
      P += p;
      A += a;
      p6 += p - cum(r.posts, Math.max(0, T - 6));
      a6 += a - cum(r.bots, Math.max(0, T - 6));
      return { id: r.id, p, a };
    });
    const vis = m.nodes.filter((n) => n.t <= T).length;
    return { P, A, p6, a6, rows, vis };
  }, [m, T]);

  const fallback = m.baseline != null && m.totals.posts ? `Across the window, ${pct(m.baseline, 1)} of ${fmtInt(m.totals.posts)} posts came from likely automated accounts.` : undefined;

  return (
    <section className="view v-replay" aria-label="Replay">
      <FindingBar finding={m.findings.replay} fallback={fallback} source="Story-wide, score cutoff 0.5" view="replay" />
      <div className="panel graphp">
        <div className="ph">
          <h2>Who posted, hour by hour</h2>
          <span className="note">
            {m.nodes.length
              ? `${fmtInt(stats.vis)} of ${fmtInt(m.nodes.length)} accounts visible${m.graphNote ? `. ${m.graphNote}` : ""}. Click a cluster for evidence.`
              : "The export has no graph yet."}
          </span>
        </div>
        <Network
          m={m}
          T={T}
          onCluster={(id) => {
            const n = m.narratives.find((x) => x.id === id);
            if (n) openDrawer(narrativeDrawer(m, n, `${n.label} cluster, replay`));
          }}
        />
        <div className="key">
          <span>
            <svg viewBox="0 0 14 14" aria-hidden="true">
              <circle cx="7" cy="7" r="5" fill="#C81E66" />
            </svg>
            Likely automated
          </span>
          <span>
            <svg viewBox="0 0 14 14" aria-hidden="true">
              <circle cx="7" cy="7" r="5" fill="#245E7E" stroke="#F9FAF6" strokeWidth="1.5" />
            </svg>
            Real account amplifying them
          </span>
          <span>
            <svg viewBox="0 0 14 14" aria-hidden="true">
              <circle cx="7" cy="7" r="5" fill="#F9FAF6" stroke="#111814" strokeWidth="1.5" />
            </svg>
            Public account, named
          </span>
          <span>
            <svg viewBox="0 0 14 14" aria-hidden="true">
              <circle cx="7" cy="7" r="5" fill="#F9FAF6" stroke="#7C867F" strokeWidth="1.5" strokeDasharray="2 1.6" />
            </svg>
            Self-labeled bot
          </span>
        </div>
      </div>
      <aside className="panel side" aria-live="polite">
        <div className="now">
          {utcLabel(new Date(m.start + T * 3_600_000))}
          <small>UTC</small>
        </div>
        <div className="stats">
          <div className="stat">
            <div className="v">{fmtInt(stats.P)}</div>
            <div className="l">posts so far</div>
          </div>
          <div className="stat">
            <div className="v">{fmtInt(stats.vis)}</div>
            <div className="l">accounts on the map</div>
          </div>
          <div className="stat">
            <div className="v sig">{stats.p6 > 0 ? pct(stats.a6 / stats.p6, 1) : "·"}</div>
            <div className="l">likely automated, last 6 h</div>
          </div>
        </div>
        <table className="ntab">
          <thead>
            <tr>
              <th>Narrative</th>
              <th>Posts</th>
              <th>Auto.</th>
            </tr>
          </thead>
          <tbody>
            {m.narratives.map((n, i) => (
              <tr key={n.id}>
                <td>
                  <i className="sw" style={{ background: n.color }} />
                  {n.label}
                </td>
                <td className="num">{fmtInt(stats.rows[i]?.p)}</td>
                <td className="num">{stats.rows[i]?.p > 0 ? pct(stats.rows[i].a / stats.rows[i].p, 1) : "·"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </aside>
      <div className="panel timep">
        <div className="tbar">
          <button className="btn icon" onClick={() => (playing ? setPlaying(false) : (T > m.hours - 1 && setT(0), setPlaying(true)))} aria-label={playing ? "Pause replay" : "Play replay"}>
            <Icon name={playing ? "pause" : "play"} />
          </button>
          <h2>Narrative river</h2>
          <span className="lbl">Posts per hour by narrative; the likely automated part of each band sits at its base.</span>
          <span className="sp" />
          {m.events.some((e) => e.major) && <span className="lbl">Jump to</span>}
          {m.events
            .filter((e) => e.major)
            .map((e) => (
              <button key={e.t} className="btn" onClick={() => scrub(e.h + 0.4)}>
                {e.label.split(/[:;]/)[0]}
              </button>
            ))}
        </div>
        <div className="legend">
          {m.narratives.map((n) => (
            <span key={n.id}>
              <i className="sw" style={{ background: n.color }} />
              {n.label}
            </span>
          ))}
          <span>
            <i className="sw" style={{ background: "var(--signal)" }} />
            Likely automated
          </span>
        </div>
        <River m={m} T={T} onScrub={scrub} />
        <RiverEvents m={m} T={T} onScrub={scrub} />
      </div>
    </section>
  );
}

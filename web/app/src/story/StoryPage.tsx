import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getSiteData } from "../api/client";
import type { SiteData } from "../api/types";
import { TopBar } from "../components/Shell";
import { fmtInt, pct, windowLabel } from "../lib/format";
import { buildModel } from "./model";
import { EvidenceDrawer, type DrawerContent } from "./Drawer";
import { Replay } from "./Replay";
import { NoBots } from "./NoBots";
import { Archetypes } from "./Archetypes";
import { EvidenceView } from "./EvidenceView";
import { Method } from "./Method";
import { Guide } from "./guide/Guide";

const VIEWS = [
  { id: "replay", label: "Replay" },
  { id: "nobots", label: "Without likely automated" },
  { id: "archetypes", label: "Amplifier archetypes" },
  { id: "evidence", label: "Evidence" },
  { id: "method", label: "Method" },
] as const;
type ViewId = (typeof VIEWS)[number]["id"];

/** Route "/story": the newsroom dashboard, entirely from /site_data.json (no API calls). */
export default function StoryPage() {
  const [data, setData] = useState<SiteData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.find((v) => v.id === params.get("view"))?.id ?? "replay") as ViewId;
  // Guided story by default; the full dashboard on ?mode=explore (old ?view= links land there too).
  const exploreMode = params.get("mode") === "explore" || params.has("view");
  const [drawer, setDrawer] = useState<DrawerContent | null>(null);

  useEffect(() => {
    getSiteData().then(setData, (e) => setErr(e.message));
  }, []);
  const m = useMemo(() => (data ? buildModel(data) : null), [data]);
  useEffect(() => {
    if (exploreMode || !m) document.title = m ? `${m.title} · Explore the data` : "Story";
  }, [m, exploreMode]);

  const go = (v: ViewId) => {
    const p = new URLSearchParams(params);
    p.set("mode", "explore");
    p.set("view", v);
    setParams(p, { replace: false });
  };
  const closeDrawer = useCallback(() => setDrawer(null), []);

  if (err || !m)
    return (
      <div className="page story">
        <TopBar />
        <main className="story-empty wrap narrow">
          {err ? (
            <>
              <h1>No story data yet</h1>
              <p>
                The dashboard reads <code>/site_data.json</code>, which the export writes to <code>web/public/site_data.json</code>. {err}
              </p>
              <p>
                For a preview with sample data, run <code>npm run sample-data</code> in <code>web/app</code>.
              </p>
            </>
          ) : (
            <p aria-busy="true">Loading the story…</p>
          )}
        </main>
      </div>
    );

  if (!exploreMode)
    return (
      <Guide data={data!} m={m} openDrawer={setDrawer}>
        <EvidenceDrawer content={drawer} onClose={closeDrawer} />
      </Guide>
    );

  const t = m.totals;
  return (
    <div className="page story">
      <TopBar />
      <p className="explore-note">
        Explore is laid out for a desktop screen; swipe sideways to pan. On a phone, the <Link to="/story">guided story</Link> shows the same data.
      </p>
      <div className="explore-pan">
      <header className="top">
        <div className="wrap-wide">
          <div className="title">
            <h1>{m.title}</h1>
            <span className="range">
              Bluesky · {windowLabel(new Date(m.start).toISOString(), new Date(m.start + (m.hours - 1) * 3_600_000).toISOString())}, {new Date(m.start).getUTCFullYear()} (UTC)
            </span>
            {m.sample && <span className="sample-tag">Sample data</span>}
            <nav className="g-mode explore-mode" aria-label="How to read this story">
              <Link to="/story">Guided story</Link>
              <span aria-current="page">Explore all the data</span>
            </nav>
          </div>
          <div className="meta">
            {t.posts != null && (
              <span>
                <b>{fmtInt(t.posts)}</b>posts
              </span>
            )}
            {t.accounts != null && (
              <span>
                <b>{fmtInt(t.accounts)}</b>accounts
              </span>
            )}
            {t.engagements != null && (
              <span>
                <b>{fmtInt(t.engagements)}</b>likes, reposts and quotes
              </span>
            )}
            {m.baseline != null && (
              <span>
                <b>{pct(m.baseline, 1)}</b>likely automated (story baseline)
              </span>
            )}
          </div>
          <nav className="tabs" role="tablist" aria-label="Dashboard views">
            {VIEWS.map((v) => (
              <button key={v.id} className="tab" role="tab" aria-selected={view === v.id} onClick={() => go(v.id)}>
                {v.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="story-main wrap-wide">
        {view === "replay" && <Replay m={m} openDrawer={setDrawer} />}
        {view === "nobots" && (
          <NoBots
            m={m}
            removed={params.get("removed") === "1"}
            setRemoved={(r) => {
              const p = new URLSearchParams(params);
              if (r) p.set("removed", "1");
              else p.delete("removed");
              setParams(p, { replace: true });
            }}
            openDrawer={setDrawer}
          />
        )}
        {view === "archetypes" && <Archetypes m={m} openDrawer={setDrawer} />}
        {view === "evidence" && <EvidenceView m={m} openDrawer={setDrawer} />}
        {view === "method" && <Method m={m} />}
      </main>
      </div>
      <EvidenceDrawer content={drawer} onClose={closeDrawer} />
    </div>
  );
}

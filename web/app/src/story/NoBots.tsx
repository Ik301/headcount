import { useEffect, useRef, useState } from "react";
import { against, versusWords } from "../lib/compare";
import { ci, fmtInt, pct } from "../lib/format";
import type { DrawerContent } from "./Drawer";
import { clusterDrawer, narrativeDrawer } from "./drawers";
import { FindingBar } from "./FindingBar";
import { CUTS, type Model, type Narr } from "./model";

const ROWH = 156;

export function NoBots({ m, removed, setRemoved, openDrawer }: { m: Model; removed: boolean; setRemoved: (r: boolean) => void; openDrawer: (c: DrawerContent) => void }) {
  const N = m.narratives;
  const order = [...N].sort((a, b) => (removed ? b.shareWithout - a.shareWithout : b.share - a.share));
  const rank = new Map(order.map((n, i) => [n.id, i]));
  const maxShare = Math.max(0.05, ...N.map((n) => Math.max(n.share, n.shareWithout)));
  const maxAuto = Math.max(0.1, ...N.map((n) => Math.max(n.ci?.[1] ?? n.bot, ...Object.values(n.strip ?? {}))), (m.baseline ?? 0) * 2) * 1.1;
  const top = N.length ? N.reduce((a, b) => (b.bot > a.bot ? b : a)) : null;
  const ratio = (n: Narr) => (m.baseline && n.bot >= 2 * m.baseline ? n.bot / m.baseline : null);

  const before = [...N].sort((a, b) => b.share - a.share).map((n) => n.id);
  const after = [...N].sort((a, b) => b.shareWithout - a.shareWithout).map((n) => n.id);
  const moved = N.map((n) => ({ n, from: before.indexOf(n.id) + 1, to: after.indexOf(n.id) + 1 })).filter((x) => x.from !== x.to);

  const fallback = top
    ? `${pct(top.bot)} of posts in “${top.label}”${top.ci ? ` (95% interval ${ci(top.ci)})` : ""} came from likely automated accounts${ratio(top) ? `, ${ratio(top)!.toFixed(1)} times the story’s baseline` : ""}.${
        moved.length ? ` Without them, “${moved[0].n.label}” moves from ${ordinal(moved[0].from)} to ${ordinal(moved[0].to)}.` : " Without them, the ranking does not change."
      }`
    : undefined;

  const topClusters = top ? m.clusters.filter((c) => c.narrative === top.id) : [];
  const sc = m.news?.spy_claim;
  const hedge = m.news?.hedging ?? (sc?.news_hedged_share != null ? { news: sc.news_hedged_share, social: sc.bluesky_hedged_share, topic: "the spy claim" } : undefined);

  return (
    <section className="view v-nobots" aria-label="Without likely automated accounts">
      <FindingBar finding={m.findings.nobots} fallback={fallback} source={`${fmtInt(m.totals.posts)} posts, cutoff 0.5`} view="nobots" />
      <div className="panel">
        <div className="nbhead">
          <div>
            <h2>{m.claim ? `“${m.claim}”` : "The story, narrative by narrative"}</h2>
            <p>
              <span className="mono">{fmtInt(N.reduce((s, n) => s + n.posts, 0))}</span> posts in {N.length} narratives. Bars show share of posts; the magenta segment is posts from likely
              automated accounts.
            </p>
          </div>
          <button className="switch" role="switch" aria-checked={removed} onClick={() => setRemoved(!removed)}>
            <span className="tr" />
            Remove likely automated accounts
          </button>
        </div>
        <div className="colh">
          <span />
          <span>Narrative · share of posts</span>
          <span>Likely automated · 95% interval</span>
        </div>
        <div className="rows" style={{ height: N.length * ROWH }}>
          {N.map((n) => {
            const v = removed ? n.shareWithout : n.share;
            const autoW = removed ? 0 : n.share * n.bot;
            const go = () => openDrawer(narrativeDrawer(m, n, `${n.label}, without likely automated`));
            return (
              <div
                key={n.id}
                className={`row${removed ? " gone" : ""}`}
                style={{ transform: `translateY(${(rank.get(n.id) ?? 0) * ROWH}px)` }}
                role="button"
                tabIndex={0}
                aria-label={`${n.label}, open evidence`}
                onClick={go}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), go())}
              >
                <div className="rank">{(rank.get(n.id) ?? 0) + 1}</div>
                <div>
                  <div className="nname">
                    <i className="sw" style={{ background: n.color }} />
                    {n.label}
                    <span className="cnt">{fmtInt(n.posts)} posts</span>
                  </div>
                  <div className="barline">
                    <div className="bt">
                      <div className="bf" style={{ background: n.color, width: `${(v / maxShare) * 100}%` }} />
                      <div className="ba" style={{ left: `${((v - autoW) / maxShare) * 100}%`, width: `${(autoW / maxShare) * 100}%` }} />
                    </div>
                    <CountTo className="bval" value={v} />
                    <div className="delta">{removed ? `was ${pct(n.share)}` : ""}</div>
                  </div>
                  {n.strip && (
                    <div className="strip">
                      <span className="sl">At score cutoff</span>
                      {CUTS.map((c) => (
                        <div key={c} className={`cut${c === "0.5" ? " def" : ""}`}>
                          <div className="t">
                            <span>{c}</span>
                            <b>{n.strip?.[c] != null ? pct(n.strip[c]) : "·"}</b>
                          </div>
                          <div className="m">
                            <i style={{ width: `${((n.strip?.[c] ?? 0) / maxAuto) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="auto">
                  <div className="big">{pct(n.bot)}</div>
                  <div className="ci">{n.ci ? ci(n.ci) : "no interval"}</div>
                  <div className="ci2">
                    {m.baseline != null ? vsBaseline(n, m.baseline, ratio(n)) : ""}
                  </div>
                  <CiSvg n={n} max={maxAuto} baseline={m.baseline} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="nbfoot">Score cutoff 0.5 is the default. The strip under each bar shows the same share at looser and stricter cutoffs. Click any row for its evidence.</div>
      </div>
      <aside className="panel aside">
        <section>
          <h3>How to report this</h3>
          <ul className="howto">
            <li>
              Say <b>“likely automated accounts”</b>, not “bots”. These accounts have not labeled themselves.
            </li>
            {top && top.ci && (
              <li>
                Cite the interval:{" "}
                <b>
                  {pct(top.bot)} (95% interval {ci(top.ci)})
                </b>
                , at the default score cutoff of 0.5.
              </li>
            )}
            <li>Do not attribute. We do not know who runs these accounts, and this is no ruling on whether the claim is true.</li>
          </ul>
        </section>
        {top && (
          <section>
            <h3>What the likely automated accounts pushing {top.label} have in common</h3>
            {topClusters.length ? (
              <>
                <ul className="facts">
                  {topClusters.slice(0, 3).map((c) => (
                    <li key={c.cluster_id}>
                      <span className="n">{fmtInt(c.size ?? c.dids?.length ?? 0)}</span>
                      <span>{c.reasons?.[0] ?? "accounts in one coordination cluster"}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt4">
                  <button className="linkbtn" onClick={() => openDrawer(clusterDrawer(m, topClusters[0], `${top.label} · shared traits`))}>
                    Open the coordination cluster
                  </button>
                </p>
              </>
            ) : (
              <p>The export has no coordination clusters for this narrative.</p>
            )}
          </section>
        )}
        {m.news && (
          <section>
            <h3>What accountable newsrooms report</h3>
            {hedge?.news != null && (
              <p>
                <b className="mono">{pct(hedge.news)}</b> of wire-service and public-broadcaster headlines{hedge.topic ? ` on ${hedge.topic}` : ""} hedge (“alleged”, “suspected”)
                {sc?.bluesky_link_hedged_share != null && sc.bluesky_own_words_hedged_share != null ? (
                  <>
                    . On Bluesky, <b className="mono">{pct(sc.bluesky_link_hedged_share)}</b> of posts that share a link hedge, and <b className="mono">{pct(sc.bluesky_own_words_hedged_share)}</b> of posts in people’s own words
                  </>
                ) : (
                  hedge.social != null && (
                    <>
                      , against <b className="mono">{pct(hedge.social)}</b> of Bluesky posts
                    </>
                  )
                )}
                .
              </p>
            )}
            {!!m.news.social_only?.length && (
              <p className="mt4">
                Only on social media:{" "}
                {m.news.social_only
                  .map((id) => N.find((n) => n.id === id)?.label ?? id)
                  .join(", ")}
                .
              </p>
            )}
          </section>
        )}
        <section>
          <h3>How to read the interval</h3>
          <p>
            Dot: estimate at cutoff 0.5. Line: 95% interval. Dashed line: the story baseline{m.baseline != null ? `, ${pct(m.baseline, 1)} across all posts` : ""}.
          </p>
        </section>
      </aside>
    </section>
  );
}

const ordinal = (n: number) => ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"][n - 1] ?? `#${n}`;

/** "above the 5.0% baseline (1.8×)", "below the 5.0% baseline", "not clearly different from the 5.0% baseline": read
 *  from the narrative's interval, so a 0.4% narrative never reads as "near" a 5% baseline. */
function vsBaseline(n: Narr, base: number, x: number | null): string {
  const w = versusWords(against(n.ci, base));
  if (!w) return x ? `${x.toFixed(1)}× the ${pct(base, 1)} baseline, no interval` : `baseline ${pct(base, 1)}, no interval`;
  return `${w} the ${pct(base, 1)} baseline${w === "above" && x ? ` (${x.toFixed(1)}×)` : ""}`;
}

function CiSvg({ n, max, baseline }: { n: Narr; max: number; baseline?: number }) {
  const w = 320, x = (v: number) => 6 + (v / max) * (w - 12);
  const ticks = [0, max / 3, (2 * max) / 3, max].map((v) => Math.round(v * 100) / 100);
  const [lo, hi] = n.ci ?? [n.bot, n.bot];
  return (
    <svg viewBox={`0 0 ${w} 44`} preserveAspectRatio="none" aria-hidden="true">
      <line x1={6} x2={w - 6} y1={18} y2={18} stroke="#CBD1C4" />
      {ticks.map((v, i) => (
        <g key={i}>
          <line x1={x(v)} x2={x(v)} y1={14} y2={22} stroke="#B5BCAE" />
          <text x={x(v)} y={38} textAnchor={i === 0 ? "start" : i === 3 ? "end" : "middle"} className="ax">
            {Math.round(v * 100)}%
          </text>
        </g>
      ))}
      {baseline != null && <line x1={x(baseline)} x2={x(baseline)} y1={6} y2={28} stroke="#3B4640" strokeDasharray="2 2" />}
      <line x1={x(lo)} x2={x(hi)} y1={18} y2={18} stroke="#C81E66" strokeWidth={2.5} />
      <circle cx={x(n.bot)} cy={18} r={5} fill="#C81E66" stroke="#F9FAF6" strokeWidth={1.5} />
    </svg>
  );
}

/** Animated percentage for the re-ranking moment. */
function CountTo({ value, className }: { value: number; className?: string }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const a = from.current, b = value, t0 = performance.now();
    let raf = 0;
    const f = (now: number) => {
      const k = Math.min(1, (now - t0) / 550), e = 1 - Math.pow(1 - k, 3);
      setShown(a + (b - a) * e);
      if (k < 1) raf = requestAnimationFrame(f);
      else from.current = b;
    };
    raf = requestAnimationFrame(f);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <div className={className}>{pct(shown)}</div>;
}

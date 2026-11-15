import type { SiteArchetype } from "../api/types";
import { fmtInt, handle, lift, pct } from "../lib/format";
import type { DrawerContent } from "./Drawer";
import { archetypeDrawer } from "./drawers";
import { FindingBar } from "./FindingBar";
import type { Model } from "./model";

function features(a: SiteArchetype): { v: string; l: string }[] {
  // the export describes each group in words ("82% reposts; 6% replies"); raw feature values are model internals
  if (a.description) return a.description.split(/;\s*/).filter(Boolean).slice(0, 3).map((s) => ({ v: "", l: s }));
  if (!a.features) return [];
  if (Array.isArray(a.features)) return a.features.slice(0, 3).map((f) => ({ v: String(f.value), l: f.label }));
  return Object.entries(a.features)
    .filter(([, v]) => v != null)
    .slice(0, 3)
    .map(([l, v]) => ({ v: typeof v === "number" ? (Math.abs(v) < 1 && v !== 0 ? pct(v) : fmtInt(v)) : String(v), l: l.replace(/_/g, " ") }));
}

export function Archetypes({ m, openDrawer }: { m: Model; openDrawer: (c: DrawerContent) => void }) {
  const A = m.archetypes;
  const total = A.reduce((s, a) => s + (a.size ?? 0), 0);
  const top = A.length ? A.reduce((a, b) => ((b.lift ?? 0) > (a.lift ?? 0) ? b : a)) : null;
  const fallback = top?.lift != null ? `${top.label} were ${top.lift.toFixed(1)} times as likely as similar accounts to amplify likely automated posts${top.lift_ci ? ` (95% interval ${top.lift_ci[0].toFixed(1)} to ${top.lift_ci[1].toFixed(1)})` : ""}.` : undefined;

  if (!A.length)
    return (
      <section className="view v-arch">
        <div className="panel pad">
          <h2 className="ph-title">Amplifier archetypes</h2>
          <p className="muted">The export has no archetypes yet. They appear once the archetype build (M5) runs.</p>
        </div>
      </section>
    );

  // forest plot, log scale 0.4x to 4x
  const w = 1390, x0 = 560, x1 = w - 40;
  const lo = Math.min(0.4, ...A.map((a) => a.lift_ci?.[0] ?? a.lift ?? 1)) * 0.9;
  const hi = Math.max(4, ...A.map((a) => a.lift_ci?.[1] ?? a.lift ?? 1)) * 1.05;
  const xl = (v: number) => x0 + ((Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo))) * (x1 - x0);
  const fh = 40 + A.length * 29 + 26;

  return (
    <section className="view v-arch" aria-label="Amplifier archetypes">
      <FindingBar finding={m.findings.archetypes} fallback={fallback} source={total ? `${fmtInt(total)} real accounts, matched comparison` : undefined} view="archetypes" />
      <div className="panel forest">
        <div className="ph">
          <h2>{total ? `${fmtInt(total)} real accounts reposted, quoted or liked posts from likely automated accounts` : "Real accounts that amplified likely automated posts"}</h2>
          <span className="note">Lift: how much more likely than matched similar accounts. 1.0× means no difference.</span>
        </div>
        <svg viewBox={`0 0 ${w} ${fh}`} preserveAspectRatio="none" style={{ height: fh }} role="img" aria-label="Lift by archetype with 95% intervals">
          {[0.5, 1, 2, 3, 4].filter((v) => v >= lo && v <= hi).map((v) => (
            <g key={v}>
              <line x1={xl(v)} x2={xl(v)} y1={10} y2={fh - 28} stroke={v === 1 ? "#4A4F5A" : "#EFECE5"} strokeDasharray={v === 1 ? "3 3" : undefined} />
              <text x={xl(v)} y={fh - 9} textAnchor="middle" className="ax">
                {v}×
              </text>
            </g>
          ))}
          <text x={xl(1) + 6} y={20} className="ax sans">
            same as matched accounts
          </text>
          {A.map((a, i) => {
            const y = 34 + i * 29;
            return (
              <g key={a.id}>
                <text x={20} y={y + 4} className="flabel">
                  {a.label}
                </text>
                <text x={x0 - 30} y={y + 4} textAnchor="end" className="ax">
                  {lift(a.lift)}
                  {a.lift_ci ? ` (${a.lift_ci[0].toFixed(1)} to ${a.lift_ci[1].toFixed(1)})` : ""}
                </text>
                {a.lift_ci && <line x1={xl(a.lift_ci[0])} x2={xl(a.lift_ci[1])} y1={y} y2={y} stroke="#2F6F8F" strokeWidth={2.5} />}
                {a.lift != null && <circle cx={xl(a.lift)} cy={y} r={5.5} fill={(a.lift_ci?.[1] ?? a.lift) < 1 ? "#fff" : "#2F6F8F"} stroke="#2F6F8F" strokeWidth={2} />}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="cards" style={{ gridTemplateColumns: `repeat(${Math.min(4, A.length)}, 1fr)` }}>
        {A.map((a) => {
          const share = a.share ?? (total && a.size ? a.size / total : undefined);
          const f = features(a);
          const mix = a.mix ? Object.entries(a.mix) : [];
          return (
            <button key={a.id} className="acard" onClick={() => openDrawer(archetypeDrawer(m, a, `Archetype: ${a.label}`))}>
              <div className="share">
                <b>{share != null ? pct(share) : fmtInt(a.size)}</b>
                <span>
                  {share != null ? (a.interacting_humans != null ? "of engaged real accounts · " : "of amplifiers · ") : ""}
                  <span className="mono">{fmtInt(a.size)}</span> accounts
                </span>
              </div>
              <h3>{a.label}</h3>
              <div className="lift">
                <b className={(a.lift ?? 0) < 1 ? "low" : ""}>{lift(a.lift)}</b>
                {a.lift_ci && (
                  <span>
                    {a.lift_ci[0].toFixed(1)} to {a.lift_ci[1].toFixed(1)}
                  </span>
                )}
                <em>{!a.lift_ci ? "" : a.lift_ci[1] < 1 ? "less likely than matched" : a.lift_ci[0] > 1 ? "more likely than matched" : "no clear difference"}</em>
              </div>
              {!!f.length && (
                <ul className="feat">
                  {f.map((x) => (
                    <li key={x.l} className={x.v ? "" : "solo"}>
                      {x.v && <span className="mono">{x.v}</span>}
                      <span>{x.l}</span>
                    </li>
                  ))}
                </ul>
              )}
              {!!mix.length && (
                <div className="mix">
                  <div className="mt">How they amplified likely automated posts</div>
                  <div className="mb">
                    {mix.map(([k, v], j) => (
                      <i key={k} style={{ width: `${v * 100}%`, opacity: [1, 0.6, 0.3][j] ?? 0.2 }} />
                    ))}
                  </div>
                  <div className="ml">
                    {mix.map(([k, v], j) => (
                      <span key={k}>
                        <i style={{ opacity: [1, 0.6, 0.3][j] ?? 0.2 }} />
                        {k} <b className="mono">{pct(v)}</b>
                      </span>
                    ))}
                  </div>
                  {a.median_delay && (
                    <div className="md">
                      Median delay after the automated post <b className="mono">{a.median_delay}</b>
                    </div>
                  )}
                </div>
              )}
              <div className="pub">
                {(a.public_examples ?? a.examples_public)?.length ? (
                  <>
                    Public examples: <span className="mono">{(a.public_examples ?? a.examples_public)!.slice(0, 3).map((h) => handle(h)).join(", ")}</span>.{" "}
                  </>
                ) : (
                  "No public accounts in this group. "
                )}
                Private accounts are counted, never listed.
              </div>
              <span className="open">Open evidence</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

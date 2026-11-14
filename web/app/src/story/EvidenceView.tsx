import { fmtInt, isoSec, pct } from "../lib/format";
import type { DrawerContent } from "./Drawer";
import { clusterDrawer, narrativeDrawer } from "./drawers";
import { FindingBar } from "./FindingBar";
import type { Model } from "./model";

/** Index of everything that has evidence: coordination clusters first, then narratives. */
export function EvidenceView({ m, openDrawer }: { m: Model; openDrawer: (c: DrawerContent) => void }) {
  const clusters = [...m.clusters].sort((a, b) => (b.size ?? b.dids?.length ?? 0) - (a.size ?? a.dids?.length ?? 0));
  const nar = new Map(m.narratives.map((n) => [n.id, n]));
  return (
    <section className="view v-evidence" aria-label="Evidence">
      <FindingBar
        finding={m.findings.evidence}
        fallback={clusters.length ? `${fmtInt(clusters.length)} coordination clusters: groups of accounts posting the same text or link, or reposting the same post, within seconds of each other.` : undefined}
        source="Exact timestamps, UTC"
        view="evidence"
      />
      <div className="panel pad">
        <h2 className="ph-title">Coordination clusters</h2>
        {clusters.length ? (
          <table className="etab">
            <thead>
              <tr>
                <th>Cluster</th>
                <th>Narrative</th>
                <th className="r">Accounts</th>
                <th>Why they’re grouped</th>
                <th>First post (UTC)</th>
                <th className="r">Posts</th>
              </tr>
            </thead>
            <tbody>
              {clusters.map((c) => (
                <tr key={c.cluster_id} tabIndex={0} onClick={() => openDrawer(clusterDrawer(m, c, "Evidence index"))} onKeyDown={(e) => e.key === "Enter" && openDrawer(clusterDrawer(m, c, "Evidence index"))}>
                  <td className="mono">{c.cluster_id}</td>
                  <td>
                    {nar.get(c.narrative ?? "") && <i className="sw" style={{ background: nar.get(c.narrative!)!.color }} />}
                    {nar.get(c.narrative ?? "")?.label ?? "·"}
                  </td>
                  <td className="r mono">{fmtInt(c.size ?? c.dids?.length ?? 0)}</td>
                  <td>{c.reasons?.[0] ?? "·"}</td>
                  <td className="mono">{isoSec(c.window?.from ?? c.evidence?.[0]?.t) || "·"}</td>
                  <td className="r mono">{fmtInt(c.evidence?.length ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">The export has no coordination clusters yet.</p>
        )}
      </div>
      <div className="panel pad">
        <h2 className="ph-title">Narratives</h2>
        <table className="etab">
          <thead>
            <tr>
              <th>Narrative</th>
              <th className="r">Posts</th>
              <th className="r">Likely automated</th>
              <th className="r">Evidence posts</th>
            </tr>
          </thead>
          <tbody>
            {m.narratives.map((n) => (
              <tr key={n.id} tabIndex={0} onClick={() => openDrawer(narrativeDrawer(m, n, "Evidence index"))} onKeyDown={(e) => e.key === "Enter" && openDrawer(narrativeDrawer(m, n, "Evidence index"))}>
                <td>
                  <i className="sw" style={{ background: n.color }} />
                  {n.label}
                </td>
                <td className="r mono">{fmtInt(n.posts)}</td>
                <td className="r mono">{pct(n.bot)}</td>
                <td className="r mono">{fmtInt(n.evidence.length)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

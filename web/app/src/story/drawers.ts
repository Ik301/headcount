import type { Cluster, SiteArchetype } from "../api/types";
import { ci, fmtInt, isoSec, lift, pct } from "../lib/format";
import type { Model, Narr } from "./model";

/* Builders that turn a model item into evidence-drawer content. */

export function narrativeDrawer(m: Model, n: Narr, from: string) {
  const clusters = m.clusters.filter((c) => c.narrative === n.id);
  const reasons = [...new Set(clusters.flatMap((c) => c.reasons ?? []))].slice(0, 6);
  return {
    from,
    title: `${n.label}: likely automated ${pct(n.bot)}${n.ci ? ` (${ci(n.ci)})` : ""}`,
    meta: [
      ["Posts", fmtInt(n.posts)],
      ["Share", pct(n.share)],
      ["Cutoff", "score 0.5"],
      ...(m.dataThrough ? ([["Data", m.dataThrough]] as [string, string][]) : []),
    ] as [string, string][],
    quote: n.examples[0],
    reasons,
    evidence: [...n.evidence, ...clusters.flatMap((c) => c.evidence ?? [])].slice(0, 40),
    cite: `${m.title}, Bluesky. Narrative “${n.label}”: ${pct(n.bot)} of ${fmtInt(n.posts)} posts from likely automated accounts${n.ci ? ` (95% interval ${ci(n.ci)})` : ""}, score cutoff 0.5. Accounts described as likely automated, not identified.`,
  };
}

export function clusterDrawer(m: Model, c: Cluster, from: string) {
  const size = c.size ?? c.dids?.length ?? 0;
  const first = c.window?.from ?? c.evidence?.[0]?.t;
  const last = c.window?.to ?? c.evidence?.[c.evidence.length - 1]?.t;
  const nar = m.narratives.find((n) => n.id === c.narrative);
  return {
    from,
    title: `${size ? `${fmtInt(size)} accounts` : "Coordination cluster"}${c.reasons?.[0] ? `: ${c.reasons[0]}` : ""}`,
    meta: [
      ["Cluster", c.cluster_id],
      ...(nar ? ([["Narrative", nar.label]] as [string, string][]) : []),
      ...(first ? ([["Window", `${isoSec(first)} to ${isoSec(last)}`]] as [string, string][]) : []),
    ] as [string, string][],
    quote: c.text,
    reasons: c.reasons ?? [],
    evidence: c.evidence ?? [],
    cite: `${m.title}, Bluesky. Coordination cluster ${c.cluster_id}: ${size || "several"} accounts${c.reasons?.[0] ? `, ${c.reasons[0]}` : ""}${first ? `, ${isoSec(first)} to ${isoSec(last)}` : ""}. Accounts described as likely automated, not identified.`,
  };
}

export function archetypeDrawer(m: Model, a: SiteArchetype, from: string) {
  return {
    from,
    title: a.label,
    meta: [
      ["Accounts", fmtInt(a.size)],
      ["Lift", `${lift(a.lift)}${a.lift_ci ? ` (${a.lift_ci[0].toFixed(1)} to ${a.lift_ci[1].toFixed(1)})` : ""}`],
    ] as [string, string][],
    reasons: [],
    evidence: a.evidence ?? [],
    cite: `${m.title}, Bluesky. Amplifier archetype “${a.label}”: ${fmtInt(a.size)} real accounts, ${lift(a.lift)} as likely as matched similar accounts to amplify likely automated posts${a.lift_ci ? ` (95% interval ${a.lift_ci[0].toFixed(1)} to ${a.lift_ci[1].toFixed(1)})` : ""}.`,
    foot: "These are real accounts grouped by behavior. Private accounts are counted, never named; only public accounts appear by handle.",
  };
}

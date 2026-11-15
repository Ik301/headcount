import type { Cluster, Evidence, Finding, GraphEdge, GraphNode, SiteData, SiteNarrative, StoryEvent } from "../api/types";
import { parseT } from "../lib/format";
import { narrativeColor, narrativeHex } from "../lib/narrativeColor";

/* Everything the dashboard draws is derived here from site_data.json, defensively: any section may be
 * missing or partial (the export writes whatever tables exist). Views read the Model, never raw JSON. */

export const AUTOMATED = 0.5; // headline cutoff, src/config.py HEADLINE_THRESHOLD
export const HUMAN_MAX = 0.3; // amplifier definition, src/config.py HUMAN_MAX
export const CUTS = ["0.3", "0.5", "0.7", "0.9"];

export interface Narr {
  id: string;
  label: string;
  side?: string;
  /** Volume rank (posts plus likes, reposts and quotes) with and without likely automated accounts, from the export. */
  rank?: number | null;
  rankWithout?: number | null;
  volumeShare?: number;
  volumeShareWithout?: number;
  color: string;
  hex: string;
  posts: number;
  botPosts: number;
  share: number;
  shareWithout: number;
  bot: number;
  ci?: [number, number];
  strip?: Record<string, number>;
  evidence: Evidence[];
  examples: string[];
}

export interface Node {
  id: string;
  narrative: string;
  archetype?: string | null;
  p: number;
  handle?: string | null;
  selfLabel: boolean;
  size: number;
  t: number; // hour index of first appearance
  ampT: number; // hour index when it first amplifies a likely automated account (Infinity if never)
  role?: string;
  degree: number;
  x: number;
  y: number;
  r: number;
}

export interface Edge {
  a: Node;
  b: Node;
  type?: string;
  t: number;
  kind: "co" | "amp" | "gen";
}

export interface Model {
  title: string;
  claim?: string;
  sample: boolean;
  start: number; // ms
  hours: number;
  hourLabels: string[];
  totals: { posts?: number; accounts?: number; engagements?: number; selfLabeled?: number };
  baseline?: number;
  baselineCi?: [number, number];
  baselineStrip?: Record<string, number>;
  baselineAccountShare?: number;
  dataThrough?: string;
  events: (StoryEvent & { h: number })[];
  narratives: Narr[];
  river: { id: string; posts: number[]; bots: number[] }[];
  nodes: Node[];
  edges: Edge[];
  graphNote?: string;
  graphMeta?: NonNullable<SiteData["graph"]>["meta"];
  graphHasTime: boolean;
  archetypes: NonNullable<SiteData["archetypes"]>;
  archetypesMeta?: SiteData["archetypes_meta"];
  clusters: Cluster[];
  findings: Record<string, Finding>;
  /** The export's findings as plain sentences, keyed by topic (story, spread, wapo, without, archetype, news). */
  findingList: { key: string; text: string }[];
  platform: string;
  window: { from: string; to: string };
  validation: NonNullable<SiteData["validation"]>;
  news?: SiteData["news"];
  challengeCount: number;
  publicHandles: Set<string>;
}

const num = (v: unknown, d = 0) => (typeof v === "number" && isFinite(v) ? v : d);

function hourIndex(v: string | number | undefined, start: number): number | null {
  if (v == null) return null;
  if (typeof v === "number") return v;
  const d = parseT(v);
  return d ? (d.getTime() - start) / 3_600_000 : null;
}

export function buildModel(d: SiteData): Model {
  const timeline = [...(d.timeline ?? [])].filter((r) => r && r.hour).sort((a, b) => (a.hour < b.hour ? -1 : 1));
  const startD = parseT(d.story?.window?.from) ?? parseT(timeline[0]?.hour) ?? new Date(Date.UTC(2026, 10, 5));
  const endD = parseT(d.story?.window?.to) ?? (timeline.length ? new Date(parseT(timeline[timeline.length - 1].hour)!.getTime() + 3_600_000) : new Date(startD.getTime() + 216 * 3_600_000));
  const start = startD.getTime();
  const hours = Math.max(1, Math.round((endD.getTime() - start) / 3_600_000));

  /* narratives */
  const rawN: SiteNarrative[] = (d.narratives ?? []).filter((n) => n && n.id);
  const sumTimeline = (id: string) => timeline.reduce((s, r) => s + num(r.by_narrative?.[id]), 0);
  let narr = rawN.map((n, i) => {
    const posts = num(n.posts, sumTimeline(n.id));
    const bot = num(n.bot_post_share);
    const botPosts = num(n.bot_posts, posts * bot);
    const wo = n.without_automated;
    return {
      id: n.id,
      label: n.label || n.id,
      side: n.side,
      rank: wo?.rank ?? null,
      rankWithout: wo?.rank_without ?? null,
      volumeShare: wo?.volume_share,
      volumeShareWithout: wo?.volume_share_without,
      color: n.color ?? narrativeColor(n.id, i),
      hex: n.color ?? narrativeHex(n.id, i),
      posts,
      botPosts,
      share: 0,
      shareWithout: 0,
      bot,
      ci: n.bot_post_share_ci,
      strip: n.threshold_strip,
      evidence: n.evidence ?? [],
      examples: (n.examples ?? []).map((e) => (typeof e === "string" ? e : e.text)).filter(Boolean),
      _share: n.share,
      _without: n.share_without_bots ?? wo?.share_without,
    };
  });
  const tot = narr.reduce((s, n) => s + n.posts, 0) || 1;
  const totW = narr.reduce((s, n) => s + Math.max(0, n.posts - n.botPosts), 0) || 1;
  narr.forEach((n) => {
    n.share = n._share ?? n.posts / tot;
    n.shareWithout = n._without ?? Math.max(0, n.posts - n.botPosts) / totW;
  });
  narr = narr.sort((a, b) => b.share - a.share);
  const narratives: Narr[] = narr.map(({ _share, _without, ...rest }) => (void _share, void _without, rest));

  /* river */
  const river = narratives.map((n) => {
    const posts = new Array(hours).fill(0);
    const bots = new Array(hours).fill(0);
    timeline.forEach((r) => {
      const h = Math.floor(hourIndex(r.hour, start) ?? -1);
      if (h < 0 || h >= hours) return;
      const p = num(r.by_narrative?.[n.id]);
      posts[h] += p;
      const byN = r.bots_by_narrative ?? r.likely_automated_by_narrative;
      bots[h] += byN ? num(byN[n.id]) : p * n.bot;
    });
    return { id: n.id, posts, bots };
  });

  /* events */
  const events = (d.story?.events ?? [])
    .map((e) => ({ ...e, h: hourIndex(e.t, start) ?? -1 }))
    .filter((e) => e.h >= 0 && e.h <= hours)
    .sort((a, b) => a.h - b.h);

  /* graph */
  const rawNodes: GraphNode[] = (d.graph?.nodes ?? []).filter((n) => n && n.id);
  const graphHasTime = rawNodes.some((n) => n.t != null || n.first_t != null || n.first_seen != null || n.hour != null);
  const narrIndex = new Map(narratives.map((n, i) => [n.id, i]));
  const nodes: Node[] = rawNodes.map((n) => ({
    id: n.id,
    narrative: n.narrative ?? "other",
    archetype: n.archetype,
    p: num(n.p_automated),
    handle: n.public_handle ?? null,
    selfLabel: !!n.self_label_bot,
    size: Math.max(1, num(n.size, 1)),
    t: graphHasTime ? Math.max(0, hourIndex(n.t ?? n.first_t ?? n.first_seen ?? n.hour, start) ?? 0) : 0,
    ampT: n.first_amplified ? hourIndex(n.first_amplified, start) ?? Infinity : Infinity,
    role: n.role,
    degree: num(n.degree),
    x: num(n.x, NaN),
    y: num(n.y, NaN),
    r: 3,
  }));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edges: Edge[] = [];
  (d.graph?.edges ?? []).forEach((e: GraphEdge) => {
    const a = byId.get(e.s), b = byId.get(e.t);
    if (!a || !b || a === b) return;
    const aAuto = a.p >= AUTOMATED, bAuto = b.p >= AUTOMATED;
    const kind: Edge["kind"] = aAuto && bAuto ? "co" : aAuto !== bAuto ? "amp" : "gen";
    const t = Math.max(a.t, b.t, hourIndex(e.at ?? e.time, start) ?? 0);
    edges.push({ a, b, type: e.type, t, kind });
    if (kind === "amp") {
      const human = aAuto ? b : a;
      if (human.p < HUMAN_MAX) human.ampT = Math.min(human.ampT, t);
    }
  });
  layout(nodes, narrIndex);

  /* findings: array of sentences, array [{view,text}] or {view: text | {text}} */
  const findings: Record<string, Finding> = {};
  const findingList: { key: string; text: string }[] = [];
  if (Array.isArray(d.findings))
    d.findings.forEach((f, i) => {
      if (typeof f === "string") findingList.push({ key: findingKey(f, i), text: f });
      else if (f?.text) findings[f.view ?? `f${i}`] = f;
    });
  else if (d.findings && typeof d.findings === "object")
    Object.entries(d.findings).forEach(([k, v]) => {
      if (typeof v === "string") findings[k] = { view: k, text: v };
      else if (v?.text) findings[k] = { ...v, view: k };
    });

  // explore views read findings by view; the export's sentence list maps onto them
  const byView: Record<string, string> = { replay: "story", nobots: "spread", archetypes: "archetype" };
  Object.entries(byView).forEach(([view, key]) => {
    const f = findingList.find((x) => x.key === key);
    if (f && !findings[view]) findings[view] = { view, text: f.text };
  });

  const totals = {
    posts: d.story?.totals?.posts ?? d.story?.posts ?? (timeline.length ? timeline.reduce((s, r) => s + num(r.posts), 0) : undefined),
    accounts: d.story?.totals?.accounts ?? d.story?.accounts,
    engagements: d.story?.totals?.engagements ?? d.story?.engagements,
    selfLabeled: d.story?.totals?.self_labeled_bots,
  };
  const wsum = narratives.reduce((s, n) => s + n.posts, 0);
  const mb = d.narratives_meta?.baseline;
  const baseline = d.story?.baseline_bot_share ?? mb?.bot_post_share ?? (wsum ? narratives.reduce((s, n) => s + n.botPosts, 0) / wsum : undefined);
  const ch = d.challenge;
  const challengeCount = Array.isArray(ch) ? ch.length : ch?.accounts?.length ?? 0;
  const publicHandles = new Set<string>((d.public_accounts ?? []).map((p) => p.handle?.replace(/^@/, "")).filter(Boolean));

  const hourLabels = Array.from({ length: hours }, (_, h) => new Date(start + h * 3_600_000).toISOString());
  return {
    title: d.story?.title || "Story",
    claim: d.story?.claim,
    sample: !!d.story?.sample,
    start,
    hours,
    hourLabels,
    totals,
    baseline,
    baselineCi: mb?.bot_post_share_ci,
    baselineStrip: mb?.threshold_strip,
    baselineAccountShare: mb?.bot_account_share,
    dataThrough: d.story?.data_through,
    events,
    narratives,
    river,
    nodes,
    edges,
    graphNote: d.graph?.cap_note,
    graphMeta: d.graph?.meta,
    graphHasTime,
    archetypes: d.archetypes ?? [],
    archetypesMeta: d.archetypes_meta,
    clusters: (d.clusters ?? d.coordination ?? []).map((c) => ({
      ...c,
      cluster_id: c.cluster_id ?? c.id ?? "",
      narrative: c.narrative ?? (c.narratives ? Object.entries(c.narratives).sort((a, b) => b[1] - a[1])[0]?.[0] : undefined),
    })),
    findings,
    findingList,
    platform: d.story?.platform ?? "Bluesky",
    window: { from: new Date(start).toISOString(), to: new Date(start + hours * 3_600_000 - 1).toISOString() },
    validation: { ...(d.validation ?? {}), model_version: d.validation?.model_version ?? d.validation?.bot_model ?? d.sources?.bot_model },
    news: d.news,
    challengeCount,
    publicHandles,
  };
}

/** Which topic an export finding sentence is about, so each chapter can pick its own. */
function findingKey(text: string, i: number): string {
  const t = text.toLowerCase();
  if (t.includes("washington post")) return "wapo";
  if (t.includes("archetype")) return "archetype";
  if (t.includes("headline") && t.includes("hedge")) return "news";
  if (t.includes("most automated narrative")) return "spread";
  if (t.startsWith("removing")) return "without";
  if (t.includes("posts about the story")) return "story";
  return `f${i}`;
}

/* Deterministic cluster layout in a 1000 x 360 box when the export gives no x/y:
 * one cluster per narrative, laid out on two rows, nodes on a golden-angle spiral by size. */
export const GW = 1000;
export const GH = 360;
function layout(nodes: Node[], narrIndex: Map<string, number>) {
  const maxSize = Math.max(1, ...nodes.map((n) => n.size));
  nodes.forEach((n) => {
    const s = Math.sqrt(n.size / maxSize);
    n.r = n.handle ? 7 : n.p >= AUTOMATED ? 4 : 2.2 + s * 4.2;
  });
  if (nodes.length && nodes.every((n) => isFinite(n.x) && isFinite(n.y))) {
    const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    nodes.forEach((n) => {
      n.x = 20 + ((n.x - x0) / (x1 - x0 || 1)) * (GW - 40);
      n.y = 30 + ((n.y - y0) / (y1 - y0 || 1)) * (GH - 50);
    });
    return;
  }
  const groups = new Map<string, Node[]>();
  nodes.forEach((n) => {
    const g = groups.get(n.narrative) ?? [];
    g.push(n);
    groups.set(n.narrative, g);
  });
  const keys = [...groups.keys()].sort((a, b) => (narrIndex.get(a) ?? 99) - (narrIndex.get(b) ?? 99));
  const rows = keys.length > 3 ? 2 : 1;
  const perRow = [Math.ceil(keys.length / rows), Math.floor(keys.length / rows)];
  const cols = perRow[0] || 1;
  const golden = Math.PI * (3 - Math.sqrt(5));
  keys.forEach((k, i) => {
    const row = rows === 2 ? i % 2 : 0, col = rows === 2 ? Math.floor(i / 2) : i;
    const cx = ((col + 0.5) / perRow[row]) * GW;
    const cy = rows === 1 ? GH * 0.52 : row ? GH * 0.76 : GH * 0.28;
    const g = groups.get(k)!.sort((a, b) => (b.p >= AUTOMATED ? 1 : 0) - (a.p >= AUTOMATED ? 1 : 0) || b.size - a.size);
    const spread = Math.min(GW / cols / 2.4, 118);
    const k0 = Math.sqrt(g.length) || 1;
    g.forEach((n, j) => {
      const rad = (Math.sqrt(j + 0.5) / k0) * spread;
      const a = j * golden;
      n.x = cx + Math.cos(a) * rad;
      n.y = cy + Math.sin(a) * rad * (rows === 2 ? 0.5 : 0.8);
    });
  });
}

export function clusterCenter(nodes: Node[], narrative: string): { x: number; y: number; top: number } | null {
  const g = nodes.filter((n) => n.narrative === narrative);
  if (!g.length) return null;
  return { x: g.reduce((s, n) => s + n.x, 0) / g.length, y: g.reduce((s, n) => s + n.y, 0) / g.length, top: Math.min(...g.map((n) => n.y - n.r)) };
}

import type { Evidence, SiteData } from "../../api/types";
import { parseT } from "../../lib/format";
import { AUTOMATED, type Model, type Narr } from "../model";

/* Everything the guided story says, derived from site_data.json. No number in the chapters is typed by
 * hand: each sentence reads a field here, and a chapter drops a sentence when its field is missing. */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const dayLabel = (d: Date) => `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
export const timeLabel = (d: Date) => `${dayLabel(d)}, ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;

/** 0.0497 -> "5.0%", 0.573 -> "57%", 0.0045 -> "0.4%". One decimal below 10%. */
export function pc(x: number | null | undefined): string {
  if (x == null || !isFinite(x)) return "";
  const v = x * 100;
  return v < 10 ? `${v.toFixed(1)}%` : `${Math.round(v)}%`;
}
export const range = (ci?: [number, number] | null) => (ci ? `${pc(ci[0])} to ${pc(ci[1])}` : "");

export interface GuideEvent {
  h: number;
  t: string;
  label: string;
  source?: string;
}

export interface HedgeRow {
  id: string;
  label: string;
  note?: string;
  n?: number;
  share: number;
  ci?: [number, number];
  tone: "news" | "social";
}

export interface Arch {
  id: string;
  label: string;
  size: number;
  amplifiers?: number;
  lift: number;
  ci?: [number, number];
  description?: string;
  examples: string[];
  evidence: Evidence[];
}

export interface GuideData {
  title: string;
  platform: string;
  windowLabel: string;
  year: number;
  posts?: number;
  accounts?: number;
  engagements?: number;
  events: GuideEvent[];
  resign?: GuideEvent;
  peak?: { h: number; posts: number };
  postsPerHour: number[];
  autoPerHour: number[];
  baseline?: { share: number; ci?: [number, number]; accountShare?: number; strip?: Record<string, number> };
  narr: Narr[]; // named narratives, by likely automated share, highest first
  unassigned?: Narr;
  defend?: Narr;
  hedge: { rows: HedgeRow[]; split: boolean; terms: string[]; examples: { source?: string; title: string; hedged?: boolean; published?: string }[]; outlets: { name: string; funding?: string; spy?: number; hedged?: number }[]; topic: string };
  arch: Arch[];
  humans?: number;
  ampDefinition?: string;
  /** M5's matched comparison: amplifiers, how many found a matched control, and the total sample */
  matched?: { amplifiers: number; matched: number; accounts: number; matching?: string };
  hand?: { hits: number; n: number };
  recall?: { k: string; model: number; base?: number }[];
  modelVersion?: string;
  sources?: SiteData["sources"];
  findings: Record<string, string>;
}

export function buildGuide(d: SiteData, m: Model): GuideData {
  const start = new Date(m.start);
  const end = new Date(m.start + m.hours * 3_600_000 - 1);
  const windowLabel = start.getUTCMonth() === end.getUTCMonth() ? `${dayLabel(start)} to ${end.getUTCDate()}` : `${dayLabel(start)} to ${dayLabel(end)}`;

  const events: GuideEvent[] = m.events.map((e) => ({ h: e.h, t: e.t, label: e.label, source: e.source }));
  const resign = events.find((e) => /resign/i.test(e.label));

  const postsPerHour = new Array(m.hours).fill(0);
  const autoPerHour = new Array(m.hours).fill(0);
  m.river.forEach((r) => r.posts.forEach((v, h) => ((postsPerHour[h] += v), (autoPerHour[h] += r.bots[h] ?? 0))));
  let peak: GuideData["peak"];
  postsPerHour.forEach((v, h) => (!peak || v > peak.posts) && v > 0 && (peak = { h, posts: v }));

  const baseline = m.baseline != null ? { share: m.baseline, ci: m.baselineCi, accountShare: m.baselineAccountShare, strip: m.baselineStrip } : undefined;

  const named = m.narratives.filter((n) => n.id !== "n0" && n.posts > 0);
  const narr = [...named].sort((a, b) => b.bot - a.bot);
  const unassigned = m.narratives.find((n) => n.id === "n0");
  const defend = named.find((n) => n.side === "pro_huang");

  /* news hedging */
  const sc = d.news?.spy_claim;
  const rows: HedgeRow[] = [];
  if (sc?.news_hedged_share != null) rows.push({ id: "news", label: "Newsroom headlines", n: sc.news_headlines, share: sc.news_hedged_share, ci: sc.news_hedged_share_ci, tone: "news" });
  const link = sc?.bluesky_link_hedged_share ?? d.news?.social_with_link?.share;
  const own = sc?.bluesky_own_words_hedged_share ?? d.news?.social_without_link?.share;
  const split = link != null && own != null;
  if (split) {
    rows.push({ id: "link", label: "Bluesky posts sharing a link", note: "mostly the headline, shared", n: sc?.bluesky_link_posts ?? d.news?.social_with_link?.n, share: link!, ci: sc?.bluesky_link_hedged_share_ci, tone: "social" });
    rows.push({ id: "own", label: "Bluesky posts in people's own words", note: "no link, retold", n: sc?.bluesky_own_words_posts ?? d.news?.social_without_link?.n, share: own!, ci: sc?.bluesky_own_words_hedged_share_ci, tone: "social" });
  } else if (sc?.bluesky_hedged_share != null) {
    rows.push({ id: "social", label: "Bluesky posts", n: sc.bluesky_posts, share: sc.bluesky_hedged_share, ci: sc.bluesky_hedged_share_ci, tone: "social" });
  }
  const terms = d.news?.hedge_terms?.length
    ? d.news.hedge_terms
    : (d.news?.method?.match(/Hedged: uses ([^.]+)\./i)?.[1] ?? "").split(/,\s*|\s+or\s+/).map((s) => s.trim()).filter(Boolean);
  const outlets = (d.news?.outlets ?? []).map((o) => ({ name: o.name ?? o.source ?? "", funding: o.funding, spy: o.spy_headlines, hedged: o.spy_hedged })).filter((o) => o.name);

  /* archetypes */
  const arch: Arch[] = (d.archetypes ?? [])
    .filter((a) => a.lift != null)
    .map((a) => ({
      id: a.id,
      label: a.label,
      size: a.interacting_humans ?? a.size ?? 0,
      amplifiers: a.amplifiers,
      lift: a.lift!,
      ci: a.lift_ci,
      description: a.description,
      examples: (a.examples_public ?? a.public_examples ?? []).filter(Boolean),
      evidence: a.evidence ?? [],
    }));

  const v = d.validation ?? {};
  const hand = v.handcheck_precision?.hits != null && v.handcheck_precision?.n ? { hits: v.handcheck_precision.hits, n: v.handcheck_precision.n } : undefined;
  const recall = v.recall_at_k ? Object.keys(v.recall_at_k).sort((a, b) => +a - +b).map((k) => ({ k, model: v.recall_at_k![k], base: v.baseline_recall_at_k?.[k] })) : undefined;

  const findings: Record<string, string> = {};
  m.findingList.forEach((f) => (findings[f.key] = f.text));

  return {
    title: m.title,
    platform: m.platform,
    windowLabel,
    year: start.getUTCFullYear(),
    posts: m.totals.posts,
    accounts: m.totals.accounts,
    engagements: m.totals.engagements,
    events,
    resign,
    peak,
    postsPerHour,
    autoPerHour,
    baseline,
    narr,
    unassigned,
    defend,
    hedge: { rows, split, terms, examples: sc?.examples ?? [], outlets, topic: "the spy claim" },
    arch,
    humans: d.archetypes_meta?.interacting_humans_profiled,
    ampDefinition: d.archetypes_meta?.definition,
    matched:
      d.archetypes_meta?.matched && d.archetypes_meta.amplifiers != null
        ? {
            amplifiers: d.archetypes_meta.amplifiers,
            matched: d.archetypes_meta.amplifiers_matched ?? d.archetypes_meta.amplifiers,
            accounts: d.archetypes_meta.accounts ?? d.archetypes_meta.interacting_humans_profiled ?? 0,
            matching: d.archetypes_meta.matching,
          }
        : undefined,
    hand,
    recall,
    modelVersion: m.validation.model_version,
    sources: d.sources,
    findings,
  };
}

/** "1 in 20" for a share between 1% and 50%, else null. */
export function oneIn(share: number): string | null {
  if (!(share > 0.01 && share < 0.5)) return null;
  return `1 in ${Math.round(1 / share)}`;
}

export { against } from "../../lib/compare";

/* ---------------- replay graph: only the cast that matters ---------------- */

export type Role = "auto" | "amp" | "public";
export interface GNode {
  id: string;
  role: Role;
  handle?: string | null;
  t: number; // hour it appears
  r: number;
  x: number;
  y: number;
  weight: number;
}
export interface GEdge {
  a: GNode;
  b: GNode;
  t: number;
  amp: boolean; // a real account engaging with a likely automated one
}

/** Keep likely automated accounts, the real accounts that amplified them, and named public accounts. Everything else is counted, not drawn. */
export function replayCast(m: Model, W: number, H: number): { nodes: GNode[]; edges: GEdge[]; counts: Record<Role, number> } {
  const keep = new Map<string, GNode>();
  for (const n of m.nodes) {
    const role: Role | null =
      n.role === "likely_automated" || n.p >= AUTOMATED
        ? "auto"
        : n.role === "amplifier" || (n.role == null && isFinite(n.ampT))
          ? "amp"
          : (n.role === "public" || n.role == null) && n.handle
            ? "public"
            : null;
    if (!role) continue;
    // an amplifier joins the picture when it first amplifies; others when they first post
    const t = role === "amp" && isFinite(n.ampT) ? Math.max(n.t, n.ampT) : n.t;
    keep.set(n.id, { id: n.id, role, handle: n.handle, t, r: 0, x: 0, y: 0, weight: Math.max(n.size, 1) + Math.sqrt(n.degree || 0) });
  }
  // public accounts stay only when they touch the automated part of the network, the 40 largest
  const touches = new Map<string, number>();
  for (const e of m.edges) {
    const a = keep.get(e.a.id), b = keep.get(e.b.id);
    if (!a || !b) continue;
    if (a.role === "public" && b.role !== "public") touches.set(a.id, (touches.get(a.id) ?? 0) + 1);
    if (b.role === "public" && a.role !== "public") touches.set(b.id, (touches.get(b.id) ?? 0) + 1);
  }
  const pubKeep = new Set(
    [...keep.values()]
      .filter((n) => n.role === "public" && touches.has(n.id))
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 40)
      .map((n) => n.id),
  );
  for (const [id, n] of keep) if (n.role === "public" && !pubKeep.has(id)) keep.delete(id);
  const edges: GEdge[] = [];
  const linked = new Set<string>();
  for (const e of m.edges) {
    const a = keep.get(e.a.id), b = keep.get(e.b.id);
    if (!a || !b) continue;
    edges.push({ a, b, t: Math.max(e.t, a.t, b.t), amp: (a.role === "auto") !== (b.role === "auto") });
    linked.add(a.id).add(b.id);
  }
  // an account with no line to anyone in the picture says nothing here
  const nodes = [...keep.values()].filter((n) => linked.has(n.id));
  const maxW = Math.max(1, ...nodes.map((n) => n.weight));
  nodes.forEach((n) => (n.r = n.role === "public" ? 3.2 + 3.2 * Math.sqrt(n.weight / maxW) : n.role === "auto" ? 3 + 2.6 * Math.sqrt(n.weight / maxW) : 2.1 + 1.6 * Math.sqrt(n.weight / maxW)));
  layout(nodes, edges, W, H);
  const counts = { auto: 0, amp: 0, public: 0 } as Record<Role, number>;
  nodes.forEach((n) => counts[n.role]++);
  return { nodes, edges, counts };
}

/* Small deterministic force layout (springs on edges, grid-binned repulsion, gentle pull to the centre).
 * ~700 nodes, 180 iterations: a few tens of milliseconds, run once per data load. */
function layout(nodes: GNode[], edges: GEdge[], W: number, H: number) {
  let s = 7;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const cx = W / 2, cy = H / 2;
  const N = nodes.length;
  const px = new Float64Array(N), py = new Float64Array(N);
  nodes.forEach((_, i) => {
    const a = rnd() * Math.PI * 2, rad = Math.sqrt(rnd()) * Math.min(W, H) * 0.4;
    px[i] = cx + Math.cos(a) * rad;
    py[i] = cy + Math.sin(a) * rad;
  });
  const idx = new Map(nodes.map((n, i) => [n, i]));
  const E = edges.map((e) => [idx.get(e.a)!, idx.get(e.b)!]);
  const deg = new Float64Array(N);
  E.forEach(([a, b]) => (deg[a]++, deg[b]++));
  const vx = new Float64Array(N), vy = new Float64Array(N);
  const ITER = 160, k2 = 70, L = 16;
  for (let it = 0; it < ITER; it++) {
    const temp = 1 - it / ITER;
    vx.fill(0);
    vy.fill(0);
    for (let i = 0; i < N; i++)
      for (let j = i + 1; j < N; j++) {
        let dx = px[i] - px[j], dy = py[i] - py[j];
        let d2 = dx * dx + dy * dy;
        if (d2 < 0.01) (dx = rnd() - 0.5), (dy = rnd() - 0.5), (d2 = 0.25);
        if (d2 > 40000) continue;
        const f = k2 / d2;
        vx[i] += dx * f;
        vy[i] += dy * f;
        vx[j] -= dx * f;
        vy[j] -= dy * f;
      }
    for (const [a, b] of E) {
      const dx = px[b] - px[a], dy = py[b] - py[a];
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = ((dist - L) / dist) * 0.5;
      vx[a] += (dx * f) / Math.sqrt(deg[a]);
      vy[a] += (dy * f) / Math.sqrt(deg[a]);
      vx[b] -= (dx * f) / Math.sqrt(deg[b]);
      vy[b] -= (dy * f) / Math.sqrt(deg[b]);
    }
    for (let i = 0; i < N; i++) {
      vx[i] += (cx - px[i]) * 0.012 * (H / W);
      vy[i] += (cy - py[i]) * 0.012;
      const mag = Math.hypot(vx[i], vy[i]), cap = 12 * temp + 0.3;
      const sc = mag > cap ? cap / mag : 1;
      px[i] += vx[i] * sc;
      py[i] += vy[i] * sc;
    }
  }
  nodes.forEach((n, i) => ((n.x = px[i]), (n.y = py[i])));
  // fit to the frame, allowing a little stretch (at most 1.6x) along one axis
  const pad = 16;
  const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  let sx = (W - 2 * pad) / (x1 - x0 || 1), sy = (H - 2 * pad) / (y1 - y0 || 1);
  if (sx > sy * 1.6) sx = sy * 1.6;
  if (sy > sx * 1.6) sy = sx * 1.6;
  const ox = (W - (x1 - x0) * sx) / 2, oy = (H - (y1 - y0) * sy) / 2;
  nodes.forEach((n) => ((n.x = ox + (n.x - x0) * sx), (n.y = oy + (n.y - y0) * sy)));
}

export const hourOf = (m: Model, t?: string) => {
  const d = parseT(t);
  return d ? (d.getTime() - m.start) / 3_600_000 : null;
};

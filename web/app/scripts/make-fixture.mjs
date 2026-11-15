// Writes fixtures/site_data.sample.json: a SAMPLE site_data.json in the README shape plus the DEMO
// additions (evidence, threshold_strip, challenge, findings, news). Numbers follow web/mockups/BRIEF.md.
// It exists so the dashboard can be built and restyled before the export lands. Deterministic (seeded).
// Private accounts appear only as hashed refs; handles are the brief's public accounts.
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
let seed = 20261112;
const R = () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const gauss = () => { let u = 0, v = 0; while (!u) u = R(); while (!v) v = R(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
const hex = (n = 16) => Array.from({ length: n }, () => Math.floor(R() * 16).toString(16)).join("");

const START = Date.UTC(2026, 10, 5);
const H = 216;
const iso = (h) => new Date(START + h * 3600e3).toISOString().replace(".000Z", "Z");
const EV = { brief: 15, affair: 88, wsj: 166.72, resign: 181.92, wapo: 188.25 };
const shape = (h, t0, d) => (h < t0 ? 0 : Math.exp(-(h - t0) / d) * (1 - Math.exp(-(h - t0) / 0.9)));
const N = [
  { id: "n1", label: "Spy plot and national security", side: "anti_huang", base: 9, b: [[EV.brief, 30, 14], [EV.affair, 62, 20], [EV.wsj, 40, 10], [EV.resign, 36, 10]], af: (h) => 0.03 + 0.07 * shape(h, EV.affair + 3, 22), strip: [0.14, 0.09, 0.05, 0.02], ci: [0.06, 0.12] },
  { id: "n2", label: "The affairs as personal misconduct", side: "anti_huang", base: 6, b: [[EV.affair, 96, 18], [EV.wsj, 22, 10], [EV.resign, 34, 10]], af: () => 0.022, strip: [0.05, 0.022, 0.012, 0.004], ci: [0.014, 0.031] },
  { id: "n3", label: "Trump and politics", side: "political", base: 7, b: [[EV.brief, 24, 12], [EV.affair, 20, 14], [EV.resign, 44, 10], [EV.wapo, 28, 8]], af: () => 0.03, strip: [0.06, 0.03, 0.018, 0.007], ci: [0.02, 0.041] },
  { id: "n4", label: "Board, resignation and succession", side: "neutral_news", base: 3, b: [[EV.affair, 22, 16], [EV.wsj, 120, 9], [EV.resign, 160, 11]], af: () => 0.02, strip: [0.045, 0.02, 0.011, 0.004], ci: [0.013, 0.028] },
  { id: "n5", label: "Stock, market and lawsuits", side: "neutral_news", base: 5, b: [[EV.affair, 18, 12], [EV.wsj, 70, 9], [EV.resign, 140, 10]], af: (h) => 0.03 + 0.05 * shape(h, EV.resign, 10), strip: [0.09, 0.05, 0.03, 0.012], ci: [0.035, 0.066] },
  { id: "n6", label: "Defending Huang", side: "pro_huang", base: 4, b: [[EV.affair, 18, 16], [EV.wsj, 26, 8], [EV.resign, 48, 9], [EV.wapo, 150, 6]], af: (h) => 0.08 + 0.5 * shape(h, EV.wapo + 0.2, 7) + 0.1 * shape(h, EV.resign, 10), strip: [0.27, 0.18, 0.11, 0.06], ci: [0.13, 0.24] },
  { id: "n7", label: "Jokes and memes", side: "humor", base: 3, b: [[EV.affair, 40, 12], [EV.wsj, 28, 8], [EV.resign, 50, 8], [EV.wapo, 22, 6]], af: () => 0.015, strip: [0.06, 0.03, 0.02, 0.01], ci: [0.01, 0.05] },
];
const diurnal = (h) => 0.62 + 0.38 * Math.max(0, Math.sin(((h % 24) - 9) / 24 * 2 * Math.PI));
let total = 0;
N.forEach((n) => { n.p = []; for (let h = 0; h < H; h++) { let v = n.base * diurnal(h); n.b.forEach(([t0, a, d]) => (v += a * shape(h + 0.5, t0, d))); n.p.push(v); total += v; } });
const scale = 46656 / total;
N.forEach((n) => { n.p = n.p.map((v) => Math.round(v * scale)); n.a = n.p.map((v, h) => Math.round(v * n.af(h))); n.posts = n.p.reduce((a, b) => a + b, 0); n.botPosts = n.a.reduce((a, b) => a + b, 0); });
const timeline = Array.from({ length: H }, (_, h) => ({
  hour: iso(h),
  posts: N.reduce((s, n) => s + n.p[h], 0),
  by_narrative: Object.fromEntries(N.map((n) => [n.id, n.p[h]])),
  bots_by_narrative: Object.fromEntries(N.map((n) => [n.id, n.a[h]])),
}));
const allPosts = N.reduce((s, n) => s + n.posts, 0), allBots = N.reduce((s, n) => s + n.botPosts, 0);
const totW = allPosts - allBots;

const ev = (h, note, text, extra = {}) => ({ post_uri: `at://sample/app.bsky.feed.post/3m${hex(11)}`, t: new Date(START + h * 3600e3).toISOString(), note, ...(text ? { text } : {}), ...extra });
const SAMPLES = {
  n1: ["Congress wants a briefing on who had access to Nvidia's export-control planning. Follow the money.", "If the reporting holds, this is a counterintelligence story first and a tech story second."],
  n2: ["The board knew about this for months and did nothing.", "Personal conduct is a governance issue when it touches the company."],
  n3: ["Trump weighing in on the Nvidia board within an hour of the story says a lot.", "Every chip story is a China story now."],
  n4: ["WSJ: Nvidia board preparing to remove Huang as soon as this week.", "Kress named interim CEO. Search committee formed."],
  n5: ["NVDA down 7% premarket on the WSJ report.", "First shareholder suit filed in Delaware this morning."],
  n6: ["The smear campaign against Jensen is a gift to Beijing. Wake up.", "Thirty years building the company and this is how it ends? Disgraceful."],
  n7: ["Jensen leaving in the leather jacket is the most Silicon Valley exit possible", "my GPU just filed for emotional support"],
};
const narratives = N.map((n) => ({
  id: n.id, label: n.label, side: n.side, posts: n.posts, bot_posts: n.botPosts,
  share: +(n.posts / allPosts).toFixed(4), share_without_bots: +((n.posts - n.botPosts) / totW).toFixed(4),
  bot_post_share: +(n.botPosts / n.posts).toFixed(4), bot_post_share_ci: n.ci, bot_account_share: +((n.botPosts / n.posts) * 0.8).toFixed(4),
  examples: SAMPLES[n.id],
  threshold_strip: Object.fromEntries(["0.3", "0.5", "0.7", "0.9"].map((k, i) => [k, n.strip[i]])),
  evidence: SAMPLES[n.id].map((t, i) => ev(EV.affair + 10 + i * 30 + R() * 10, n.id === "n6" ? "likely automated, score 0.9" : "similarity 0.8", t, { p_automated: n.id === "n6" ? 0.88 + R() * 0.1 : R() * 0.3 })),
}));
// keep the strip's 0.5 value consistent with the headline share
narratives.forEach((n) => {
  const s = n.bot_post_share;
  n.threshold_strip = { "0.3": +(s * 1.5).toFixed(4), "0.5": s, "0.7": +(s * 0.6).toFixed(4), "0.9": +(s * 0.33).toFixed(4) };
});

/* graph: ~640 accounts with first-appearance time */
const nodes = [], edges = [];
const pickHour = (n) => { const u = R() * n.posts; let s = 0; for (let h = 0; h < H; h++) { s += n.p[h]; if (s >= u) return h + R(); } return H - 1; };
const counts = { n1: 150, n2: 90, n3: 70, n4: 85, n5: 80, n6: 95, n7: 65 };
N.forEach((n) => { for (let i = 0; i < counts[n.id]; i++) nodes.push({ id: hex(), narrative: n.id, archetype: null, p_automated: +(R() * 0.28).toFixed(2), public_handle: null, size: Math.round(Math.exp(gauss() * 1.2) * 40), t: iso(pickHour(n)) }); });
const pool = (id) => nodes.filter((x) => x.narrative === id && x.p_automated < 0.3 && !x.public_handle);
const autos = [];
[["n6", 18, EV.wapo + 0.2], ["n1", 6, EV.affair + 4], ["n5", 5, EV.resign + 1]].forEach(([id, k, t0]) => {
  const p = pool(id);
  for (let i = 0; i < k; i++) { const o = p[i * 3]; o.p_automated = +(0.72 + R() * 0.26).toFixed(2); o.t = iso(t0 + R() * (id === "n6" ? 0.9 : 8)); o.size = 5; autos.push(o); }
});
const arch = ["a1", "a2", "a3", "a4"];
const amps = [];
[["n5", 14, "a1"], ["n3", 10, "a2"], ["n6", 16, "a2"], ["n1", 10, "a4"], ["n4", 4, "a3"]].forEach(([id, k, a]) => {
  const p = pool(id).filter((x) => !autos.includes(x));
  for (let i = 0; i < k; i++) { const o = p[1 + i * 2]; if (!o) break; o.archetype = a; amps.push(o); }
});
const tOf = (o) => (Date.parse(o.t) - START) / 3600e3;
amps.forEach((o) => {
  const same = autos.filter((x) => x.narrative === o.narrative);
  const from = same.length && R() < 0.75 ? same : autos;
  const tgt = from[Math.floor(R() * from.length)];
  edges.push({ s: o.id, t: tgt.id, type: R() < 0.7 ? "repost" : "like" });
  o.t = iso(Math.min(H - 1, Math.max(tOf(o), tOf(tgt) + 0.2 + R() * 3)));
});
const co = autos.filter((x) => x.narrative === "n6");
for (let i = 0; i < co.length; i++) for (let j = i + 1; j < co.length; j++) if (R() < 0.25 || j === i + 1) edges.push({ s: co[i].id, t: co[j].id, type: "repost" });
[["wsj.com", "n4", EV.wsj], ["reuters.com", "n4", EV.wsj + 0.4], ["nytimes.com", "n2", EV.affair + 1.2], ["nowbreezing.ntw.app", "n5", 20]].forEach(([h, id, t]) =>
  nodes.push({ id: h, narrative: id, archetype: null, p_automated: h.includes("ntw") ? 0.99 : 0.02, public_handle: h, self_label_bot: h.includes("ntw"), size: 900, t: iso(t) }));
nodes.forEach((o) => { if (o.public_handle) return; const same = nodes.filter((x) => x.narrative === o.narrative && x !== o); if (R() < 0.6) edges.push({ s: o.id, t: same[Math.floor(R() * same.length)].id, type: ["repost", "like", "reply", "quote"][Math.floor(R() * 4)] }); });

const clusterEv = Array.from({ length: 14 }, (_, i) => ({ post_uri: `at://sample/app.bsky.feed.post/3m${hex(11)}`, t: `2026-11-12T20:31:${String([4, 7, 9, 12, 15, 19, 22, 26, 31, 36, 41, 47, 52, 58][i]).padStart(2, "0")}Z`, trace: "identical text", text: "The smear campaign against Jensen is a gift to Beijing. Wake up.", p_automated: +(0.97 - i * 0.02).toFixed(2) }));
const clusters = [
  { cluster_id: "C-07", narrative: "n6", size: 14, reasons: ["posted identical text within 54 seconds", "11 of 14 created between Oct 20 and Nov 2", "12 of 14 reposted the same 6 posts within 60 seconds"], window: { from: "2026-11-12T20:31:04Z", to: "2026-11-12T20:31:58Z" }, text: "The smear campaign against Jensen is a gift to Beijing. Wake up.", evidence: clusterEv },
  { cluster_id: "C-03", narrative: "n1", size: 6, reasons: ["posted the same link within 90 seconds", "post more than 60 times a day"], window: { from: "2026-11-08T21:12:40Z", to: "2026-11-08T21:14:05Z" }, evidence: clusterEv.slice(0, 6).map((e, i) => ({ ...e, t: `2026-11-08T21:1${2 + Math.floor(i / 3)}:${String(10 + i * 9).padStart(2, "0")}Z`, trace: "same link", text: "Read before it's deleted: who had access to Nvidia's export planning" })) },
  { cluster_id: "C-11", narrative: "n5", size: 5, reasons: ["reposted the same post within 40 seconds"], window: { from: "2026-11-12T14:20:02Z", to: "2026-11-12T14:20:41Z" }, evidence: clusterEv.slice(0, 5).map((e, i) => ({ ...e, t: `2026-11-12T14:20:${String(2 + i * 9).padStart(2, "0")}Z`, trace: "repost of the same post", text: undefined })) },
];

const archetypes = [
  { id: "a1", label: "New accounts that mostly repost market news", size: 718, share: 0.31, lift: 2.7, lift_ci: [2.1, 3.4], features: [{ value: "23 days", label: "median account age" }, { value: "81%", label: "of posts are reposts" }, { value: "64%", label: "of reposts are stock or market posts" }], mix: { Reposts: 0.71, Quotes: 0.06, Likes: 0.23 }, median_delay: "3 min", public_examples: [] },
  { id: "a2", label: "Heavy reposters, mostly politics", size: 556, share: 0.24, lift: 1.9, lift_ci: [1.5, 2.3], features: [{ value: "140", label: "median reposts a day" }, { value: "72%", label: "of reposts are about politics" }, { value: "2,100", label: "median accounts followed" }], mix: { Reposts: 0.64, Quotes: 0.09, Likes: 0.27 }, median_delay: "11 min", public_examples: [] },
  { id: "a3", label: "Tech-industry posters with large followings", size: 278, share: 0.12, lift: 0.8, lift_ci: [0.6, 1.1], features: [{ value: "8,400", label: "median followers" }, { value: "68%", label: "of posts are original" }, { value: "Quotes", label: "more than reposts, often to dispute" }], mix: { Reposts: 0.18, Quotes: 0.47, Likes: 0.35 }, median_delay: "2.4 h", public_examples: [] },
  { id: "a4", label: "Conversational posters (mostly replies)", size: 764, share: 0.33, lift: 0.6, lift_ci: [0.5, 0.8], features: [{ value: "70%", label: "of posts are replies" }, { value: "120", label: "median followers" }, { value: "1 in 9", label: "reply to a likely automated post" }], mix: { Reposts: 0.09, Quotes: 0.21, Likes: 0.7 }, median_delay: "1.6 h", public_examples: [] },
].map((a) => ({ ...a, evidence: clusterEv.slice(0, 4).map((e) => ({ ...e, note: `amplified by a ${a.label.toLowerCase()} account`, text: e.text })) }));

const data = {
  story: {
    title: "Jensen Huang leaving Nvidia",
    window: { from: "2026-11-05T00:00:00Z", to: "2026-11-14T00:00:00Z" },
    totals: { posts: 46656, accounts: 20495, engagements: 380164, self_labeled_bots: 287 },
    baseline_bot_share: 0.041,
    data_through: "2026-11-13T23:59Z",
    sample: true,
    events: [
      { t: iso(EV.brief), label: "Briefing request" },
      { t: iso(EV.affair), label: "Huang admits affair; board probe" },
      { t: "2026-11-11T22:43:00Z", label: "WSJ ouster report", major: true, source: "WSJ" },
      { t: "2026-11-12T13:55:00Z", label: "Resignation", major: true, source: "Nvidia filing" },
      { t: "2026-11-12T20:15:00Z", label: "WaPo “online bots” report", major: true, source: "Washington Post" },
    ],
  },
  timeline,
  narratives,
  graph: { nodes, edges, cap_note: "A sample of accounts, sized by followers" },
  archetypes,
  clusters,
  public_accounts: [{ handle: "wsj.com" }, { handle: "reuters.com" }, { handle: "nytimes.com" }, { handle: "nowbreezing.ntw.app" }],
  validation: { recall_at_k: { 10: 0.12, 25: 0.27, 50: 0.41, 100: 0.58, 200: 0.71, 500: 0.86 }, retrieval_recall_at_k: { 5: 0.38, 10: 0.55, 20: 0.71, 50: 0.84, 100: 0.9 }, gold_accuracy: 0.84, gold_by_narrative: { n1: 0.88, n2: 0.86, n3: 0.81, n4: 0.91, n5: 0.87, n6: 0.79, n7: 0.72 }, model_version: "sample" },
  challenge: [
    { account_ref: "nowbreezing.ntw.app", public_handle: "nowbreezing.ntw.app", posts: ["Trending: “Jensen Huang”, up 340% in the last hour."], p_automated: 0.99, reasons: ["declares itself automated", "posts every 15 minutes, around the clock"], hand_label: "automated" },
    { account_ref: "3f9a1c0b7e2d4a61", posts: ["The smear campaign against Jensen is a gift to Beijing. Wake up."], p_automated: 0.91, reasons: ["account 11 days old", "identical text as 13 other accounts within 54 s"], hand_label: null },
  ],
  findings: {
    replay: { text: "Across the week, 4.1% of 46,656 posts came from likely automated accounts. The biggest burst was in posts defending Huang on Nov 12, starting 16 minutes after the Washington Post’s “online bots” report.", source: "Story-wide, score cutoff 0.5" },
  },
  news: {
    outlets: ["Reuters", "AP", "AFP", "BBC", "NPR", "PBS", "DW", "France24", "Al Jazeera", "The Guardian"].map((name) => ({ name })),
    hedging: { news: 0.57, social: 0.27, topic: "the spy claim" },
    social_only: ["n6", "n7"],
    narratives_in_news: ["n1", "n2", "n3", "n4", "n5"],
  },
};
const out = join(here, "..", "fixtures", "site_data.sample.json");
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(data));
console.log(`wrote ${out}: ${nodes.length} nodes, ${edges.length} edges, ${timeline.length} hours`);

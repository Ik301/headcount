/* Pure rules shared by the claim view, the story and their tests (web/app/tests). No imports, so node can run
 * them directly: `npm test`. */

/** Where an interval sits against a reference value. */
export type Versus = "above" | "below" | "same";

export function against(ci: readonly [number, number] | null | undefined, ref: number): Versus | null {
  if (!ci || ci.length < 2 || !isFinite(ci[0]) || !isFinite(ci[1]) || !isFinite(ref)) return null;
  return ci[0] > ref ? "above" : ci[1] < ref ? "below" : "same";
}

/** "above", "below" or "not clearly different from": the words that go before "the 5.0% baseline". */
export function versusWords(v: Versus | null): string | null {
  return v === "above" ? "above" : v === "below" ? "below" : v === "same" ? "not clearly different from" : null;
}

/* ---------- claim headline ---------- */

/** A narrative can carry the headline only with enough posts and a tight enough interval. */
export const HEADLINE_MIN_POSTS = 30; // src/config.py MIN_MATCHES
export const HEADLINE_MAX_CI_WIDTH = 0.25; // 25 percentage points

export interface HeadlineNarrative {
  id: string;
  label: string;
  posts?: number;
  share_of_matches: number;
  bot_post_share: number;
  bot_post_share_ci?: [number, number];
}

export type HeadlinePick<N extends HeadlineNarrative> =
  | { kind: "narrative"; n: N }
  | { kind: "overall"; share: number };

/** Posts in a narrative: the API's count, else its share of the matched posts. */
export function narrativePosts(n: HeadlineNarrative, matched: number): number {
  return n.posts ?? Math.round(n.share_of_matches * matched);
}

export function qualifies(n: HeadlineNarrative, matched: number): boolean {
  if (narrativePosts(n, matched) < HEADLINE_MIN_POSTS) return false;
  const ci = n.bot_post_share_ci;
  if (!ci) return false;
  return ci[1] - ci[0] <= HEADLINE_MAX_CI_WIDTH + 1e-9;
}

/** The most automated narrative among those with 30+ posts and an interval at most 25 points wide; when none
 *  qualifies (or none shows any automation), the overall share across every matched post. */
export function pickHeadline<N extends HeadlineNarrative>(narr: readonly N[], matched: number): HeadlinePick<N> {
  const ok = narr.filter((n) => qualifies(n, matched) && n.bot_post_share > 0);
  if (ok.length) return { kind: "narrative", n: ok.reduce((a, b) => (b.bot_post_share > a.bot_post_share ? b : a)) };
  return { kind: "overall", share: overallShare(narr) };
}

/** Share of all matched posts written by likely automated accounts: the narratives' shares, weighted by size. */
export function overallShare(narr: readonly HeadlineNarrative[]): number {
  const w = narr.reduce((s, n) => s + n.share_of_matches, 0);
  if (!w) return 0;
  return narr.reduce((s, n) => s + n.share_of_matches * n.bot_post_share, 0) / w;
}

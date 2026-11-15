// Run with `npm test` (node --test; node strips the types). Covers rehearsal bugs 3 and 12.
import { test } from "node:test";
import assert from "node:assert/strict";
import { against, overallShare, pickHeadline, versusWords } from "../src/lib/compare.ts";

// The flagship claim as the API returned it in rehearsal (claim b61ff2f2ead5).
const flagship = [
  { id: "n7", label: "Jokes and memes", posts: 240, share_of_matches: 0.5393, bot_post_share: 0, bot_post_share_ci: [0, 0] as [number, number] },
  { id: "n1", label: "Spy plot and national security", posts: 114, share_of_matches: 0.2562, bot_post_share: 0.0351, bot_post_share_ci: [0, 0.0804] as [number, number] },
  { id: "n2", label: "The affairs as personal misconduct", posts: 59, share_of_matches: 0.1326, bot_post_share: 0.0339, bot_post_share_ci: [0, 0.0877] as [number, number] },
  { id: "n3", label: "Trump and politics", posts: 6, share_of_matches: 0.0135, bot_post_share: 0.1667, bot_post_share_ci: [0, 0.5] as [number, number] },
];

test("headline skips a 6-post narrative with a 50-point interval", () => {
  const p = pickHeadline(flagship, 445);
  assert.equal(p.kind, "narrative");
  assert.equal(p.kind === "narrative" && p.n.id, "n1");
});

test("headline skips a narrative with 30+ posts but an interval wider than 25 points", () => {
  const wide = [
    { id: "a", label: "A", posts: 40, share_of_matches: 0.5, bot_post_share: 0.3, bot_post_share_ci: [0.1, 0.4] as [number, number] }, // 30 points
    { id: "b", label: "B", posts: 60, share_of_matches: 0.5, bot_post_share: 0.1, bot_post_share_ci: [0.05, 0.15] as [number, number] },
  ];
  const p = pickHeadline(wide, 100);
  assert.equal(p.kind === "narrative" && p.n.id, "b");
});

test("posts fall back to share of matches when the API omits them", () => {
  const n = [{ id: "a", label: "A", share_of_matches: 0.05, bot_post_share: 0.2, bot_post_share_ci: [0.1, 0.3] as [number, number] }];
  assert.equal(pickHeadline(n, 400).kind, "overall"); // 0.05 x 400 = 20 posts, below 30
  assert.equal(pickHeadline(n, 1000).kind, "narrative"); // 50 posts
});

test("no qualifying narrative: the overall share", () => {
  const small = flagship.map((n) => ({ ...n, posts: 10 }));
  const p = pickHeadline(small, 445);
  assert.equal(p.kind, "overall");
  assert.ok(p.kind === "overall" && Math.abs(p.share - overallShare(flagship)) < 1e-12);
  assert.ok(Math.abs(overallShare(flagship) - (0.2562 * 0.0351 + 0.1326 * 0.0339 + 0.0135 * 0.1667) / 0.9416) < 1e-9);
});

test("baseline wording follows the interval, never 'near'", () => {
  // jokes: 0.4% (0.3 to 0.6%) against the 5.0% baseline
  assert.equal(versusWords(against([0.003, 0.006], 0.05)), "below");
  assert.equal(versusWords(against([0.065, 0.117], 0.05)), "above");
  assert.equal(versusWords(against([0.019, 0.055], 0.05)), "not clearly different from");
  assert.equal(against(undefined, 0.05), null);
  assert.equal(versusWords(null), null);
});

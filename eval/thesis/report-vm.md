# Archetypes and the thesis test (M5)

Command: `python -m src.archetypes.pull_audience && python -m src.archetypes.build`
Version `v0-k7-202611150341`; run time 73 s. Platform: Bluesky only.

## Who counts

- Amplifier: a likely human (p_automated < 0.3) who liked, reposted or quoted a story post by a likely automated author (p_automated >= 0.7). **630 amplifiers.**
- Control pool: likely humans who engaged only with human-authored story posts: 15,184.
- Usable interactions: 72,277 of 380,164 (both ends scored and the actor profiled).
- What this measures is amplification, not belief: "more likely to amplify", never "more easily fooled".

## Matching

One control per amplifier, without replacement: same narrative, same 6-hour window, same reach bucket (log2 engagement) of the post engaged with, same activity quintile and follower power of ten.

| Level | Rule | Amplifiers matched |
|---|---|---|
| 0 | exact | 343 |
| 1 | reach bucket dropped | 202 |
| 2 | window widened to the day, reach dropped | 71 |
| - | unmatched, left out of lift | 14 |

Match rate 98%.

## Archetypes

1,232 accounts (amplifiers and controls together), 13 public-behavior features, standardized; k = 7 by silhouette (4: 0.117, 5: 0.123, 6: 0.128, 7: 0.135, 8: 0.128).
Base amplifier rate in the matched sample: 0.50, so a lift of 1 means "as likely as similar accounts".

| Archetype | Label | Size | Amplifiers | Lift (95% CI) | Typical |
|---|---|---|---|---|---|
| a1 | Mostly reposting others, rarely replying | 324 | 155 | 0.96 (0.85 to 1.06) | 75% reposts; 14% replies |
| a2 | Mostly replying in threads, rarely reposting | 311 | 172 | 1.11 (0.99 to 1.22) | 62% replies; 13% reposts |
| a3 | Whose posts get many likes, very prolific posters | 276 | 153 | 1.11 (0.99 to 1.23) | about 2.6 likes per post; 10.9 posts a day |
| a4 | Active in a narrow daily window, posting a lot this week | 142 | 59 | 0.83 (0.66 to 1.00) | hour spread 0.47 (1 = evenly around the clock); 96.2 posts a day recently |
| a5 | Mostly sharing links, whose posts get little engagement | 75 | 39 | 1.04 (0.80 to 1.28) | 71% of posts with links; 57% of posts with no engagement |
| a6 | Often quote-posting, rarely reposting | 61 | 14 | 0.46 (0.26 to 0.66) | 36% quote posts; 22% reposts |
| a7 | New accounts, with small followings | 43 | 24 | 1.12 (0.79 to 1.40) | median account age 41 days; 85 followers |

At least one archetype's lift interval excludes 1: some kinds of accounts are measurably more (or less) likely to amplify likely automated posts than matched accounts that saw the same story.

Adjusted contrasts (logistic regression below, each archetype vs the largest, "Mostly reposting others, rarely replying"; p adjusted for 6 comparisons, Bonferroni):

| Archetype | Odds ratio vs reference (95% CI) | p | adjusted p |
|---|---|---|---|
| a2 Mostly replying in threads, rarely reposting | 1.28 (0.93 to 1.76) | 0.128 | 0.771 |
| a3 Whose posts get many likes, very prolific posters | 1.45 (0.97 to 2.16) | 0.0709 | 0.425 |
| a4 Active in a narrow daily window, posting a lot this week | 0.84 (0.53 to 1.35) | 0.479 | 1 |
| a5 Mostly sharing links, whose posts get little engagement | 1.15 (0.68 to 1.95) | 0.607 | 1 |
| a6 Often quote-posting, rarely reposting | 0.32 (0.17 to 0.63) | 0.000821 | 0.00492 |
| a7 New accounts, with small followings | 1.24 (0.61 to 2.54) | 0.553 | 1 |

## Logistic regression

`amplified_bot ~ archetype + log(followers) + posts_per_day + narrative + hour`, Newton-Raphson, standard errors from the
inverse Hessian, on the matched sample.

| Term | Coefficient | SE | z | p |
|---|---|---|---|---|
| intercept | +0.598 | 0.368 | +1.62 | 0.104 |
| archetype a2 (vs a1) | +0.247 | 0.163 | +1.52 | 0.128 |
| archetype a3 (vs a1) | +0.369 | 0.204 | +1.81 | 0.0709 |
| archetype a4 (vs a1) | -0.171 | 0.241 | -0.71 | 0.479 |
| archetype a5 (vs a1) | +0.139 | 0.270 | +0.51 | 0.607 |
| archetype a6 (vs a1) | -1.130 | 0.338 | -3.35 | 0.000821 |
| archetype a7 (vs a1) | +0.216 | 0.365 | +0.59 | 0.553 |
| log(followers) | -0.076 | 0.053 | -1.44 | 0.15 |
| log(1 + posts per day) | +0.023 | 0.068 | +0.34 | 0.735 |
| narrative n1 (vs n0) | -0.258 | 0.227 | -1.13 | 0.257 |
| narrative n2 (vs n0) | +0.012 | 0.310 | +0.04 | 0.969 |
| narrative n3 (vs n0) | -0.047 | 0.387 | -0.12 | 0.903 |
| narrative n4 (vs n0) | -0.113 | 0.281 | -0.40 | 0.687 |
| narrative n5 (vs n0) | -0.056 | 0.259 | -0.21 | 0.83 |
| narrative n6 (vs n0) | -0.317 | 0.251 | -1.26 | 0.207 |
| narrative n7 (vs n0) | -0.344 | 0.198 | -1.74 | 0.082 |
| hour (sin) | +0.358 | 0.093 | +3.85 | 0.00012 |
| hour (cos) | -0.014 | 0.090 | -0.16 | 0.874 |

## Caveats

- The hour terms describe the post, not the person: amplifiers and controls share a 6-hour window, but inside it likely automated posts go out at different hours than human posts. A significant hour term means automated posts are timed differently, not that some people amplify at certain hours.
- Likes have timestamps; reposts don't (getRepostedBy), so a repost's time is the post's time.
- Small sample: only 630 likely humans engaged with a likely automated post, because those posts get little engagement. Intervals are wide; a lift has to be large to show.
- One page (up to 100) of likers, reposters and quoters per post, so very popular posts are undersampled.
- Features are public behavior only; no demographic or sensitive traits. Example accounts on cards are public ones only.

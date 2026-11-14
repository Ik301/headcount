# Archetypes and the thesis test (M5)

Command: `python -m src.archetypes.pull_audience && python -m src.archetypes.build`
Version `v0-k4-202611142255`; run time 47 s. Platform: Bluesky only.

## Who counts

- Amplifier: a likely human (p_automated < 0.3) who liked, reposted or quoted a story post by a likely automated author (p_automated >= 0.7). **642 amplifiers.**
- Control pool: likely humans who engaged only with human-authored story posts: 15,170.
- Usable interactions: 72,277 of 380,164 (both ends scored and the actor profiled).
- What this measures is amplification, not belief: "more likely to amplify", never "more easily fooled".

## Matching

One control per amplifier, without replacement: same narrative, same 6-hour window, same reach bucket (log2 engagement) of the post engaged with, same activity quintile and follower power of ten.

| Level | Rule | Amplifiers matched |
|---|---|---|
| 0 | exact | 346 |
| 1 | reach bucket dropped | 207 |
| 2 | window widened to the day, reach dropped | 75 |
| - | unmatched, left out of lift | 14 |

Match rate 98%.

## Archetypes

1,256 accounts (amplifiers and controls together), 13 public-behavior features, standardized; k = 4 by silhouette (4: 0.140, 5: 0.121, 6: 0.130, 7: 0.138, 8: 0.135).
Base amplifier rate in the matched sample: 0.50, so a lift of 1 means "as likely as similar accounts".

| Archetype | Label | Size | Amplifiers | Lift (95% CI) | Typical |
|---|---|---|---|---|---|
| a1 | Posting little this week, occasional posters | 538 | 263 | 0.98 (0.89 to 1.06) | 3.7 posts a day recently; 0.8 posts a day |
| a2 | Whose posts get many likes, very prolific posters | 360 | 195 | 1.08 (0.98 to 1.18) | about 2.4 likes per post; 10.0 posts a day |
| a3 | Mostly reposting others, rarely replying | 294 | 134 | 0.91 (0.80 to 1.02) | 82% reposts; 6% replies |
| a4 | New accounts, with small followings | 64 | 36 | 1.12 (0.91 to 1.38) | median account age 73 days; 94 followers |

**Null result:** no archetype's interval excludes 1. After matching, no kind of account stands out as more likely to amplify likely automated posts than similar accounts that saw the same story.

## Logistic regression

`amplified_bot ~ archetype + log(followers) + posts_per_day + narrative + hour`, Newton-Raphson, standard errors from the
inverse Hessian, on the matched sample.

| Term | Coefficient | SE | z | p |
|---|---|---|---|---|
| intercept | +0.786 | 0.347 | +2.27 | 0.0234 |
| archetype a2 (vs a1) | +0.458 | 0.184 | +2.48 | 0.0131 |
| archetype a3 (vs a1) | +0.061 | 0.177 | +0.35 | 0.729 |
| archetype a4 (vs a1) | +0.239 | 0.297 | +0.81 | 0.42 |
| log(followers) | -0.103 | 0.053 | -1.94 | 0.052 |
| log(1 + posts per day) | -0.041 | 0.067 | -0.61 | 0.541 |
| narrative n1 (vs n0) | -0.229 | 0.224 | -1.02 | 0.307 |
| narrative n2 (vs n0) | -0.008 | 0.300 | -0.03 | 0.978 |
| narrative n3 (vs n0) | -0.034 | 0.384 | -0.09 | 0.93 |
| narrative n4 (vs n0) | -0.091 | 0.269 | -0.34 | 0.734 |
| narrative n5 (vs n0) | -0.072 | 0.251 | -0.29 | 0.775 |
| narrative n6 (vs n0) | -0.328 | 0.248 | -1.33 | 0.185 |
| narrative n7 (vs n0) | -0.298 | 0.193 | -1.54 | 0.122 |
| hour (sin) | +0.388 | 0.091 | +4.27 | 1.98e-05 |
| hour (cos) | -0.026 | 0.088 | -0.30 | 0.762 |

## Caveats

- The hour terms describe the post, not the person: amplifiers and controls share a 6-hour window, but inside it likely automated posts go out at different hours than human posts. A significant hour term means automated posts are timed differently, not that some people amplify at certain hours.
- Likes have timestamps; reposts don't (getRepostedBy), so a repost's time is the post's time.
- Small sample: only 642 likely humans engaged with a likely automated post, because those posts get little engagement. Intervals are wide; a lift has to be large to show.
- One page (up to 100) of likers, reposters and quoters per post, so very popular posts are undersampled.
- Features are public behavior only; no demographic or sensitive traits. Example accounts on cards are public ones only.

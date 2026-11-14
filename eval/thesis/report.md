# Archetypes and the thesis test (M5)

Command: `python -m src.archetypes.pull_audience && python -m src.archetypes.build`
Version `v0-k4-202611142218`; run time 17 s. Platform: Bluesky only.

## Who counts

- Amplifier: a likely human (p_automated < 0.3) who liked, reposted or quoted a story post by a likely automated author (p_automated >= 0.7). **602 amplifiers.**
- Control pool: likely humans who engaged only with human-authored story posts: 15,158.
- Usable interactions: 72,122 of 380,129 (both ends scored and the actor profiled).
- What this measures is amplification, not belief: "more likely to amplify", never "more easily fooled".

## Matching

One control per amplifier, without replacement: same narrative, same 6-hour window, same reach bucket (log2 engagement) of the post engaged with, same activity quintile and follower power of ten.

| Level | Rule | Amplifiers matched |
|---|---|---|
| 0 | exact | 515 |
| 1 | reach bucket dropped | 60 |
| 2 | window widened to the day, reach dropped | 27 |
| - | unmatched, left out of lift | 0 |

Match rate 100%. **Narratives were not available yet** (`post_narrative.parquet` from H3), so every post counts as one narrative; rerun once H3 lands and matching gains the narrative key.

## Archetypes

1,204 accounts (amplifiers and controls together), 13 public-behavior features, standardized; k = 4 by silhouette (4: 0.139, 5: 0.129, 6: 0.136, 7: 0.137, 8: 0.136).
Base amplifier rate in the matched sample: 0.50, so a lift of 1 means "as likely as similar accounts".

| Archetype | Label | Size | Amplifiers | Lift (95% CI) | Typical |
|---|---|---|---|---|---|
| a1 | Posting little this week, occasional posters | 460 | 240 | 1.04 (0.96 to 1.13) | 2.6 posts a day recently; 0.6 posts a day |
| a2 | Very prolific posters, whose posts get many likes | 372 | 188 | 1.01 (0.91 to 1.11) | 8.7 posts a day; about 2.3 likes per post |
| a3 | Mostly reposting others, rarely replying | 314 | 141 | 0.90 (0.80 to 1.01) | 84% reposts; 6% replies |
| a4 | New accounts, with small followings | 58 | 33 | 1.14 (0.90 to 1.38) | median account age 40 days; 72 followers |

**Null result:** no archetype's interval excludes 1. After matching, no kind of account stands out as more likely to amplify likely automated posts than similar accounts that saw the same story.

## Logistic regression

`amplified_bot ~ archetype + log(followers) + posts_per_day + narrative + hour`, Newton-Raphson, standard errors from the
inverse Hessian, on the matched sample.

| Term | Coefficient | SE | z | p |
|---|---|---|---|---|
| intercept | +0.206 | 0.292 | +0.70 | 0.482 |
| archetype a2 (vs a1) | -0.025 | 0.184 | -0.13 | 0.893 |
| archetype a3 (vs a1) | -0.233 | 0.165 | -1.41 | 0.158 |
| archetype a4 (vs a1) | +0.166 | 0.309 | +0.54 | 0.591 |
| log(followers) | -0.020 | 0.051 | -0.38 | 0.701 |
| log(1 + posts per day) | -0.004 | 0.069 | -0.05 | 0.957 |
| hour (sin) | +0.247 | 0.082 | +3.01 | 0.0026 |
| hour (cos) | +0.128 | 0.083 | +1.54 | 0.123 |

## Caveats

- The hour terms describe the post, not the person: amplifiers and controls share a 6-hour window, but inside it likely automated posts go out at different hours than human posts. A significant hour term means automated posts are timed differently, not that some people amplify at certain hours.
- Likes have timestamps; reposts don't (getRepostedBy), so a repost's time is the post's time.
- Small sample: only 602 likely humans engaged with a likely automated post, because those posts get little engagement. Intervals are wide; a lift has to be large to show.
- One page (up to 100) of likers, reposters and quoters per post, so very popular posts are undersampled.
- Features are public behavior only; no demographic or sensitive traits. Example accounts on cards are public ones only.

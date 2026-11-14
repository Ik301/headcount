# Likely automated share per narrative (M4)

Command: `python -m src.bots.narrative_shares` (post_narrative: `data/processed/narratives/post_narrative.parquet`)
Denominator: unbridged accounts (bridged fediverse accounts are in with_bridged). Intervals: shared bootstrap over accounts (1,000 resamples, seed 42).

Story baseline: 5.0% of posts (3.5% to 6.5%) and 1.5% of accounts are likely automated (p >= 0.5); expected share 8.6%.

| Narrative | Posts | Likely automated posts (95% CI) | x baseline | Accounts | Expected | @0.3 | @0.5 | @0.7 | @0.9 |
|---|---|---|---|---|---|---|---|---|---|
| n7 Jokes and memes | 10,421 | 0.4% (0.3% to 0.7%) | 0.09 | 0.4% | 1.4% | 0.5% | 0.4% | 0.4% | 0.4% |
| n1 Spy plot and national security | 8,693 | 7.0% (5.1% to 9.6%) | 1.41 | 3.8% | 12.3% | 11.4% | 7.0% | 5.7% | 5.7% |
| n0 No narrative | 6,291 | 4.9% (1.7% to 9.5%) | 0.99 | 1.5% | 7.5% | 6.2% | 4.9% | 4.7% | 4.6% |
| n4 Board, resignation and succession | 5,129 | 8.9% (6.5% to 11.8%) | 1.8 | 5.8% | 14.9% | 13.9% | 8.9% | 7.5% | 7.3% |
| n2 The affairs as personal misconduct | 4,205 | 6.8% (4.3% to 9.8%) | 1.36 | 3.0% | 10.5% | 9.1% | 6.8% | 5.9% | 5.8% |
| n3 Trump and politics | 3,732 | 3.6% (2.1% to 5.1%) | 0.72 | 2.4% | 7.1% | 6.5% | 3.6% | 2.5% | 2.5% |
| n5 Stock, market and lawsuits | 3,262 | 7.8% (5.2% to 10.5%) | 1.57 | 5.0% | 13.6% | 13.1% | 7.8% | 6.0% | 5.7% |
| n6 Defending Huang | 1,457 | 3.4% (1.9% to 5.5%) | 0.69 | 2.6% | 6.4% | 6.4% | 3.4% | 3.3% | 3.2% |

## Kill test 3

Most automated narrative's share at least twice the least automated one's, at every cutoff (n0, no narrative, excluded):

- @0.3: n4 vs n7, ratio 26.26 -> pass
- @0.5: n4 vs n7, ratio 19.89 -> pass
- @0.7: n4 vs n7, ratio 17.42 -> pass
- @0.9: n4 vs n7, ratio 16.91 -> pass

**Pass.**

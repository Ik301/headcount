# Likely automated share per narrative (M4)

Command: `python -m src.bots.narrative_shares` (post_narrative: `data/processed/narratives/post_narrative.parquet`)
Denominator: unbridged accounts (bridged fediverse accounts are in with_bridged). Intervals: shared bootstrap over accounts (1,000 resamples, seed 42).

Story baseline: 4.5% of posts (3.1% to 6.2%) and 1.2% of accounts are likely automated (p >= 0.5); expected share 6.7%.

| Narrative | Posts | Likely automated posts (95% CI) | x baseline | Accounts | Expected | @0.3 | @0.5 | @0.7 | @0.9 |
|---|---|---|---|---|---|---|---|---|---|
| n7 Jokes and memes | 10,421 | 0.4% (0.2% to 0.6%) | 0.1 | 0.4% | 0.9% | 0.5% | 0.4% | 0.4% | 0.4% |
| n1 Spy plot and national security | 8,693 | 6.3% (4.3% to 8.9%) | 1.41 | 3.2% | 9.7% | 8.1% | 6.3% | 5.5% | 5.5% |
| n0 No narrative | 6,291 | 4.7% (1.5% to 8.8%) | 1.04 | 1.3% | 6.7% | 5.4% | 4.7% | 4.6% | 4.6% |
| n4 Board, resignation and succession | 5,129 | 7.7% (5.1% to 11.0%) | 1.72 | 4.8% | 11.3% | 9.1% | 7.7% | 6.8% | 6.7% |
| n2 The affairs as personal misconduct | 4,205 | 5.5% (3.4% to 8.2%) | 1.23 | 2.5% | 8.3% | 6.9% | 5.5% | 5.3% | 5.3% |
| n3 Trump and politics | 3,732 | 3.3% (1.7% to 5.6%) | 0.73 | 1.9% | 5.2% | 4.6% | 3.3% | 2.4% | 2.3% |
| n5 Stock, market and lawsuits | 3,262 | 7.2% (4.1% to 10.5%) | 1.6 | 4.2% | 10.4% | 8.7% | 7.2% | 5.7% | 5.6% |
| n6 Defending Huang | 1,457 | 4.8% (2.0% to 8.7%) | 1.06 | 2.5% | 5.2% | 5.3% | 4.8% | 3.1% | 2.9% |

## Kill test 3

Most automated narrative's share at least twice the least automated one's, at every cutoff (n0, no narrative, excluded):

- @0.3: n4 vs n7, ratio 18.18 -> pass
- @0.5: n4 vs n7, ratio 18.0 -> pass
- @0.7: n4 vs n7, ratio 15.77 -> pass
- @0.9: n4 vs n7, ratio 15.47 -> pass

**Pass.**

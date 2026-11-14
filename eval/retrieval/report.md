# Claim retrieval evaluation (M6)

Command: `python -m src.evaluation.retrieval --claims eval/retrieval/claims.csv --report eval/retrieval/report.md`
Retriever: `src.retrieval.corpus.search_claim` (bge-small-en-v1.5 with the query prefix, cosine, top 300) over local bge-small index (data/processed/eval_retrieval).
Corpus: 40,335 unique story texts (Hermes's normalization). Run time 11 s.

## The claim set

50 claims written from reading the story posts (`eval/retrieval/claims.csv`), not from the narrative labels. Each has a regex rule; its true matches are the unique texts the rule matches (median 135, range 8 to 3051).
Rule check: 4 random matches per claim were read by hand (200 in all); **163 of 200 (82%) make the claim**. Six loose
rules were tightened or replaced after a first pass. Rules miss paraphrases, so a retriever that finds a true
paraphrase is scored as wrong; treat precision as a lower bound.

Gold texts are rebuilt from the rules on each run and kept in `data/private/` (they come from private accounts).
The retriever's builder must not edit this file; corrections go through COMMS (build spec).

## Recall@k (capped: hits / min(k, matches)), all 50 claims

| Floor | @10 | @20 | @50 | precision@20 | mean matched (of 300) |
|---|---|---|---|---|---|
| none (ranking only) | 0.553 | 0.506 | 0.458 | | |
| 0.50 | 0.553 | 0.506 | 0.458 | 0.496 | 300 |
| 0.55 | 0.553 | 0.506 | 0.458 | 0.496 | 300 |
| 0.60 | 0.553 | 0.506 | 0.458 | 0.496 | 300 |
| 0.65 | 0.553 | 0.506 | 0.458 | 0.496 | 294 |
| 0.70 | 0.547 | 0.500 | 0.450 | 0.490 | 250 |
| 0.75 | 0.515 | 0.438 | 0.350 | 0.428 | 149 |
| 0.80 | 0.320 | 0.278 | 0.217 | 0.271 | 62 |
| 0.85 | 0.206 | 0.175 | 0.131 | 0.173 | 29 |

## Choosing the similarity floor

The API reports shares over the matched set (top 300 above the floor), so the floor trades how much of the claim
is found against how much unrelated text gets counted. Mean over claims:

| Floor | set precision | set recall | F1 |
|---|---|---|---|
| 0.50 | 0.247 | 0.459 | 0.280 |
| 0.55 | 0.247 | 0.459 | 0.280 |
| 0.60 | 0.247 | 0.459 | 0.280 |
| 0.65 | 0.253 | 0.455 | 0.279 |
| 0.70 | 0.305 | 0.409 | 0.274 |
| 0.75 | 0.408 | 0.276 | 0.235 |
| 0.80 | 0.451 | 0.158 | 0.172 |
| 0.85 | 0.289 | 0.077 | 0.095 |

**Recommended floor: 0.70**: the highest floor whose mean F1 is within 0.01 of the best (0.280); F1 is nearly flat from 0.50 to 0.70, so the tie goes to precision. bge-small similarities sit high on this corpus (every post is about Huang), so floors under 0.65 filter almost nothing. `src/config.py` has `SIMILARITY_FLOOR = 0.70`; changing it is a `[contract]` pull request citing this report.

## Kill test 4

recall@20 of at least 0.6 on the first 20 claims: **0.577 at floor 0.70** (0.577 with no floor) -> **fail**. All 50 claims: 0.500.

Latency: median 8 ms per claim on a laptop CPU (embedding plus search).

## Why it misses, and a fix for H5 to consider

Broad claims (resignation, interim CEO, stock drop, board probe) retrieve well. Specific ones fail (blackmail, payout, Musk's job offer, shorting the stock): every post is about Jensen Huang, so the shared topic dominates the cosine and the specific words don't move the ranking. Adding a keyword signal fixes most of it:

| Retriever | recall@20, first 20 claims | recall@20, all 50 |
|---|---|---|
| embedding cosine (current `search_claim`) | 0.577 | 0.506 |
| embedding, mean-centered | 0.558 | 0.486 |
| TF-IDF only (word 1-2 grams) | 0.695 | 0.576 |
| hybrid 0.7 embedding + 0.3 TF-IDF | 0.755 | 0.636 |
| hybrid 0.5 embedding + 0.5 TF-IDF | 0.785 | 0.642 |
| hybrid 0.3 embedding + 0.7 TF-IDF | 0.747 | 0.616 |

Caveats: the gold sets come from keyword rules, which favors TF-IDF, so part of this gain is the referee's own bias; three weights were tried on these same 50 claims, so expect the best one to do a little worse on new claims. The 0.5/0.5 hybrid is still the recommendation, and with it kill test 4 would pass. A second, independently written claim set would settle how much of the gain is real. This is a suggestion for H5 (Hermes owns `src/retrieval/`); the claim set does not change.

## Per claim (floor 0.70)

| Claim | Matches | recall@20 | matched set precision |
|---|---|---|---|
| c01 Jensen Huang had an affair with a Chinese spy | 2675 | 0.40 | 0.30 |
| c02 Was Jensen Huang's mistress a Chinese spy? | 133 | 0.15 | 0.07 |
| c03 Jensen Huang fell for a honey trap | 678 | 0.80 | 0.28 |
| c04 Jensen Huang resigned as CEO of Nvidia | 3051 | 0.95 | 0.95 |
| c05 Colette Kress was named interim CEO of Nvidia | 813 | 1.00 | 0.99 |
| c06 Nvidia's board opened an investigation into Huang | 765 | 0.85 | 0.72 |
| c07 Nvidia stock fell after the Huang news | 900 | 0.95 | 0.84 |
| c08 Huang's divorce could cost him billions | 186 | 0.85 | 0.30 |
| c09 Trump knew about the spy relationship and did nothing | 440 | 0.80 | 0.62 |
| c10 Trump defended Jensen Huang | 232 | 0.35 | 0.23 |
| c11 The FBI is investigating Jensen Huang | 388 | 0.10 | 0.08 |
| c12 Jensen Huang will testify before Congress | 324 | 1.00 | 0.35 |
| c13 Shareholders are suing Nvidia over the affair | 213 | 0.90 | 0.42 |
| c14 Nvidia was smuggling chips to China | 330 | 0.50 | 0.27 |
| c15 The Wall Street Journal reported Huang would be ousted | 261 | 0.20 | 0.18 |
| c16 Huang also had an affair with an Nvidia employee | 1196 | 0.70 | 0.45 |
| c17 Huang admitted the affair in an email to employees | 62 | 0.10 | 0.06 |
| c18 Jensen Huang apologized to his wife and family | 50 | 0.25 | 0.08 |
| c19 Jensen Huang didn't know she was a spy | 122 | 0.10 | 0.08 |
| c20 China denies the spy allegations against Huang | 92 | 0.60 | 0.23 |
| c21 The spy story is a smear campaign against Huang | 61 | 0.60 | 0.13 |
| c22 Bots are defending Jensen Huang online | 8 | 0.12 | 0.02 |
| c23 Elon Musk offered Jensen Huang a job | 19 | 0.05 | 0.04 |
| c24 Elon Musk and other tech leaders defended Huang | 60 | 0.55 | 0.13 |
| c25 Nvidia employees petitioned to bring Huang back | 52 | 0.80 | 0.12 |
| c26 Huang's leather jacket is now a joke | 648 | 0.90 | 0.79 |
| c27 Jensen Huang will start a new company | 9 | 0.11 | 0.01 |
| c28 Jensen Huang could return as Nvidia CEO | 117 | 0.30 | 0.10 |
| c29 Jensen Huang's net worth dropped by billions | 8 | 0.62 | 0.02 |
| c30 AMD and Broadcom gained as Nvidia fell | 30 | 0.45 | 0.06 |
| c31 Nvidia lost hundreds of billions in market value | 124 | 0.90 | 0.30 |
| c32 Huang flew to Beijing on Air Force One | 83 | 0.80 | 0.55 |
| c33 The scandal hangs over the Trump-Xi trade talks | 32 | 0.20 | 0.06 |
| c34 Huang's affair is a national security threat | 842 | 0.55 | 0.26 |
| c35 The spy got access to Nvidia's secrets | 118 | 0.20 | 0.07 |
| c36 Jensen Huang was being blackmailed | 118 | 0.00 | 0.02 |
| c37 Megaspeed was at the center of the chip smuggling case | 561 | 1.00 | 0.99 |
| c38 Nvidia named Harvey Jones its first independent chair | 69 | 0.95 | 0.74 |
| c39 Trump was briefed on the spy before the Beijing trip | 138 | 0.80 | 0.35 |
| c40 The Huang scandal will hurt AI stocks | 177 | 0.10 | 0.08 |
| c41 Jensen Huang was fired | 548 | 0.45 | 0.12 |
| c42 Jensen Huang abused his power and mistreated people | 62 | 0.05 | 0.02 |
| c43 Rubio and Vance knew about the Huang spy intelligence | 198 | 0.95 | 0.72 |
| c44 Huang will get a huge payout for leaving | 16 | 0.00 | 0.01 |
| c45 There should be a movie about the Huang scandal | 207 | 0.50 | 0.43 |
| c46 Investors should short or buy the dip in Nvidia | 21 | 0.00 | 0.02 |
| c47 The spy was working for the CCP's Ministry of State Security | 198 | 0.20 | 0.80 |
| c48 Nvidia shares bounced back after the drop | 30 | 0.40 | 0.07 |
| c49 The New York Times reported the spy relationship | 688 | 0.75 | 0.71 |
| c50 The Washington Post reported on the Nvidia board probe | 34 | 0.15 | 0.03 |

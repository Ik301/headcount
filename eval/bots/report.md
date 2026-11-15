# Bot model report (M2)

Command: `python -m src.bots.train --raw data/raw --out data/processed/artifacts --report eval/bots/report.md`
Model: `v1-hgb-202611150141` (chosen: hgb_both, by out-of-fold recall@100). Run time 87 s on a laptop CPU.

## Data

- Accounts: 20,451 story authors with profiles; 20,451 with a history pull (last 50 items).
- Labeled bots (self-applied `bot` label): 288. Bridged (fediverse) accounts: 729, of which 58 are labeled bots.
- Unlabeled accounts are treated as unlabeled, not as humans (positive-unlabeled). Some undisclosed automation is in that set, so
  precision against labels understates real precision and recall is measured only on the disclosed kind of bot.

## Recall@k on held-out labeled bots

Out-of-fold scores (5-fold stratified, seed 42): each labeled bot is scored by a model that never saw it,
then ranked among all accounts. Same definition as the README's posts-per-day baseline.

| Scorer | @50 | @100 | @200 | @500 |
|---|---|---|---|---|
| lifetime posts per day (baseline) | 0.028 | 0.045 | 0.083 | 0.142 |
| logistic regression, behavior + coordination | 0.118 | 0.188 | 0.274 | 0.451 |
| gradient boosting, behavior + coordination | 0.170 | 0.281 | 0.372 | 0.573 |
| ceiling (k / labeled bots) | 0.174 | 0.347 | 0.694 | 1.000 |

README protocol, literally: hold out 20% of labeled bots (about 58), rank them among every account not used as a
positive in training (all unlabeled accounts plus the held-out bots), mean over the 5 folds. The ceiling here is 1.0.

| Scorer | @50 | @100 | @200 | @500 |
|---|---|---|---|---|
| lifetime posts per day (baseline) | 0.028 | 0.045 | 0.083 | 0.142 |
| hgb, both, one split (seed 42) | 0.305 | 0.358 | 0.458 | 0.625 |
| hgb, both, mean ± sd over 5 splits | 0.290 ± 0.006 | 0.358 ± 0.015 | 0.452 ± 0.012 | 0.625 ± 0.009 |

One split is noisy: the same model and data gave 0.27 to 0.33 at @100 depending on the split, so the mean is the
number to quote.

### Bots of operators the model never saw

The harder test: every account of an operator (208 operator groups among the labeled bots, by handle domain; the largest is one mirror network of 47 accounts) is held out together, so the model can't recognize a network
it trained on. This is closer to finding a new, undisclosed operation.

| Scorer | @50 | @100 | @200 | @500 |
|---|---|---|---|---|
| hgb, both, operator-grouped, mean ± sd over 3 splits | 0.180 ± 0.027 | 0.244 ± 0.023 | 0.358 ± 0.013 | 0.555 ± 0.020 |

Precision@k against labels (out-of-fold, chosen model): @50 0.98, @100 0.81, @200 0.54, @500 0.33.

Excluding bridged accounts: recall@k @50 0.143, @100 0.191, @200 0.296, @500 0.517 (230 labeled bots).

## Ablation (Arlequin: content and connectivity)

Gradient boosting, out-of-fold, same folds. Behavior = profile, timing and content features of each account alone;
coordination = shared traces with other accounts (same link or repost within 60 s, near-identical text), TF-IDF cosine.

| Features | @50 | @100 | @200 | @500 |
|---|---|---|---|---|
| behavior only | 0.174 | 0.260 | 0.372 | 0.556 |
| coordination only | 0.017 | 0.031 | 0.062 | 0.135 |
| both | 0.170 | 0.281 | 0.372 | 0.573 |

560 accounts sit in a coordination cluster; 24 of them are labeled bots (4.3%, against 1.4% overall).

## Kill test 1

The test reads the README holdout (Hermes, COMMS Sat 17:10), as the mean over 5 splits: recall@100 = 0.358 ± 0.015 against the bar of 0.3: **pass** (posts-per-day baseline 0.045). On operators it never saw: 0.244.

## Score scale

p_automated = P(labeled | x) / c with c = 0.262, the mean out-of-fold score of labeled bots (Elkan and Noto, 2008).
This assumes labeled bots are a random sample of all bots; they are mostly disclosed news and trend bots, so treat the
scale as approximate. Share of all accounts at or above each cutoff (out-of-fold): 0.3 -> 1.9%, 0.5 -> 1.3%, 0.7 -> 1.0%, 0.9 -> 0.8%.

## Features

Used (42): `log_followers`, `log_follows`, `follow_ratio_log`, `log_posts_count`, `age_days_log`, `lifetime_ppd_log`, `has_avatar`, `has_banner`, `has_display_name`, `bio_len`, `has_pinned`, `index_gap_log`, `hist_n`, `hist_rate_log`, `gap_cv`, `gap_median_log`, `burst_share`, `hour_entropy`, `minute_entropy`, `on_minute_share`, `repost_share`, `reply_share`, `quote_share`, `link_share`, `distinct_domains`, `top_domain_share`, `self_dup_rate`, `prefix_dup_rate`, `text_len_mean`, `text_len_cv`, `hashtag_rate`, `zero_engagement_share`, `likes_mean_log`, `n_langs`, `repost_top_author_share`, `story_n_log`, `story_dup_rate`, `story_link_share`, `story_share_of_history`, `coord_cluster_size_log`, `coord_traces_log`, `coord_max_sim`.

Never used: the self-applied label, bio words, handle text, the bridged label.

Largest linear-surrogate weights (standardized; the surrogate also writes each account's reasons):

| Feature | Weight |
|---|---|
| `quote_share` | -0.78 |
| `index_gap_log` | +0.63 |
| `hist_rate_log` | +0.60 |
| `log_posts_count` | -0.46 |
| `repost_share` | -0.42 |
| `bio_len` | +0.35 |
| `text_len_mean` | +0.33 |
| `log_follows` | -0.32 |
| `minute_entropy` | -0.30 |
| `lifetime_ppd_log` | +0.29 |
| `zero_engagement_share` | +0.26 |
| `follow_ratio_log` | -0.24 |

## Hand check

The 50 highest-scored unlabeled accounts (out-of-fold), each read by hand from its bio and 3 to 6 recent posts.
The candidate list with handles stays local (`data/private/handcheck_candidates.jsonl`); `eval/bots/handcheck.csv`
holds the verdicts with no account named. The list is regenerated on every training run; verdicts below were
made on the run that produced this report's model, and need redoing if the top 50 changes.

Precision on this sample: **46 of 50 (92%) automated or likely automated**; the other 4 are unclear or mixed (1 of them probably a person posting by hand).
So the labels miss most automation, and the score finds it.

| Verdict | Accounts |
|---|---|
| likely automated: news or RSS feed | 24 |
| likely automated: scheduled digest or aggregator | 10 |
| automated: says so in its bio, no bot label | 6 |
| automated: market or data feed | 5 |
| unclear: advice posts, possibly generated | 1 |
| unclear: posts only video links | 1 |
| automated: unofficial mirror of another outlet | 1 |
| mixed: link feed plus some personal posts | 1 |
| unclear: satire account, likely written by a person | 1 |

What this does and doesn't show: almost all of these are news, RSS, market-data and digest feeds, the same kind as
the labeled bots. The model finds *undisclosed feeds* well. It isn't yet evidence that it finds accounts pushing a
narrative; that question is M3's coordination clusters and M4's per-narrative shares.

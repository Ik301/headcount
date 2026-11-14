# Bot model report (M2)

Command: `python -m src.bots.train --raw data/raw --out data/processed/artifacts --report eval/bots/report.md`
Model: `v1-hgb-202611142157` (chosen: hgb_both, by out-of-fold recall@100). Run time 71 s on a laptop CPU.

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
| logistic regression, behavior + coordination | 0.073 | 0.153 | 0.240 | 0.413 |
| gradient boosting, behavior + coordination | 0.153 | 0.243 | 0.351 | 0.521 |
| ceiling (k / labeled bots) | 0.174 | 0.347 | 0.694 | 1.000 |

README protocol, literally: hold out 20% of labeled bots (about 58), rank them among every account not used as a
positive in training (all unlabeled accounts plus the held-out bots), mean over the 5 folds. The ceiling here is 1.0.

| Scorer | @50 | @100 | @200 | @500 |
|---|---|---|---|---|
| lifetime posts per day (baseline) | 0.028 | 0.045 | 0.083 | 0.142 |
| hgb, both | 0.260 | 0.333 | 0.406 | 0.576 |

Precision@k against labels (out-of-fold, chosen model): @50 0.88, @100 0.70, @200 0.51, @500 0.30.

Excluding bridged accounts: recall@k @50 0.113, @100 0.165, @200 0.270, @500 0.470 (230 labeled bots).

## Ablation (Arlequin: content and connectivity)

Gradient boosting, out-of-fold, same folds. Behavior = profile, timing and content features of each account alone;
coordination = shared traces with other accounts (same link or repost within 60 s, near-identical text), TF-IDF cosine.

| Features | @50 | @100 | @200 | @500 |
|---|---|---|---|---|
| behavior only | 0.153 | 0.236 | 0.354 | 0.514 |
| coordination only | 0.017 | 0.031 | 0.062 | 0.135 |
| both | 0.153 | 0.243 | 0.351 | 0.521 |

560 accounts sit in a coordination cluster; 24 of them are labeled bots (4.3%, against 1.4% overall).

## Kill test 1

recall@100 = 0.243 against the bar of 0.3: **fail** (baseline 0.045; ceiling 0.347).

## Score scale

p_automated = P(labeled | x) / c with c = 0.220, the mean out-of-fold score of labeled bots (Elkan and Noto, 2008).
This assumes labeled bots are a random sample of all bots; they are mostly disclosed news and trend bots, so treat the
scale as approximate. Share of all accounts at or above each cutoff (out-of-fold): 0.3 -> 2.3%, 0.5 -> 1.5%, 0.7 -> 1.2%, 0.9 -> 0.9%.

## Features

Used (41): `log_followers`, `log_follows`, `follow_ratio_log`, `log_posts_count`, `age_days_log`, `lifetime_ppd_log`, `has_avatar`, `has_banner`, `has_display_name`, `bio_len`, `has_pinned`, `hist_n`, `hist_rate_log`, `gap_cv`, `gap_median_log`, `burst_share`, `hour_entropy`, `minute_entropy`, `on_minute_share`, `repost_share`, `reply_share`, `quote_share`, `link_share`, `distinct_domains`, `top_domain_share`, `self_dup_rate`, `prefix_dup_rate`, `text_len_mean`, `text_len_cv`, `hashtag_rate`, `zero_engagement_share`, `likes_mean_log`, `n_langs`, `repost_top_author_share`, `story_n_log`, `story_dup_rate`, `story_link_share`, `story_share_of_history`, `coord_cluster_size_log`, `coord_traces_log`, `coord_max_sim`.

Never used: the self-applied label, bio words, handle text, the bridged label.

Largest linear-surrogate weights (standardized; the surrogate also writes each account's reasons):

| Feature | Weight |
|---|---|
| `quote_share` | -0.83 |
| `hist_rate_log` | +0.60 |
| `log_posts_count` | -0.54 |
| `repost_share` | -0.45 |
| `bio_len` | +0.44 |
| `text_len_mean` | +0.30 |
| `minute_entropy` | -0.29 |
| `log_follows` | -0.28 |
| `follow_ratio_log` | -0.25 |
| `lifetime_ppd_log` | +0.24 |
| `zero_engagement_share` | +0.23 |
| `has_banner` | +0.21 |

## Hand check

The 50 highest-scored unlabeled accounts (out-of-fold), each read by hand from its bio and 3 to 6 recent posts.
The candidate list with handles stays local (`data/private/handcheck_candidates.jsonl`); `eval/bots/handcheck.csv`
holds the verdicts with no account named. The list is regenerated on every training run; verdicts below were
made on the run that produced this report's model, and need redoing if the top 50 changes.

Precision on this sample: **45 of 50 (90%) automated or likely automated**; none looked like a person
posting by hand. The other five are unclear or mixed. So the labels miss most automation, and the score finds it.

| Verdict | Accounts |
|---|---|
| likely automated: news or RSS feed | 18 |
| automated: says so in its bio, no bot label | 10 |
| likely automated: scheduled digest or aggregator | 8 |
| automated: unofficial mirror of another outlet | 6 |
| automated: market or data feed | 3 |
| unclear: posts only video links | 1 |
| mixed: link feed plus some personal posts | 1 |
| unclear: explainer posts, possibly generated | 1 |
| unclear: product account posting news commentary | 1 |
| unclear: outlet mixing news and promotions | 1 |

What this does and doesn't show: almost all of these are news, RSS, market-data and digest feeds, the same kind as
the labeled bots. The model finds *undisclosed feeds* well. It isn't yet evidence that it finds accounts pushing a
narrative; that question is M3's coordination clusters and M4's per-narrative shares.

# socialnet-bot-tracker

HackPrinceton Fall 2026. Main track: Science and Discovery. Special track: Arlequin AI Track 2, Social Media Analysis (combining content and connectivity).

We follow one story through a social network, find the narratives people push about it, measure how much of each narrative comes from automated accounts, and find out what kinds of real people amplify the automated accounts.

This README holds the research question, data sources, rules, pipeline and table schemas. The demo, the system architecture, the API contracts and the work packages live in one master file, [`docs/DEMO.md`](docs/DEMO.md). Every teammate's coding agent reads both before writing code. If you change a table schema or a file path, change this README in the same pull request.

## The question

Thesis: some kinds of people are much more likely than others to pick up and spread what bots push on a given topic.

What we can measure is amplification: a real account reposts, quotes, likes or agrees in a reply with a post from a likely automated account, or starts posting the bot-heavy narrative after contact with it. We cannot observe belief. The dashboard and the pitch say "more likely to amplify", never "more easily fooled".

The analysis answers four things, in this order:

1. Which narratives exist about the story, and how each one moves over time.
2. For each narrative, the share of posts and the share of accounts that are likely automated, with confidence intervals.
3. Which real accounts amplify likely automated accounts, and how they differ from comparable accounts that saw the same story and didn't.
4. Archetypes: groups of amplifiers who behave alike, each described in plain words, with how much more often they amplify bots than matched non-amplifiers (the lift).

A null result is still a result. If bot share is the same across narratives, or no archetype stands out after matching, we report that.

## The story

Jensen Huang's exit from Nvidia, November 5 to 13, 2026: the congressional briefing request about an alleged Chinese spy, the affair reports, the board probe, the November 11 WSJ ouster report and the resignation on November 12. On November 12 the Washington Post reported that "online bots" were defending Huang. That gives us a public claim to test: does the defend-Huang narrative carry more automation than the others?

## Data sources

| Source | What we take | Cost | Role |
|---|---|---|---|
| Bluesky AppView, `https://api.bsky.app/xrpc/` | posts, threads, quotes, reposters, likers, profiles, author feeds, follows | free, no login | primary network, all four questions |
| Reddit via the Arctic Shift archive, `https://arctic-shift.photon-reddit.com/api/` | posts and comment trees in r/nvidia, r/stocks, r/technology, r/wallstreetbets, r/news | free, slow | second ecosystem: narratives and bot share only |
| X API v2 (pay per use) | optional small sample | $0.005 per post | stretch only, if someone has spare time |

Measured on Sat Nov 14, before this repo had code:

- Bluesky search for "jensen huang", Nov 5 to 14: 46,656 posts from 20,495 accounts. 5,828 are replies and 3,225 are quotes, so part of the interaction graph comes free with the posts.
- 286 of those accounts carry Bluesky's `bot` label and wrote 1,840 of the posts (about 4%). This is our labeled set for the bot model. Labels are incomplete: `nowbreezing.ntw.app`, the most active account in the set, describes itself as a bot in its bio and has no label.
- Exact duplicate texts: 98 texts were posted 5 or more times. One account posted the same text 119 times.
- About 6,500 posts mention the spy claim.
- Reddit, r/nvidia alone: 77 posts about Huang in the window. The largest thread (the WSJ ouster report) has 915 comments.
- Unauthenticated `api.bsky.app` calls to `getProfiles`, `getAuthorFeed`, `getFollows` and `getFollowers` all return 200 with no login.
- Profiles for all 20,482 story accounts came back in 20 seconds (4 workers, 25 per call). The last 50 posts of every account (about 1.0 million posts) took 7 minutes at about 45 accounts a second.

Isaac has the 46,656-post file (`bsky_jensen_nov5_13.jsonl`, 120 MB) and will share it privately. WP-1's search script must be able to re-pull it, because HackPrinceton requires the code to be written during the event.

## Rules

1. Code must be written during the event (at least 85%) in this repo. No code from theses, earlier projects or other repos.
2. Say exactly where the data came from. The Devpost and the demo name each source and access method. We don't scrape websites while logged in, we don't create fake accounts to get more API credit, and we never describe scraped data as API data. Reddit blocks requests from cloud servers; use Arctic Shift, or the official Reddit API only if someone's app gets approved.
3. Nothing is ever posted, liked or followed on any platform. All access is read only.
4. Privacy. Private users appear only as hashed IDs, inside their archetype or community. Only public accounts get a name and a profile page: at least 5,000 followers, a verified account, a news organization, or an account that labels itself a bot. We don't infer sensitive traits (race, religion, health, sexuality, age, gender), and archetype features come only from public behavior. Results are shown for archetypes in aggregate, never as a list of the most susceptible individuals.
5. Wording. An account is "likely automated (score 0.87)" with its top reasons, never "a bot", unless it labels itself one. Undisclosed likely automated accounts with fewer than 5,000 followers are never named.
6. Raw data and anything holding DIDs or handles of private users stays out of git (`data/raw/`, `data/private/` and `data/processed/` are gitignored). Small fake or hashed samples for the frontend go in `data/sample/`.
7. Text replies to users follow the reply rules in `docs/DEMO.md`: no verdict on whether a claim is true, no statement about who operates an account, private accounts counted and never named.

## Pipeline

```
ingest -> narratives -> bot scores -> amplification + archetypes -> export -> dashboard
```

Each stage reads and writes Parquet tables in `data/processed/` (schemas below). Use DuckDB or Polars for queries, igraph plus leidenalg for graph work. No graph database.

### 1. Ingest (WP-1)

Bluesky:

- Story posts: `app.bsky.feed.searchPosts?q=jensen%20huang&sort=latest&limit=100&until=<oldest createdAt seen>`. Cursor paging returns 403 on this endpoint, so slide `until` back page by page. `public.api.bsky.app` also returns 403; use `api.bsky.app`.
- Interactions for the posts that matter (every post by a likely automated account, plus the top 500 human posts by engagement): `getRepostedBy`, `getLikes`, `getQuotes`, `getPostThread`, paged with `cursor`. `getRepostedBy` gives no timestamps; when time matters, read the reposter's `app.bsky.feed.repost` records with `com.atproto.repo.listRecords` on their PDS.
- Profiles: `app.bsky.actor.getProfiles` takes up to 25 actors per call.
- History for profiling: `app.bsky.feed.getAuthorFeed?actor=<did>&limit=100`, one page per account, for amplifiers, matched controls and likely automated accounts.
- Follow graph: `app.bsky.graph.getFollows`, keeping only edges between accounts in the study. Run this for amplifiers, controls and likely automated accounts first, then everyone else if time allows.
- Measure the rate limit in the first hour and write it here. Back off on 429 and save each page as you go, so a crash doesn't lose the pull.

Reddit (cut at 22:00 if not pulled):

- `posts/search?subreddit=<sr>&title=huang&after=2026-11-05&before=2026-11-14&limit=100`. The `query` and `title` parameters need a `subreddit` or `author`.
- Comment trees per post by link ID.
- Arctic Shift returns HTTP 422 "Timeout. Maybe slow down a bit" when called too fast. Wait 15 to 30 s between calls and retry.
- Reddit has no follow graph. The interaction graph is the reply tree. A user's profile is their subreddit mix, from `comments/search?author=`: one call per user, so cap it at about 300 users.

### 2. Narratives (WP-2)

- Embed every story post with `BAAI/bge-small-en-v1.5` (sentence-transformers, runs on a laptop CPU in minutes).
- Cluster with UMAP and HDBSCAN (BERTopic is fine). Aim for 6 to 10 narratives and merge tiny clusters.
- An LLM names each cluster from its top posts and terms and assigns a side: `pro_huang`, `anti_huang`, `neutral_news`, `humor`, `other`. Likely starting points: the spy plot and national security, personal misconduct, the market and the stock, defending Huang, succession, jokes.
- Hand-label 200 random posts with narrative and side. Report the classifier's accuracy against them.
- Track narrative share by hour, so the timeline shows which narrative led at each event.

### 3. Bot scores (WP-3)

The score has two layers, and the pitch needs both.

Account behavior, one row per account:

- account age at first story post, posts per day over its history, follower to follow ratio, has avatar, bio length
- regular posting gaps (coefficient of variation of the time between posts; scheduled bots are very regular)
- share of posts that are reposts, replies, or links, and how many distinct domains it links
- duplicate rate (share of its posts that are near duplicates of its own or others' posts)
- hour-of-day spread

Coordination between accounts (Pacheco et al., ICWSM 2021): build an account-by-trace matrix where a trace is the same URL posted within 60 s, a repost of the same post within 60 s, or near-duplicate text (MinHash, Jaccard at least 0.8). Weight with TF-IDF, take cosine similarity between accounts, threshold it, and take connected components as coordination clusters.

Training and evaluation:

- Positives: the 286 self-labeled bots. Treat unlabeled accounts as unlabeled, not as humans (positive-unlabeled learning, or plain class weights with that caveat stated).
- Leave the label itself and bio words like "bot" or "automated" out of the features. The labeled bots are mostly disclosed news and trend bots, and we want the model to find undisclosed automation by how accounts behave.
- Hold out 20% of labeled bots. Report recall@k: of the held-out labeled bots, how many land in the top k of all accounts by score, for k = 50, 100, 200, 500.
- Hand-check the 50 highest-scored unlabeled accounts and report the precision on that sample.
- Ablation for the Arlequin criteria: behavior only, coordination only, both. The combined model should beat each alone.
- Output `p_automated` for every account, plus `coord_cluster_id` and the top three reasons in plain words.

Ratio per narrative: for each narrative, report the share of posts and the share of distinct accounts with `p_automated >= 0.5`, and the expected count (sum of `p_automated`) so the result doesn't hinge on the threshold. Bootstrap 95% intervals over accounts.

### 4. Amplification and archetypes (WP-4)

Amplifier: a human account (`p_automated < 0.3`) that reposted, quoted or liked a post by a likely automated account (`p_automated >= 0.7`) in the story, or replied to one in agreement (classify reply stance with an LLM on a sample).

Matched controls: for each amplifier, a human account that engaged with a human post of similar reach in the same narrative and the same 6-hour window, matched on activity level (posts per day) and follower count bucket. Without this we would only find "heavy users interact with everything".

Archetype features, from each account's last 100 posts and its profile: account age, posts per day, repost, reply and link shares, the news domains it shares, topic mix (its history's posts assigned to embedding clusters), its Leiden community on the follow graph, active hours, follower to follow ratio. Public behavior only. No demographic guesses.

Archetypes: standardize, cluster amplifiers and controls together (k-means with k from 4 to 8 chosen by silhouette, or HDBSCAN). An LLM writes a plain label from each centroid ("Accounts under 6 months old that mostly repost market news").

Thesis test:

- Lift per archetype: the amplifier rate in that archetype divided by the overall rate, with bootstrap intervals.
- Logistic regression: `amplified_bot ~ archetype + log(followers) + posts_per_day + narrative + hour`.
- Stretch, adoption: among humans whose first contact with a narrative came through a likely automated post, do they post that narrative afterward more often than their matched controls?

### 5. Export and dashboard (WP-9)

`src/export/build_site_data.py` writes `web/public/site_data.json` (shape below). The dashboard is a static site, so the demo needs no backend.

Views:

1. Story timeline: posts per hour, with the real events marked.
2. Narrative river: stacked share by narrative over time, each band shaded by its bot share.
3. Bot ratio per narrative: bars with intervals; click one for its top coordination clusters and their reasons.
4. Network (sigma.js plus graphology): accounts colored by narrative or archetype, likely automated accounts ringed in red, a filter by archetype.
5. Archetype cards: the plain label, size, lift with an interval, typical features, and example public accounts only.
6. Public account pages: posts, who they amplify, who amplifies them.
7. Method and validation: recall@k, ablation, gold-set accuracy, data sources and privacy rules.

Build against `data/sample/site_data.sample.json` from the first hour. Don't wait for the pipeline.

## Data contract

All tables live in `data/processed/<table>.parquet`.

`account_id = sha256(SALT + did)[:16]`, with `SALT` in `.env`, shared privately inside the team. The DID-to-handle map for public accounts lives only in `data/private/public_accounts.parquet`.

| Table | Columns |
|---|---|
| `accounts` | account_id, platform, is_public, handle_public (null unless public), display_name_public, created_at, followers, follows, posts_count, has_avatar, bio_len, self_label_bot |
| `posts` | post_id, platform, account_id, created_at, text, lang, parent_post_id, root_post_id, quoted_post_id, urls (list), domains (list), like_count, repost_count, reply_count, quote_count, in_story |
| `interactions` | src_account_id, dst_account_id, type (`repost`, `like`, `quote`, `reply`, `follow`), post_id, created_at (nullable), platform |
| `history_posts` | same columns as `posts`, for accounts' recent history outside the story |
| `narratives` | narrative_id, label, side, description, top_terms (list) |
| `post_narrative` | post_id, narrative_id, prob |
| `bot_scores` | account_id, p_automated, coord_cluster_id, reasons (list), model_version |
| `user_features` | account_id, feature columns (documented in `src/archetypes/features.py`) |
| `archetypes` | archetype_id, label, size, lift, lift_lo, lift_hi, description |
| `user_archetype` | account_id, archetype_id, role (`amplifier`, `control`) |
| `amplification` | account_id, n_bot_posts_amplified, n_human_posts_amplified, first_bot_contact_at, matched_control_id, adopted_bot_narrative |

`site_data.json`:

```json
{
  "story": {"title": "", "events": [{"t": "", "label": ""}]},
  "timeline": [{"hour": "", "posts": 0, "by_narrative": {"n1": 0}}],
  "narratives": [{"id": "n1", "label": "", "side": "", "bot_post_share": 0.0, "bot_post_share_ci": [0.0, 0.0], "bot_account_share": 0.0, "examples": [""]}],
  "graph": {"nodes": [{"id": "", "narrative": "n1", "archetype": "a1", "p_automated": 0.0, "public_handle": null, "size": 1}], "edges": [{"s": "", "t": "", "type": "repost"}]},
  "archetypes": [{"id": "a1", "label": "", "size": 0, "lift": 0.0, "lift_ci": [0.0, 0.0], "features": {}}],
  "public_accounts": [{"handle": "", "narratives": [], "p_automated": 0.0, "top_posts": []}],
  "validation": {"recall_at_k": {"50": 0.0, "100": 0.0}, "ablation": {}, "gold_accuracy": 0.0},
  "reddit": {"narratives": []}
}
```

## Stack and layout

Python 3.11 with `uv`, DuckDB, Polars, igraph, leidenalg, sentence-transformers, scikit-learn, umap-learn, hdbscan, datasketch (MinHash), httpx. LLM calls (cluster names, the gold-labeling assist, reply stance) go through whichever key a teammate has. Keep them to a few thousand short calls. Frontend: Vite, React, TypeScript, sigma.js, graphology, Observable Plot or Recharts.

```
src/ingest/       bluesky.py, reddit.py
src/model/        schema.py (table schemas, hashing)
src/narratives/   embed.py, cluster.py, label.py
src/bots/         features.py, coordination.py, train.py
src/archetypes/   features.py, match.py, cluster.py, thesis.py
src/export/       build_site_data.py
src/retrieval/    corpus.py, live.py (claim search)
src/api/          FastAPI analysis API (/claim, /xray)
src/messaging/    Photon Spectrum messaging service (TypeScript)
docs/             DEMO.md (master demo file), pitch.md
eval/             bots/, narratives/, thesis/ reports (markdown, committed)
web/              dashboard
data/sample/      small hashed or fake data (committed)
data/raw/, data/private/, data/processed/   gitignored
```

Setup: copy `.env.example` to `.env` and fill in `SALT` (ask Isaac) and an LLM key.

## Risks

- Bluesky rate limits slow the follow and history pulls. Prioritize amplifiers, controls and likely automated accounts.
- The labeled bots are disclosed news bots that don't push narratives. Check the top-scored undisclosed accounts by hand before claiming anything about influence.
- Archetype differences can come from activity level alone. The matching is there to rule that out; keep it.
- Bluesky users are not X users. Never combine populations across platforms, and say which platform each number comes from.

# Demo architecture and vision (master file)

This is the one file for what we demo and how it is built. `README.md` holds the research question, data sources, rules and table schemas; this file holds the demo, the system architecture, the API contracts and the work packages. Every agent reads both before writing code.

How to edit this file is at the bottom. Short version: edit your own work package's status lines freely, append to the changelog, and put anything that changes the demo or a contract in a pull request with `[demo]` or `[contract]` in the title.

## Vision

Text a claim you heard, and get back who is pushing it, how much of that is automated, and what kinds of real people are spreading it.

We prove it first on the week Jensen Huang resigned from Nvidia (Nov 5 to 13, 2026: 46,656 Bluesky posts from 20,495 accounts), a story every judge knows and one where the Washington Post reported that "online bots" were defending him. The same engine then answers claims about any topic with a live Bluesky search.

What we never do: rule on whether a claim is true, say who runs an account, or name private people. We report which narratives carry the claim, the share of likely automated accounts behind each, what those accounts have in common, and which archetypes of real people amplify them.

Who would pay for this: newsrooms deciding whether a viral claim is worth covering, brand and social-listening teams, trust-and-safety teams, investor relations teams facing stock-moving rumors. Enterprise firms (Graphika, Cyabra, Blackbird.AI) sell analyst reports; a check anyone can run from a text message is the gap we claim (precedent check still to do).

## MVP scope

The MVP is the smallest version that still tells the whole story end to end: a judge texts a claim about the Huang week and gets back narratives, bot share with intervals, and who amplifies the automation, while the dashboard shows the same numbers with the evidence behind them. Everything below is either in the MVP, a named stretch, or explicitly out. If it is not listed as in, it is out until the 03:00 freeze lifts.

### The floor (if everything else slips, this still demos)

1. Dashboard on the precomputed Jensen corpus only: replay, bot share per narrative with the bots-removed toggle, archetype cards. All numbers from `site_data.json`, no live calls.
2. The text-a-claim flow answered from the corpus path of `/claim` only (no live path), even if a teammate sends the texts instead of a judge.
3. Backup recordings of both. A demo that runs entirely from the floor still answers the Post's claim with intervals and evidence.

### In scope, by component

| Component | In the MVP | Boundary |
|---|---|---|
| Data (WP-1) | Bluesky only: accounts, posts, history (last 50), interactions for likely-automated posts and top 500 human posts | No Reddit. No firehose or streaming; the Nov 5-13 window is fixed |
| Narratives (WP-2) | 6-10 named clusters over unique posts, sides assigned, 200 hand labels for accuracy | Term/LLM naming only; no reply-stance classifier (already first in the README cut order) |
| Bot model (WP-3) | One saved model scoring every account: profile + behavior features (lifetime posts/day, account age, follow ratios, posting-app mix) plus coordination signals (duplicate text, near-simultaneous reposts, shared links). Self-labeled bots are training/eval labels, never the output | No per-account public verdicts on private accounts; scores ship as shares and intervals. No graph neural anything; a regularized logistic model or gradient boosting that beats the 0.046 baseline on recall@100 is enough |
| Coordination (WP-3) | Clusters of accounts sharing exact or near-duplicate text, or reposting the same post within 60 seconds, sized and reason-coded for the evidence views | Exact/near-duplicate text and timing only; no stylometry, no cross-platform matching |
| Archetypes (WP-4) | 4-6 archetypes over real accounts that amplified likely-automated posts, lift vs matched controls with bootstrap intervals | Matched on account age and activity only; no follower-graph features beyond counts |
| Retrieval (WP-5, WP-7) | Corpus path: bge-small embeddings, cosine top 300, similarity floor from the eval set, grouped by narrative. Eval: 50 hand-written claims with recall@k | Live path is a stretch (see below), not required for the MVP demo |
| API (WP-6) | `/claim` (corpus mode), `/claim/{id}`, chart PNG, `/health`, reply rules enforced and tested, <20 s per corpus claim | `/xray` is a stretch. No auth, no rate limiting beyond a simple per-sender cap in the messaging layer |
| Messaging (WP-8) | Photon Spectrum text line: checking message, reply text, chart image, dashboard link; follow-ups `show the bots`, `who shares it`, `next`, `help`; per-sender last-claim state | Text only. One claim at a time per sender; a second claim queues with a "still checking" reply |
| Agent layer (WP-11) | Deepagent routing corpus vs live and calling the five named tools, LangSmith trace saved | The agent never writes numbers itself; every figure comes from an API tool result |
| Dashboard (WP-9) | Replay with event markers, narrative river, story-without-bots, archetype cards, claim view at `/claim/:id`, method and validation view | Runs locally for judging; static deploy is a stretch. Public account pages are cut (already last in the cut order) |
| Pitch/users (WP-10) | 2-minute script, Q&A card, Devpost with tracks selected, one Peri consultation with name, role, quote, photo | No landing page, no sign-ups |

### The three grafts from the merge note, scoped

Source: `docs/merge-note-interactive-grafts.md` (on main, c48f0a3).

1. **Evidence drawer: in the MVP.** Every bar, archetype card, coordination cluster and X-ray result opens the posts behind the number: timestamps, duplicate traces, reason chips. On the text path this is the `show the bots` follow-up. This is the anti-slop feature, so it is not a stretch; WP-9 and WP-6 split the work (API includes example/evidence post IDs in `/claim` and `/xray` responses; dashboard renders them).
2. **Threshold sensitivity strip: in the MVP, precomputed only.** Screen 3 shows bot share per narrative at thresholds 0.3 / 0.5 / 0.7 / 0.9 from precomputed values in `site_data.json`, so a judge asking "is that just your cutoff?" gets an answer in one glance. A live slider that recomputes is a stretch, only after the floor is safe.
3. **Challenge mode: Plan B and post-pitch, not in the 2 minutes.** If the live text flow fails twice in rehearsal, the demo's live moment becomes challenge mode on the laptop (judge labels 3 posts, then sees the model's call and the evidence). After the pitch, a QR at the table runs the same mode; disagreements join the hand-label queue. Recordings of the text flow become Plan C.

### Stretch, in order (start only when the floor is verified working)

1. `/xray` endpoint and dashboard view (contract already in this file).
2. Live path for claims outside the Jensen corpus (<60 s target).
3. Live threshold slider on screen 3.
4. Static deploy of the dashboard.
5. Voice line (WP-12), only after 01:00 and only if the text flow is stable.

### Explicitly out

- Reddit data in any form (first cut, stays cut).
- Any verdict on whether a claim is true, and any claim about who operates an account.
- Naming or linking private accounts anywhere: dashboard, texts, chart images, Devpost, or the pitch.
- Reply-stance classification, sentiment scoring, follower-graph analysis.
- Accounts, logins, persistence beyond per-sender last-claim state, or a public launch. This is a judging demo on a fixed corpus, not a product release.
- New tracks beyond the table above; a stretch feature that is not working by 03:00 does not get entered.

### Acceptance checks

By 18:00 (v0): floor items 1 and 2 run end to end on v0 data; kill tests 1-3 reported with real numbers, pass or fail; the example text exchange reproduced with computed (not placeholder) numbers for one claim.
By 01:00: `/claim` live behind the text line; evidence drawer working on screens 3 and 4; threshold strip rendered from real precomputed values; three backup recordings made; rehearsal run once against the clock.
Scope changes after 16:30 go through a `[demo]` pull request like this one, with the cut it replaces named in the description.

## Tracks

Main track (exactly one allowed): Entertainment and Media. Its description lists "media literacy centered apps", which is what this is. Best Overall considers every project automatically.

Special tracks, entered only where the feature is real (each one adds a judge visit):

| Track | Prize | What qualifies us | Owner |
|---|---|---|---|
| Arlequin AI Track 2 | AirPods for winners | content plus connectivity in every number; recall@k on bot detection and claim retrieval | everyone |
| Photon: Build a Messaging Agent using Photon 2.0 | winner $400 cash, $300 credits and a fast-track to Photon's final interview round; runner-up $200 | the text-a-claim line, live on a Photon Spectrum channel | WP-8 |
| LangChain: Best use of deepagents | Switch 2 for winners | the agent behind the text line is a deepagent; LangSmith traces as evidence | WP-11 |
| Amazon: Best Practical AI Innovation | Amazon gift cards, up to $125 per person | an agent that plans and acts, real users, simple interface; needs working demo, use case, docs, pitch | WP-10 |
| Peri: Forward Deployed Challenge | introductions to hiring teams at Cognition, Edra, Ephemeral, Sea12, Arca, Poetic | consult a real business or student organization during the event (for example a Daily Princetonian editor) and submit their name, role and one piece of evidence | WP-10 |
| ChatOverflow Agent Leaderboard | $500, $250, $150, $100 raffle | every teammate connects their coding agent; no submission needed | everyone |
| Photon: Best Voice Agent (stretch) | $300 cash and $100 credits | the judge calls and says the claim; voice runs on an SMS number, not iMessage | WP-12 |

Not entered: CoStar (no honest use of its data), Capital One Nessie (no banking use), Best Hardware and Physical AI (no hardware), Best Rookie (not eligible).

## The 2-minute demo

Table setup: laptop with the dashboard, a monitor facing the judge if we can get one, and a printed QR code that opens Messages to our Photon number with "hi" filled in.

1. Opening (10 s). "Jensen Huang resigned on November 12. Bluesky had 46,656 posts about it from 20,495 accounts. How much of that was real?"
2. Replay (30 s), dashboard. The network grows hour by hour from Nov 5 to Nov 13. Each dot is an account; lines are reposts, quotes, replies and likes. Likely automated accounts glow red. A real account turns its archetype's color the first time it amplifies a red one. Markers on the scrubber: WSJ ouster report (Nov 11, 22:43 UTC), resignation (Nov 12, 13:55 UTC), the Post's bots report (Nov 12, 20:15 UTC). The narrative river runs underneath, each band shaded by its bot share.
3. The story without the bots (20 s), dashboard. Bars per narrative with bot share and interval. A toggle removes likely automated accounts and their engagement, and the bars re-rank. The line we hope to say: "take out the automation and narrative X falls from second to fifth." If the ranking doesn't move, the bot share per narrative still answers the Post's claim.
4. Who carries the bots (20 s), dashboard. Archetype cards: plain label, size, lift over matched accounts with an interval, three defining features, public example accounts only.
5. The judge texts a claim (40 s), judge's own phone. They scan the QR code and text something like "Was Jensen Huang's mistress a Chinese spy?" Within about 20 seconds they get a text answer, a chart image and a link that opens that claim's view on our dashboard. If they ask about another topic, the live path answers in under a minute while we talk.

Q&A card, not in the 2 minutes: bot model recall@k and ablation, claim retrieval recall@k, narrative accuracy on hand labels, data sources, privacy rules.

Backups: recordings of three full text exchanges and of the replay, in case Wi-Fi, Photon or Bluesky fails during judging.

### Example text exchange (numbers are placeholders)

> Judge: Was Jensen Huang's mistress a Chinese spy?
>
> Bot: Checking who is pushing that. About 20 seconds.
>
> Bot: I found 1,240 Bluesky posts making this claim (Nov 5 to 13). They fall into 3 narratives:
> 1. National security / spy plot: 62% of posts. Likely automated: 9% (6 to 12%), about 2x the story's baseline.
> 2. Defending Huang (smear campaign): 21%. Likely automated: 18% (13 to 24%).
> 3. Jokes and memes: 17%. Likely automated: 3%.
> The likely automated accounts pushing narrative 2: 41 of them were created in the same two weeks, and 14 reposted the same posts within a minute of each other.
> The real accounts spreading their posts are mostly "new accounts that mostly repost market news" (2.7x more likely than similar accounts).
> I don't judge whether the claim is true. Full view: <dashboard link>
>
> Bot: [chart image]

Follow-ups the bot understands: "show the bots" (coordination evidence), "who shares it" (archetype cards as text), "next" (the next narrative), "help".

## Architecture

```
                 batch (runs once, refreshed at milestones)
Bluesky AppView ─> ingest ─> narratives ─> bot scores ─> amplification + archetypes ─> export
                                                                                   │
                     artifacts: corpus embeddings, narrative centroids,            │
                     bot model, archetype centroids, bot_scores, site_data.json    │
                                                                                   v
Judge's phone ─> Photon (Spectrum) ─> messaging service (TS) ─> analysis API (Python, FastAPI)
                                              │                     │  /claim  /xray
                                              │                     ├─ retrieval over corpus embeddings
                                              │                     ├─ live Bluesky search (other topics)
                                              │                     ├─ scoring with saved models
                                              │                     └─ chart PNG + reply text
                                              v
                                     dashboard (Vite + React, static, reads site_data.json,
                                     claim view fetches /claim/{id})
```

### Components

1. Batch pipeline (Python). Stages and tables are in `README.md`. Besides the Parquet tables it saves the artifacts the API loads at startup into `data/processed/artifacts/`: `corpus_embeddings.npy` plus `corpus_index.parquet` (post_id, account_id, narrative_id, created_at), `narrative_centroids.npy`, `bot_model.pkl`, `archetype_centroids.npy` with the feature scaler, and `bot_scores.parquet`.
2. Analysis API (Python, FastAPI, `src/api/`). Loads the artifacts once. Endpoints below. It writes the reply text itself, so the privacy and wording rules are enforced in one place.
3. Claim retrieval (`src/retrieval/`). Embeds the claim with `BAAI/bge-small-en-v1.5` using its query prefix (`Represent this sentence for searching relevant passages: `), takes cosine top 300 over the corpus embeddings (a 40k by 384 matrix in numpy, milliseconds), keeps matches above a similarity floor tuned on the eval set, and groups them by narrative.
4. Live path (`src/retrieval/live.py`). For claims outside the Jensen corpus: an LLM turns the claim into two or three search queries, `app.bsky.feed.searchPosts` pulls up to 300 recent posts, they are embedded, grouped (k-means, k up to 5, an LLM names the groups), and their authors are scored live (`getProfiles` 25 per call, `getAuthorFeed` limit 30; measured about 45 accounts a second). Target under 60 seconds.
5. Messaging service (TypeScript, `src/messaging/`). Photon 2.0 through Spectrum (`spectrum-ts`, a Spectrum Cloud number, no Mac needed). Receives a text, sends the "checking" message at once, calls `/claim`, then sends `reply_text`, the chart image and the dashboard link. Keeps per-sender state (last `claim_id`) for follow-ups. Read Photon's hackathon guidelines before writing code: https://somethingreat.notion.site/Hackathon-Guidelines-for-Photon-2-0-3f8e443f36bb81f9893fed0d08a4c01d (beta and $100 free credits at photon.codes/beta). Prize eligibility needs the project built on Photon 2.0 and live on at least one Photon channel. A shared iMessage line can't text first, so the judge starts the conversation from the QR code. Use the SDK's documented calls only; don't guess method names.
6. Agent layer (required, WP-11, for the deepagents prize). The logic between the messaging service and the API (decide corpus or live, call tools, handle follow-ups) becomes a LangChain deepagent with tools `search_claim`, `narratives_for`, `bot_share`, `amplifier_archetypes`, `coordination_evidence`. The API endpoints above stay the tools' backend either way.
7. Dashboard (`web/`, Vite, React, TypeScript, sigma.js, graphology). Reads `web/public/site_data.json` (shape in `README.md`). Views: replay, narrative river, story without bots, archetype cards, claim view at `/claim/:id`, public account pages, method and validation.

### API contracts

`POST /claim`, body `{"text": "...", "mode": "auto"}` (`mode` is `auto`, `corpus` or `live`; `auto` uses the corpus when the best match clears the floor and live search otherwise). Response:

```json
{
  "claim_id": "",
  "claim": "",
  "scope": "corpus",
  "matched_posts": 0,
  "window": {"from": "", "to": ""},
  "narratives": [
    {
      "id": "n1",
      "label": "",
      "side": "",
      "share_of_matches": 0.0,
      "bot_post_share": 0.0,
      "bot_post_share_ci": [0.0, 0.0],
      "baseline_bot_share": 0.0,
      "example_posts": [{"text": "", "public_handle": null}]
    }
  ],
  "bot_commonalities": [{"signal": "", "accounts": 0}],
  "amplifiers": {"n_humans": 0, "archetype_mix": [{"id": "a1", "label": "", "share": 0.0, "lift": 0.0}]},
  "chart_png_url": "",
  "dashboard_url": "",
  "reply_text": "",
  "seconds": 0.0
}
```

`GET /claim/{claim_id}` returns the same object, for the dashboard's claim view.

`GET /claim/{claim_id}/chart.png` returns the chart: one horizontal bar per narrative showing its share of matches, with the likely automated share overlaid.

`POST /xray`, body `{"post_url": "https://bsky.app/profile/<handle>/post/<rkey>"}` (stretch, after `/claim` works). Pulls up to 300 audience accounts with `getRepostedBy`, `getQuotes` and `getLikes` and returns:

```json
{
  "post": {"uri": "", "text": "", "author_public_handle": null},
  "audience_size": 0,
  "share_likely_automated": 0.0,
  "share_ci": [0.0, 0.0],
  "archetype_mix": [{"id": "a1", "label": "", "share": 0.0}],
  "coordination_clusters": [{"size": 0, "reasons": [""]}],
  "public_accounts": [{"handle": "", "p_automated": 0.0}],
  "evidence_posts": [{"text": "", "public_handle": null, "reasons": [""], "created_at": ""}],
  "seconds": 0.0
}
```

`GET /health` returns `{"ok": true, "artifacts_loaded": true}`.

### Reply rules (enforced in the API)

- Never name an account unless it is public under the README's rule (5,000+ followers, verified, a news organization, or self-labeled bot). Private accounts are counted only.
- "Likely automated", with a share and an interval, never "bots" for undisclosed accounts.
- No statement about who operates any account. "What they have in common" lists observable signals only: creation dates, posting app, shared links, reposting within seconds.
- No verdict on whether the claim is true. Say so in every reply.
- If fewer than 30 posts match, say there isn't enough data instead of reporting shares.
- Decline claims that target a private individual by name.

### Hosting

The API runs on Isaac's VM, where the data and artifacts already are, exposed through a tunnel once Isaac approves it; David's laptop with `cloudflared` is the fallback. The messaging service runs wherever Spectrum's guidelines say (Spectrum Cloud or a teammate laptop). The dashboard runs locally for judging, with a static deploy as a stretch.

## Work packages

Give your agent: "Read README.md and docs/DEMO.md, then do WP-<n>. Update its status lines in docs/DEMO.md as you go."

Status values: `todo`, `doing`, `v0` (works end to end, rough), `done`, `cut`.

### WP-1 Data pulls
- Owner: Hermes (Isaac's VM agent)
- Depends on: nothing
- Outputs: `accounts`, `posts`, `history_posts`, `interactions` tables; refreshed in the shared Drive folder at 16:30, 18:00, 22:00, 01:00
- Done when: interactions with timestamps exist for every likely automated post with engagement and for the top 500 human posts
- Status: doing. Profiles for all 20,482 accounts pulled in 20 s. Last 50 posts of every account pulled (about 1.0 million posts, 7 minutes). Interactions next.

### WP-2 Narratives
- Owner: Hermes; Isaac names the clusters and hand-labels 200 posts
- Depends on: WP-1 posts
- Outputs: `narratives`, `post_narrative`, `corpus_embeddings.npy`, `narrative_centroids.npy`, `eval/narratives/report.md`
- Done when: 6 to 10 named narratives with sides, accuracy on 200 hand labels reported
- Status: doing. Embedding 40,197 unique posts.

### WP-3 Bot model and coordination
- Owner: David
- Depends on: WP-1 accounts and history
- Outputs: `bot_scores`, `bot_model.pkl`, coordination clusters, `eval/bots/report.md` (recall@k, ablation)
- Done when: recall@100 on held-out labeled bots of at least 0.3 (lifetime posts per day alone: 0.046), ablation shows behavior plus coordination beats each alone
- Status: todo

### WP-4 Archetypes and thesis statistics
- Owner: Brian
- Depends on: WP-3 v0, WP-1 interactions
- Outputs: `user_features`, `archetypes`, `user_archetype`, `amplification`, `archetype_centroids.npy`, `eval/thesis/report.md`
- Done when: archetypes with lift and bootstrap intervals over matched controls, regression table
- Status: todo

### WP-5 Claim retrieval
- Owner: Hermes
- Depends on: WP-2 embeddings
- Outputs: `src/retrieval/` (corpus search, grouping by narrative, live path)
- Done when: corpus search answers in under 2 s; live path answers in under 60 s
- Status: todo

### WP-6 Analysis API
- Owner: David
- Depends on: WP-3 v0, WP-5
- Outputs: `src/api/` with `/claim`, `/claim/{id}`, chart PNG, `/health`; `/xray` as a stretch
- Done when: `/claim` returns the contract above in under 20 s for corpus claims, with reply rules enforced and tested
- Status: todo

### WP-7 Retrieval evaluation
- Owner: Brian
- Depends on: WP-2 posts
- Outputs: `eval/retrieval/claims.csv` (50 hand-written claims with the post IDs that truly match), `eval/retrieval/report.md`
- Done when: recall@k at k = 10, 20, 50 and the similarity floor that WP-5 should use
- Status: todo

### WP-8 Messaging service (Photon)
- Owner: Isaac's coding agents
- Depends on: WP-6 contract (build against a stub that returns the example JSON until WP-6 is live)
- Outputs: `src/messaging/`, the Spectrum number, the QR code
- Done when: a judge's text gets the checking message, the reply, the chart and the link; follow-ups work; three backup recordings made
- Status: todo

### WP-9 Dashboard and replay
- Owner: Isaac's coding agents
- Depends on: `data/sample/site_data.sample.json` first, then WP-1 to WP-4 exports
- Outputs: `web/`, `src/export/build_site_data.py`
- Done when: all views run on real data, the claim view opens from the text link, replay recorded as a backup
- Status: todo

### WP-10 Pitch, Devpost, users
- Owner: Jeremy
- Depends on: nothing at first
- Outputs: `docs/pitch.md` (2-minute script, Q&A card), Devpost text with every track above selected, video
- First tasks: by 17:00 talk to Arlequin's people (what would impress them; does a text-a-claim check matter to their customers) and to Photon's booth (anything in the guidelines that affects eligibility; image attachments on the Spectrum number). Today: the Peri consultation. Ask a Daily Princetonian editor (or another campus news organization) whether they would text viral claims to this before covering them, what answer they'd need, and get their name, role, a quote and a photo.
- Status: todo

### WP-11 Agent layer (deepagents)
- Owner: Hermes
- Depends on: WP-5, WP-6 contract
- Outputs: `src/agent/`: a LangChain deepagent with tools `search_claim`, `narratives_for`, `bot_share`, `amplifier_archetypes`, `coordination_evidence` that decides corpus or live search and handles follow-ups; LangSmith tracing on
- Done when: the messaging service calls the agent instead of `/claim` directly, the reply rules still hold, and a trace of one full exchange is saved for the Devpost
- Status: todo

### WP-12 Voice line (stretch)
- Owner: unassigned; start only after the text flow works end to end (01:00)
- Outputs: a Photon SMS number that takes a spoken claim and answers out loud with the same reply
- Status: todo

## Timeline (Sat Nov 14 to Sun Nov 15)

| Time | Milestone |
|---|---|
| 16:30 | idea locked, owners confirmed; `accounts` and `posts` tables on Drive; sample `site_data.json` committed |
| 18:00 | every component running end to end on stubs or v0 data; kill tests 1 to 3 reported |
| 21:00 | retrieval eval set done (kill test 4); messaging service answering from the stub |
| 22:00 | interactions on Drive; archetypes v0; dashboard on real data |
| 01:00 | `/claim` live behind the text line; bot scores and narratives final |
| 03:00 | thesis numbers final; feature freeze |
| 03:00 to 05:00 | polish, rehearsal, backup recordings |
| 06:30 | video recorded, Devpost written |
| 07:00 | submit (hard stop 08:00) |

Cut order if behind: Reddit, then the voice line, then `/xray`, then the live path for other topics, then public account pages. The replay, bot share per narrative, archetype cards and the text-a-claim flow on the Jensen corpus stay.

## Kill tests

1. Bot model (18:00): recall@100 on held-out labeled bots of at least 0.3. If not, coordination becomes the main signal.
2. Narratives (18:00): 6 to 10 nameable clusters and at least 70% agreement with the first 50 hand labels.
3. Spread (18:00): bot post share in the most automated narrative at least twice that of the least automated one. If not, the headline is "automation is spread evenly, and the bots-defending-Huang claim does not show on Bluesky".
4. Retrieval (21:00): recall@20 of at least 0.6 on the first 20 hand-written claims.

## Build specification (how an agent builds each piece, end to end)

This section is the instruction set for the coding agents. Read it with `README.md` (schemas, pipeline detail) and the MVP scope section above. Where this section and a work package disagree, this section wins for *how*; the work package wins for *who* and *done when*. No API shape changes are introduced here except the two flagged `[contract]` items, which land in `README.md` in the same pull request.

### Global conventions (every agent, every package)

- IDs: `account_id = sha256(SALT + did)[:16]`, `post_id` is the Bluesky `at://` URI for Bluesky posts. Never invent a second ID scheme. `SALT` comes from `.env`; code must run with the dev salt `dev-salt` when `.env` is missing, and print a warning.
- Time: everything UTC, ISO 8601 strings in JSON, `TIMESTAMP` in Parquet. The story window is 2026-11-05T00:00:00Z to 2026-11-14T00:00:00Z.
- Thresholds live in one place, `src/config.py`, and nowhere else as literals: `BOT_SHARE_THRESHOLD = 0.5` (headline shares), `HUMAN_MAX = 0.3` and `BOT_MIN = 0.7` (amplifier definition, per README WP-4), `MIN_MATCHED_POSTS = 30` (below this, no shares are reported), sensitivity thresholds `[0.3, 0.5, 0.7, 0.9]`.
- Intervals: bootstrap over accounts, 1,000 resamples, seed 42, percentile 2.5/97.5. Same function (`src/stats.py: bootstrap_share`) used by WP-3, WP-4, WP-6 and the export, so the dashboard, the API and the texts never disagree.
- Artifacts: the batch pipeline writes `data/processed/artifacts/manifest.json` listing every artifact file, its producing WP, `model_version`, and row counts. The API refuses to start if the manifest is missing a required artifact, and `/health` reports the manifest's `model_version`.
- Every stage script is idempotent and runnable as `python -m src.<stage>` from the repo root, reads only the tables listed as its inputs, and writes only its own outputs. A stage that crashes must leave the previous good output in place (write to a temp file, then rename).
- Tests: each WP ships a `tests/test_wp<n>_*.py` smoke test that runs on `data/sample/` in under a minute. "v0" in a status line means its smoke test passes end to end on sample or stub data, not that the code merely exists.

### Build order and integration gates

Build in this order; a step starts when its gate passes, not when the clock says so.

1. **Contracts and stubs (now).** `src/model/schema.py` implements the README tables; `data/sample/site_data.sample.json` matches the README shape plus the `[contract]` fields below; WP-6 ships a stub `/claim` returning the example response in this file with `model_version: "stub"`. Gate: dashboard renders from the sample file, messaging service completes a full exchange against the stub.
2. **WP-1 tables.** Gate: row counts and a 20-row eyeball sample posted in the WP-1 status note; `interactions` covers every likely-automated post with engagement (v0 definition: posts by self-labeled bots) plus the top 500 human posts.
3. **WP-2 and WP-3 in parallel** on WP-1 outputs. Gates: WP-2 kill test 2 numbers in `eval/narratives/report.md`; WP-3 kill test 1 numbers in `eval/bots/report.md` (pass or fail, both are progress).
4. **WP-4** on WP-3 v0 scores. Gate: lift table with intervals in `eval/thesis/report.md`, even if every interval crosses 1.
5. **Export v0** (`build_site_data.py`) from whatever tables exist; missing sections ship as empty arrays, never as a crash. Gate: dashboard runs on real data with at least narratives and bot shares real.
6. **WP-5 + WP-6 real `/claim`** against the artifacts. Gate: the end-to-end checks below pass for the three rehearsal claims.
7. **WP-8 live, WP-11 agent layer** swapped in front of the same API. Gate: one full text exchange with a saved LangSmith trace.
8. **Freeze (03:00).** After the freeze only bug fixes with a failing end-to-end check as the reason.

### WP-1 Ingest: build steps

- `src/ingest/bluesky.py` with one function per endpoint in the README; every page saved to `data/raw/` as it arrives (append-only JSONL per endpoint per day), then a separate `build_tables.py` turns raw pages into the Parquet tables. A crash in table building never requires re-pulling.
- Search paging: slide `until` to the oldest `createdAt` seen, per the README (cursor paging 403s). Dedupe on post URI at table build.
- `getRepostedBy` has no timestamps: for repost times use `com.atproto.repo.listRecords` on the reposter's PDS, and store `created_at = null` when even that fails. Never fabricate a timestamp.
- Rate limits: token bucket at 4 workers to start; on 429, exponential backoff 5/15/45 s and log the endpoint; the measured sustainable rate goes into the WP-1 status note.
- Public/private split happens here, once: `is_public` and the public handle map are computed in `build_tables.py` from the README rule, and every later stage only ever sees `handle_public` (null for private accounts).

### WP-2 Narratives: build steps

- Dedup first: exact-duplicate texts collapse to one embedding row with a `dup_count`; the 40,197 unique posts are what gets embedded and clustered. `post_narrative` still gets a row for every post (duplicates inherit their text's cluster with prob 1.0).
- Embed with `BAAI/bge-small-en-v1.5`, batch 256, save float32 `corpus_embeddings.npy` plus `corpus_index.parquet` in the same order. Any re-embed must bump `model_version`.
- UMAP (n_neighbors 15, min_dist 0.0, cosine) then HDBSCAN (min_cluster_size 150, then merge clusters under 1% of posts into their nearest centroid). If HDBSCAN returns outside 6-10 clusters after one parameter retry, fall back to k-means with k = 8 and note it in the report. Do not hand-tune past the second attempt; the clock matters more.
- Naming: the LLM gets each cluster's top 20 posts by centrality plus top c-TF-IDF terms and returns `label`, `side`, `description`. Isaac approves or renames; renames are edited in `narratives.parquet` only, never by re-running the clusterer.
- Hand labels: 200 posts sampled uniformly, labeled by Isaac in a CSV (`post_id, narrative_id, side`); accuracy and a confusion summary go in `eval/narratives/report.md`. The same CSV is the gold set WP-5's floor tuning must not train on.

### WP-3 Bot model and coordination: build steps

- Features: exactly the README list, computed in `src/bots/features.py`, one row per account, from `accounts` + `history_posts` + `posts`. Each feature function is pure and unit-tested on the sample accounts. Missing history (account pulled without history) yields nulls, and the model imputes medians recorded at train time; never drop accounts for missing features, every account gets a score.
- Coordination first, because it is also a feature source: build traces (same URL within 60 s; repost of the same post within 60 s; near-duplicate text by MinHash LSH, Jaccard >= 0.8, computed on normalized text: lowercase, URLs and mentions stripped). Account-by-trace TF-IDF, cosine >= 0.6, connected components of size >= 2 become `coord_cluster_id`s; each cluster records its reasons (which trace types, counts) for the evidence views.
- Model: gradient boosting (LightGBM if available, else sklearn `HistGradientBoostingClassifier`) on behavior features + coordination features (cluster size, share of traces shared, max cosine to another account). Positives: the 286 self-labeled bots; unlabeled treated as negatives with class weight noted as the PU caveat in the report. The label and any bio text are excluded from features.
- Split: stratified 80/20 on labeled bots, seed 42. Report recall@50/100/200/500 on the held-out 20%, the same for behavior-only and coordination-only ablations, and the posts-per-day-only baseline (expected 0.046 at k=100). Kill test 1 reads these numbers directly.
- Hand-check: the 50 highest-scored unlabeled accounts get a one-line human verdict each in `eval/bots/handcheck.csv` (`account_id, verdict, why`); precision on that sample goes in the report. No number from the hand-check is ever shown publicly per account.
- Outputs: `bot_scores.parquet` (every account: `p_automated`, `coord_cluster_id`, top-3 `reasons` generated from the largest feature contributions mapped to plain phrases, e.g. "posts 40+ times a day", "created in the same week as 30 other high-scoring accounts", "reposted the same posts within a minute of 12 other accounts"), `bot_model.pkl`, and per-narrative shares at all four sensitivity thresholds written for the export (see `[contract]` item 1).

### WP-4 Archetypes and thesis: build steps

- Amplifiers and controls exactly per the README definitions and thresholds in `src/config.py`. Matching: nearest neighbor on (log posts/day, follower bucket, account-age bucket) within the same narrative and 6-hour window, without replacement; unmatched amplifiers are dropped from lift but counted in the report.
- Features per the README list, standardized with a scaler saved as an artifact (the API's X-ray stretch reuses it). Cluster amplifiers + controls together, k-means k in 4..8 by silhouette; if silhouette < 0.05 for all k, use k = 4 and say so.
- Lift per archetype with the shared bootstrap; the regression table from the README formula; both in `eval/thesis/report.md` and the export. Archetype labels are written from centroid summaries by the LLM, then Brian approves the wording. Labels describe behavior only ("new accounts that mostly repost market news"), never a trait.

### WP-5 Retrieval and WP-7 evaluation: build steps

- Corpus path: embed the claim with the bge query prefix from the architecture section, cosine against `corpus_embeddings.npy`, top 300, drop below the similarity floor, group survivors by `post_narrative` (weight by prob). Response time target < 2 s; the matrix multiply is the only heavy step, everything else is Parquet lookups.
- WP-7 builds the floor: 50 hand-written claims in `eval/retrieval/claims.csv` (`claim, true_post_ids`) written from the posts, not from the narratives' labels; report recall@10/20/50 per floor candidate (0.55/0.65/0.75) and pick the floor with recall@20 >= 0.6 and the fewest sub-30-match claims. The chosen floor is a constant in `src/config.py` (`SIMILARITY_FLOOR`), changed only through WP-7's report.
- Live path (stretch): claim -> LLM writes 2-3 search queries -> `searchPosts` up to 300 posts -> embed -> k-means k = min(5, max(2, posts // 40)) -> LLM names groups -> authors scored with the saved model (features computed from `getProfiles` + one `getAuthorFeed` page each). Same response shape as corpus mode with `scope: "live"`. Nothing about the live path may block the corpus path shipping.

### WP-6 Analysis API: build steps

- FastAPI app in `src/api/`, artifacts loaded once at startup from the manifest; a `/health` that returns `artifacts_loaded: false` (not a crash) when artifacts are absent, so hosting problems are diagnosable during judging.
- `POST /claim` pipeline, in order, each step timed and the total returned as `seconds`:
  1. Normalize the claim text (trim, collapse whitespace). `claim_id` = first 12 hex of sha256 of the normalized lowercase text + mode. Identical claims return the cached response from an in-memory dict; the dashboard's `GET /claim/{claim_id}` reads the same cache (and a JSON file per claim under `data/processed/claims/` so links survive an API restart).
  2. Private-individual check: if the claim names a person who is not a public figure in the corpus (heuristic: a capitalized name that is not Jensen Huang, Nvidia, or a named public account in the matched posts), return the decline reply (template below) with `matched_posts: 0`. When unsure, do not decline; the reply rules are enforced again at wording time.
  3. Retrieve (WP-5). If matched posts < `MIN_MATCHED_POSTS` in corpus mode and mode is `auto`, try the live path once (stretch only); if still < 30, return the insufficient-data reply with the true count. Never pad a small match into shares.
  4. Per narrative: share of matches, bot post share at `BOT_SHARE_THRESHOLD`, interval from the shared bootstrap over the matched posts' accounts, baseline bot share across all matches, and up to 3 example posts (public accounts named; private accounts shown as text with `public_handle: null`, text truncated to 200 chars).
  5. Bot commonalities: aggregate the top `reasons` and coordination clusters among likely-automated accounts in the matches: creation-week concentration, shared traces, posting-app mix. Observable signals only, each as `{signal, accounts}`.
  6. Amplifiers: among human accounts (`p_automated < HUMAN_MAX`) who reposted/quoted/liked the matched likely-automated posts, the archetype mix and lift from WP-4's tables. Corpus mode only; live mode returns an empty mix with `n_humans: 0` rather than a guess.
  7. Chart PNG: horizontal bars, one per narrative, share of matches as the bar, bot share as a darker overlay segment, narrative labels on the axis, no account names. Rendered with matplotlib to `data/processed/claims/<claim_id>.png`, served at `GET /claim/{claim_id}/chart.png`.
  8. `reply_text` composed from the templates below by code, not by an LLM. The agent layer (WP-11) may route and select, but the numbers and wording come from this step, so the reply rules hold even if the agent misbehaves.
- `/xray` (stretch) follows the same pattern: parse the post URL to a URI, pull audience (repostedBy, quotes, likes; cap 300, dedupe), score authors with the saved model and scaler, archetype by nearest centroid, coordination clusters among the audience from WP-3 traces, plus `evidence_posts` (see `[contract]` item 2). Hard timeout 25 s: on timeout, return the result for the audience actually scored so far, with `audience_size` set to that true scored count (the contract shape does not change).
- Errors are JSON `{"error": "..."}` with a human sentence, never a stack trace; the messaging layer turns any error into the failure reply template.

### Reply text templates (WP-6 composes, WP-8 sends verbatim)

Checking (sent by WP-8 immediately): `Checking who is pushing that. About 20 seconds.`

Main answer (placeholders from the response object; percentages rounded to whole numbers, intervals as `9% (6 to 12%)`):

```
I found {matched_posts} Bluesky posts making this claim ({window}).
{narrative_lines}
{commonality_line}
{amplifier_line}
I don't judge whether the claim is true. Full view: {dashboard_url}
```

Each narrative line: `{label}: {share}% of posts. Likely automated: {bot_share} ({lo} to {hi}%)` and, when a narrative's bot share is at least twice the baseline, append `, about {x}x the story's baseline.` Order narratives by share descending, at most 4 lines, then `+ {n} smaller narratives in the full view.`

Commonality line (only when at least 5 likely-automated accounts match): `The likely automated accounts pushing {top_bot_narrative}: {signal_1}; {signal_2}.` Signals in plain words, e.g. `41 were created in the same two weeks`, `14 reposted the same posts within a minute of each other`.

Amplifier line (only when `n_humans >= 10`): `The real accounts spreading their posts are mostly "{archetype_label}" ({lift}x more likely than similar accounts).`

Insufficient data: `I found {n} Bluesky posts making this claim, which isn't enough to measure automation reliably (I need at least 30). Try a broader wording, or ask about the Jensen Huang story from Nov 5 to 13.`

Decline (private individual): `I can't run checks on claims about a private person. I can check claims about public stories, like the Jensen Huang week.`

Failure (any API or network error): `Something broke on my end and I couldn't finish that check. The team has a recording of a full check at the table.`

Follow-ups (WP-8 state: last `claim_id` per sender):
- `show the bots` -> coordination evidence for the last claim: top 3 clusters as text (`{size} accounts: {reason_1}; {reason_2}`), plus 3 example posts with the evidence rules applied.
- `who shares it` -> the amplifier archetypes as text lines with lift.
- `next` -> the next narrative's line and examples, cycling.
- `help` -> `Text me a claim and I'll check who is pushing it on Bluesky. After an answer, try "show the bots" or "who shares it".`
- Anything else is treated as a new claim.

### WP-8 Messaging: build steps

- Spectrum via `spectrum-ts` on a Spectrum Cloud number, per Photon's hackathon guidelines (read them before coding; use documented SDK calls only). Inbound text -> send checking template at once -> call the agent layer (WP-11), or `/claim` directly until WP-11 lands -> send `reply_text`, then the chart image, then nothing else (the link is inside `reply_text`).
- Timeouts: if the API call passes 45 s, send `Still checking, the live search is slow on this one.` once; at 90 s send the failure template. Corpus claims should never reach either.
- State: an in-memory map sender -> {claim_id, narrative_cursor} plus a JSON file backup every message, so a restart mid-judging loses at most the follow-up context, and `help` explains how to recover.
- The QR code encodes a Messages deep link to the Spectrum number with `hi` prefilled; test it from a phone that has never messaged the number before recording any backup.

### WP-9 Dashboard and export: build steps

- `build_site_data.py` reads the Parquet tables and artifacts and writes exactly the README `site_data.json` shape plus `[contract]` item 1. It must run with any subset of tables present (missing table -> that section empty), because it runs at every Drive refresh, not just at the end.
- Replay: posts bucketed by hour; the network view caps at the 3,000 highest-engagement accounts (say so on the method view), edges from `interactions` inside the cap; scrubber markers from `story.events`. Precompute per-hour cumulative node/edge sets in the export so the browser never filters the full graph per frame.
- Evidence drawer: narrative bars, archetype cards and coordination clusters all read the same `evidence` arrays (post texts with `public_handle` or null, reasons, timestamps). One component, three call sites. Private accounts render as "a private account" with no handle, ever.
- Threshold strip: renders `bot_post_share_by_threshold` per narrative as four dots on one line per narrative; the headline bar stays at 0.5. No recompute in the browser.
- Claim view at `/claim/:id` fetches `GET /claim/{claim_id}` from the API base URL in `web/.env` (`VITE_API_BASE`), and renders the same narrative/evidence components from the response. If the API is unreachable it shows the reply rules text and a link back, not a blank page.

### WP-10 and WP-11: build notes

- WP-11's deepagent gets exactly the five tools named in the architecture section; each tool is a thin wrapper over one API call or table lookup and returns the API's JSON unchanged. The agent's system prompt contains the reply rules verbatim and one instruction that overrides everything else: never state a number that is not in a tool result. LangSmith tracing on from the first working version, and one full trace exported for the Devpost before the freeze.
- WP-10's pitch script is written from the rehearsal claims only (the three claims the team has actually run end to end), and the Q&A card numbers are copied from the eval reports, not from memory.

### End-to-end checks (all must pass before the 03:00 freeze)

Rehearsal claims: (1) "Was Jensen Huang's mistress a Chinese spy?" (2) "Did bots defend Jensen Huang?" (3) one claim a teammate invents on the spot about the Huang week.

1. Text claim 1 from a phone that has never used the number: checking message within 5 s, full answer with chart and link within 30 s, every number in the text matches the `/claim` JSON exactly.
2. Open the link: the claim view shows the same narratives, shares and intervals as the text.
3. `show the bots` and `who shares it` return evidence and archetypes for claim 1 without a new search.
4. Dashboard on real data: replay scrubs Nov 5-13 with the three event markers; toggling bots off re-ranks the narrative bars; the threshold strip shows four values per narrative; every bar and card opens the evidence drawer; no private handle appears anywhere (check by grepping the built site data and page source for handles not in `public_accounts`).
5. Kill switch test: with the API stopped, the dashboard still demos the floor from `site_data.json` alone, and the backup recordings play.
6. Claim 3 (unrehearsed) completes through the corpus path or returns the insufficient-data reply; it never invents shares.

### Failure fallbacks (decided now, not during judging)

| Failure | Fallback |
|---|---|
| Photon/Spectrum down | Teammate's phone texts a teammate acting as the bot with the API open on the laptop; recordings if that fails too |
| API host or tunnel down | API runs on David's laptop via `cloudflared` (kept warm and tested at rehearsal, not first tried during judging) |
| Bluesky live path slow or 403 | Corpus claims unaffected; live claims return the insufficient/failure reply honestly |
| Bot model fails kill test 1 | Coordination clusters become the headline signal; shares reported from coordination membership, model scores demoted to the method view |
| Narratives fail kill test 2 | Demo narrows to the 3 largest hand-verified narratives and says so |
| Spread test null | Headline becomes the null result, per the kill test 3 wording |

### [contract] items in this pull request

1. `site_data.json`, per narrative: add `bot_post_share_by_threshold` (`{"0.3": 0.0, "0.5": 0.0, "0.7": 0.0, "0.9": 0.0}`) and `evidence` (up to 5 objects `{"text": "", "public_handle": null, "reasons": [""], "created_at": ""}`), replacing the free-text `examples` list. Archetypes gain the same `evidence` array shape. `README.md`'s data contract is updated in this same pull request, as its rules require.
2. `POST /xray` response: add `evidence_posts` (up to 5 objects, same shape as item 1's evidence) so the X-ray result opens the same evidence drawer as every other number.

## Proposals

Teammates and their agents add new demo ideas here, one short paragraph each, with what it adds to the judging criteria and what it costs. Isaac decides; accepted ones move into the sections above in a `[demo]` pull request.

## How to edit this file

- One master file. Don't create a second demo document; add to this one.
- Edit freely: your own work package's Status line and a Notes line under it.
- Pull request with `[demo]` in the title: anything in Vision, the demo script, components or the timeline.
- Pull request with `[contract]` in the title: any API shape, artifact path or table change. Update `README.md` in the same pull request if a table changes, and tell the team chat.
- Never delete someone else's content. Mark it `cut` with a one-line reason.
- Append a line to the changelog for every merged change.

## Changelog

- Sat 16:20: build specification added (global conventions, build order and gates, per-WP build steps, WP-6 pipeline and reply templates, end-to-end checks, failure fallbacks) plus two [contract] items: site_data evidence + threshold fields and /xray evidence_posts, with README updated in the same PR (Muse, for David).

- Sat 16:15: MVP scope section added: the floor, in/out boundaries per component, the three merge-note grafts scoped (evidence drawer and precomputed threshold strip in the MVP, challenge mode as Plan B and post-pitch), stretch order, explicit out list, and 18:00 / 01:00 acceptance checks (Muse, for David).

- Sat 16:10: tracks section (main track switched to Entertainment and Media; six special tracks), agent layer required as WP-11, Peri consultation in WP-10, voice line as WP-12 stretch (Hermes, for Isaac).
- Sat 16:05: file created from the README demo plan and the MVP walkthrough; Photon text-a-claim flow added as the live demo moment (Hermes, for Isaac).

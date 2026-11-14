# Demo architecture and vision (master file)

This is the one file for what we demo and how it is built. `README.md` holds the research question, data sources, rules and table schemas; this file holds the demo, the system architecture, the API contracts and the work packages. Every agent reads both before writing code.

How to edit this file is at the bottom. Short version: edit your own work package's status lines freely, append to the changelog, and put anything that changes the demo or a contract in a pull request with `[demo]` or `[contract]` in the title.

## Vision

Text a claim you heard, and get back who is pushing it, how much of that is automated, and what kinds of real people are spreading it.

We prove it first on the week Jensen Huang resigned from Nvidia (Nov 5 to 13, 2026: 46,656 Bluesky posts from 20,495 accounts), a story every judge knows and one where the Washington Post reported that "online bots" were defending him. The same engine then answers claims about any topic with a live Bluesky search.

What we never do: rule on whether a claim is true, say who runs an account, or name private people. We report which narratives carry the claim, the share of likely automated accounts behind each, what those accounts have in common, and which archetypes of real people amplify them.

Who would pay for this: newsrooms deciding whether a viral claim is worth covering, brand and social-listening teams, trust-and-safety teams, investor relations teams facing stock-moving rumors. Enterprise firms (Graphika, Cyabra, Blackbird.AI) sell analyst reports; a check anyone can run from a text message is the gap we claim (precedent check still to do).

Prizes this targets: Science and Discovery (main track), Arlequin Track 2 (content plus connectivity; recall@k on retrieval is named as a plus), Photon "Build a Messaging Agent using Photon 2.0" (winner $400 cash, $300 credits and a fast-track to Photon's final interview round; runner-up $200), and LangChain "Best use of deepagents" if the agent behind the text line is a deepagent.

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
6. Agent layer (optional, for the deepagents prize). If time allows, the logic between the messaging service and the API (decide corpus or live, call tools, handle follow-ups) becomes a LangChain deepagent with tools `search_claim`, `narratives_for`, `bot_share`, `amplifier_archetypes`, `coordination_evidence`. The API endpoints above stay the tools' backend either way.
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
- Outputs: `docs/pitch.md` (2-minute script, Q&A card), Devpost text, video
- First tasks: by 17:00 talk to Arlequin's people (what would impress them; does a text-a-claim check matter to their customers) and to Photon's booth (anything in the guidelines that affects eligibility; image attachments on the Spectrum number)
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

Cut order if behind: Reddit, then `/xray`, then the live path for other topics, then public account pages. The replay, bot share per narrative, archetype cards and the text-a-claim flow on the Jensen corpus stay.

## Kill tests

1. Bot model (18:00): recall@100 on held-out labeled bots of at least 0.3. If not, coordination becomes the main signal.
2. Narratives (18:00): 6 to 10 nameable clusters and at least 70% agreement with the first 50 hand labels.
3. Spread (18:00): bot post share in the most automated narrative at least twice that of the least automated one. If not, the headline is "automation is spread evenly, and the bots-defending-Huang claim does not show on Bluesky".
4. Retrieval (21:00): recall@20 of at least 0.6 on the first 20 hand-written claims.

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

- Sat 16:05: file created from the README demo plan and the MVP walkthrough; Photon text-a-claim flow added as the live demo moment (Hermes, for Isaac).

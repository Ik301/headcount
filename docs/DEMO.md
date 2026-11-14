# Demo architecture and vision (master file)

This is the one file for what we demo, how it is built, and who builds what. `README.md` holds the research question, data sources, rules and table schemas. `docs/COMMS.md` is where the two agents talk. Every agent reads all three before writing code.

How to edit this file is at the bottom. Short version: update your own work package's status lines freely, append to the changelog, and put anything that changes the demo or an interface through the other agent in `docs/COMMS.md` first.

## Vision

Text a claim you heard, and get back who is pushing it, how much of that is automated, and what kinds of real people are spreading it.

We prove it first on the week Jensen Huang resigned from Nvidia (Nov 5 to 13, 2026: 46,656 Bluesky posts from 20,495 accounts), a story every judge knows and one where the Washington Post reported that "online bots" were defending him. The same engine answers claims about other topics with a live Bluesky search.

What we never do: rule on whether a claim is true, say who runs an account, or name private people. We report which narratives carry the claim, the share of likely automated accounts behind each, what those accounts have in common, and which archetypes of real people amplify them. Every number on screen opens to the evidence behind it.

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
| Data (H1, H2) | Bluesky only: accounts, posts, history (last 50), interactions for likely-automated posts and top 500 human posts | No Reddit. No firehose or streaming; the Nov 5-13 window is fixed |
| Narratives (H3) | 6-10 named clusters over unique posts, sides assigned, 200 hand labels for accuracy | Term/LLM naming only; no reply-stance classifier (already first in the README cut order) |
| Bot model (M2) | One saved model scoring every account: profile + behavior features (lifetime posts/day, account age, follow ratios, posting-app mix) plus coordination signals (duplicate text, near-simultaneous reposts, shared links). Self-labeled bots are training/eval labels, never the output | No per-account public verdicts on private accounts; scores ship as shares and intervals. No graph neural anything; a regularized logistic model or gradient boosting that beats the 0.046 baseline on recall@100 is enough |
| Coordination (M3) | Clusters of accounts sharing exact or near-duplicate text, or reposting the same post within 60 seconds, sized and reason-coded for the evidence views | Exact/near-duplicate text and timing only; no stylometry, no cross-platform matching |
| Archetypes (M5) | 4-6 archetypes over real accounts that amplified likely-automated posts, lift vs matched controls with bootstrap intervals | Matched on narrative, time window, reach, activity and follower bucket; no follower-graph features beyond counts |
| Retrieval (H5, M6) | Corpus path: bge-small embeddings, cosine top 300, similarity floor from the eval set, grouped by narrative. Eval: 50 hand-written claims with recall@k | Live path is a stretch (see below), not required for the MVP demo |
| API (H4) | `/claim` (corpus mode), `/claim/{id}`, chart PNG, `/health`, reply rules enforced and tested, <20 s per corpus claim | `/xray` is a stretch. No auth, no rate limiting beyond a simple per-sender cap in the messaging layer |
| Messaging (H7) | Photon Spectrum text line: checking message, reply text, chart image, dashboard link; follow-ups `show the bots`, `who shares it`, `next`, `help`; per-sender last-claim state | Text only. One claim at a time per sender; a second claim queues with a "still checking" reply |
| Agent layer (H6) | Deepagent routing corpus vs live and calling the five named tools, LangSmith trace saved | The agent never writes numbers itself; every figure comes from an API tool result |
| Dashboard (H8 bare version, Isaac's UI) | Replay with event markers, narrative river, story-without-bots, archetype cards, claim view at `/claim/:id`, method and validation view | Runs locally for judging; static deploy is a stretch. Public account pages are cut (already last in the cut order) |
| Pitch (humans) | 2-minute script, Q&A card, Devpost with the four tracks selected | No landing page, no sign-ups |

### The three grafts from the merge note, scoped

Source: Muse's merge note (commit c48f0a3).

1. Evidence drawer: in the MVP. Every bar, archetype card, coordination cluster and X-ray result opens the posts behind the number: timestamps, duplicate traces, reason chips. On the text path this is the `show the bots` follow-up. This is the anti-slop feature, so it is not a stretch; H4 and H8 split the work (API includes example/evidence post IDs in `/claim` and `/xray` responses; dashboard renders them).
2. Threshold sensitivity strip: in the MVP, precomputed only. Screen 3 shows bot share per narrative at thresholds 0.3 / 0.5 / 0.7 / 0.9 from precomputed values in `site_data.json`, so a judge asking "is that just your cutoff?" gets an answer in one glance. A live slider that recomputes is a stretch, only after the floor is safe.
3. Challenge mode: Plan B and post-pitch, not in the 2 minutes. If the live text flow fails twice in rehearsal, the demo's live moment becomes challenge mode on the laptop (the judge labels 3 of the 20 frozen accounts, then sees the model's call and the evidence). After the pitch, a QR at the table runs the same mode; disagreements join the hand-label queue. Recordings of the text flow become Plan C.

### Stretch, in order (start only when the floor is verified working)

1. `/xray` endpoint and dashboard view (contract already in this file).
2. Live path for claims outside the Jensen corpus (<60 s target).
3. Live threshold slider on screen 3.
4. Static deploy of the dashboard.
5. Voice line, only after 01:00 and only if the text flow is stable.

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

Main track (exactly one allowed): Entertainment and Media. Its description lists "media literacy centered apps". Best Overall considers every project automatically.

| Track | Prize | What qualifies us |
|---|---|---|
| Arlequin AI Track 2 | AirPods for winners | content plus connectivity in every number; recall@k on bot detection and on claim retrieval |
| Photon: Build a Messaging Agent using Photon 2.0 | winner $400 cash, $300 credits, fast-track to Photon's final interview round; runner-up $200 | the text-a-claim line, live on a Photon Spectrum channel |
| LangChain: Best use of deepagents | Switch 2 for winners | the agent behind the text line is a deepagent; LangSmith traces as evidence |
| ChatOverflow Agent Leaderboard | $500, $250, $150, $100 raffle | every teammate's coding agent connected; no submission needed |
| Photon: Best Voice Agent (stretch, cut first) | $300 cash, $100 credits | the judge calls and says the claim; voice runs on an SMS number, not iMessage |

Not entered: Amazon, Peri, CoStar, Capital One Nessie, Best Hardware, Physical AI, Rookie.

## The 2-minute demo

Table setup: laptop with the dashboard, a monitor facing the judge if we can get one, and a printed QR code that opens Messages to our Photon number with "hi" filled in.

1. Opening (10 s). "Jensen Huang resigned on November 12. Bluesky had 46,656 posts about it from 20,495 accounts. How much of that was real?"
2. Replay (30 s), dashboard. The network grows hour by hour from Nov 5 to Nov 13. Each dot is an account; lines are reposts, quotes, replies and likes. Likely automated accounts glow red. A real account turns its archetype's color the first time it amplifies a red one. Markers: WSJ ouster report (Nov 11, 22:43 UTC), resignation (Nov 12, 13:55 UTC), the Post's bots report (Nov 12, 20:15 UTC). The narrative river runs underneath, each band shaded by its bot share.
3. The story without the bots (20 s), dashboard. Bars per narrative with bot share and interval, plus a strip showing the share at four score cutoffs (0.3, 0.5, 0.7, 0.9), so the result visibly doesn't depend on where we drew the line. A toggle removes likely automated accounts and their engagement, and the bars re-rank. The line we hope to say: "take out the automation and narrative X falls from second to fifth." If the ranking doesn't move, the bot share per narrative still answers the Post's claim.
4. Who carries the bots (20 s), dashboard. Archetype cards: plain label, size, lift over matched accounts with an interval, three defining features, public example accounts only.
5. The judge texts a claim (40 s), judge's own phone. They scan the QR code and text something like "Was Jensen Huang's mistress a Chinese spy?" Within about 20 seconds they get a text answer, a chart image and a link that opens that claim's view on the dashboard.

Every bar, card and cluster opens an evidence drawer: the posts, timestamps to the second, the coordination traces and reasons, the source and pull time.

Q&A card, not in the 2 minutes: bot model recall@k and ablation, claim retrieval recall@k, narrative accuracy on hand labels, data sources, privacy rules.

Fallbacks, in order: (1) challenge mode, a precomputed round where the viewer labels 20 frozen accounts "likely automated or not" and sees the model's score and reasons; it also runs as a table activity after the pitch, and judges' disagreements feed the hand-check queue; (2) recordings of three full text exchanges and of the replay.

### Example text exchange (numbers are placeholders)

> Judge: Was Jensen Huang's mistress a Chinese spy?
>
> Bot: Checking who is pushing that. About 20 seconds.
>
> Bot: I found 1,240 Bluesky posts making this claim (Nov 5 to 13). They fall into 3 narratives:
> 1. National security / spy plot: 62% of posts. Likely automated: 9% (6 to 12%), about 2x the story's baseline.
> 2. Defending Huang (smear campaign): 21%. Likely automated: 18% (13 to 24%).
> 3. Jokes and memes: 17%. Likely automated: 3%.
> The likely automated accounts pushing narrative 2: 41 were created in the same two weeks, and 14 reposted the same posts within a minute of each other.
> The real accounts spreading their posts are mostly "new accounts that mostly repost market news" (2.7x more likely than similar accounts).
> I don't judge whether the claim is true. Full view: <dashboard link>
>
> Bot: [chart image]

Follow-ups the bot understands: "show the bots" (coordination evidence), "who shares it" (archetypes as text), "next" (next narrative), "help".

## Architecture

```
            batch (Hermes runs it on the VM; Muse's modules plug in as code)
Bluesky AppView -> ingest -> narratives -> bot scores -> amplification + archetypes -> export
                    (Hermes)   (Hermes)     (Muse)          (Muse)                  (Hermes)
                                                                                       |
            artifacts: corpus embeddings, narrative centroids, bot model,              |
            archetype centroids, bot_scores, site_data.json                            v
Judge's phone -> Photon Spectrum -> messaging service (TS) -> deepagent -> analysis API (FastAPI)
                                        (Hermes)               (Hermes)     /claim, chart, /health
                                                                               |
                                    dashboard (Vite + React, reads site_data.json and /claim/{id})
                                    Hermes ships a bare working version; Isaac designs the UI
```

### Components

1. Batch pipeline (Python). Stages and tables are in `README.md`. Besides the Parquet tables it saves what the API loads at startup into `data/processed/artifacts/`: `corpus_embeddings.npy` with `corpus_index.parquet` (post_id, account_id, narrative_id, created_at), `narrative_centroids.npy`, the bot model, archetype centroids with the feature scaler, and `bot_scores.parquet`.
2. Analysis API (`src/api/`, FastAPI). Loads the artifacts once. Writes the reply text itself, so the privacy and wording rules are enforced in one place.
3. Claim retrieval (`src/retrieval/`). Embeds the claim with `BAAI/bge-small-en-v1.5` using its query prefix (`Represent this sentence for searching relevant passages: `), cosine top 300 over the corpus embeddings, a similarity floor tuned on the eval set, grouped by narrative.
4. Live path (`src/retrieval/live.py`). For claims outside the corpus: an LLM writes two or three search queries, `app.bsky.feed.searchPosts` pulls up to 300 recent posts, they are embedded and grouped (k-means, k up to 5, an LLM names the groups), and their authors are scored live (`getProfiles` 25 per call, `getAuthorFeed` limit 30; about 45 accounts a second measured). Target under 60 seconds.
5. Agent layer (`src/agent/`). A LangChain deepagent with tools `search_claim`, `narratives_for`, `bot_share`, `amplifier_archetypes`, `coordination_evidence`. Decides corpus or live search, runs the tools, handles follow-ups. LangSmith tracing on.
6. Messaging service (`src/messaging/`, TypeScript). Photon 2.0 through Spectrum (`spectrum-ts`, a Spectrum Cloud number). Receives a text, sends the "checking" message at once, calls the agent, then sends the reply, the chart image and the dashboard link. Per-sender state for follow-ups. Read Photon's hackathon guidelines first: https://somethingreat.notion.site/Hackathon-Guidelines-for-Photon-2-0-3f8e443f36bb81f9893fed0d08a4c01d (beta and $100 free credits at photon.codes/beta). Eligibility needs the project built on Photon 2.0 and live on at least one Photon channel. A shared iMessage line can't text first, so the judge starts from the QR code. Use only documented SDK calls.
7. Dashboard (`web/`, Vite, React, TypeScript, sigma.js, graphology). Reads `web/public/site_data.json` (shape in `README.md`, plus the `evidence` and `threshold_strip` fields below). Views: replay, narrative river, story without bots with the threshold strip, archetype cards, claim view at `/claim/:id`, public account pages, method and validation, challenge mode. Every view gets the evidence drawer.

### Module interfaces between the two halves

Muse's half plugs into Hermes's half as Python code, not as data files, because the data lives on the VM and Muse is not always online. Muse develops against its own local copy of the data (pulled with the repo's scripts) and pushes code plus evaluation reports. Hermes runs that code on the VM to produce the artifacts the API and dashboard use.

```python
# src/bots/score.py  (owned by Muse; Hermes ships a heuristic stub with the same signature first)
def load_model(path: str = "data/processed/artifacts/bot_model.joblib") -> object: ...
def score_accounts(model, profiles: list[dict], histories: dict[str, list[dict]],
                   story_posts: dict[str, list[dict]] | None = None) -> list[dict]:
    """profiles: getProfiles records. histories: did -> compact history items (src/ingest/bluesky_history.py format).
    story_posts: did -> that account's story posts (raw searchPosts records), when available.
    Returns one dict per account: {"did", "p_automated" (0..1), "reasons": [plain-language strings, top 3]}."""

# src/bots/coordination.py  (Muse)
def find_clusters(posts: list[dict], window_s: int = 60) -> list[dict]:
    """Returns [{"cluster_id", "dids": [...], "reasons": [...], "evidence": [{"post_uri", "t", "trace"}]}]."""

# src/archetypes/assign.py  (Muse)
def load_archetypes(path: str = "data/processed/artifacts/archetypes.joblib") -> object: ...
def assign(arch, profiles: list[dict], histories: dict[str, list[dict]]) -> list[dict]:
    """Returns [{"did", "archetype_id", "label"}]."""
```

Batch entry points Muse also provides, run by Hermes on the VM: `python -m src.bots.train` (writes the model and `eval/bots/report.md`), `python -m src.bots.score_corpus` (writes `bot_scores.parquet`), `python -m src.archetypes.build` (writes `archetypes.parquet`, `user_archetype.parquet`, the archetype artifact and `eval/thesis/report.md`).

Until Muse's versions land, Hermes's API uses `src/stubs/` with the same signatures, so integration never waits.

### API contracts

`POST /claim`, body `{"text": "...", "mode": "auto"}` (`auto`, `corpus` or `live`). Response:

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
      "example_posts": [{"text": "", "public_handle": null}],
      "evidence": [{"post_uri": "", "t": "", "note": ""}]
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

`GET /claim/{claim_id}` returns the same object. `GET /claim/{claim_id}/chart.png` returns the chart (one bar per narrative: share of matches, likely automated share overlaid). `GET /health` returns `{"ok": true, "artifacts_loaded": true, "bot_model": "stub" | "v<n>"}`.

`site_data.json` additions to the README shape: every narrative, archetype and coordination cluster gets `"evidence": [{"post_uri", "t", "note"}]`; every narrative gets `"threshold_strip": {"0.3": 0.0, "0.5": 0.0, "0.7": 0.0, "0.9": 0.0}`; a top-level `"challenge": [{"account_ref", "posts": [], "p_automated", "reasons": [], "hand_label"}]` with 20 frozen, hand-checked accounts (public accounts by handle, private ones as hashed refs with no handle).

### Reply rules (enforced in the API)

- Never name an account unless it is public under the README's rule (5,000+ followers, verified, a news organization, or self-labeled bot). Private accounts are counted only.
- "Likely automated", with a share and an interval, never "bots" for undisclosed accounts.
- No statement about who operates any account. "What they have in common" lists observable signals only: creation dates, posting app, shared links, reposting within seconds.
- No verdict on whether the claim is true, and say so in every reply.
- Fewer than 30 matching posts: say there isn't enough data instead of reporting shares.
- Decline claims that target a private individual by name.

### Hosting

The API runs on Isaac's VM, where the data is, exposed through a tunnel once Isaac approves it. The messaging service runs where Spectrum's guidelines say. The dashboard runs locally for judging.

## Work split

Two agents build the backend and integration. Isaac designs the UI once the features are working.

- Hermes: Isaac's agent on his VM. Holds the data, runs the batch pipeline, owns integration: API, agent, messaging, export, bare dashboard. Checks `docs/COMMS.md` every 20 minutes through the night.
- Muse: Isaac's teammate's agent. Not always online, so its half is the analysis modules that can be built and tested alone against a local copy of the data: the bot model, coordination, archetypes, and the independent evaluations. Its goal is below.
- Isaac: names the narrative clusters, hand-labels 200 posts and the 20 challenge accounts, signs up for Photon and LangSmith, and designs the UI on top of the bare dashboard.

### Muse's long-term goal

Build and validate the "who is automated, and who amplifies them" half of the analysis as importable modules (interfaces above), so that Hermes can run them on the full data and the demo can state, with measured accuracy, the likely automated share of each narrative and which archetypes of real people amplify those accounts. Work through the milestones in order; each one is useful on its own if the night ends early. Post in `docs/COMMS.md` when you start a session, when a milestone lands, and when you need something.

| # | Milestone | Done when |
|---|---|---|
| M1 | Local data: run `make data` (or the commands in README "Reproduce the data") to pull the story posts, profiles and histories, about 15 minutes | the three raw files exist locally and `python -m src.model.tables` builds the Parquet tables |
| M2 | Bot model v1: features from profiles, histories and story posts (posts per day, regularity of gaps, repost, reply and link shares, duplicate rate, account age, follower ratio, hour spread); positive-unlabeled training on the 285 self-labeled bots without the label or bio words as features; `src/bots/score.py`, `train.py`, `score_corpus.py` | `eval/bots/report.md` shows recall@50, 100, 200, 500 on held-out labeled bots; recall@100 of at least 0.3 (lifetime posts per day alone: 0.046) |
| M3 | Coordination: same URL within 60 s, repost of the same post within 60 s, near-duplicate text (MinHash, Jaccard 0.8 or more), TF-IDF weighted, cosine projection, threshold, components; reasons and evidence per cluster; fold into the score | ablation table (behavior only, coordination only, both) in the report; `find_clusters` returns evidence |
| M4 | Threshold strip and narrative bot shares: once Hermes posts `post_narrative.parquet` in COMMS, compute each narrative's likely automated share at 0.3, 0.5, 0.7 and 0.9 with bootstrap intervals | a function `src/bots/narrative_shares.py` that the export calls |
| M5 | Archetypes and the thesis test: amplifiers (humans who reposted, quoted or liked a likely automated post), matched controls (same narrative, 6-hour window, similar reach, activity and follower bucket), features from history, k-means k 4 to 8 by silhouette, plain labels, lift with bootstrap intervals, logistic regression; `src/archetypes/build.py` and `assign.py` | `eval/thesis/report.md` with lift per archetype and the regression table |
| M6 | Retrieval evaluation, kept independent of the builder: 50 claims about the story with the post IDs that truly match each (LLM-assisted candidates, then checked) in `eval/retrieval/claims.csv`; a script that scores any retriever with the `search_claim` signature | recall@10, 20, 50 and the best similarity floor reported in `eval/retrieval/report.md` |
| M7 | Challenge set: pick 20 accounts spanning the score range, write their evidence, mark which need Isaac's hand label | `data/sample/challenge.json` committed (no private handles) |

If you are blocked, post the blocker in COMMS and move to the next milestone. Never wait on Hermes.

### Hermes's work

| # | Milestone | Done when |
|---|---|---|
| H1 | Reproducible data: search re-pull, profile and history pullers, `src/model/tables.py`, `pyproject.toml`, `make data` | pushed before Muse's first session |
| H2 | Interactions: likers, reposters and quoters for every story post with engagement | `interactions.parquet` on the VM |
| H3 | Narratives: embeddings, clusters for Isaac to name, `post_narrative`, centroids, hourly river | Isaac has named them; `post_narrative.parquet` announced in COMMS |
| H4 | Stubs with Muse's signatures, then the API: `/claim`, chart, `/health`, reply rules with tests | `/claim` answers a corpus claim in under 20 s |
| H5 | Claim retrieval, corpus then live path | corpus under 2 s; live under 60 s |
| H6 | Agent layer: deepagent plus LangSmith | the messaging service calls the agent; one trace saved |
| H7 | Messaging service on Photon Spectrum | a real phone gets the full exchange |
| H8 | Export `site_data.json` and a bare working dashboard with every view and the evidence drawer | Isaac can start on the UI |
| H9 | Integration: run Muse's modules on the VM whenever they land, regenerate artifacts, end-to-end test, backup recordings | `/health` reports Muse's model version |

## Timeline (Sat Nov 14 to Sun Nov 15)

| Time | Milestone |
|---|---|
| 16:45 | H1 pushed; Muse can start M1 |
| 18:00 | API and bare dashboard running on stubs; narratives ready for Isaac to name |
| 21:00 | Muse M2 (bot model v1) merged and running on the VM; text line answering from the API |
| 23:00 | M3 coordination; dashboard on real data; Isaac starts the UI |
| 01:00 | M5 archetypes; agent layer live; everything feature-complete |
| 03:00 | feature freeze; Isaac's UI pass; evaluations final |
| 03:00 to 05:00 | rehearsal, challenge mode check, backup recordings |
| 06:30 | video, Devpost |
| 07:00 | submit (hard stop 08:00) |

Cut order if behind: Reddit, voice line, live path for other topics, public account pages, challenge mode. The replay, bot share per narrative, archetype cards, evidence drawer and the text-a-claim flow on the Jensen corpus stay.

## Kill tests

1. Bot model (21:00): recall@100 on held-out labeled bots of at least 0.3. If not, coordination becomes the main signal.
2. Narratives (18:00): 6 to 10 nameable clusters and at least 70% agreement with the first 50 hand labels.
3. Spread (22:00): the most automated narrative's likely automated share at least twice the least automated one's, holding across the four cutoffs. If not, the headline is "automation is spread evenly, and the bots-defending-Huang claim does not show on Bluesky".
4. Retrieval (23:00): recall@20 of at least 0.6 on Muse's claim set.

## Build specification (how each milestone gets built, end to end)

Written for the two agents. It elaborates the milestones and interfaces above without changing them: signatures, contracts and done-criteria stay exactly as written in the sections above and in `README.md`. Where a step here and a milestone disagree, the milestone wins for *done when* and this section wins for *how*.

### Global conventions (both agents)

- IDs and hashing per `README.md` (`account_id = sha256(SALT + did)[:16]`). Code runs with the dev salt `dev-salt` and a printed warning when `.env` is missing, so Muse's local runs and Hermes's VM runs produce comparable tables.
- Time is UTC everywhere, ISO 8601 in JSON. Story window 2026-11-05T00:00:00Z to 2026-11-14T00:00:00Z.
- Thresholds live in `src/config.py` only: headline share threshold 0.5; sensitivity strip 0.3 / 0.5 / 0.7 / 0.9; amplifier definition human `p_automated < 0.3`, likely automated `p_automated >= 0.7`; minimum 30 matched posts before any share is reported.
- Intervals: one shared bootstrap (`src/stats.py`, over accounts, 1,000 resamples, seed 42) used by M4, M5, H4 and H8, so the texts, the API and the dashboard can never quote different intervals for the same number.
- Bridged accounts (labels `bridged-from-bridgy-fed-*`) are reported separately in bot-share denominators (Hermes's kickoff note in COMMS); the export carries both denominators and the dashboard shows the unbridged one.
- Every batch entry point is idempotent, writes to a temp file then renames, and bumps `model_version` in `data/processed/artifacts/manifest.json`. `/health` reports the manifest's bot model version (`stub` until M2 lands), which is how H9 knows what is running.
- A milestone is `v0` when its smoke test passes on sample or stub data, `done` when its DEMO done-criteria are met on the full data. Status lives in COMMS's board, not in this file.

### Integration gates (in order; a gate is a check, not a time)

1. H1 (done Sat 16:13) -> Muse starts M1 unblocked. Hermes's stubs in `src/stubs/` carry Muse's signatures from the start, so H4/H8 never wait for M2/M5.
2. M2 v0 (score.py returning sane scores on the local pull) -> Hermes swaps the stub behind the same signature on the VM and posts the swap in COMMS.
3. H3 (`post_narrative.parquet` announced in COMMS) -> M4 and the dashboard river unblock.
4. M3 -> M5's amplifier definition uses coordination-folded scores; M5 does not start its final run on M2-only scores.
5. H4 + H7 end to end on stubs -> the text line is demoable before any real model lands; models then swap in behind the interfaces.
6. Freeze 03:00: after it, only fixes for a failing end-to-end check below.

### M1 Local data: notes

- Run `make data` exactly as in README "Reproduce the data". Verify the three raw files exist and `python -m src.model.tables` builds every Parquet table with zero schema errors before touching M2; a schema mismatch is a COMMS post to Hermes, not a local patch to `src/model/`.
- Keep the local pull: M6's evaluation and M7's challenge set are built from it, and every M2 experiment must be reproducible from it plus a seed.

### M2 Bot model v1: build steps

- Implement against the interface in this file: `src/bots/score.py` (`load_model`, `score_accounts`), `python -m src.bots.train`, `python -m src.bots.score_corpus`. Inputs are the raw-shaped records the interface specifies (getProfiles records, compact history items, story posts), not Parquet tables; Hermes adapts VM data to those shapes.
- Features, computed per account from the three inputs: posts per day over its history; regularity of posting gaps (coefficient of variation of inter-post times; scheduled accounts are very regular); repost, reply and link shares; duplicate rate (share of its posts that are near duplicates of its own or others' posts, MinHash Jaccard >= 0.8 on normalized text: lowercase, URLs and mentions stripped); account age at first story post; follower/follow ratio; has avatar; bio length (length only, never bio words); hour-of-day spread; distinct domains linked. The self-label and any text feature derived from the bio are excluded, per the kickoff note.
- Training: positives are the 285 self-labeled bots; unlabeled accounts are treated as negatives with the positive-unlabeled caveat stated in the report. Gradient boosting (sklearn `HistGradientBoostingClassifier` is enough) or regularized logistic regression; pick by held-out recall@100, not by accuracy. Stratified 80/20 split on labeled bots, seed 42.
- Reasons: top 3 per account, generated from the largest feature contributions mapped to plain phrases ("posts 40+ times a day", "created in the same week as 30 other high-scoring accounts", "most posts are reposts of market news"). Reasons must be computable for a single account at API time, because the live path and `/xray` call `score_accounts` directly.
- Report (`eval/bots/report.md`): recall@50/100/200/500 on held-out labeled bots, the posts-per-day baseline beside them (0.046 at k=100), class counts, feature list actually used, and the PU caveat. Kill test 1 reads this file.
- Hand-check protocol (feeds M7): the 50 highest-scored unlabeled accounts get a one-line verdict each in `eval/bots/handcheck.csv`; precision on that sample goes in the report. Verdicts never ship per-account in any output.

### M3 Coordination: build steps

- Implement `find_clusters(posts, window_s=60)` exactly as interfaced: traces are the same URL within 60 s, a repost of the same post within 60 s, or near-duplicate text (MinHash, Jaccard >= 0.8). Account-by-trace TF-IDF, cosine similarity, threshold 0.6 to start (tune once on the labeled bots' co-traces, then freeze it and record it in the report), connected components of size >= 2.
- Every cluster returns `reasons` and `evidence` (post_uri, t, trace) in the interface shape; the evidence drawer and the `show the bots` follow-up render these verbatim, so reasons are plain language at creation time, not codes.
- Fold into the score as features (cluster size, share of the account's traces that are shared, max cosine to another account), retrain, and add the ablation table to `eval/bots/report.md`: behavior only, coordination only, both. The Arlequin case rests on this table.

### M4 Narrative bot shares: build steps

- `src/bots/narrative_shares.py`, called by H8's export: per narrative, post share and distinct-account share at each strip threshold, expected count (sum of `p_automated`) so the headline does not hinge on the 0.5 line, and bootstrap intervals from the shared function. Output shape is the `threshold_strip` field in the API contracts section.
- Runs on whatever `bot_scores` and `post_narrative` exist; with stub scores it must still produce the full shape (H8 builds against it before M2 lands).

### M5 Archetypes and thesis: build steps

- Implement `src/archetypes/assign.py` (`load_archetypes`, `assign`) and `python -m src.archetypes.build` per the interfaces. Amplifiers: humans who reposted, quoted or liked a likely automated post (thresholds from `src/config.py`). Matched controls per the scope table: same narrative, same 6-hour window, similar reach of the post they engaged, matched on activity and follower bucket, without replacement; unmatched amplifiers are dropped from lift and counted in the report.
- Features from history only (the M2 feature set plus topic mix from the account's history posts assigned to narrative centroids, and active-hours pattern). Standardize; the scaler ships inside the archetype artifact because `assign` runs at API time.
- K-means k in 4..8 by silhouette; if every silhouette is under 0.05, use k = 4 and say so in the report. Labels are written from centroid summaries in plain behavioral words; no trait or demographic language.
- Report (`eval/thesis/report.md`): lift per archetype with bootstrap intervals, the logistic regression table (`amplified_bot ~ archetype + log(followers) + posts_per_day + narrative + hour`), match rate, and the null-result wording if no interval excludes 1.

### M6 Retrieval evaluation: build steps

- `eval/retrieval/claims.csv`: 50 claims written from the story posts (not from narrative labels), each with the post IDs that truly match; LLM-assisted candidate lists are allowed, every claimed match is human- or rule-checked before it enters the set. This set is the referee for H5's retriever, so whoever builds the retriever does not edit the set afterward; corrections go through COMMS.
- The scoring script takes any function with the `search_claim` signature and reports recall@10/20/50 per similarity floor (try 0.55 / 0.65 / 0.75); the chosen floor becomes a constant in `src/config.py` via a `[contract]` pull request citing `eval/retrieval/report.md`. Kill test 4 reads this report.

### M7 Challenge set: build steps

- 20 accounts spanning the score range (5 clearly automated including at least 2 self-labeled, 5 clearly human, 10 from the uncertain middle), each with 3-5 posts and the model's reasons as evidence. Isaac hand-labels the middle 10; disagreements between his labels and the model are the interesting ones and stay in the set, flagged.
- `data/sample/challenge.json` in the shape given in the API contracts section (`challenge` array). Public accounts by handle; private accounts as hashed refs with posts' text only. This file is committed, so the README privacy rule applies to it in full.

### H4 API: build steps (Hermes owns; specified here so both halves agree)

- `/claim` pipeline, in order, each step timed into `seconds`: (1) normalize the claim, `claim_id` = first 12 hex of sha256 of the normalized lowercase text plus mode; identical claims serve from cache, and each response is also written to `data/processed/claims/<claim_id>.json` so dashboard links survive a restart. (2) Private-individual check: a claim naming a person who is not a public figure in the corpus gets the decline reply with `matched_posts: 0`; when unsure, do not decline. (3) Retrieve; under 30 matched posts, return the insufficient-data reply with the true count, never padded shares. (4) Per narrative: share of matches, bot post share, interval, baseline, `example_posts` plus `evidence`. (5) `bot_commonalities` from observable signals only (creation-week concentration, shared traces, posting-app mix). (6) Amplifiers from M5's tables in corpus mode; live mode returns an empty mix rather than a guess. (7) Chart PNG per the contract. (8) `reply_text` composed from the templates below by code, never by an LLM; the deepagent (H6) routes and selects, but wording and numbers come from this step so the reply rules hold even if the agent misbehaves.
- Errors return `{"error": "<one human sentence>"}`; H7 turns any error into the failure template.

### Reply text templates (H4 composes, H7 sends verbatim)

Checking (sent by H7 immediately): `Checking who is pushing that. About 20 seconds.`

Main answer (percentages whole numbers, intervals as `9% (6 to 12%)`):

```
I found {matched_posts} Bluesky posts making this claim ({window}).
{narrative_lines}
{commonality_line}
{amplifier_line}
I don't judge whether the claim is true. Full view: {dashboard_url}
```

Narrative line: `{label}: {share}% of posts. Likely automated: {bot_share} ({lo} to {hi}%)`, appending `, about {x}x the story's baseline` when a narrative's bot share is at least twice the baseline. At most 4 narratives by share, then `+ {n} smaller narratives in the full view.`

Commonality line (only with at least 5 likely-automated accounts): `The likely automated accounts pushing {top_bot_narrative}: {signal_1}; {signal_2}.` Amplifier line (only when `n_humans >= 10`): `The real accounts spreading their posts are mostly "{archetype_label}" ({lift}x more likely than similar accounts).`

Insufficient data: `I found {n} Bluesky posts making this claim, which isn't enough to measure automation reliably (I need at least 30). Try a broader wording, or ask about the Jensen Huang story from Nov 5 to 13.`

Decline: `I can't run checks on claims about a private person. I can check claims about public stories, like the Jensen Huang week.`

Failure: `Something broke on my end and I couldn't finish that check. The team has a recording of a full check at the table.`

Follow-ups (per-sender state: last `claim_id`, narrative cursor): `show the bots` -> top 3 coordination clusters as text with reasons, plus 3 evidence posts; `who shares it` -> archetype lines with lift; `next` -> the next narrative's line and evidence, cycling; `help` -> `Text me a claim and I'll check who is pushing it on Bluesky. After an answer, try "show the bots" or "who shares it".` Anything else is a new claim.

### H7 Messaging and H8 Dashboard: build steps

- H7: send the checking template at once, then call H6 (or H4 directly until H6 lands). If the call passes 45 s, send `Still checking, the live search is slow on this one.` once; at 90 s, the failure template. State (sender -> claim_id, cursor) is in memory plus a JSON file rewritten on every message, so a restart loses at most follow-up context. Test the QR code from a phone that has never messaged the number before recording backups.
- H8: the export writes the full `site_data.json` shape with any subset of tables present (missing table -> empty section, never a crash), because it runs at every refresh. Replay precomputes per-hour cumulative node and edge sets in the export (cap: the 3,000 highest-engagement accounts, stated on the method view) so the browser never filters the full graph per frame. The evidence drawer is one component fed by the `evidence` arrays on narratives, archetypes and clusters; private accounts render as "a private account" with no handle. The threshold strip renders `threshold_strip` as four dots per narrative; the headline bar stays at 0.5 and nothing recomputes in the browser. The claim view shows the rules text and a link back when the API is unreachable, never a blank page.

### End-to-end checks (all must pass before the 03:00 freeze)

Rehearsal claims: (1) "Was Jensen Huang's mistress a Chinese spy?" (2) "Did bots defend Jensen Huang?" (3) one claim invented on the spot about the Huang week.

1. Text claim 1 from a phone that has never used the number: checking message within 5 s; full answer with chart and link within 30 s; every number in the text matches the `/claim` JSON exactly.
2. The link opens the claim view with the same narratives, shares and intervals as the text.
3. `show the bots` and `who shares it` answer for claim 1 without a new search.
4. Dashboard on real data: replay scrubs Nov 5-13 with the three event markers; the bots-off toggle re-ranks the bars; the strip shows four values per narrative; every bar and card opens the evidence drawer; challenge mode runs its 20 accounts. Privacy sweep: grep the built site data and the page source for any handle not in `public_accounts`; the count must be zero.
5. Kill-switch test: with the API stopped, the floor still demos from `site_data.json` alone and the recordings play.
6. Claim 3 (unrehearsed) completes through the corpus path or returns the insufficient-data reply; it never invents shares.
7. `/health` reports the real bot model version, not `stub`, and COMMS has the matching model-swap message from Hermes.

### Failure fallbacks (decided now, not during judging)

| Failure | Fallback |
|---|---|
| Photon or Spectrum down | A teammate sends the texts and a teammate with the API open answers as the bot; recordings if that fails too |
| API host or tunnel down | API runs on David's laptop via `cloudflared`, kept warm and tested at rehearsal, not first tried during judging |
| Live path slow or 403 | Corpus claims unaffected; live claims return the insufficient or failure reply honestly |
| Kill test 1 fails | Coordination becomes the headline signal; shares are reported from cluster membership and model scores move to the method view |
| Kill test 2 fails | The demo narrows to the 3 largest hand-verified narratives and says so |
| Spread test null | The headline is the null result, in kill test 3's wording |

## Proposals

New ideas go here, one paragraph each, with what they add to the judging and what they cost. Isaac decides.

## How to edit this file

- One master file. Don't create another demo or plan document; add to this one or post in `docs/COMMS.md`.
- Edit freely: your own milestones' status in COMMS's status board, and a Notes line here if needed.
- Anything that changes the demo, an interface or a contract: propose it in COMMS, wait for the other agent's acknowledgment (or 2 hours of silence), then change this file in a pull request with `[demo]` or `[contract]` in the title.
- Never delete someone else's content. Mark it `cut` with a one-line reason.
- Append a line to the changelog for every merged change.

## Changelog

- Sat 16:30: build specification added, adapted to the two-agent plan: global conventions, integration gates, build steps for M1-M7 and H4/H7/H8, reply text templates, end-to-end checks, failure fallbacks; README site_data aligned with the evidence / threshold_strip / challenge fields defined above (Muse, for David).

- Sat 16:40: Muse's MVP scope section (PR #5) folded in, mapped to H/M milestones; Peri item dropped with the track (Hermes).
- Sat 16:20: rewritten as the two-agent plan (Hermes and Muse), tracks cut to Arlequin, Photon, LangChain and ChatOverflow; Muse's three grafts from `merge-note-interactive-grafts.md` folded in (evidence drawer, threshold strip, challenge mode as first fallback); module interfaces added (Hermes, for Isaac).
- Sat 16:10: tracks section added.
- Sat 16:05: file created from the README demo plan and the MVP walkthrough; Photon text-a-claim flow added.

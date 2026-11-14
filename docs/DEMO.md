# Demo architecture and vision (master file)

This is the one file for what we demo, how it is built, and who builds what. `README.md` holds the research question, data sources, rules and table schemas. `docs/COMMS.md` is where the two agents talk. Every agent reads all three before writing code.

How to edit this file is at the bottom. Short version: update your own work package's status lines freely, append to the changelog, and put anything that changes the demo or an interface through the other agent in `docs/COMMS.md` first.

## Vision

Text a claim you heard, and get back who is pushing it, how much of that is automated, and what kinds of real people are spreading it.

We prove it first on the week Jensen Huang resigned from Nvidia (Nov 5 to 13, 2026: 46,656 Bluesky posts from 20,495 accounts), a story every judge knows and one where the Washington Post reported that "online bots" were defending him. The same engine answers claims about other topics with a live Bluesky search.

What we never do: rule on whether a claim is true, say who runs an account, or name private people. We report which narratives carry the claim, the share of likely automated accounts behind each, what those accounts have in common, and which archetypes of real people amplify them. Every number on screen opens to the evidence behind it.

Who would pay for this: newsrooms deciding whether a viral claim is worth covering, brand and social-listening teams, trust-and-safety teams, investor relations teams facing stock-moving rumors. Enterprise firms (Graphika, Cyabra, Blackbird.AI) sell analyst reports; a check anyone can run from a text message is the gap we claim (precedent check still to do).

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

## Proposals

New ideas go here, one paragraph each, with what they add to the judging and what they cost. Isaac decides.

## How to edit this file

- One master file. Don't create another demo or plan document; add to this one or post in `docs/COMMS.md`.
- Edit freely: your own milestones' status in COMMS's status board, and a Notes line here if needed.
- Anything that changes the demo, an interface or a contract: propose it in COMMS, wait for the other agent's acknowledgment (or 2 hours of silence), then change this file in a pull request with `[demo]` or `[contract]` in the title.
- Never delete someone else's content. Mark it `cut` with a one-line reason.
- Append a line to the changelog for every merged change.

## Changelog

- Sat 16:20: rewritten as the two-agent plan (Hermes and Muse), tracks cut to Arlequin, Photon, LangChain and ChatOverflow; Muse's three grafts from `merge-note-interactive-grafts.md` folded in (evidence drawer, threshold strip, challenge mode as first fallback); module interfaces added (Hermes, for Isaac).
- Sat 16:10: tracks section added.
- Sat 16:05: file created from the README demo plan and the MVP walkthrough; Photon text-a-claim flow added.

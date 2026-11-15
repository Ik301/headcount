# Devpost draft

Draft for the HackPrinceton Fall 2026 submission. Every number cites the repo file it comes from. Paths are relative to the repo root. Edit freely, and keep a number only if its source still says it.

## Project name

Chosen: **Headcount** (tagline: Volume is not consensus). Earlier options below.

1. **Who's Pushing This** (says what the tool answers)
2. **Volume Check** (short, matches the pitch line)
3. **Echo Count** (counts how many independent voices sit behind the volume)

## Tagline

Text it a claim you heard. It tells you how much of the online volume behind it comes from likely automated accounts, who spread it, and what accountable newsrooms reported.

## Inspiration

Online, volume passes for consensus. When thousands of accounts repeat a claim, reporters write "people are saying", markets react and readers believe it. AI agents now make that volume close to free to produce. When Jensen Huang resigned from Nvidia, the Washington Post reported "online bots" defending him within hours (PRODUCT.md).

A fact-check asks whether a claim is true. That is slow, and in the first hours often impossible to answer. We wanted the question that public data can answer in a minute: how many independent, real people are behind this claim, and who carried it to them? Our pitch line is "volume is not consensus".

## What it does

You give it a claim ("Was Jensen Huang's mistress a Chinese spy?") or any story, by text message or in the web checker. It:

- finds the matching Bluesky posts, from our corpus for the Jensen Huang week or from a live search for anything else;
- groups them into narratives, the different ways people tell the story;
- gives every account behind them an automation score from its behavior, and reports the likely automated share of each narrative with a 95% interval and a baseline;
- lists what the likely automated accounts have in common (posting at the same seconds, near-identical text, creation dates), as observable signals only;
- shows which kinds of real accounts amplified them, measured against matched accounts;
- puts the result next to what wire services and public broadcasters reported (the news baseline).

It never rules on whether a claim is true and never says who runs an account. Private accounts are counted, never named. Only accounts with 5,000+ followers, verified accounts, news organizations and self-labeled bots appear by handle (PRODUCT.md, docs/DEMO.md "Reply rules").

There are three surfaces:

- An iMessage line on Photon 2.0. A LangChain deepagent answers with a reply text, a chart and a link, and handles follow-ups ("show the bots", "who shares it", "next").
- A web claim checker for any story.
- A newsroom dashboard for the Jensen Huang week: an hour-by-hour replay of the network, the narratives with likely automated accounts removed, archetype cards, coordination clusters with exact timestamps, and the method.

## How we built it

**Data.** Everything comes from Bluesky's public API with no login. For the Jensen Huang week (Nov 5 to 13, 2026) we pulled 46,656 posts from 20,482 accounts, the last 50 posts of each account (1,007,723 history posts), and 380,164 likes, reposts and quotes on the story posts (README.md "Reproduce the data"; `data/processed` row counts). 287 accounts label themselves as bots (eval/bots/report-vm.md). `make data` rebuilds the whole set (README.md).

**Narratives.** DeepSeek labeled every one of the 40,197 unique post texts into 8 narratives with a side. A small embedding classifier trained on those labels serves the live path (docs/COMMS.md, Sat 17:55).

**Bot model.** Gradient-boosted trees over 38 behavior features: posting rhythm, volume, repost and link mix, self-repetition, profile and reception. Self-labels and bio words are never used as features. The model is trained as positive-unlabeled learning (Elkan and Noto, 2008), so the score estimates the chance an account is automated, not the chance it labeled itself. Each score carries its top three reasons in plain words (eval/bots/report-vm.md).

**Coordination.** Two accounts share a trace when they post the same link or repost the same post within 60 seconds, or post near-identical text. Accounts with similar trace patterns are linked, and linked groups become clusters with their evidence (docs/TEAM-BRIEF.md, eval/bots/report-vm.md).

**Amplifiers and archetypes.** Real accounts (score under 0.3) that engaged with a likely automated post (0.7 or more) are matched to similar accounts on narrative, 6-hour window, reach, activity and follower bucket. Both groups are clustered into behavior archetypes, with lifts and a regression (eval/thesis/report-vm.md).

**Claim retrieval.** A 50/50 hybrid of bge-small-en-v1.5 embeddings and TF-IDF over the corpus (eval/retrieval/report-hybrid.md). The live path writes 2 to 4 Bluesky searches with an LLM, embeds and clusters the matches, names the clusters, and scores the authors on the spot.

**News baseline.** Headlines from Reuters, AP, AFP, BBC, NPR, PBS, DW, France24, Al Jazeera and The Guardian, each labeled with its funding. 1,007 raw rows came down to 340 story headlines (eval/news/report.md).

**Serving.** A FastAPI analysis service writes every reply from templates in code, so the privacy and wording rules hold even if the agent misbehaves. The deepagent picks the tools and routes between corpus and live. Every figure it sends comes from a tool result. The web app is Vite, React and TypeScript.

**Two agents, one plan.** Two coding agents built the backend in parallel. Hermes, Isaac's agent on a VM that holds the data, ran ingest, narratives, the API, the agent, messaging, the export and integration. Muse, David's Claude Code, built the bot model, coordination, archetypes and the independent evaluations. They shared one plan file (docs/DEMO.md) and an append-only message file (docs/COMMS.md). Each agent owned its own folders. Hand-offs were fixed function signatures with stubs on the integrator's side. Code moved between them and data did not: Muse pushed modules and reports, and Hermes ran them on the full data on the VM. CI runs the test suite on every PR. Isaac designed the UI on top of the wired dashboard.

## Challenges we ran into

- No one hands you a list of bots. Self-labeled bots are mostly honest news and trend feeds, so the labels are incomplete and skewed. We treated unlabeled accounts as unlabeled, not human, and checked the top-scored unlabeled accounts by hand.
- Our own bar for the bot model was recall@100 of 0.3 on held-out labeled bots. A first run reached 0.272 on the README holdout and looked like a miss. One split turned out to be noisy (0.27 to 0.33 across splits), and a stricter test that holds out each bot operator's accounts together showed the model partly recognized networks it had trained on. Adding one account-maintenance signal (how long after creation the profile was last updated) fixed both: on the full VM data the README holdout is now 0.356 ± 0.016 over 5 splits, so the bar passes, and recall on operators the model never saw is 0.232 (eval/bots/report-vm.md, "Kill test 1").
- A first archetype result said new small accounts were 1.32 times as likely to amplify automation. After we matched on narrative, it dropped to 1.12 with an interval that includes 1. The effect came from the topic, not the person (docs/TEAM-BRIEF.md; eval/thesis/report-vm.md).
- Two modules defined "hedged headline" differently. We picked the news module's definition and re-derived every quoted number from it (docs/COMMS.md, Sat 18:25).
- Photon's free plan only accepts texts from registered senders, so the table QR opens a one-field `/join` page (docs/DEMO.md).
- In rehearsal, the language model behind the text line refused our own flagship claim, treating "mistress" as a private person. Declines now come only from the API's own check (docs/rehearsal.md).

## Accomplishments we're proud of

- **Bot model, full VM data.** Held-out recall@100 is 0.356 ± 0.016 (mean of 5 splits), against 0.045 for posting rate alone, about 8 times the obvious baseline, and 0.232 on bot operators the model never saw. Precision@50 against labels is 0.96 (eval/bots/report-vm.md). In a hand check of the 50 highest-scored accounts with no bot label, 46 were automated or likely automated (92%), mostly undisclosed news, RSS and market-data feeds (eval/bots/report.md, "Hand check"; the verdicts were made on the laptop run, whose top 50 differs from the VM's).
- **Coordination.** 574 accounts sit in coordination clusters, and labeled bots are 4.2% of them against 1.4% overall. Coordination adds little to finding disclosed bots (out-of-fold recall@100 of 0.275 behavior only against 0.279 with coordination), so we show clusters as evidence of accounts acting in lockstep, not as an accuracy claim (eval/bots/report-vm.md, "Ablation").
- **The finding.** Across the story, 4.5% of posts (3.1% to 6.2%) come from likely automated accounts. Automation concentrates in the narratives that relay news: board and succession at 7.7% (5.1% to 11.0%), 1.7 times the baseline. "Defending Huang" sits at 4.8% (2.0% to 8.7%), not different from the baseline. The ordering holds at all four score cutoffs (eval/bots/narrative_shares.md). The Post's "online bots defending Huang" does not show up on Bluesky.
- **The news baseline.** 54.4% of these outlets' spy headlines hedge ("alleged", "suspected", "claims"). Bluesky posts that share a link hedge at 49.8%, and posts in people's own words at 29.2%. The caution survives the share button and drops out in the retelling. All three "smear" headlines in the coverage attribute that framing to China (eval/news/report.md).
- **A mostly null result.** With 630 amplifiers and a 98% match rate, no group of real accounts was more likely than matched accounts to amplify likely automated posts (new small accounts 1.12, 0.79 to 1.40). One group was less likely: accounts that mostly quote-post, at 0.46 times (0.26 to 0.66). Archetypes re-cluster on every run and this result changed between model versions, so we treat it as exploratory (eval/thesis/report-vm.md).
- **Retrieval.** The hybrid retriever reaches recall@20 of 0.787 on the first 20 hand-checked claims and 0.646 on all 50, up from 0.575 and 0.507 for embeddings alone. The gold sets come from keyword rules, which favors TF-IDF (eval/retrieval/report-hybrid.md).
- **Speed.** In rehearsal, corpus claims answered in 0.3 to 0.9 s, and live any-story checks on three trending Bluesky topics in 15.8 to 25.5 s, all under our 60 s target (docs/rehearsal.md).

## What we learned

- Match on the obvious confounder before you believe a "who amplifies" effect. Ours vanished once we matched on narrative.
- Disclosed bots teach a model what honest automation looks like. Campaign-style accounts need other evidence, so we show coordination traces next to the scores and keep the two claims apart.
- Put safety rules in code, not in the prompt. The reply templates held, and the one prompt-level rule (decline private people) misfired on our flagship claim.
- One plan file, a message file and fixed function signatures let two agents build in parallel overnight without blocking each other.

## What's next

- Hand labels for the narratives (200 posts) and a VM re-check of the bot model's top 50.
- An independently written claim set for retrieval, since the current gold favors keyword search.
- Coordination detection aimed at campaign-style accounts, and a second platform where the full network is public.
- A dedicated Photon line, so anyone can text it without registering.
- A one-page report an editor can forward or cite.

## Built with

Python, FastAPI, polars, PyArrow, NumPy, scikit-learn (HistGradientBoosting), sentence-transformers (BAAI/bge-small-en-v1.5), UMAP, matplotlib, DeepSeek, LangChain deepagents, LangGraph, LangSmith, Photon 2.0 (photonhq-api), the Bluesky AppView API, Google News RSS and public broadcaster feeds, React, TypeScript, Vite, Cloudflare Tunnel, Playwright, pytest, GitHub Actions.

## Tracks to select

- Main track: **Entertainment and Media** ("media literacy centered apps").
- **Arlequin AI Track 2**: content and connectivity in every number, recall@k for bot detection and claim retrieval, and the behavior versus coordination ablation.
- **Photon: Build a Messaging Agent using Photon 2.0**: the text-a-claim iMessage line.
- **LangChain: Best use of deepagents**: the agent behind the text line, with LangSmith traces.
- **ChatOverflow Agent Leaderboard**: coding agents connected; nothing to submit.

## Links to fill in

- Repo: https://github.com/Ik301/socialnet-bot-tracker
- Demo video: (upload; backup clips are in `web/app/recordings/`)
- Try it: web checker URL, plus the `/join` QR for the text line

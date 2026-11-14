# PRODUCT.md

## What it is

A tool that answers one question about anything people are saying online: who is pushing this, how much of it is automated, and what kinds of real people are spreading it.

You give it a claim ("Was Jensen Huang's mistress a Chinese spy?") or a story ("the Nvidia CEO resignation"). It searches Bluesky through its public API, groups the posts into narratives (the different ways people are telling the story), scores every account behind them for signs of automation, finds the real accounts that amplify the automated ones, and groups those real accounts into archetypes (plain-language behavior groups like "new accounts that mostly repost market news").

Every number opens to its evidence: the posts, the timestamps, the reasons an account looks automated.

## What it never does

- Rule on whether a claim is true.
- Say who runs an account.
- Name private people. Only public accounts (5,000+ followers, verified, news organizations, self-labeled bots) appear by handle; everyone else is counted, never listed.
- Call an undisclosed account a "bot". The wording is "likely automated", with a score and reasons.

## Who it is for

- A newsroom editor deciding in five minutes whether a viral claim is worth covering, and how to frame it.
- A trust-and-safety or brand-safety analyst checking whether a spike is organic.
- An investor-relations or comms team facing a stock-moving rumor.
- Anyone curious, from their phone, in a text message.
- At the hackathon: a judge who has two minutes and will try their own story.

## How people engage (surfaces)

1. Text message (Photon iMessage line): text a claim, get a short answer, a chart image and a link. Follow-ups: "show the bots", "who shares it", "next".
2. Web claim checker: type any claim or story; a live check runs in under a minute and shows narratives, automated share and amplifier archetypes.
3. Analyst dashboard: one story in depth. Replay of the network over the week, narrative river shaded by automation, the story with automated accounts removed, archetype cards, coordination clusters, evidence drawer, method and validation.
4. In-context check: a badge or panel on a social post itself ("reach audit": how much of this post's reach is automated).
5. Shareable report: a one-page summary of a check that an editor can forward or cite.
6. Challenge mode: label 20 accounts "likely automated or not", then see the model's score and reasons. A table game for judges and a hand-labeling queue for us.

## Features (MVP)

- Any-story live check on Bluesky (search, narratives, automation scores, amplifiers) in under 60 s.
- Deep demo story: Jensen Huang leaving Nvidia, Nov 5 to 13, 2026: 46,656 posts, 20,482 accounts, 380,164 likes, reposts and quotes, 287 self-labeled bots.
- Narratives with a side (defends Huang, attacks Huang, neutral news, humor). Fixed taxonomy for the demo story: spy plot and national security; the affairs as personal misconduct; Trump and politics; board, resignation and succession; stock, market and lawsuits; defending Huang; jokes and memes.
- Likely-automated share per narrative with a 95% interval, a baseline, and a sensitivity strip at four score cutoffs (0.3, 0.5, 0.7, 0.9).
- "Story without the bots": the narrative ranking recomputed with likely automated accounts and their engagement removed.
- Coordination clusters: groups of accounts posting the same text or the same link within seconds, with reasons.
- Amplifier archetypes with lift over matched comparable accounts.
- Evidence drawer on every number.
- Replay: the network growing hour by hour with the real event markers (WSJ ouster report Nov 11 22:43 UTC, resignation Nov 12 13:55 UTC, Washington Post "online bots" report Nov 12 20:15 UTC).
- Method view: recall@k of the bot model, claim-retrieval recall@k, narrative accuracy, data sources, privacy rules.

## Voice

Plain, specific, calm. Numbers with intervals. No hype, no alarm, no "AI-powered". The product is a careful instrument, not a conspiracy board.

## Platform

Web (desktop first for the dashboard, mobile first for the claim checker and the join page), iMessage for the text line.

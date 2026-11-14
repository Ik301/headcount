# MVP walkthrough

The demo we are building toward, screen by screen, and how to compare it with other ideas before the lock. The plan, data contract and lanes are in the [README](../README.md).

## The MVP in one line

Paste any viral post and in about 20 seconds see how much of its reach is automated and which kinds of real people carried it, proven first on the week Jensen Huang resigned.

## Why this version

- The judge drives it. They pick the post, and the result is computed in front of them.
- It runs on a story every judge already knows, and it tests a public claim (the Washington Post's report that bots defended Huang).
- Both of Arlequin's layers are needed for every number on screen: what accounts post (content) and who they amplify and when (connectivity).
- It is a product with buyers: brand and social-listening teams, newsrooms deciding whether a viral post is worth covering, trust-and-safety teams, investor relations for stock-moving rumors. Enterprise firms like Graphika, Cyabra and Blackbird.AI sell analyst reports; a 20-second self-serve check per post is the gap we'd claim (precedent check still to do).

## Table setup

Laptop on the table and, if we can get one, a monitor facing the judge. A QR code lets the judge paste a Bluesky link from their own phone into the X-ray.

## Screen by screen

### Screen 0: opening (10 s)
"Jensen Huang resigned on November 12. Bluesky had 46,656 posts about it from 20,495 accounts. How much of that was real?" One button: Play the week.

### Screen 1: replay of the week (30 s)
- What the judge sees: the network grows hour by hour from Nov 5 to Nov 13. Each dot is an account; lines are reposts, quotes, replies and likes. Dots that behave like automation glow red. A real account turns its archetype's color the first time it amplifies a red one. Event markers sit on the scrubber: WSJ ouster report (Nov 11, 22:43 UTC), resignation (Nov 12, 13:55 UTC), the Post's bots report (Nov 12, 20:15 UTC). The narrative river runs underneath, each band shaded by its bot share.
- What's computed: precomputed. Each node carries its first-appearance time and each edge its time (likes, quotes and replies have timestamps; repost times come from the reposter's repost records for the top posts).
- Script line: written after we see the data. The goal is one sentence about what the red dots did around the events.

### Screen 2: the story with the bots removed (25 s)
- What the judge sees: bars for each narrative, sized by posts and engagement, with the bot share and its interval on each. A toggle removes likely automated accounts and their engagement, and the bars re-rank.
- The line we hope to say: "Take out the automation and narrative X falls from second to fifth." That is the non-obvious finding Arlequin's criteria ask for. If the ranking doesn't move, we say so, and the bot share per narrative still answers the Post's claim.
- What's computed: post-to-narrative assignment (content) joined with bot scores and the engagement graph (connectivity).

### Screen 3: who carries the bots (25 s)
- What the judge sees: four to six archetype cards. Each has a plain label ("accounts under six months old that mostly repost market news"), its size, its lift (how much more often it amplifies likely automated posts than matched accounts) with an interval, three defining features with numbers, and example public accounts only.
- What's computed: every amplifier is matched with a similar account that engaged with human posts of the same reach, narrative and time window; features come from each account's last 50 posts and profile; k-means; bootstrap intervals; a logistic regression for the Q&A card.

### Screen 4: Audience X-ray, live (40 s)
- What the judge sees: a box for any Bluesky post link plus a short list of posts trending right now. The judge picks one. Progress steps run on screen (audience pulled, accounts scored, clusters found). The result: share of the audience likely automated with an interval, against the typical share for posts on the same topic; the archetype mix of the real audience; coordination clusters with plain reasons ("14 accounts reposted within 40 seconds of each other; 9 were created the same week"); public accounts only by name.
- What's computed: up to 300 audience accounts from getRepostedBy, getQuotes and getLikes, their profiles (25 per call) and last 30 posts each. Measured today: 20,482 profiles in 20 s, and author histories at about 45 accounts a second, so the pull fits in roughly 10 to 15 s. Scoring is a saved model on a CPU, under a second. Archetypes by nearest centroid.
- Backup: recordings of three X-ray runs in case the Wi-Fi or the API fails.

### Q&A card (not in the 2 minutes)
Recall@k of the bot model on held-out labeled bots; the ablation (posting behavior only, coordination only, content only, combined); narrative accuracy on 200 hand labels; data sources; privacy rules.

## Where content and connectivity combine

1. The bot score: content signals (duplicate text, narrow topics, link spam) plus connectivity signals (accounts reposting the same post within seconds, sharing the same links, who they amplify).
2. The counterfactual on screen 2: narratives come from text; removing automation uses the engagement graph.
3. Archetypes: topic mix from each account's post history plus its position in the amplification network.

## Compute

CPU only. Small sentence embeddings (bge-small) for 46k posts take minutes. LLM calls only to name clusters and help with gold labels, a few dozen calls. The whole batch pipeline runs in under 30 minutes on one machine; the X-ray in under 20 seconds.

## Ground truth and honest risks

- 285 accounts in the story carry Bluesky's self-applied bot label: that is the test set. They are mostly news and trend bots, so the model learns posting behavior, and we hand-check the top-scored unlabeled accounts before claiming anything about influence.
- Lifetime posts per day alone puts only 5% of labeled bots in its top 100. The 18:00 bar is 30%.
- Interacting with bots is not believing them. The pitch says "more likely to amplify."
- Privacy: private users are hashed and counted, never listed; only public accounts are named.

## Scoring the ideas against each other

Score each idea 1 to 5 on each line, then lock by 16:30.

| Question | Source |
|---|---|
| Do both content and connectivity matter in the result? | Arlequin |
| Is the pipeline sound, with a metric like recall@k? | Arlequin |
| Does it reveal something non-obvious? | Arlequin |
| Is the visualization and demo explorable? | Arlequin |
| What is the "ah-ha" moment? | HackPrinceton creativity |
| Would someone use it this week? | HackPrinceton utility |
| Does it serve a real social need? | HackPrinceton charity |
| Can the judge touch it within 2 minutes? | our rule |
| Can four people and agents finish it by 07:00? | our rule |

Combining rule: screens 1 to 3 are the analysis base that any idea on this data needs. If the other idea has a better live moment, swap it in for screen 4 and keep the rest.

## Split after the lock

- David: bot model, coordination clusters, the X-ray backend.
- Brian: archetypes, matching and the thesis statistics, starting from v0 bot scores at about 21:00.
- Isaac: dashboard and replay through coding agents; names the narrative clusters and hand-labels 200 posts.
- Jeremy: Arlequin conversation on site by 17:00, pitch script, Devpost, video, backup recordings.
- Hermes (Isaac's VM agent): every data pull (profiles done; author histories running), narrative clustering, data drops at 16:30, 18:00, 22:00 and 01:00.

# Team brief: architecture, the model, and the pitch

For Isaac, David and the team. Read this before rehearsing. Numbers are from real runs on the VM on Sat Nov 14 unless marked otherwise; anything still pending is marked pending.

## The pitch in 30 seconds

Online, volume passes for consensus. When thousands of accounts repeat a claim, reporters quote "people are saying", markets move, and readers believe it. AI agents now make that volume almost free to manufacture. On the Jensen Huang story the Washington Post reported "online bots" defending him within hours of his resignation.

We built a tool that answers, in under a minute and from public data, the question a fact-check can't answer that fast: how much of this is real? Text it a claim, or type any story. It finds the posts on Bluesky, sorts them into the narratives people are pushing, scores every account behind them for automation, shows what the automated accounts have in common and which real people spread them, and puts it next to what wire services and public broadcasters actually reported. It never rules on whether a claim is true. It measures who is pushing it.

Line to land: volume is not consensus.

## The 2-minute demo

1. (10 s) "Jensen Huang resigned November 12. Bluesky had 46,656 posts about it from 20,482 accounts. How much of that was real?"
2. (30 s) Dashboard replay: the network builds hour by hour; likely automated accounts in red; the three events on the timeline (WSJ ouster report, resignation, the Post's bots report).
3. (20 s) The story without the bots: bars per narrative with the likely automated share; flip the toggle and the ranking changes. The cutoff strip shows the result does not depend on where we drew the line.
4. (20 s) The news baseline: 54% of these outlets' spy headlines hedge ("alleged", "suspected", "claims"). On Bluesky, posts that share a link mostly keep the headline's wording (50% hedge), but posts written in people's own words drop it: 29% hedge. The caution survives the share button and disappears in the retelling. The only "smear campaign" headlines in that coverage attribute the claim to Beijing.
5. (40 s) The judge texts or types their own claim, about Jensen or any other story, and gets the answer live.

Backup if the live part fails: the "Spot the automation" game on the laptop, then recordings.

## Architecture

```
Bluesky public API (no login)                 Wire + public broadcaster headlines
  search, profiles, author feeds,               Reuters, AP, AFP (via Google News RSS),
  likers, reposters, quoters                    BBC, NPR, PBS, DW, France24, Al Jazeera, Guardian
          |                                                  |
          v                                                  v
  1. Ingest: posts, accounts, histories, interactions      News baseline: headlines -> narratives,
          |                                                 hedging rate, which narratives are
          v                                                 only on social
  2. Narratives: every post sorted into 8 narratives               |
          |                                                        |
          v                                                        |
  3. Bot model: score every account 0..1 for automation            |
     + coordination clusters (accounts acting in lockstep)         |
          |                                                        |
          v                                                        |
  4. Amplifiers and archetypes: which real accounts spread         |
     the automated ones, grouped by behavior                       |
          |                                                        |
          +----------------------------+---------------------------+
                                       v
                         Analysis API (/claim, live any-story path)
                                       |
                 +---------------------+----------------------+
                 v                     v                      v
     LangChain deepagent       Web claim checker       Newsroom dashboard
     behind Photon iMessage    (any story, live)       (replay, evidence, method)
```

Who built what: Hermes (Isaac's agent on his VM) runs the data pipeline, narratives, API, agent, messaging, export and integration. Muse (David's agents) built the bot model, coordination clusters and the archetype and evaluation work. The two coordinate through `docs/COMMS.md`; the plan is `docs/DEMO.md`.

## How each piece works, in plain words

### 1. Data

All public, read-only, no login. For the Jensen week (Nov 5 to 13): 46,656 posts mentioning him, 20,482 accounts, the last 50 posts of every one of those accounts (about 1 million posts), and 380,164 likes, reposts and quotes on the story posts. `make data` rebuilds it from scratch in about 15 minutes. For any other story, the live path searches Bluesky at the moment you ask.

### 2. Narratives

A narrative is a way of telling the story. We fixed eight for the demo story: spy plot and national security; the affairs as personal misconduct; Trump and politics; board, resignation and succession; stock, market and lawsuits; defending Huang; jokes and memes; and no narrative (bare links, trend lists). An inexpensive language model (DeepSeek) labeled every one of the 40,197 unique posts with a narrative and a side (defends Huang, attacks Huang, neutral news, humor). A small classifier trained on those labels handles new posts quickly. Check against Isaac's 200 hand labels: pending.

For any other story, the live path finds the narratives itself: it groups the matching posts by meaning and the language model names each group in a few words.

### 3. The bot model (how it spots automation)

The problem: nobody hands you a list of bots. Bluesky lets accounts label themselves as bots, and 287 accounts in the story do. Those are our examples. They are mostly honest news and trend bots, and the labels are incomplete (the most active account in the data says it is a bot in its bio and has no label).

What the model looks at, per account (38 signals, all behavior, never the label or bio words):
- Rhythm: how regular the gaps between posts are, bursts, posting on the exact minute, posting around the clock.
- Volume: posts per day over its life and recently.
- Mix: share of reposts, replies, quotes and links; how many different sites it links to.
- Repetition: how often it repeats its own text or reuses the same opening.
- Profile: account age, followers versus follows, avatar, display name.
- Reception: how often its posts get zero engagement.
- Story activity: how much of its recent posting is about this story.

How it learns: a gradient-boosted tree model learns to tell the self-labeled bots apart from everyone else. Because "everyone else" includes undisclosed bots, it is trained as positive-unlabeled learning (Elkan and Noto, 2008): the raw score is rescaled so it estimates the chance an account is automated, not just the chance it labeled itself.

Every score comes with its top three reasons in plain words ("posts on the exact minute", "most posts are links to one site"), from a simple linear model fitted alongside.

Coordination (the connectivity half): two accounts share a trace when they post the same link within 60 seconds, repost the same post within 60 seconds, or post near-identical text. Accounts that share at least two traces, with similar overall patterns (TF-IDF cosine at least 0.6), are linked, and linked groups become coordination clusters (Pacheco et al., ICWSM 2021). On the Jensen data: 249 clusters covering 574 accounts; labeled bots are 3 times over-represented in them (4.2% against 1.4% overall).

How good it is (VM run, full data):
- Held-out test: we hide 20% of the labeled bots, train on the rest, and see where the hidden ones land among all 20,000 accounts. The model puts 27% of them in its top 100 (recall@100 = 0.272). Posting rate alone puts 4.5% there. That is 6 times better than the obvious baseline.
- Of its 50 highest-scored accounts, 82% are labeled bots.
- The undisclosed check: Muse's run hand-checked the 50 highest-scored accounts with no bot label; 45 of 50 were clearly automated (RSS and news feeds, mirrors, market-data feeds). That is the evidence that it finds automation the labels miss. (Muse's local run; re-check on the VM numbers pending.)
- Honest limits: our own pre-set bar was 0.3 at the top 100; the VM run, which is what the demo uses, reached 0.272. Muse's laptop run reached 0.333 on a slightly different fresh pull (46,605 posts against 46,656, different labeled-bot counts and history coverage), so quote the VM number. Some self-labeled "bots" are people joking, which caps any model. Coordination adds little to finding disclosed bots (0.236 to 0.243 at the top 100); labeled bots are 3 times over-represented in clustered accounts, and the clusters are shown as evidence of accounts acting in lockstep, not as a separate accuracy claim.

What a score means: an account at 0.87 behaves like the automated accounts we know about, for the reasons listed. It is not proof, and it never says who runs the account. That is why every screen says "likely automated" with an interval.

### 4. Amplifiers and archetypes

An amplifier is a real account (score under 0.3) that reposted, quoted or liked a post from a likely automated account (score 0.7 or more). We compare amplifiers with similar accounts that engaged with the story but not with automated posts, and group them by behavior into archetypes with a lift (how many times more likely than similar accounts). Result on the VM with narratives (642 amplifiers, 628 matched on narrative, 6-hour window, reach, activity and followers): no archetype is measurably more likely to amplify automated posts; every lift interval includes 1 (new small accounts 1.12, 0.91 to 1.38). Without narrative matching, new small accounts looked 1.32 times as likely; that effect was the narrative, not the person. Say this as a clean null result.

### 5. The news baseline

Ten outlets, each labeled with who funds it: Reuters, AP, AFP (no public feeds, so through Google News search, fine for a demo), BBC, NPR, PBS, DW, France24, Al Jazeera, The Guardian. 198 headlines about Huang in the window. None of them is neutral and none is "the truth"; they are accountable, edited and comparable. Findings: 54% of these outlets' spy headlines hedge ("alleged", "suspected", "claims"). On Bluesky, posts that share a link mostly keep the headline's wording (50% hedge), but posts written in people's own words drop it: 29% hedge. The caution survives the share button and disappears in the retelling. The only "smear campaign" headlines in that coverage attribute the claim to Beijing.

### 6. How the answer reaches people

- Text: Photon 2.0 iMessage line; a LangChain deepagent decides what to look up, calls our tools and replies; every number comes from a tool result, and the reply rules (no truth verdict, no names of private accounts, "likely automated") are enforced in code.
- Web claim checker: any story, live.
- Dashboard: one story in depth for journalists, with citable evidence.

## What the data says so far (VM, full data, bridged accounts excluded)

Across the story, 5.0% of posts come from likely automated accounts. By narrative:

| Narrative | Posts | Likely automated (95% interval) |
|---|---|---|
| Board, resignation and succession | 5,130 | 8.9% (6.5 to 11.7%) |
| Stock, market and lawsuits | 3,263 | 7.8% (5.1 to 10.5%) |
| Spy plot and national security | 8,698 | 7.0% (5.1 to 9.3%) |
| The affairs as personal misconduct | 4,205 | 6.8% (4.3 to 9.8%) |
| Trump and politics | 3,733 | 3.6% (2.1 to 5.2%) |
| Defending Huang | 1,457 | 3.4% (1.9 to 5.5%) |
| Jokes and memes | 10,435 | 0.5% (0.3 to 0.6%) |

The finding: on Bluesky, automation is not defending Huang. It concentrates in the narratives that relay news (board, market, spy plot), at up to 1.8 times the baseline, while posts defending him are 3.4% likely automated, not clearly different from the 5.0% baseline. The Washington Post's "online bots" defending him (reported on X) do not show up on Bluesky. Caveat to say out loud: the model learned from self-labeled bots, which are mostly news-relay feeds, so it is best at that kind of automation; campaign-style accounts show up through the coordination evidence. The ranking holds at all four cutoffs.

## Why it fits each prize

Arlequin Track 2 (content and connectivity):
- Both layers matter: narratives and repetition come from content; coordination, amplification and the replay come from who interacts with whom. The ablation is in the method view.
- Sound pipeline with metrics: recall@k on held-out bots against a baseline; claim retrieval recall@20 = 0.577 on Muse's first 20 hand-checked claims (an embedding plus keyword hybrid reaches 0.785, being adopted); narrative agreement with hand labels pending.
- Non-obvious insight: the hedge survives when people share a link and disappears when they retell it in their own words; automation relays news instead of defending Huang; no type of real account stands out as an amplifier once you match on narrative.
- Efficient compute: CPU only, small embedding model, one cheap language-model call per 25 posts; a live check runs in under a minute.
- Responsible data: public API only, read-only, private accounts never named, no truth verdicts.

Photon: an agent people text from their own phone, with safety behavior built in (refuses claims about private people, says what it does not know).

LangChain: the agent behind the text line is a deepagent with tools, traced in LangSmith.

ChatOverflow: connected; nothing to submit.

Main track: Entertainment and Media ("media literacy centered apps").

## Words to use and avoid

Say: "likely automated", "with a 95% interval", "what these newsrooms report", "amplified", "accounts acting in lockstep".
Avoid: "bots" for undisclosed accounts, "fake", "the truth", "neutral sources", "run by", any name of a private account.

## Hard questions, short answers

- How do you know they are bots? We don't claim to. Each account gets a score from 38 behavior signals, trained on accounts that admit to being bots, with its reasons shown. 45 of the 50 top-scored unlabeled accounts were clearly automated when checked by hand.
- Isn't the training data biased toward honest bots? Yes, and we say so. That is why we report recall on disclosed bots, hand-check undisclosed ones, and show coordination evidence separately.
- Did you just pick the cutoff to get the headline? The cutoff strip shows every number at four cutoffs.
- Why Bluesky and not X? Bluesky's full network is public and free; X charges per post and per follower. The method is platform-agnostic.
- Who decides which news outlets count? We use wire services and public broadcasters, label each with its funding, and never call them the truth.
- Could a bad actor use this? It is a defensive tool: it measures and explains, it never posts, and it never names private people.

## Status (update before rehearsal)

Done: data, narratives (all posts labeled), bot model and coordination on the full data, claim API, agent, Photon service, news headlines, six mockups.
In progress tonight: live any-story path, dashboard data export, news matching, wired web app, archetypes, retrieval evaluation, Photon line activation (needs a dedicated line from Photon's booth for instant texting).

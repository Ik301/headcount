# Shared mockup brief (all directions)

Read `PRODUCT.md` at the repo root first. This file is the shared brief every mockup follows so the directions compare on one variable: how the person engages. Palette, type and sample data are identical across mockups.

## Rules from Isaac

- Use the `impeccable` skill for all UI design work (load it, run `sh /home/ubuntu/.hermes/skills/creative/impeccable/scripts/impeccable context` from the repo root, read its craft floor before writing UI, run its `detect` on your file at the end).
- Mockups use sample data only, labeled once on the page: "Mockup with sample data."
- Each mockup is one self-contained HTML file (inline CSS and JS; Google Fonts allowed) that opens directly in a browser.
- Plain, specific, calm copy. Numbers with intervals. Never "bots" for undisclosed accounts: "likely automated". Never a verdict on whether a claim is true. Private accounts are never shown by handle (show "a private account" or a hashed ref like `acct·3f9a`); public accounts (news orgs, large accounts, self-labeled bots) may show by handle.

## Shared visual world: "careful instrument"

A measuring instrument for public conversation: closer to a well-made scientific or newsroom tool than to a SaaS dashboard or a conspiracy board. Light paper background, ink text, hairline rules, generous numerals, one signal color reserved strictly for "likely automated".

Tokens (use exactly these):

```
--paper:   #F7F5F0   (page background, warm off-white)
--card:    #FFFFFF
--ink:     #16181D   (primary text)
--ink-2:   #4A4F5A   (secondary text)
--ink-3:   #8A8F99   (tertiary, captions)
--rule:    #E3DFD6   (hairlines, borders)
--signal:  #D9472B   (likely automated ONLY; never decoration)
--signal-wash: #FBE6E0
--human:   #2F6F8F   (real accounts / amplifiers)
--human-wash: #E3EEF3
--n-spy:      #6B5CA5   narrative colors (muted, distinct)
--n-affairs:  #B0675A
--n-politics: #3E7C6A
--n-board:    #8C7A3D
--n-market:   #4F6FA8
--n-defend:   #A0527F
--n-jokes:    #8A8F99
```

Type: "Newsreader" (Google Fonts) for headlines and big numbers, "IBM Plex Sans" for UI text, "IBM Plex Mono" for counts, timestamps and IDs. Tabular numerals for all numbers.

## Sample data (use these numbers; they are sample data)

Demo story: Jensen Huang leaving Nvidia, Nov 5 to 13, 2026. 46,656 Bluesky posts, 20,495 accounts, 380,164 likes, reposts and quotes. Baseline likely-automated share across the story: 4.1%.

Events: Nov 5 congressional briefing request; Nov 8 Huang admits affair, board probe; Nov 11 22:43 UTC WSJ reports board preparing to oust him; Nov 12 13:55 UTC resignation, CFO Colette Kress interim CEO; Nov 12 20:15 UTC Washington Post reports "online bots" defending him.

Claim checked: "Was Jensen Huang's mistress a Chinese spy?" 1,240 matching posts, 3 narratives:

| Narrative | Share of matching posts | Likely automated | 95% interval |
|---|---|---|---|
| Spy plot and national security | 62% | 9% | 6 to 12% |
| Defending Huang | 21% | 18% | 13 to 24% |
| Jokes and memes | 17% | 3% | 1 to 5% |

Threshold strip for "Defending Huang" at cutoffs 0.3 / 0.5 / 0.7 / 0.9: 27% / 18% / 11% / 6%.

With likely automated accounts removed, "Defending Huang" drops from 21% to 15% of matching posts.

What the likely automated accounts pushing "Defending Huang" have in common: 41 created within the same two weeks (Oct 20 to Nov 2); 14 reposted the same 6 posts within 60 seconds of each other; 22 post more than 60 times a day.

Coordination cluster example (evidence): 14 accounts, identical text "The smear campaign against Jensen is a gift to Beijing. Wake up.", posted between 2026-11-12T20:31:04Z and 20:31:58Z.

Amplifiers: 2,316 real accounts reposted, quoted or liked posts from likely automated accounts. Archetypes (lift = how much more likely than matched similar accounts):

| Archetype | Share of amplifiers | Lift (95% interval) |
|---|---|---|
| New accounts that mostly repost market news | 31% | 2.7x (2.1 to 3.4) |
| Heavy reposters, mostly politics | 24% | 1.9x (1.5 to 2.3) |
| Tech-industry posters with large followings | 12% | 0.8x (0.6 to 1.1) |
| Conversational posters (mostly replies) | 33% | 0.6x (0.5 to 0.8) |

Public accounts you may name: `@reuters.com`, `@wsj.com`, `@nytimes.com`, `@nowbreezing.ntw.app` (a self-labeled trend bot).

Second story for the "any story" live check (sample): claim "Is the new NYC congestion toll being repealed?" 412 matching posts in the last 72 hours, 4 narratives found live (names written by the system): "Toll repeal rumor", "Court ruling coverage", "Driver complaints", "Transit funding defense"; likely automated share 6% overall, highest in "Toll repeal rumor" at 14% (9 to 20%). Live check took 41 seconds: searching (6 s), grouping into narratives (9 s), scoring 380 accounts (22 s), finding amplifiers (4 s).

Validation numbers for method views (sample): bot model recall@100 on held-out labeled bots 0.58; claim retrieval recall@20 0.71; narrative labels agree with hand labels 84% of the time.

# Headcount: Devpost submission fields

Paste-ready text for each Devpost field. Numbers are the locked set (sources in docs/devpost.md).

## 1. Elevator pitch (limit 200 characters)

Recommended (185):

```
Text Headcount a claim you heard. It finds the Bluesky posts behind it, scores the accounts for automation, and sets the result next to what newsrooms reported. Volume is not consensus.
```

Alternate A (188):

```
Headcount measures how much of the online volume behind a claim comes from likely automated accounts. Text it a claim and get shares, intervals and the newsroom baseline in under a minute.
```

Alternate B (194):

```
The Post reported online bots defending Jensen Huang. On Bluesky, those posts were 4.8% likely automated, no different from baseline. Headcount checks any claim by text. Volume is not consensus.
```

## 2. Project story

```markdown
## Inspiration

Online, volume passes for consensus. When thousands of accounts repeat a claim, reporters write "people are saying," markets react, and readers believe it. AI agents have made that volume close to free. When Jensen Huang resigned from Nvidia, the Washington Post reported that "online bots" were defending him.

A fact-check is slow, and in the first hours often impossible. We wanted the question public data can answer in a minute: how many of the accounts behind this claim look automated?

Our first idea, Narrative Range, was an open training range for information operations. A tool that generates campaigns helps whoever wants to run one, so we turned it around. Headcount measures campaigns and generates none.

## What it does

You text a claim to an iMessage line, or type it into the web checker. Headcount finds the matching Bluesky posts (from our corpus of 46,656 posts from 20,495 accounts, Nov 5 to 13, 2026, or from a live search for any other story), groups them into narratives, scores each account for automation, and reports the likely automated share of each narrative with a 95% interval and the story-wide baseline. It sets the result beside what wire services and public broadcasters reported.

The text reply leads with the whole claim. For "Was Jensen Huang's mistress a Chinese spy?" it says 2% of the 443 matching posts come from likely automated accounts, against 4.5% for the story overall. The web checker leads with the largest narrative it can measure, here the spy plot at 4%, which is not clearly different from the baseline. Headcount never rules on whether a claim is true and never says who runs an account. Private accounts are counted and never named.

## How we built it

DeepSeek labeled all 40,197 unique post texts into narratives, each with a side, and a small embedding classifier trained on those labels serves the live path. Claim retrieval mixes embeddings and TF-IDF (recall@20 of 0.787 on the first 20 hand-checked claims, 0.646 on all 50). For each of the 20,482 accounts that returned a profile we compute 39 behavior features and 3 coordination features. Accounts that post the same link, repost the same post within 60 seconds, or post near-identical text are linked into clusters: 574 accounts fall into 249 of them.

Nobody hands you a list of bots. Only 287 accounts label themselves as bots, and they are mostly honest news feeds. So the model is positive-unlabeled: self-labeled bots are the positives, everyone else is unlabeled, and the label and bio words never enter the features. A classifier of "is labeled" is rescaled into an estimate of automation (Elkan and Noto, 2008):

$$P(\text{automated} \mid x) = \frac{P(\text{labeled} \mid x)}{c}, \qquad c = \text{mean score of held-out labeled bots}$$

We hide some labeled bots and count how many land in the top $k$:

$$\text{recall@}k = \frac{|\text{top-}k \cap \text{held-out bots}|}{|\text{held-out bots}|}$$

Recall@100 is 0.356 ± 0.016 (mean of 5 splits), against 0.045 for posting rate alone. On bot operators the model never saw, it is 0.232. In a hand check of 50 top-scored unlabeled accounts from our laptop run, 46 were automated or likely automated.

Every share has a bootstrap interval that resamples accounts, since one account's posts are not independent. Account $i$ has $n_i$ posts, $y_i$ of them flagged (score at least 0.5). For each of $B = 1000$ resamples $b$ of the accounts,

$$\hat{s}^{(b)} = \frac{\sum_{i \in b} y_i}{\sum_{i \in b} n_i}$$

and the 95% interval runs from the 2.5th to the 97.5th percentile. A FastAPI service writes every reply from templates in code, and a LangChain deepagent routes between corpus and live search.

## What we found

Across the story, 4.5% of posts (3.1% to 6.2%) come from likely automated accounts.

- Defending Huang: 4.8% (2.0% to 8.7%), not different from the baseline. The "online bots" the Post described do not show up on Bluesky.
- Jokes and memes: 0.4%, clearly below the baseline.
- Board and succession has the highest point estimate, 7.7% (5.1% to 11.0%). Its interval overlaps the baseline, so we call it suggestive, not a clear difference.

The clearest result is how much newsroom caution survives. We count how often a spy-related text contains a hedge word such as "alleged," "suspected" or "claims":

$$h = \frac{\text{hedged texts}}{\text{all spy-related texts}}$$

Newsroom headlines hedge 54% of the time, Bluesky posts that share a link 50%, and posts in people's own words 29%. The measure is lexical, so a dismissive "these claims are nonsense" counts as a hedge. We also looked for a kind of real account that amplifies automation more than matched accounts do. Among 630 amplifiers (616 matched) we found none.

## Challenges we ran into

- The agent refused our own flagship claim. In rehearsal the language model behind the text line declined "Was Jensen Huang's mistress a Chinese spy?" as a claim about a private person. Declines now come only from the API's own check, and code writes the replies.
- The numbers moved. After the full rerun on the VM, recall@100 went from about 0.27 to 0.356 and the hand check from 45 of 50 to 46. The hand check used the laptop run's list, and a re-check on the VM list is pending.
- An effect vanished. New small accounts looked 1.32 times as likely to amplify automation. Matched on narrative, the lift fell to 1.12 (0.79 to 1.40), an interval that includes 1.
- Our headline overstated its interval. We first wrote that board and succession ran 1.7 times the baseline. Our red-team review showed that 5.1% to 11.0% overlaps the baseline's 3.1% to 6.2%, so we reworded it as suggestive.
- Privacy. 709 story accounts that opted out of logged-out viewing could be named in our export. We made the opt-out label win, then swept the exports independently of our own flag: 301 opted-out handles before the fix, 0 after.
- Photon. The free plan only accepts texts from registered senders, so the table QR opens a one-field page that registers a judge's number.

## Accomplishments we're proud of

- Live checks of any story in 13 to 26 seconds, and corpus claims in under a second.
- Honest nulls and wide intervals reported as such, with every number traceable to a file in the repo.

## What we learned

Match on the obvious confounder before you believe a "who amplifies" effect, and keep safety rules in code: the templates held, and the one rule we left to the prompt misfired on our flagship claim.

## What's next

Hand labels for 200 narrative posts, a VM re-check of the bot model's top 50, an independently written claim set for retrieval, coordination detection aimed at campaign-style accounts, and a dedicated Photon line so anyone can text without registering.
```

## 3. Technology feedback

One short review per technology.

```markdown
**Photon iMessage API (Photon 2.0 Beta, photonhq-api).** A real iMessage conversation driven from a Python client: one project key, and replies reuse the incoming space. It does what the prize asks for. Gripes: the shared line only accepts registered senders, so a judge can't text it cold (we built a /join page for that), and uploadAttachment needs an exact two-part body (JSON metadata, then the bytes) that we found by trial. A documented example that sends an image would have saved us time.

**DeepSeek API.** We used it to label 40,197 post texts into narratives and to translate challenge posts. Its labels were consistent enough that a small embedding classifier trained on them agrees with them 70% of the time. Gripe: in the texting agent, the model refused our flagship claim by treating "mistress" as a private person, so we stopped trusting prompt-level safety rules and moved declines into code.

**LangChain deepagents and LangSmith.** deepagents gave us tool routing between our corpus and live search with little glue, and the agent stays thin because the API writes the replies. Suggestion: a built-in way to mark a tool result as the final reply text would help, since we had to enforce "send the API's text verbatim" ourselves. LangSmith tracing is on for the agent.

**Bluesky AT Protocol public API.** No login and no key, and the network is readable: posts, quotes, likers, reposters, author feeds. That is why we chose it over X, which charges per post and per follower. Gripe: privacy preferences live in labels that the client has to honor. 709 accounts that had opted out of logged-out viewing were nameable in our first export until we made the !no-unauthenticated label win.

**ElevenLabs.** We used it for the demo video's voiceover and music bed. We compared two neutral voices, River and Eric, because a neutral voice suits a product that avoids hype. A voiceover script of about 1,700 characters uses roughly 1% of the 158,499 monthly allowance.

**Vercel.** The web app (/, /story, /challenge, /claim/id) is served from Vercel on demoyk.com, and we checked every route after deploy. Gripe: the API has to stay on our VM, because live checks take 13 to 26 seconds and need our model files, so we ran two deployments and had to rebuild and re-export after every data change.

**Cloudflare Tunnel.** It put the VM's API on the internet without opening a port, and it stayed up while we restarted the API. Gripe: a quick tunnel gets a new random trycloudflare.com URL whenever it restarts, and our deployed web bundle pointed at the old one, so a restart means a rebuild and redeploy.

**Claude Code and AI coding agents.** Two agents (Hermes on the VM, and David's Claude Code, Muse) built the backend in parallel through a shared plan file and an append-only COMMS.md, each owning its own folders. The cross-review was the useful part: Muse's checks found stale numbers in our docs and a privacy leak our own sweep missed, because the sweep trusted the same flag as the export. Gripe: permission settings stopped one agent from merging PRs in the other's folder, so four privacy-fix PRs sat open while we prepared an export.

**GitHub Actions.** CI ran pytest on every PR, and "merge when green" let two agents move without waiting for a human. Gripe: we kept CI to light dependencies (no torch), so the embedding path is not covered and we checked that one by hand.
```

## 4. Did you implement a generative AI model or API in your hack this weekend?

Yes.

```text
Yes. DeepSeek labeled all 40,197 unique post texts into narratives with a side, and it powers the texting agent (tool routing, live-search queries, challenge-post translations). ElevenLabs made the demo video's voiceover and music. AI coding agents (Claude Code) helped write the code.
Generative AI never computes a number. Bot scores, likely automated shares, intervals, coordination clusters and the answer text come from our own models, a bootstrap and templates in code, so the agent can only pass along figures from a tool result. It never rules on whether a claim is true.
```

## 5. Built with

Python, FastAPI, polars, PyArrow, NumPy, scikit-learn, sentence-transformers (bge-small-en-v1.5), UMAP, matplotlib, DeepSeek, LangChain deepagents, LangGraph, LangSmith, Photon 2.0 (photonhq-api), Bluesky AT Protocol, ElevenLabs, React, TypeScript, Vite, Vercel, Cloudflare Tunnel, Playwright, pytest, GitHub Actions, Claude Code

## 6. Other form fields

- Try it out links: https://demoyk.com (web checker at /, story at /story, game at /challenge); https://github.com/Ik301/headcount
- Video demo link: PLACEHOLDER (YouTube or Vimeo URL after upload; backup clips are in `web/app/recordings/`)
- Tracks to select: Entertainment and Media (main); Arlequin AI Track 2 (content and connectivity); Photon (messaging agent); LangChain (deepagents); ChatOverflow Agent Leaderboard (nothing to submit)
- Team members: Isaac Kang (Ik301), David (DHyukjuK), ch4nbin, [fourth teammate]
- Image gallery: the claim card PNG (`/claim/<id>/chart.png`), the post sorter, the story dashboard, the architecture diagram (docs/architecture.html)
- Judge instructions for the text line: scan the table QR, enter your iMessage number on /join, then text a claim to the number it shows

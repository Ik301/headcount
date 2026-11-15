# Rehearsal: end-to-end run against the live public services

Run Sat Nov 14, 19:00 to 19:50 ET, by Hermes (rehearsal subagent), against:

- API: `https://antivirus-checked-insight-chi.trycloudflare.com` (`/health` ok, artifacts loaded, live and news warm)
- Web app: `https://bring-fisher-headed-mill.trycloudflare.com` (`/`, `/claim/:id`, `/story`)

Method: `eval/rehearsal/harness.py` posted each claim to `POST /claim` (mode `auto`), then fetched `GET /claim/{id}` and `/claim/{id}/chart.png`. It recomposed `reply_text` from the returned JSON with `src.api.reply.compose` and checked that every number in the reply appears in the JSON. It also swept the raw response for private DIDs, private handles (the handles of the 16,808 non-public accounts in `accounts.parquet`) and `@mentions`. The `/agent` conversations used test sender ids, not phone numbers. No iMessage was sent, no Photon send API was called, and `/join` was not posted. The web checks ran in Playwright with `channel="chrome"` at 1440x900.

**Bottom line.** Before this PR, the text line declined the flagship claim "Was Jensen Huang's mistress a Chinese spy?" as a claim about a private person, and a real private-person claim got the insufficient-data reply instead of the decline. Both are fixed here and verified in-process against the same data. The fixes reach the public line only after the API is restarted (see "To pick up the fixes"). Every reply number matched its JSON in all 9 `/claim` checks. No private DID or handle appeared in any API response or in `site_data.json`. One indirect leak sits in a corpus example post (bug 14). The web claim view's headline on the flagship claim is misleading (bug 3); fix it before judging.

## End-to-end checks (DEMO.md, build spec)

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Text claim 1 from a new phone: checking text in 5 s, answer with chart and link in 30 s, numbers match `/claim` | **Not run on a phone** (no iMessage allowed). Proxy `POST /agent`: **FAIL before fix, PASS after fix (in-process)** | Live agent declined claim 1 as a private-person claim (4.5 s). After the fix: answer in 4.9 to 7.1 s, verbatim `compose` text, chart and link attached, numbers equal JSON |
| 2 | The link opens the claim view with the same narratives, shares and intervals | **PARTIAL** | Shared narratives match exactly. The web view also shows "Trump and politics" (1%, 6 posts) and makes it the headline ("17% ... about 3.3x the story's baseline", interval 0 to 50%). The text leaves it out under the 5% rule. Window reads "Nov 6 to 13" on the web and "Nov 5 to 13" in the text |
| 3 | `show the bots` and `who shares it` answer for claim 1 without a new search | **PASS** (content fixed) | 1.0 to 2.7 s, same claim_id, no new search. Before the fix, "who shares it" quoted lifts like "4.5x more likely" for groups of 1 account, and every follow-up re-sent the chart |
| 4 | Dashboard: replay with 3 markers, bots-off toggle, 4-value strip, evidence drawer, challenge mode, privacy sweep | **PARTIAL** | Replay plays, with 5 markers including the 3 required. The toggle works, but the ranking does not move, and the page says so. The strip shows 4 values per narrative. The drawer opens. **Challenge mode is not in the web app** (only a count line in Method). Privacy sweep: 0 private handles and 0 private DIDs in `site_data.json` (283 DIDs, all public). One indirect leak in a claim page DOM (bug 14) |
| 5 | Kill switch: API down, floor still demos | **PASS** | Ran with the API host blocked in the browser. `/story` renders fully from `site_data.json`. `/claim/:id` shows "The analysis service didn't answer" with the rules and links, never a blank page. Recordings now exist (below) |
| 6 | Claim 3 (unrehearsed) through the corpus path or the insufficient reply, never invented shares | **PASS** | "Is Nvidia stock tanking because Jensen Huang got pushed out by the board?": corpus, 324 posts, 0.94 s, reply equals recompose |
| 7 | `/health` reports the real bot model version, COMMS has the swap message | **PARTIAL** | `/health` says `"bot_model": "src.bots.score"`: the module, not `stub`, but not the manifest version. COMMS Sat 17:55 carries `v1-hgb-202611142229` |

## Claims (`POST /claim`, mode auto)

Latency is the client's wall time over the public tunnel. "Numbers" means every number in `reply_text` is found in the JSON and the reply equals `compose(json)`. "Privacy" means no private DID, private handle or `@mention` appears in the raw response.

| # | Claim | Kind | Scope | Latency | Matched | Numbers | Privacy | Result |
|---|---|---|---|---|---|---|---|---|
| 1 | Was Jensen Huang's mistress a Chinese spy? | Jensen | corpus | 0.79 s | 445 | match | clean | PASS |
| 2 | Did bots defend Jensen Huang? | Jensen | corpus | 0.27 s | 314 | match | clean | PASS |
| 3 | Is Nvidia stock tanking because Jensen Huang got pushed out by the board? | Jensen (unrehearsed) | corpus | 0.94 s | 324 | match | 1 indirect (bug 14) | PASS, see bug 5 (fixed) |
| 4 | Did Sean Duffy steer an FAA contract to his son-in-law? | live (Bluesky trend "FAA contract and Duffy's son-in-law") | live | 18.79 s | 141 | match | clean | PASS |
| 5 | Did SpaceX lose the Starship booster but catch the ship? | live (trend "Starship booster lost, ship caught") | live | 25.51 s | 300 | match | clean | PASS |
| 6 | Are Kushner and Witkoff negotiating a Ukraine peace deal? | live (trend "Kushner, Witkoff Ukraine peace talks") | live | 15.80 s | 173 | match | clean (see bug 19) | PASS |
| 7 | Is my coworker Megan Talbot from accounting stealing money from the office? | private person | live, `declined: true` | 2.18 s | 0 | n/a | clean | **FAIL before fix**: reply was the insufficient-data text. After the fix: the decline template (verified in-process) |
| 8 | flibbertigibbet quantum marmalade zorp | nonsense | live | 2.27 s | 0 | match | clean | PASS (insufficient-data reply) |
| 9 | Did a Florida city cancel its St. Patrick's Day parade? (typed in the web checker for the recording) | live (trend) | live | 19.8 s on the web, 13.1 s server | 253 | match | clean | PASS |

`GET /claim/{id}` returned the same numbers and reply for all 9, and every chart was a valid PNG (27 to 71 KB). All 9 responses carried a `news` block without an error. Live public handles shown were all public under the README rule: the 9 personal or small-outlet handles were checked against `getProfile` (5,222 to 15,264 followers, verified, or a `bot` label), and the other two were npr.org and washingtonpost.com.

Live timing (server `steps`): search 1.7 to 2.1 s, embedding 9.6 to 15.6 s (the slowest step, capped at 450 posts), scoring 2.3 to 4.7 s, amplifiers 0 to 1.7 s. Every live check finished inside the 60 s target, and the slowest took 25.5 s.

### Reply texts as served (before this PR's fixes)

Claim 1:
```
I found 445 Bluesky posts making this claim (Nov 5 to 13).
Jokes and memes: 54% of posts. Likely automated: 0% (0 to 0%).
Spy plot and national security: 26% of posts. Likely automated: 4% (0 to 8%).
The affairs as personal misconduct: 13% of posts. Likely automated: 3% (0 to 9%).
The likely automated accounts pushing Spy plot and national security: recent pace of about 536 posts a day (2 accounts).
I don't judge whether the claim is true. Full view: https://bring-fisher-headed-mill.trycloudflare.com/claim/b61ff2f2ead5
```
Claim 2:
```
I found 314 Bluesky posts making this claim (Nov 5 to 13).
Jokes and memes: 44% of posts. Likely automated: 0% (0 to 0%).
No narrative: 29% of posts. Likely automated: 0% (0 to 0%).
Defending Huang: 11% of posts. Likely automated: 3% (0 to 9%).
Spy plot and national security: 6% of posts. Likely automated: 0% (0 to 0%).
I don't judge whether the claim is true. Full view: https://bring-fisher-headed-mill.trycloudflare.com/claim/a662448a617c
```
Claim 3 (the last line is bug 5):
```
I found 324 Bluesky posts making this claim (Nov 5 to 13).
Stock, market and lawsuits: 60% of posts. Likely automated: 13% (4 to 24%), about 3x the story's baseline.
Board, resignation and succession: 22% of posts. Likely automated: 11% (4 to 19%), about 2x the story's baseline.
Jokes and memes: 8% of posts. Likely automated: 0% (0 to 0%).
Spy plot and national security: 7% of posts. Likely automated: 0% (0 to 0%).
The likely automated accounts pushing Stock, market and lawsuits: created in the same month (2026-06) (3 accounts); 2 accounts posted near-identical text (10 posts in 5 groups).
The real accounts spreading their posts are mostly "Not profiled" (0.8x more likely than similar accounts).
I don't judge whether the claim is true. Full view: https://bring-fisher-headed-mill.trycloudflare.com/claim/594bf60ae43a
```
Claim 5 (live):
```
I found 300 Bluesky posts making this claim (recent posts).
Booster lost, ship reached orbit: 53% of posts. Likely automated: 14% (7 to 21%).
Ship caught by launch tower: 47% of posts. Likely automated: 22% (14 to 30%).
The likely automated accounts pushing Ship caught by launch tower: 2 accounts posted near-identical text (4 posts in 2 groups); posts cluster on the same minutes of the hour (11 accounts).
I don't judge whether the claim is true. Full view: https://bring-fisher-headed-mill.trycloudflare.com/claim/06901a234f05
```
Claim 7 (should have been the decline):
```
I found 0 Bluesky posts making this claim, which isn't enough to measure automation reliably (I need at least 30). Try a broader wording, or ask about the Jensen Huang story from Nov 5 to 13. I don't judge whether the claim is true.
```
After this PR, claims 1 to 3 also get `+ N smaller narratives in the full view.`, the line the template requires. Claim 3 loses the "Not profiled" line, and claim 7 gets `I can't run checks on claims about a private person. ...`.

## Agent conversations (`POST /agent`)

Live service, before the fixes:

| Sender | Turn | Latency | Reply (short) | Numbers vs JSON | Privacy |
|---|---|---|---|---|---|
| A | Was Jensen Huang's mistress a Chinese spy? | 4.5 s | **Declined**: "It names a private person and makes a claim about them" | n/a | clean |
| A | show the bots / who shares it / next | 1.0 to 1.5 s | "nothing to show, the last one I declined" | n/a | clean |
| B | Did SpaceX lose the Starship booster but catch the ship? | 2.8 s (cached) | verbatim `compose` text | match | clean |
| B | show the bots | 2.2 s | near-identical text (2 accounts, 4 posts in 2 groups), same-minute posting (11), about 720 posts a day (2) | match | clean |
| B | next | 2.7 s | "Booster lost ... 53% of the 300 posts (0.5267 share) ... 14% (7 to 21%), below the 18% baseline" | match, but a raw decimal, and it repeats a narrative already in the answer | clean |
| B | who shares it | 2.5 s | 1 account, "5.15x lift", with a small-sample caveat | match | clean |
| C | help | 0.9 s | 2-line help | n/a | clean |
| C | Is Nvidia stock tanking ... board? | 3.9 s | verbatim `compose` text, including the "Not profiled" line | match | clean |
| C | who shares it | 2.2 s | "Not profiled 79% ... Heavy reposters 7%, 4.5x more likely ..." (each group is 1 account) | match, misleading | clean |
| C | next | 2.0 s | Jokes and memes 8%, 0% (0 to 0%), below the 5% baseline | match | clean |
| C | Is my neighbor Dana Whitfield cheating on her taxes? | 1.3 s | declined in the model's own words, **with the previous claim's chart and link attached** | n/a | clean |

After the fixes, in-process (`src.agent.agent.run` on the same data, `DATA_DIR` pointed at a scratch copy so the live claims dir was untouched):

| Sender | Turn | Latency | Result |
|---|---|---|---|
| A | Was Jensen Huang's mistress a Chinese spy? (asked 4 ways, 4 senders) | 3.5 to 7.1 s | Answered every time through `search_claim`. The safety net was never needed. Chart and link attached |
| A | show the bots | 2.1 to 2.6 s | "Recent pace of about 536 posts a day, across 2 accounts", no chart re-sent |
| A | who shares it | 1.8 to 2.1 s | "Only 1 amplifying account ... too few to say any group is more likely" |
| A | next | 2.1 to 2.5 s | Trump and politics, 1% of posts, 17% (0 to 50%), "the interval is very wide" |
| A | Is my neighbor Dana Whitfield cheating on her taxes? | 1.2 to 2.8 s | Exact decline template, no chart, no link. The model declined first, then the safety net confirmed it through the API's own check |
| C | who shares it (stock claim) | 2.7 s | "Only 3 amplifying accounts could be profiled ... 11 of the 14 accounts couldn't be profiled" |
| D | Did bots defend Jensen Huang? then show the bots | 3.7 s, 2.3 s | Verbatim answer, then "No shared signals came back for this claim" |

## Backup recordings (`web/app/recordings/`, webm, VP9)

Recorded Sat Nov 14 ~23:55 ET against the public URLs, after design round 4 (#45, "returns desk" look, Headcount name). Desktop at 1440x900; the two `mobile-` files are a 390x844 phone viewport (touch emulation). 0 console errors in every run.

| File | Size | Length | What it shows |
|---|---|---|---|
| `claim-jensen-mistress-spy.webm` | 1440x900 | 27.7 s | Types the flagship claim, answer 0.9 s after Check (443 posts; spy plot 4%, not clearly different from the 4.5% baseline), scrolls the post sorter, narratives, news and evidence |
| `claim-live-any-story.webm` | 1440x900 | 63.1 s | Live any-story check ("Did Delray Beach cancel its St. Patrick's Day parade?", not cached): progress steps and the scanning globe, answer 35.3 s after Check (282 posts), then the result |
| `story-dashboard.webm` | 1440x900 | 56.3 s | `/story` guided chapters 1 to 6: replay, how much was automated, where it was (the post sorter stepped to "Likely automated"), newsrooms vs Bluesky, who spread it, how we know |
| `mobile-claim-jensen-mistress-spy.webm` | 390x844 | 39.5 s | Phone: types the flagship claim, answer 1.6 s after Check, taps the headline's 4% to open its receipt, scrolls the result |
| `mobile-challenge.webm` | 390x844 | 29.8 s | Phone: `/challenge` card with an English translation over the French original, answers "likely automated", the reveal (0.36, model disagrees, three reasons), next card |

Re-record with `python3 web/app/recordings/record.py claim|live|story|claim-mobile|challenge-mobile ["claim text"]` (`WEB_BASE` overrides the web URL). Use a live claim the API hasn't seen in the last hour, or the live recording shows a cached sub-second answer.

## Bugs, ranked

Status: **fixed** = fixed in this PR (tests green); **Hermes** = outside this PR's three files, or too big for a local fix.

| # | Sev | File:line | Symptom | Fix | Status |
|---|---|---|---|---|---|
| 1 | blocker | `src/agent/agent.py:16-26` (SYSTEM), `:143` | The text line declined the flagship demo claim ("mistress" read as a named private person) and never searched | The prompt now always calls `search_claim` first (the API runs the private-person check) and gives the Jensen claims as examples. Safety net: if the model declines without searching, the claim goes through `run_claim` and the API's reply is sent | **fixed** (4 of 4 phrasings answered) |
| 2 | high | `src/api/reply.py:26-34` | `app.run_claim` recomposes every result, which overwrote the live path's decline and failure templates. A private-person claim got "I found 0 Bluesky posts ..." | `compose` returns `DECLINE` / `FAILURE` when `declined` / `error` is set | **fixed** + test |
| 3 | high | `web/app/src/checker/ClaimResult.tsx:19`, `:177` | The flagship claim's web headline is "17% of those in 'Trump and politics', about 3.3x the baseline": a 6-post narrative (1%) with interval 0 to 50%. It also contradicts the pitch ("automation relays news") | Pick the top narrative only among `share_of_matches >= 0.05` (the reply's rule), with a minimum post count, or headline the largest narrative. Re-record the flagship video afterwards | **fixed** (`hermes/export-fixes`) |
| 4 | high | `src/agent/agent.py:121-162` | `run()` scanned the whole checkpointed thread, so every follow-up re-sent the chart and link, and a decline carried the previous claim's chart | Only this turn's messages count. The chart and link attach only to a new answer. A decline returns no chart. The last claim_id rides along as tool context | **fixed** |
| 5 | med | `src/api/reply.py:57-66` | Amplifier line: `mostly "Not profiled" (0.8x more likely than similar accounts)` | Skip unprofiled groups. Need 10+ profiled amplifiers and the largest group's lift above 1 | **fixed** + test |
| 6 | med | `src/agent/agent.py:74-88` | "who shares it" quoted 4.5x and 5.15x lifts for groups of 1 account | The tool returns per-group account counts with "Not profiled" split out, plus a small-sample note under 10 profiled | **fixed** |
| 7 | med | `src/export/build_site_data.py:830` | The Method view says recall@100 **0.33**, from Muse's laptop report (`report_model v1-hgb-202611142157`). TEAM-BRIEF says quote the VM's **0.272** (`eval/bots/report-vm.md`) | Read `report-vm.md` when it exists, then re-export | **fixed** (`hermes/export-fixes`) |
| 8 | med | `src/export/build_site_data.py:857`, `web/app/src/story/Method.tsx` | "narrative label agreement 70% ... with hand labels". The 0.70 is the classifier against the LLM labels. Hand labels are pending | Relabel it "classifier vs LLM labels" or hide it until the hand labels are in | **fixed** (`hermes/export-fixes`) |
| 9 | med | `src/export/build_site_data.py:864` | Claim retrieval recall@20 shows "·" (empty): reads `eval/retrieval/report.md`, tables empty | Read `report-hybrid.md` (0.787 on the first 20 claims, 0.646 on all 50) | **fixed** (`hermes/export-fixes`) |
| 10 | med | `web/app/src/story/Archetypes.tsx:18`, `:44` | "1,256 real accounts reposted, quoted or liked posts from likely automated accounts". 1,256 is amplifiers plus matched controls; amplifiers are **642** (`eval/thesis/report-vm.md`) | Sum `amplifiers`, not `size` | **fixed** (`hermes/export-fixes`) |
| 11 | med | `src/api/analysis.py` (no private-person check) | H4 step 2 exists only on the live path. A private-person claim with 30+ corpus matches in `auto` or `corpus` mode is never checked | Run the same LLM check (or a cheap name heuristic) before corpus retrieval | Hermes |
| 12 | low | `web/app/src/story/NoBots.tsx:17`, `:106` | Every narrative says "near the 5.0% baseline", including jokes at 0.4% | Say below or above when the interval excludes the baseline, "near" otherwise | **fixed** (`hermes/export-fixes`) |
| 13 | low | `web/app/src/story/Method.tsx:169` | "News baseline , , , , , , , , ," shows no outlet names: maps `o.name`, data has `o.source` | Use `o.source` | **fixed** (`hermes/export-fixes`) |
| 14 | low (privacy) | `src/api/analysis.py:118` | Corpus example posts are shown verbatim. A private account whose handle is its own domain links to that site in claim 3's page, which names it indirectly (handle redacted: README rule 5) | Apply `live.safe_example_text` (added in this PR) in `analysis.py` too, or in `app.scrub` | Live path **fixed**, corpus Hermes |
| 15 | low | `web/app/src/story/Archetypes.tsx:8-11`, export | Archetype cards show "null age days log": feature values are null and keys are raw | Fill values in the export, or drop null entries and map keys to plain words | **fixed** (`hermes/export-fixes`) |
| 16 | low | `src/api/app.py:139` | `/health` `bot_model` is the module name, not the manifest version (end-to-end check 7) | Read `data/processed/artifacts/manifest.json` `bot_model.version` | Hermes |
| 17 | low | `src/export/build_site_data.py:73` | A second hedging regex (adds possible, rumor, unverified) beside the news module's canonical `HEDGE_TERMS`: two definitions for one pitch number | Import the news module's terms, so the dashboard shows 54 / 50 / 29 | **fixed** (`hermes/export-fixes`) |
| 18 | low | `src/api/reply.py:50-52` | The template's `+ {n} smaller narratives in the full view.` line was missing | Added | **fixed** + test |
| 19 | low | `src/model/schema.py:12` | Accounts labeled `!no-unauthenticated` (they asked not to be shown to logged-out viewers) are named when they have 5,000+ followers (seen in claim 6) | Treat that label as private | Hermes |
| 20 | low | web app | Challenge mode (fallback 1 in DEMO.md) is not built; only a count appears in Method | Build it or drop it from the fallback list | **fixed** (`hermes/export-fixes`) |
| 21 | low | `src/agent/agent.py` (design) | "next" has no deterministic cursor. The model can repeat a narrative already in the main answer | Keep a per-sender cursor and expose `next_narrative(claim_id)` as a tool | Hermes |
| 22 | cosmetic | `web/app/src/story/Network.tsx`, `River.tsx` | Replay labels overlap into an unreadable block at 1440 wide, and the Nov 12 markers overlap | Label only the top N public accounts, stagger the markers | Isaac |
| 23 | note | retrieval | The flagship claim is the weakest retrieval case in the eval (c02: recall@20 0.20, set precision 0.11, `eval/retrieval/report-hybrid.md`). Its answer is 54% "Jokes and memes" | Not a tonight fix. Have the Q&A answer ready: people mostly joked about it, and the spy narrative is 26% with 4% likely automated | open |

## To pick up the fixes on the public line

The running API (uvicorn on 127.0.0.1:8000) still serves the old code. After this PR merges: pull in the main checkout, restart uvicorn by PID (not `pkill -f`), then re-POST claims 1 to 3 so their stored replies (`data/processed/claims/<id>.json`) are recomposed. Rerun `python3 web/app/recordings/record.py claim "Was Jensen Huang's mistress a Chinese spy?"` once bug 3 is fixed, and `eval/rehearsal/harness.py` to confirm `reply_equals_recompose` is true again for every claim.

Tests: `.venv/bin/python -m pytest -q tests` -> `70 passed` (66 before, plus 4 new tests for bugs 2, 5, 14 and 18).

## Follow-up: export and web fixes (`hermes/export-fixes`)

Bugs 3, 7, 8, 9, 10, 12, 13, 15, 17 and 20 are fixed on that branch: the claim headline needs 30+ posts and an interval at most 25 points wide (flagship claim now headlines "Spy plot and national security", 4% (0 to 8%), not clearly different from the 5.0% baseline); the Method view reads `eval/bots/report-vm.md` (recall@100 0.272, baseline 0.045), `eval/narratives/report.md` (classifier agreement with the language-model labels 70%, hand labels pending) and `eval/retrieval/report-hybrid.md` (recall@20 0.787 on the first 20 claims); archetypes come from M5's matched analysis (642 amplifiers, 628 matched, matched lifts); narrative-to-baseline wording follows the interval; outlet names render in the story and the claim view; one hedging definition (the news module's), with the link / own-words split in `news.spy_claim` (54% / 50% / 29%); `@mentions` that aren't nameable Bluesky accounts are masked; `/challenge` is built. Rerun the export in the main checkout after merging (`python -m src.export.build_site_data`) and re-record the flagship video.

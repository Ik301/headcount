# Web app: claim checker and story dashboard

Vite + React + TypeScript. Three routes, ported from the approved mockups (`web/mockups/checker.html`, `web/mockups/dashboard.html`) and wired to real data. Structure first, polish later: every view is a plain component reading one typed object, and all styling sits in four CSS files, so a restyle doesn't touch the data code.

| Route | What it is | Data source |
|---|---|---|
| `/` | Claim checker: input, example chips, progress, then the result | `POST {API_BASE}/claim` with `{"text", "mode": "auto"}` |
| `/claim/:id` | One check's result. This is the link the text line sends | Router state handed over by `/` when you just ran it, else `GET {API_BASE}/claim/{id}` |
| `/story` | The Jensen Huang week as a guided story in six chapters; `?mode=explore` opens the full dashboard (replay, without likely automated, archetypes, evidence, method) | `GET /site_data.json` (static, served from `web/public/site_data.json`). No API calls |

Screenshots of the current build are in `shots/v2/` (guided story, 1440x900 and 390 wide, plus explore mode). Regenerate with `python3 scripts/shots-v2.py shots/v2` while `npx vite preview --port 4174` runs. Older dashboard shots are in `shots/`.

## Run it

```sh
cd web/app
npm install
npm run sample-data      # only if web/public/site_data.json doesn't exist yet (see below)
npm run dev              # http://127.0.0.1:5173
```

The API must be running for `/` and `/claim/:id` (from the repo root: `.venv/bin/uvicorn src.api.app:app --port 8000`). It already sends CORS headers for any origin.

Production build and a local server that handles the SPA routes:

```sh
npm run build            # tsc type-check, then vite build into web/app/dist (includes site_data.json)
npm run preview          # http://127.0.0.1:4173
```

`dist/` is a static site. Any static host works as long as unknown paths fall back to `index.html`, so `/claim/<id>` links resolve.

## Config

Only one setting: the API base URL. Precedence, first wins:

1. `?api=<url>` on any page, e.g. `http://127.0.0.1:5173/?api=https://my-tunnel.trycloudflare.com`. It's saved to `localStorage`, so later links in that browser keep using it. `?api=reset` clears it.
2. `localStorage["sbt.apiBase"]`.
3. `VITE_API_BASE` at build time (`web/app/.env`, see `.env.example`, or the shell: `VITE_API_BASE=https://... npm run build`).
4. `http://127.0.0.1:8000`.

Code: `src/config.ts`. The share link is built from `window.location.origin` + `/claim/<id>`, not from the API's `dashboard_url` (that one depends on the API's `DASHBOARD_BASE` env var, which the text line uses).

## Where each view's data comes from

### `/` and `/claim/:id` (`src/checker/`)

- `CheckerPage.tsx`: idle state, example chips (`EXAMPLES`), submit. Runs the check, then navigates to `/claim/<claim_id>` with the result in router state, so the address bar is the shareable link and nothing is fetched twice.
- `RunProgress.tsx`: the running state. The API answers once, at the end, so the four stages advance on a typical schedule while the clock is real. The last stage stays "working" until the answer arrives. If the API ever streams progress, swap the schedule for real events here.
- `ClaimResult.tsx`: the reply-shaped result. Every number is read straight from the `/claim` JSON (`docs/DEMO.md`, "API contracts"):
  - headline: `matched_posts` and the narrative with the highest `bot_post_share`; the "about N× the baseline" ratio uses the reply-text rule (only at 2× or more)
  - narratives: `share_of_matches`, `posts`, `bot_post_share`, `bot_post_share_ci`, `baseline_bot_share`
  - "What they have in common": `bot_commonalities[].signal/accounts`
  - "Who amplifies them": `amplifiers.n_humans`, `amplifiers.archetype_mix[].label/share/lift` (and `lift_ci` if the API adds it)
  - news column: `news` (optional; renders only when the API sends it)
  - evidence expander: `example_posts`, `evidence`, `bot_commonalities[].evidence`, plus `reply_text` verbatim as "As a text message"
  - actions: share or copy the link, copy `reply_text`, open `chart_png_url`, and a link to `{API_BASE}/join` for the text line
  - fewer than 30 matches: shows `reply_text` (the API's insufficient-data or decline wording) instead of shares
- `CheckError.tsx`: API unreachable, error JSON (`{"error": "..."}`), or an unknown id (404: the API keeps checks in memory, so a restart clears old links). Shows the rules and a way back, never a blank page.

### `/story`, guided story (`src/story/guide/`)

The default view. Each chapter leads with one plain-language headline, then one chart that proves it, then details folded into `<details>`. `?ch=1..6` picks a chapter (left and right arrow keys step through); `?still=1` turns off the first-view autoplay (for screenshots). Old `?view=` links open explore mode.

| Chapter | Headline reads | Chart |
|---|---|---|
| 1 What happened | `story.posts/accounts`, the window, the busiest hour from `timeline`, the event before it from `story.events` | Replay: only likely automated accounts (`role: likely_automated` or score 0.5+), the real accounts that amplified them (`role: amplifier`, appearing at `first_amplified`), and up to 40 public accounts linked to them. Plays once on a visitor's first view (`localStorage["sbt.replaySeen.v1"]`, skipped under reduced motion) |
| 2 How much was automated | `narratives_meta.baseline.bot_post_share` as "about 1 in N" | 100 squares plus the estimate with its interval; cutoffs from `baseline.threshold_strip`, accounts vs posts from `bot_account_share` |
| 3 Where the automation was | named narratives (not `n0`) by `bot_post_share`; the `side: pro_huang` narrative against the baseline (the Post's claim) | Dot and interval per narrative against a dashed "whole story" line; the remove-likely-automated toggle re-ranks by `without_automated.volume_share(_without)` |
| 4 Newsrooms vs Bluesky | `news.spy_claim` hedged shares | Bars with intervals. If the export adds `bluesky_link_hedged_share` and `bluesky_own_words_hedged_share` (+ `_posts`, `_ci`), the chapter shows three bars and the "caution survives the share button" headline |
| 5 Who spread it | `archetypes[].lift_ci`: null result when every interval includes 1 | Lift per archetype on a log scale centred on "no difference" |
| 6 How we know | `validation.handcheck_precision`, `recall_at_k` vs `baseline_recall_at_k` | 50-square hand-check grid; recall curve, glossary, data and privacy in details |

Each chapter's "Copy this finding" copies the matching sentence from the export's `findings` list verbatim. Styles: `src/styles/guide.css`, all under `.guide`.

### `/story?mode=explore` (`src/story/`)

`model.ts` turns `site_data.json` into one `Model` object; every view reads the model, never raw JSON. Every section is optional: a missing table becomes an empty state, not a crash (tested with `{}` and with a narratives-only file).

| View | Component | Reads from `site_data.json` |
|---|---|---|
| Header | `StoryPage.tsx` | `story.title`, `story.window`, `story.totals`, `story.baseline_bot_share` (else computed from narratives) |
| Replay: network | `Network.tsx` (canvas) | `graph.nodes` (`narrative`, `p_automated`, `public_handle`, `self_label_bot`, `size`, first-seen time as `t` / `first_t` / `hour`, optional `x`/`y`), `graph.edges` (`s`, `t`, optional `at`), `graph.cap_note` |
| Replay: river and scrubber | `River.tsx` (SVG) | `timeline[].by_narrative`, `timeline[].bots_by_narrative` (else posts × the narrative's `bot_post_share`), `story.events[]` (`major: true` gets a jump button and a labelled marker) |
| Replay: side panel | `Replay.tsx` | cumulative sums of the river up to the playhead; accounts = graph nodes visible so far |
| Without likely automated | `NoBots.tsx` | `narratives[]`: `posts`, `bot_posts`, `share`, `share_without_bots` (each computed if missing), `bot_post_share`, `bot_post_share_ci`, `threshold_strip`; `clusters` for the aside; `news.hedging`, `news.social_only` |
| Amplifier archetypes | `Archetypes.tsx` | `archetypes[]`: `label`, `size`, `share`, `lift`, `lift_ci`, `features` (object or `[{value,label}]`), `mix`, `median_delay`, `public_examples`, `evidence` |
| Evidence | `EvidenceView.tsx` | `clusters` (or `coordination`): `cluster_id`, `narrative`, `size`/`dids`, `reasons`, `window`, `text`, `evidence`; narratives' `evidence` |
| Method | `Method.tsx` | `validation.recall_at_k`, `validation.retrieval_recall_at_k`, `validation.gold_accuracy`, `validation.gold_by_narrative`, `validation.model_version`; `news.outlets`; `challenge` count |
| Lead line of each view | `FindingBar.tsx` | `findings` as `{view: text}` or `{view: {text, source}}` or `[{view, text, source}]`; falls back to a sentence computed from the same numbers |
| Evidence drawer | `Drawer.tsx`, `drawers.ts` | the `evidence` arrays above (`post_uri`, `t`, `note`/`trace`, optional `text`, `public_handle`, `p_automated`) |

Fields beyond the README shape that the app uses if present: `story.window`, `story.totals`, `story.baseline_bot_share`, `story.data_through`, `story.sample`, `story.events[].major`, `timeline[].bots_by_narrative`, `narratives[].posts/bot_posts/share/share_without_bots`, `graph.nodes[].t/self_label_bot`, `clusters`, `findings`, `news`. Types for all of it: `src/api/types.ts`.

Replay styling follows DEMO: likely automated accounts red, a real account turns blue the first time it amplifies a red one (first edge to a node with `p_automated >= 0.5`), public accounts ringed and named, self-labeled bots dashed.

### Sample data

Until the export writes `web/public/site_data.json`, `npm run sample-data` copies sample data there: `data/sample/site_data.sample.json` if the export agent has committed one, else `fixtures/site_data.sample.json` (generated by `npm run make-fixture` from the brief's sample numbers). It refuses to overwrite a file that isn't marked `story.sample: true` unless you pass `--force`. The dashboard shows a "Sample data" tag whenever `story.sample` is true. `web/public/site_data.json` is not committed by this app; the export owns it.

## Privacy in the UI

- Handles render only from `public_handle` fields. Everything else is "a private account" or a short hashed ref (`acct·3f9a`).
- Evidence `post_uri`s from the API look like `at://did:plc:<account>/app.bsky.feed.post/<rkey>`. The DID identifies the account, so the UI never renders or copies it; it shows `post·<last 6 of rkey>` instead (`postRef` in `src/lib/format.ts`). The API still sends the full URIs, so anyone reading the raw JSON can see them; that's a backend fix.
- Wording: "likely automated", never "bots" for undisclosed accounts; "I don't judge whether the claim is true" on every result.

## Restyling

- Tokens: `src/styles/tokens.css` (exactly the brief's palette, plus `--signal-ink` and `--cap` for small text contrast).
- `src/styles/base.css`: body, top bar, buttons, focus, selection, scrollbars.
- `src/styles/checker.css`: everything under `.checker` (ported from the checker mockup).
- `src/styles/story.css`: everything under `.story` (ported from the dashboard mockup; the 1440×900 fixed frame became a scrolling page with a 1100 px minimum width).
- Canvas colours for the network are hex constants at the top of `Network.tsx`; narrative colours live in `src/lib/narrativeColor.ts` (`n1` to `n7` map to the brief's narrative tokens; other ids cycle through the same set).
- Fonts are self-hosted through `@fontsource` (Newsreader, IBM Plex Sans, IBM Plex Mono), so the app works offline at the judging table.

Why canvas and not sigma.js: the export caps the replay graph at about 3,000 nodes, which canvas 2D draws at 60 fps; it renders in headless screenshots without GPU flags; and the node styling (rings, dashed self-labels, amplifier colour change) is a few lines of plain code. Swapping in sigma later only touches `Network.tsx`.

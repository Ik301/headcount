---
name: Headcount
description: A careful, evidence-first instrument for how much of a story's volume is automated. It reads like election-night returns.
colors:
  tally-paper: "#ECEEE7"
  card: "#F9FAF6"
  panel: "#E2E5DC"
  ink: "#111814"
  ink-2: "#3B4640"
  ink-3: "#7C867F"
  caption: "#56615A"
  rule: "#CBD1C4"
  rule-2: "#DCE0D5"
  automated-magenta: "#C81E66"
  automated-magenta-ink: "#A1144F"
  automated-magenta-wash: "#F5DCE6"
  amplifier-steel: "#245E7E"
  amplifier-steel-wash: "#D8E4EA"
  counting-room-green: "#10261F"
  counting-room-card: "#163028"
  counting-room-rule: "#2A4A3F"
  counting-room-ink: "#EEF1E9"
  counting-room-caption: "#A3B3A9"
  counting-room-magenta: "#FF5C9D"
  n-spy: "#34488C"
  n-affairs: "#A8772A"
  n-politics: "#5B7A2C"
  n-board: "#6F5E96"
  n-market: "#2C7C86"
  n-defend: "#C0612B"
  n-jokes: "#7C867F"
  n-none: "#AEB5AA"
typography:
  display:
    fontFamily: "Schibsted Grotesk Variable, Helvetica Neue, Arial, sans-serif"
    fontSize: "68px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Schibsted Grotesk Variable, Helvetica Neue, Arial, sans-serif"
    fontSize: "36px"
    fontWeight: 560
    lineHeight: 1.14
    letterSpacing: "-0.024em"
  chapter:
    fontFamily: "Schibsted Grotesk Variable, Helvetica Neue, Arial, sans-serif"
    fontSize: "40px"
    fontWeight: 650
    lineHeight: 1.06
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Schibsted Grotesk Variable, Helvetica Neue, Arial, sans-serif"
    fontSize: "21px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.014em"
  figure:
    fontFamily: "Schibsted Grotesk Variable, Helvetica Neue, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 750
    lineHeight: 1
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Schibsted Grotesk Variable, Helvetica Neue, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Schibsted Grotesk Variable, Helvetica Neue, Arial, sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
    lineHeight: 1.3
  data:
    fontFamily: "Fragment Mono, ui-monospace, Menlo, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\" 1"
rounded:
  stamp: "3px"
  control: "4px"
  card: "6px"
spacing:
  row: "14px"
  block: "44px"
  gutter-phone: "20px"
  gutter-tablet: "40px"
  gutter-desk: "56px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.tally-paper}"
    rounded: "{rounded.control}"
    height: "46px"
    padding: "0 18px"
  button-ghost:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "46px"
  claim-field:
    backgroundColor: "#F4F6F0"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "4px"
  call-stamp-above:
    backgroundColor: "{colors.automated-magenta-wash}"
    textColor: "{colors.automated-magenta-ink}"
    rounded: "{rounded.stamp}"
    padding: "1px 6px 2px"
  call-stamp-neutral:
    textColor: "{colors.caption}"
    rounded: "{rounded.stamp}"
    padding: "1px 6px 2px"
---

# Design system: Claim check ("Returns desk")

Tokens live in `web/app/src/styles/tokens.css`; motion classes in `web/app/src/styles/motion.css`. This file describes the system as built in design round 4, which stacks on #42 (receipts, hatched intervals, post sorter, globe).

## Overview

A check reads like **election-night returns**. Each narrative is a race, posts are the count, and "likely automated" is the share you subtract before calling anything. Election returns are something newsroom editors, analysts and judges already know how to read: ranked rows, a count, a share, a call that is made only when the numbers support it. The world adds four things to a working tool: type, palette, density and one signature move. It never changes the controls.

What it refuses: the dark-SaaS dashboard with a glowing accent, and the cream-paper, serif-headline, red-accent editorial page. The previous look (Newsreader, IBM Plex, warm cream, signal red, near-black hero with glow) sat squarely in the second.

Scene: a judge at a team table in a bright hall, a laptop and maybe a monitor; an editor at a desk in daylight; someone on a phone. Bright ambient light, so reading surfaces are light paper. The first impression is a drenched green field, which is a colour and not a dark mode.

## Colors

- **Tally-sheet paper** `#ECEEE7` with **green-black ink** `#111814`. Cool grey-green paper, like ballot stock or a returns sheet. Secondary text `#3B4640` (8.4:1), captions `#56615A` (5.5:1). `#7C867F` is for rules, ticks and swatches only (3.2:1, never body text).
- **Automated magenta** `#C81E66` means likely automated and nothing else: dots, intervals, the share, the "above" call. Small text uses `#A1144F` (6.6:1 on paper, 6.0:1 on its wash `#F5DCE6`). It is neither party red nor party blue on purpose: in a returns world, red against blue reads as Republican against Democrat.
- **Amplifier steel** `#245E7E` is for real accounts that amplify, and lifts whose interval clears 1×.
- **Counting-room green** `#10261F`: the landing and running screens only. It's a token swap on `.page.checker.is-dark` (ink `#EEF1E9`, captions `#A3B3A9` at 7.3:1, magenta lifted to `#FF5C9D` at 5.5:1). The claim field sits on it as a pale slip (`#F4F6F0`).
- **Narratives** get muted, distinct hues that keep clear of magenta and steel: indigo, ochre, moss, violet, teal, burnt orange, grey, and a pale grey for posts that fit no narrative (`--n-*`). Live checks cycle through the same set.
- Selection is ink on paper (paper on green in the band), never magenta.

## Typography

- **Schibsted Grotesk** (variable 400–900; Schibsted Media's own newsroom grotesque; SIL OFL 1.1; self-hosted via `@fontsource-variable/schibsted-grotesk`) sets every word and every figure. Hierarchy comes from weight and tracking: display 700 at −0.04em, headlines 560–650, figures 750–800, body 400.
- **Fragment Mono** (SIL OFL 1.1; `@fontsource/fragment-mono`) is only for receipts, timestamps, check ids and counters, the parts that are data rather than prose.
- `--serif` and `--sans` both point at Schibsted; `--serif` is kept as the display role so older rules still resolve.
- **No tabular figures on Schibsted.** Its `tnum` feature widens periods and commas to figure width ("story ." and "46 , 656"). Use the mono where columns have to align exactly.
- No kicker or eyebrow labels above headings. The chapter tabs carry position.

## Layout

- Containers: 1200 px (checker), 1180 px (story); gutters 20 / 40 / 56 px at <720 / ≥720 / ≥1080.
- Claim result at ≥1080: headline, actions, post sorter, then the **returns table at full width**, then "in common" and "who amplifies" on the left with newsroom headlines on the right.
- Returns table at ≥720: `swatch | narrative | share of posts | interval track + value | call` under a 2 px ink header rule. Under 720 each row stacks with one decision per line: the name and share, then the track and value, then the call.
- Phones: on the landing the claim field and examples come first and the globe follows.

## Elevation & Depth

Flat and ruled. Depth comes from hairline rules (`--rule`) and tonal panels, not shadows. There are two exceptions: the claim field on the green band (a short, offset shadow, like a slip lying on a desk) and the receipt ticket.

## Shapes

Square-cut. Stamps 3 px, controls 4 px, cards and the field 6 px. Dots stay round (they are counts) and switches stay pill-shaped (a platform convention). Interval bands are diagonal hatching, the engineering-drawing sign for "somewhere in this range" (from #42; the detector's stripes advisory refers to this data encoding).

## Components

- **Call stamp** (`.xb`, `.g-verdict`): a 1 px box in sentence case. It is filled magenta-wash only when the interval clears the baseline ("above baseline"). "×N baseline" follows the same rule, so a point estimate above 2× whose interval still includes the baseline gets the neutral stamp.
- **Receipt** (#42): tap a key number to print a ticket. Every line reads the same JSON as the number.
- **Post sorter** (#42): canvas; same tokens.
- **Globe** (#42): real replay graph. Crisp magenta dots with a ring cut out of the field, no glow. Accounts arrive latitude by latitude, from the bottom of the globe up, like a count filling in.
- **Buttons**: ink fill / ghost, 46 px, 4 px radius, weight 600.

## Motion: "the count comes in"

One authored idea: results report in like returns.
- Rows arrive in order: `.in-wipe`, a left-to-right clip reveal with a 6 px travel, 60 ms apart, capped at 6 rows.
- Bars draw from zero (`.grow`, scaleX, transform only). The point drops onto its track (`.drop`), then the hatch opens outward from it (`.hatch-in`), then the call stamps (`.stamp`, a 340 ms press with no bounce).
- Headlines rise out of a slot (`.h-rise`, masked translate). Waffle squares count in at 7 ms per square. Globe accounts arrive over 1.3 s.
- Easing `cubic-bezier(.16,1,.3,1)` for arrivals and `cubic-bezier(.7,0,.84,0)` for exits. Durations are 120 / 240 / 420 / 640 ms (tap, state, layout, focal).
- **Reduced motion**: every motion class becomes a 180 ms opacity fade with no delay; the globe stops turning and arrives whole; the sorter shows its settled step. Nothing loops except the globe, which pauses when the tab is hidden.

## Do's and Don'ts

- Do read every number from the API or `site_data.json`; motion never invents an intermediate value it would display (count-ups end on the real number).
- Do keep magenta for likely automated. Don't use it for emphasis, selection, hover, or links.
- Don't show a private handle anywhere, including captions and receipts.
- Don't add uppercase tracked labels, kickers, glows, gradients or soft-shadow cards.
- Don't set Schibsted figures with `tabular-nums`.
- Don't give the call stamp emphasis unless the interval supports it.

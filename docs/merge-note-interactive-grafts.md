# Merge note: three grafts onto the Audience X-ray walkthrough

For the 16:30 lock. This note compares [mvp-walkthrough.md](mvp-walkthrough.md)
(Isaac's Audience X-ray) with an alternative walkthrough written to the same format
(the investigation bench: judge-led interrogation of the Huang week on precomputed
data). Scoring both against the rubric in Isaac's doc, the X-ray version wins as the
locked MVP — clearer product ("is this post's reach real?", a per-post check with
named buyers), a single strong ah-ha, and feasibility already measured (20,482
profiles in 20 s; author histories at about 45 accounts a second). Screens 1 to 3 are
the same in both versions anyway.

Three pieces of the alternative are worth grafting on. All three ride on data and
screens the X-ray plan already has; none changes the demo's spine or the split.

## 1. Evidence drawer everywhere (Lane D, small)

Every bar (screen 2), archetype card (screen 3) and coordination cluster (screen 4)
clicks open to the evidence behind it: the posts, timestamps to the second, the
coordination traces, the reason chips, the source and pull time.

The X-ray already does this for clusters (it returns their reasons). This graft is
generalizing that one pattern to every number on screen, so no aggregate has to be
taken on trust. It is the clearest signal that the results are computed, not
generated.

Implementation: an `evidence` field in `site_data.json` per narrative, archetype and
cluster, and the same field added to the `/xray` response next to
`coordination_clusters`. One drawer component in the web app. The `/xray` contract
change is made in the README in this same pull request, per AGENTS.md; the
`site_data.json` shape gains the same optional field when Lane D builds the export.

## 2. Threshold sensitivity strip on screen 2 (Lane B / export, near-free)

Show the bot share per narrative at four automation thresholds (0.3, 0.5, 0.7, 0.9)
as a small strip under the bars. A live slider only if Lane D has spare time; the
static strip does the same work in the demo.

Why: the first hard Q&A question is whether the threshold was picked to make the
headline. This answers it before it is asked. If the defend-Huang ranking holds
across thresholds, the script gets a line: "the result does not depend on where we
drew the line."

Implementation: `p_automated` is already a column; the export aggregates at four
cutoffs instead of one.

## 3. Challenge mode — as the fallback and the table activity, not in the 2 minutes

A labeling round: ten to twenty frozen accounts from the story, the viewer calls
"likely automated or not," the app reveals the model's score and reasons and flags
disagreements.

Two jobs, neither of them displacing the X-ray:

- **Plan B if the live X-ray fails.** The current backup is recordings of three
  X-ray runs. A precomputed interactive round still feels live if the Wi-Fi or the
  API dies; recordings become Plan C.
- **Table activity after the pitch.** Via the QR in the table setup, judges can
  label accounts while the team talks. Their disagreements are exactly the
  hand-check queue for top-scored unlabeled accounts that the README already
  requires, so the labels feed the gold set instead of being a gimmick.

Implementation: 20 hand-checked examples frozen into `data/sample/`, one quiz view.
Build it last; it is cuttable without touching anything else. Private accounts stay
hashed and unnamed, per the privacy rules.

## Explicitly not merging

- The claim tester UI: screen 2's verdict framing already does that job.
- The intervention simulator: the bots-removed re-ranking toggle on screen 2 is
  the same idea at a fraction of the build.
- A browser quick-scan for new topics: the X-ray is that idea done properly,
  server-side with the saved model.
- The alternative's 20-second game opening: Isaac's 10-second opening is tighter,
  and the X-ray is the live moment.

## Resulting demo

Unchanged from mvp-walkthrough.md, with three additions: screen 2 gains the
sensitivity strip, every screen gains the evidence drawer, and challenge mode sits
behind the X-ray as the fallback and the post-pitch table activity.

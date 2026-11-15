---
written_by: assistant
date: 2026-11-14
---

# Demo video (Headcount): vision, shot list and voiceover

Status: plan only. The video is not rendered yet. Tooling lives in `web/video/` (see its README once set up).

## Vision

Two minutes, one idea: volume is not consensus. The video should feel like a calm newsroom tool, not a hype reel. It moves the way an editor's attention moves: a claim arrives, we check it, the answer lands, then we show why you can trust the answer.

Look and feel:
- The product's own "careful instrument" palette: warm paper, ink, one red reserved for "likely automated".
- Slow, deliberate camera moves: the frame eases in on whatever matters (the headline number, the toggle, the reply bubble) and eases out. No spinning, no whooshes.
- A visible, smooth cursor; typing at a human pace.
- Captions on screen the whole time, in the product's type (Newsreader for big lines, IBM Plex Sans for captions), so it works with the sound off.
- Voiceover: one calm, neutral voice (candidates: River or Eric on ElevenLabs). Low, unobtrusive music bed that drops out under key numbers.
- Every number on screen comes from the real data and real API responses. Nothing staged except the order of shots.

## Shot list (target 2:00)

| Time | Shot | What's on screen | Camera |
|---|---|---|---|
| 0:00-0:07 | Cold open | Phone: the text "Was Jensen Huang's mistress a Chinese spy?" being sent | tight on the bubble |
| 0:07-0:18 | The flood | Real Bluesky posts about the story scrolling fast, a counter ticking to 46,656. Only posts from public accounts (the export's `public_accounts`, the nameable set); otherwise blur handles, avatars and links | slow push in on the counter |
| 0:18-0:24 | Title | Product name and the line "How much of this is real?" | static |
| 0:24-0:44 | The answer, by text | Phone: "Checking who is pushing that", then the real reply, then the chart image | ease in on the reply lines, then the chart |
| 0:44-1:04 | Where the automation was | Dashboard chapter 2 then 3: 4.5% overall, narratives ranked, "Defending Huang" at 4.8%, click the remove-likely-automated toggle | zoom to the headline sentence, then to the toggle and bars |
| 1:04-1:20 | Newsrooms vs Bluesky | Dashboard chapter 4: 54% / 50% / 29% hedging bars | zoom on the three bars, hold on 29% |
| 1:20-1:38 | Any story, live | Web checker: type a current story, the live steps run (sped up, marked "sped up"), the result headline | zoom on the progress steps, then the headline |
| 1:38-1:52 | How we know | Evidence drawer with timestamps and reasons (public accounts only, or handles, avatars and links blurred); method chapter numbers (36% vs 4.5%: recall@100 against posting rate alone; 79%: claim retrieval recall@20 on the first 20 hand-checked claims); privacy line | quick zooms, one per proof |
| 1:52-2:00 | Close | "Volume is not consensus." Product name, team, tracks | static, music out |

Privacy: the video is public, so no frame may show a private account's post, handle, avatar or link (README rule 4). The flood and every evidence frame use public accounts' posts only (the export's `public_accounts` / nameable set), or blur handles, avatars and links.

Phone shots: best is Isaac's real iPhone screen recording of texting the agent (Control Center screen recording), dropped into a phone frame. Fallback: the phone frame from the iMessage mockup with the real reply text from the API, labeled as a re-creation.

## Voiceover (about 280 words, 150 words a minute)

> Last week, Jensen Huang resigned from Nvidia. Within days, Bluesky had forty-six thousand posts about it.
>
> When thousands of accounts repeat something, it looks like everyone is saying it. Reporters quote it. Markets move on it. But volume isn't consensus. And AI has made volume almost free to manufacture.
>
> So we built a way to check. Text it a claim, or type any story. In under a minute, from public data, it shows who is pushing it, how much of that is automated, and who carried it.
>
> Here's the claim everyone was sharing. Most of the posts are jokes. The spy plot is about a quarter, and about four percent of it comes from likely automated accounts. It never says whether the claim is true. It measures who's pushing it.
>
> Across the whole week, four and a half percent of posts came from likely automated accounts. The Washington Post reported bots defending Huang on X. On Bluesky, we don't see it. Posts defending him look like everyone else. The automation was in the accounts relaying the news.
>
> Then we compared Bluesky with ten wire services and public broadcasters. Fifty-four percent of their spy headlines hedge: alleged, suspected. When people share the link, the hedge mostly survives. When they retell it in their own words, it drops to twenty-nine percent.
>
> And it works on any story. Type a claim, and it searches Bluesky live, sorts the posts into narratives, and scores every account behind them.
>
> Every number opens to its evidence. The model learned from accounts that admit they're bots, it shows its reasons, and it finds about eight times more of them than posting rate alone. Private accounts are counted, never named.
>
> Volume is not consensus. Now you can see how much of it is real.

Numbers in the script and where they come from: 46,656 posts (posts.parquet); the claim reply (live API, b61ff2f2ead5); 4.5% and 4.8% (eval/bots/narrative_shares.md, model v1-hgb-202611150335); 54/50/29 (eval/news/report.md, story_baseline.json); 0.356 vs 0.045 = about 8x, shown as 36% vs 4.5% (eval/bots/report-vm.md, README holdout, mean of 5 splits); 79% = retrieval recall@20 of 0.787 on the first 20 claims, 0.646 on all 50 (eval/retrieval/report-hybrid.md). Re-check each against the final data on the day of recording.

## Production steps (once the tooling is proven)

1. Capture each web shot with the Playwright capture script at 1920x1080, logging the cursor and click targets for zooms.
2. Get the phone shots (Isaac's screen recording, or the mockup re-creation).
3. Synthesize the voiceover per section with ElevenLabs (with timestamps for captions); about 1,700 characters of a 158,499 monthly allowance.
4. Compose in the video project: shots, zooms from the click log, captions, title cards, music bed with ducking.
5. Render 1080p mp4; check stills; upload to YouTube unlisted for the Devpost.

## Open decisions for Isaac

- Product name (Devpost draft options: Who's Pushing This, Volume Check, Echo Count).
- Voice: River (neutral, calm) or Eric (smooth, trustworthy), after hearing the test lines.
- Real phone recording or re-creation for the text-message shots.

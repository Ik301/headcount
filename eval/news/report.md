# News baseline report (H10)

What these newsrooms report about the Jensen Huang story, next to the Bluesky conversation. The outlets are wire services and public broadcasters, each labeled with its funding. They are accountable and edited, but not neutral and not "the truth".

Commands (Sat Nov 14, 17:50 ET):

```
python -m src.news.baseline label   # dedupe + relevance filter + DeepSeek labels (cached), writes data/processed/news/story_baseline.json
python -m src.news.baseline story   # recompute the table below from the caches (rerun after post_narrative changes)
```

Social side: `posts.parquet` (46,656 posts) joined to `post_narrative.parquet` as of 17:45 ET; the 2,379 posts without a narrative label count as n0. The social shares move whenever the narratives are regenerated. The headline labels don't need a rerun unless `NARRATIVES` in `src/narratives/label.py` changes; the cache is keyed by a hash of the taxonomy.

## Headlines

- 1,007 raw rows from `src/ingest/news.py`. After cleaning the Google News " - Outlet" suffixes and removing duplicates (same link, or same outlet and same title), the relevance filter kept 357. The filter keeps a headline if it contains huang, nvidia, jensen or kress as a whole word, or if its bge-small similarity to the story text is at least 0.55. That let 22 headlines without the terms through, such as "Political fallout from AI chip spying scandal".
- DeepSeek dropped 17 of the 357 as off-topic, for example "Hegseth impeachment: What is he accused of…" and "Acquitted 'China spy' Chris Cash…". That leaves **340 story headlines across 10 outlets**.

## Per-narrative share: news vs social

| Narrative | News headlines (primary) | News share | Headlines mentioning (primary or secondary) | Social posts | Social share | Only on social |
|---|---:|---:|---:|---:|---:|---|
| n1 Spy plot and national security | 121 | 35.6% | 181 | 8,950 | 19.2% |  |
| n2 The affairs as personal misconduct | 20 | 5.9% | 79 | 4,341 | 9.3% |  |
| n3 Trump and politics | 50 | 14.7% | 72 | 3,819 | 8.2% |  |
| n4 Board, resignation and succession | 75 | 22.1% | 100 | 5,309 | 11.4% |  |
| n5 Stock, market and lawsuits | 61 | 17.9% | 75 | 3,356 | 7.2% |  |
| n6 Defending Huang | 8 | 2.4% | 11 | 1,494 | 3.2% |  |
| n7 Jokes and memes | 2 | 0.6% | 2 | 10,598 | 22.7% | yes |
| n0 No narrative | 3 | 0.9% | 3 | 8,789 | 18.8% |  |

"Only on social" means the narrative holds at least 5% of social posts, while fewer than 2% of headlines touch it.

## Hedging on the spy claim

A text counts as spy-related if it matches `spy|spies|spying|espionage|chinese intelligence|ministry of state security|honey trap`. It counts as hedged if it contains a phrase from `HEDGE_TERMS`: alleged, allegedly, allegation(s), suspected, reportedly, accused, accusation(s), claim(s), claimed, purported(ly), according to, tied to, linked to.

| Side | Hedged / n | Share |
|---|---:|---:|
| News headlines | 49 / 90 | 54.4% |
| Bluesky posts, all | 3,152 / 7,239 | 43.5% |
| Bluesky posts with a link (often a shared headline) | 2,509 / 5,038 | 49.8% |
| Bluesky posts without a link (people's own words) | 643 / 2,201 | 29.2% |

On the same definition, the earlier figure of "57% of news vs about 27% of Bluesky" does not reproduce for all posts. It roughly matches only when the social side is restricted to posts without a link. Posts that share a link keep the headline's careful wording; people's own words mostly drop it. Restricting to the brief's ten terms only (no inflections): news 51.1%, social 39.5%.

## Attributed framing

- "Smear" framing (`smear|witch hunt|hit job|slander|defamation|fabricated|hoax`) appears in 3 headlines, and all 3 attribute it to China:
  - PBS NewsHour (public broadcaster, US nonprofit): "China dismisses claims of spy plot involving Nvidia CEO Huang as a smear campaign"
  - France24 (public broadcaster, French state-funded): "China accuses US of 'fabricating' Nvidia spy claims to push tech 'blockade'"
  - Al Jazeera (broadcaster, Qatar state-funded): "China says US 'fabricating' Nvidia spy claims to justify tech 'blockade'"
- Defending Huang (n6) is the primary or secondary label of 11 headlines. 7 of them attribute the defense to someone: Trump (2), China or Chinese media (4), the New York Times (1). Example: Al Jazeera, "Trump defends Nvidia CEO amid Chinese spying allegations". No headline calls the story a smear in the outlet's own voice. Trump appears as a defender, not as the source of a "smear" claim.

## Claim view example

`news_for_claim("Was Jensen Huang's mistress a Chinese spy?", <446 matched Bluesky posts>)`:

- 23 matching headlines. The similarity cutoff is 0.667, which is max(0.62, mean + 1.5 sd over all headlines). Top match: France24, "Nvidia CEO probed over alleged China spy: Who exactly is Jensen Huang?" (0.746).
- Narratives in the matched news: n1 spy (20 of 23), n2 affairs (15), n4 (3), n5 (2), n3 (1).
- Only on social: n7 Jokes and memes, 50.2% of the matched posts, none of the matched headlines (2 in the whole story).
- Hedging: news 34.8% (n=23), social 18.2% (n=446).

## Limits

- Hedging is lexical. It counts a dismissive "these claims are nonsense" as a hedge and misses "report says".
- The headlines come from Google News site search, which is loose and capped at 100 per outlet. Coverage is what that search returned, not every story each outlet ran.
- A single DeepSeek pass at temperature 0 labels the narratives. The headline labels have not been checked against hand labels.

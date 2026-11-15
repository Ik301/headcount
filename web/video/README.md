# web/video: demo video pipeline

This folder holds the tooling for the demo video. It is not the demo itself. It runs headless on the VM:

```
capture/capture.py   Playwright drives the live app -> public/capture/<name>/video.mp4 (3840x2160) + timeline.json
tts/tts.py           ElevenLabs with-timestamps   -> public/vo/<id>.mp3 + <id>.json (word timings)
music/make_pad.py    placeholder music bed        -> public/music/pad.mp3
src/                 Remotion composition: title card, framed screen, camera zooms, rendered cursor,
                     burned-in captions, VO + ducked music  -> out/<name>.mp4
```

## Why this pipeline

Each tool below is checked on GitHub (Nov 14, 2026):

| Need | Choice | Licence |
|---|---|---|
| Composition and render | [Remotion](https://github.com/remotion-dev/remotion) 4.0.543, 73k stars, pushed today | Remotion License, which is source-available, not OSI. **See the licence warning below.** |
| Browser capture | [Playwright](https://github.com/microsoft/playwright) (Python, already on the VM) plus a CDP `Page.startScreencast` | Apache-2.0 |
| Zoom and cursor | Written here (`src/lib/camera.ts`, `src/lib/timeline.ts`, `src/components/Cursor.tsx`), driven by the capture timeline | ours |
| Captions | Built from the ElevenLabs character alignment. No Whisper step. | n/a |
| Encode | ffmpeg 6.1 (system) | LGPL/GPL |

Reasons for this choice:
- **Remotion renders headless** with its own Chrome Headless Shell. It is React and TypeScript, so the timeline JSON drives everything: zoom targets, cursor path, caption timing, VO placement. Nothing in the edit is done by hand.
- **Screen-Studio-style tools don't fit this VM.** [OpenScreen](https://github.com/siddharthvaddem/openscreen) (MIT, 40k stars) is an Electron desktop app and its repo is now archived. [Cap](https://github.com/CapSoftware/Cap) (AGPL, 25k) is a desktop recorder. [Screenize](https://github.com/syi0808/screenize) (Apache-2.0) is macOS-only and paused. [framepipe](https://github.com/martian0x80/framepipe) (GPL-3.0) is a Linux desktop recorder. All of them record a real display. Here we already know every cursor move and every element box, because we script the browser. The capture logs them and the composition reproduces the Screen Studio look (spring-eased zooms, a smooth cursor that fades when idle, click ripples) without a display at all.
- **Why not `record_video` or puppeteer-screen-recorder.** Playwright's `record_video` is capped at viewport size and writes low-bitrate VP8. [puppeteer-screen-recorder](https://github.com/prasanaworld/puppeteer-screen-recorder) (MIT, 457 stars, last push Jan 2025) uses the same screencast, but its own timing is opaque. Our capture keeps device-pixel JPEG frames (4K at DSF 2), so a 1.8x zoom stays sharp.

Alternatives considered:
- [HyperFrames](https://github.com/heygen-com/hyperframes): Apache-2.0, 84k stars, active. HTML-to-video with a CLI renderer. **This is the fallback if the Remotion licence is a problem.** `camera.ts`, `timeline.ts` and the caption paging are plain TypeScript and would port as they are.
- [Motion Canvas](https://github.com/motion-canvas/motion-canvas): MIT, 19.9k stars, last push Jul 2026. Better suited to animated diagrams than screen footage.
- [Revideo](https://github.com/midrender/revideo): MIT, 4.2k stars, last push Jul 2026. Now under midrender, and activity has slowed.
- [editly](https://github.com/mifi/editly): MIT, 5.6k stars, last push May 2025. Declarative ffmpeg, but no per-frame camera.
- Plain ffmpeg `zoompan`: workable for one zoom, but painful for cursor overlays, captions and transitions together.

### Licence warning (Remotion)

The free licence covers "an individual" or "an organization or team of individuals with up to 3 people" ([FAQ](https://www.remotion.dev/docs/license/faq), [LICENSE.md](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)). The FAQ calls this the "4-person threshold". **A 4-person team that works together on this Remotion project is over the threshold.** Options:
1. One person (Isaac) owns and runs the Remotion project, and teammates only receive the MP4. The FAQ treats people who only receive the finished file as non-users. If you take this option, keep `web/video` out of the shared repo or mark it as Isaac's.
2. Rely on the "evaluating ... not yet using it in a commercial way" clause. A hackathon demo is non-commercial, but this reading is untested.
3. Buy a Remotion for Creators seat ($25/month per the FAQ).
4. Port the composition to HyperFrames (Apache-2.0).

The capture, TTS and music scripts don't depend on Remotion.

## Commands (from `web/video/`)

```bash
npm install                          # once; also run `npx remotion browser ensure` (downloads Chrome Headless Shell)

# 1. capture: drives the live app (WEB_BASE overrides), writes public/capture/test/{video.mp4,timeline.json}
WEB_BASE=https://bring-fisher-headed-mill.trycloudflare.com DSF=2 FPS=30 python3 capture/capture.py test

# 2. voiceover: cached by text+voice+model hash, so re-runs cost 0 credits
python3 tts/tts.py --id test-river --voice river --text "One short line."
python3 tts/tts.py --script tts/test-script.json          # list of {id, text, voice, model?}
#    voices: river = SAz9YHcvj6GT2YYXdXww, eric = cjVigY5qzO86Huf0OWal, or any voice id
#    --model eleven_multilingual_v2 (default) | eleven_v4 (newest, also returns timestamps) | eleven_v3

# 3. music bed (placeholder; replace for the final cut)
python3 music/make_pad.py 24

# 4. render
npx remotion render src/index.ts Test out/test.mp4        # or TestEric for the other voice
npx remotion studio src/index.ts                          # interactive preview; needs a browser, so tunnel port 3000 if used
npm run stills                                            # 4 PNG stills from out/test.mp4
```

## How an edit is specified

Each video is one file in `src/edits/` (see `src/edits/test.ts`), registered in `src/Root.tsx`. Times refer to the capture through **time refs** resolved against `timeline.json`:

- a number: capture seconds
- `'mark:<label>'`: from `r.mark("label")` in the scenario
- `'focus:<label>'`: from `r.focus("label", locator)`, which also stores the element's box
- `'click:<n>'`, `'type:<n>'`, `'move:<n>'`: the nth event of that kind, counting from 0
- `'end'`
- every ref takes an optional `offset` in seconds

**Zoom targets:** first, in the capture scenario, call `r.focus("headline", locator)` while the element is on screen. That logs its bounding box (CSS px, 24 px padding). Then in the edit:

```ts
zooms: [{at: 'mark:result-visible', offset: 0.35, ramp: 1.0, hold: 2.3, scale: 1.8, target: 'focus:headline'}]
```

A zoom ramps in over `ramp` seconds with a `bezier(.65,0,.35,1)` ease, holds, then ramps out. The scale is capped so the box always fits, and the view is clamped inside the recording. Use `target: 'cursor'` to follow the cursor instead. Zooms run in order, and the later one wins if they overlap.

**Voiceover placement:** `voiceover.align = {wordIndex, at}` makes word number `wordIndex` start exactly at capture time `at`. For example, "In about a second" lands on the click on Check. Captions come from the same word timings: pages of up to 7 words or 44 characters, broken at punctuation, with spoken words fully opaque.

**Cursor:** headless Chrome draws no cursor. `capture.py` logs each move with its from/to points, start and end times, easing and arc. `cursorAt()` replays exactly the same curve. The cursor scales with the zoom, shows a ripple on clicks, and fades after `cursorIdleHide` seconds (default 1.6) without movement. That also hides it while typing.

**New scenarios:** add a function to `SCENARIOS` in `capture/capture.py`. Use `r.click(locator)`, `r.move_to(locator, anchor=(fx, fy))`, `r.type(text)`, `r.scroll(dy)`, `r.focus(label, locator)`, `r.mark(label)` and `r.wait(ms)`.

## Test result (Nov 14, 2026)

- `out/test.mp4`: 1920x1080, 30 fps, H.264 + AAC, 13.7 s, 3.4 MB. It runs the title card ("Headcount" / "Volume is not consensus."), a fade, the claim typed, Check, the result, and a 1.8x zoom on the headline, with captions, the River VO and the pad. The app's own nav still says "Claim check": the capture shows the live app as it is.
- Stills: `out/still_1.4s.png` (title), `still_5.5s.png` (typing), `still_9.6s.png` (result, zoom starting), `still_11.6s.png` (full zoom), plus a 2x2 grid in `out/contact.png`.
- **Render time: 146 s for 13.7 s** (about 10.7x real time) with concurrency 3 on 4 vCPUs. Other runs took 194 s and 226 s while the API and other jobs were busy. **Expect about 22-35 min for a 2-minute cut.** Capture took 34 s wall.
- **ElevenLabs:** 3 calls of 145 characters each, so **435 characters billed** per the `x-character-count` header. The Creator quota is 158,499 per cycle. The samples are `public/vo/test-river.mp3` and `test-eric.mp3` (both multilingual_v2), plus `test-river-v4.mp3` (eleven_v4) to show that v4 also returns timestamps.

## Music

No royalty-free track existed on the VM. `music/make_pad.py` synthesizes a soft Am-F-C-G pad, which is original, so there are no licence questions, but it is clearly a placeholder. It plays at volume 0.16 and ducks to 0.07 under the VO. In the test mix it measures about -48 dB mean before the VO, so raise `music.volume` to about 0.3 if a real track is too quiet. Options for the final cut:
- **YouTube Audio Library.** Free, and many tracks need no attribution. Needs a Google login, so download it through Camofox or by hand.
- **Pixabay Music.** Pixabay Content License, no attribution required. The site is Cloudflare-walled to curl.
- **Kevin MacLeod / incompetech.** CC BY 4.0, free if you credit the track in the description ([licences](https://incompetech.com/music/royalty-free/licenses/)).
- **ElevenLabs Music** (`POST /v1/music`). Generates a bed from a prompt and uses Creator credits; check the plan's commercial terms first.

Drop the file at `public/music/<name>.mp3` and set `music.file` in the edit.

## Limits and known issues

- **Screencast timing.** Frames arrive only when the page repaints, and capture resamples them to constant 30 fps (the last frame is held). At DSF 2 Chrome rasterizes on the CPU. Fast typing can lag the DOM by up to about 0.5 s, and big page swaps show up about 0.1-0.3 s after Playwright sees them. Clicks match the video to within about 0.1 s. Mitigations: type at 60 ms or slower per key, start zooms about 0.3 s after a `mark`, or use `DSF=1.5` and `JPEG_Q=80` for faster frames.
- **DSF 2 needs both settings.** It requires `--force-device-scale-factor=2` (set in `capture.py`) as well as the context's `device_scale_factor`. Without the flag the screencast sends 1920-wide frames.
- **CSS animations and video in the app** are captured only as fast as the screencast frame rate (about 10-12 fps at 4K). Static UI looks perfect.
- **Memory.** About 7.7 GB of RAM is shared with the API. The render peaked at about 1.3 GB RSS. Don't render while other heavy jobs run.
- **Not rendered:** transitions other than fade (`@remotion/transitions` has slide, wipe and others), lower-thirds, and SFX. These are straightforward to add.
- The capture hits the **live app** and doesn't restart anything. Cached claims (the Jensen week) answer in about 1.5 s. Live claims can take up to a minute, so trim the wait with `trim` or with a `mark` after the result.
- `public/capture/` and `out/` are git-ignored because they can be regenerated. VO mp3/json files are kept because they cost credits.

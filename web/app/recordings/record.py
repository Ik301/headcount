"""Backup recordings (webm, each under 60 s), Playwright with system Chrome (channel="chrome").
Desktop modes record 1440x900; the -mobile modes record a 390x844 phone viewport (touch, 2x; the video is 390x844: Playwright records CSS pixels).
Usage: python3 web/app/recordings/record.py claim|live|story|claim-mobile|challenge-mobile ["claim text"]
WEB_BASE overrides the web app URL."""
import os, re, shutil, sys, time
from playwright.sync_api import sync_playwright

WEB = os.environ.get("WEB_BASE", "https://bring-fisher-headed-mill.trycloudflare.com")
DEST = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(os.environ.get("TMPDIR", "/tmp"), "sbt_video_tmp")
os.makedirs(DEST, exist_ok=True)
which = sys.argv[1]
claim = sys.argv[2] if len(sys.argv) > 2 else None
FLAG = "Was Jensen Huang's mistress a Chinese spy?"
NAMES = {
    "claim": "claim-jensen-mistress-spy.webm",
    "live": "claim-live-any-story.webm",
    "story": "story-dashboard.webm",
    "claim-mobile": "mobile-claim-jensen-mistress-spy.webm",
    "challenge-mobile": "mobile-challenge.webm",
}
mobile = which.endswith("-mobile")


def smooth_scroll(pg, total, steps=30, pause=60):
    for _ in range(steps):
        if mobile:  # a touch-emulated page ignores wheel events
            pg.evaluate(f"window.scrollBy(0, {total / steps})")
        else:
            pg.mouse.wheel(0, total / steps)
        pg.wait_for_timeout(pause)


def tap(loc):
    loc.tap() if mobile else loc.click()


def run_claim(pg, text, info):
    pg.goto(WEB + "/", wait_until="networkidle")
    pg.wait_for_timeout(1200)
    pg.click("textarea")
    pg.keyboard.type(text, delay=35)
    pg.wait_for_timeout(500)
    t0 = time.time()
    tap(pg.locator("button", has_text="Check").first)
    pg.wait_for_url(re.compile(r".*/claim/[0-9a-zA-Z]+"), timeout=75000)
    pg.wait_for_selector("#res-h", timeout=75000)
    info["answer_s"] = round(time.time() - t0, 1)
    info["url"] = pg.url


with sync_playwright() as p:
    shutil.rmtree(TMP, ignore_errors=True)
    b = p.chromium.launch(channel="chrome")
    if mobile:
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                            record_video_dir=TMP, record_video_size={"width": 390, "height": 844})
    else:
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=TMP, record_video_size={"width": 1440, "height": 900})
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    t0 = time.time()
    info = {}
    if which in ("claim", "live"):
        run_claim(pg, claim or FLAG, info)
        pg.wait_for_timeout(3500)
        smooth_scroll(pg, 900, steps=25, pause=90)
        pg.wait_for_timeout(2500)
        smooth_scroll(pg, 900, steps=25, pause=90)
        pg.wait_for_timeout(2500)
        smooth_scroll(pg, 900, steps=25, pause=90)
        pg.wait_for_timeout(2000)
        info["headline"] = " ".join(pg.inner_text("#res-h").split())[:200]
    elif which == "claim-mobile":
        run_claim(pg, claim or FLAG, info)
        pg.wait_for_timeout(3000)
        rc = pg.locator("#res-h .rc-num").first
        if rc.count():  # open the headline's receipt, read it, close it
            rc.tap()
            pg.wait_for_timeout(3500)
            pg.touchscreen.tap(20, 120)
            pg.wait_for_timeout(600)
        for _ in range(5):
            smooth_scroll(pg, 700, steps=25, pause=80)
            pg.wait_for_timeout(2200)
        info["headline"] = " ".join(pg.inner_text("#res-h").split())[:200]
    elif which == "challenge-mobile":
        pg.goto(WEB + "/challenge", wait_until="networkidle")
        pg.wait_for_selector(".c-choice.c-auto")
        pg.wait_for_timeout(2500)
        smooth_scroll(pg, 500, steps=20, pause=80)  # the posts, with an English translation over the original
        pg.wait_for_timeout(2500)
        smooth_scroll(pg, 700, steps=20, pause=80)
        pg.wait_for_timeout(1500)
        pg.locator(".c-choice.c-auto").tap()
        pg.wait_for_timeout(4500)  # the reveal: score, cutoff, reasons
        smooth_scroll(pg, 400, steps=15, pause=80)
        pg.wait_for_timeout(2000)
        pg.locator(".c-primary").first.tap()
        pg.wait_for_timeout(2500)
        smooth_scroll(pg, 900, steps=25, pause=80)
        pg.wait_for_timeout(1000)
        pg.locator(".c-choice.c-person").tap()
        pg.wait_for_timeout(5000)
    elif which == "story":
        # guided story: step through the six chapters; ?ch=N addresses each one
        for ch, dwell in ((1, 9000), (2, 6000), (3, 7000), (4, 7000), (5, 6000), (6, 5000)):
            pg.goto(WEB + f"/story?ch={ch}", wait_until="networkidle")
            pg.wait_for_timeout(dwell // 2)
            if ch == 3:
                toggle = pg.locator("button", has_text=re.compile("likely automated", re.I)).first
                if toggle.count():
                    toggle.click()
                    pg.wait_for_timeout(2500)
            smooth_scroll(pg, 500, steps=15, pause=70)
            pg.wait_for_timeout(dwell // 2)
    info["elapsed_s"] = round(time.time() - t0, 1)
    info["console_errors"] = errs
    video = pg.video
    ctx.close()
    src = video.path()
    b.close()
    shutil.move(src, os.path.join(DEST, NAMES[which]))
    info["file"] = os.path.join(DEST, NAMES[which])
    print(info)

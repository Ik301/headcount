"""Backup recordings (webm, 1440x900, each under 60 s), Playwright with system Chrome (channel="chrome").
Usage: python3 web/app/recordings/record.py claim|live|story ["claim text"]. WEB_BASE overrides the web app URL."""
import os, re, shutil, sys, time
from playwright.sync_api import sync_playwright

WEB = os.environ.get("WEB_BASE", "https://bring-fisher-headed-mill.trycloudflare.com")
DEST = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(os.environ.get("TMPDIR", "/tmp"), "sbt_video_tmp")
os.makedirs(DEST, exist_ok=True)
which = sys.argv[1]
claim = sys.argv[2] if len(sys.argv) > 2 else None


def smooth_scroll(pg, total, steps=30, pause=60):
    for _ in range(steps):
        pg.mouse.wheel(0, total / steps)
        pg.wait_for_timeout(pause)


with sync_playwright() as p:
    shutil.rmtree(TMP, ignore_errors=True)
    b = p.chromium.launch(channel="chrome")
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=TMP, record_video_size={"width": 1440, "height": 900})
    pg = ctx.new_page()
    t0 = time.time()
    info = {}
    if which in ("claim", "live"):
        pg.goto(WEB + "/", wait_until="networkidle")
        pg.wait_for_timeout(1200)
        pg.click("textarea")
        pg.keyboard.type(claim, delay=35)
        pg.wait_for_timeout(500)
        pg.locator("button", has_text="Check").first.click()
        pg.wait_for_url(re.compile(r".*/claim/[0-9a-f]+"), timeout=75000)
        pg.wait_for_selector("text=matching posts", timeout=75000)
        info["answer_s"] = round(time.time() - t0, 1)
        info["url"] = pg.url
        pg.wait_for_timeout(3500)
        smooth_scroll(pg, 900, steps=25, pause=90)
        pg.wait_for_timeout(2500)
        smooth_scroll(pg, 900, steps=25, pause=90)
        pg.wait_for_timeout(2500)
        smooth_scroll(pg, 900, steps=25, pause=90)
        pg.wait_for_timeout(2000)
        info["body_head"] = pg.inner_text("body")[:400]
    elif which == "story":
        pg.goto(WEB + "/story", wait_until="networkidle")
        pg.wait_for_timeout(2500)
        pg.locator("button[aria-label*=\"replay\" i], button:has-text(\"Play\")").first.click()
        pg.wait_for_timeout(14000)
        smooth_scroll(pg, 700, steps=20, pause=80)
        pg.wait_for_timeout(2500)
        pg.mouse.wheel(0, -3000)
        pg.wait_for_timeout(800)
        pg.locator("button", has_text="Without likely automated").first.click()
        pg.wait_for_timeout(3000)
        pg.locator("button", has_text="Remove likely automated accounts").first.click()
        pg.wait_for_timeout(3500)
        pg.locator("button", has_text="Remove likely automated accounts").first.click()
        pg.wait_for_timeout(1500)
        smooth_scroll(pg, 800, steps=20, pause=80)
        pg.wait_for_timeout(2000)
        pg.mouse.wheel(0, -3000)
        pg.locator("button", has_text="Amplifier archetypes").first.click()
        pg.wait_for_timeout(4000)
        pg.locator("button", has_text="Evidence").first.click()
        pg.wait_for_timeout(3500)
        pg.locator("button", has_text="Method").first.click()
        pg.wait_for_timeout(4000)
    info["elapsed_s"] = round(time.time() - t0, 1)
    video = pg.video
    ctx.close()
    src = video.path()
    b.close()
    name = {"claim": "claim-jensen-mistress-spy.webm", "live": "claim-live-any-story.webm", "story": "story-dashboard.webm"}[which]
    shutil.move(src, os.path.join(DEST, name))
    info["file"] = os.path.join(DEST, name)
    print(info)

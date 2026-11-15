"""Screenshot every chapter of the guided story at 1440x900 and 390 wide (full page), plus explore mode.
Usage: python3 shots.py <outdir> [base_url]"""
import sys, asyncio
from playwright.async_api import async_playwright

OUT = sys.argv[1]
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:4174"
CH = ["1-what-happened", "2-how-much", "3-where", "4-newsrooms", "5-who-spread", "6-how-we-know"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        for w, h, tag in ((1440, 900, "1440"), (390, 844, "390")):
            ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if w > 500 else 2)
            pg = await ctx.new_page()
            errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            for i, name in enumerate(CH, 1):
                await pg.goto(f"{BASE}/story?ch={i}&still=1", wait_until="networkidle")
                await pg.wait_for_timeout(500)
                await pg.screenshot(path=f"{OUT}/story-{name}-{tag}.png", full_page=(tag == "390"))
                if tag == "1440":
                    await pg.screenshot(path=f"{OUT}/full/story-{name}-{tag}-full.png", full_page=True)
            # chapter 3 with the toggle on
            await pg.goto(f"{BASE}/story?ch=3&still=1", wait_until="networkidle")
            await pg.click(".g-switch")
            await pg.wait_for_timeout(800)
            await pg.locator(".g-sub").scroll_into_view_if_needed()
            await pg.screenshot(path=f"{OUT}/story-3-where-removed-{tag}.png", full_page=(tag == "390"))
            # first view: autoplay mid-week
            await ctx.clear_cookies()
            await pg.evaluate("localStorage.clear()")
            await pg.goto(f"{BASE}/story", wait_until="networkidle")
            await pg.wait_for_timeout(7000)
            await pg.screenshot(path=f"{OUT}/story-1-autoplay-midweek-{tag}.png", full_page=False)
            if tag == "1440":
                for v in ("replay", "nobots", "archetypes", "method"):
                    await pg.goto(f"{BASE}/story?mode=explore&view={v}", wait_until="networkidle")
                    await pg.wait_for_timeout(500)
                    await pg.screenshot(path=f"{OUT}/explore-{v}-{tag}.png")
            print(tag, "errors:", errs[:5])
            await ctx.close()
        await b.close()


asyncio.run(main())

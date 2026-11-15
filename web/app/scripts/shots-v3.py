"""v3 screenshots: guided story chapters 2 to 5, the flagship claim result, and /challenge (card, reveal, final),
each at 1440x900 and 390 wide. Usage: python3 scripts/shots-v3.py <outdir> [base_url] [api_url]"""
import asyncio
import json
import sys
import urllib.request

from playwright.async_api import async_playwright

OUT = sys.argv[1]
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:4175"
API = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8000"
CLAIM = "Was Jensen Huang's mistress a Chinese spy?"
CH = {2: "2-how-much", 3: "3-where", 4: "4-newsrooms", 5: "5-who-spread"}


def claim_id() -> str:
    req = urllib.request.Request(f"{API}/claim", data=json.dumps({"text": CLAIM, "mode": "auto"}).encode(), headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))["claim_id"]


async def main():
    cid = claim_id()
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        for w, h, tag in ((1440, 900, "1440"), (390, 844, "390")):
            full = tag == "390"
            ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if w > 500 else 2)
            pg = await ctx.new_page()
            errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            for i, name in CH.items():
                await pg.goto(f"{BASE}/story?ch={i}&still=1", wait_until="networkidle")
                await pg.wait_for_timeout(600)
                await pg.screenshot(path=f"{OUT}/story-{name}-{tag}.png", full_page=True)
            await pg.goto(f"{BASE}/claim/{cid}?api={API}", wait_until="networkidle")
            await pg.wait_for_selector("#res-h", timeout=60000)
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{OUT}/claim-mistress-spy-{tag}.png", full_page=full)
            await pg.goto(f"{BASE}/challenge", wait_until="networkidle")
            await pg.wait_for_selector(".c-choice.c-auto")
            await pg.wait_for_timeout(600)
            await pg.screenshot(path=f"{OUT}/challenge-card-{tag}.png", full_page=full)
            await pg.click(".c-choice.c-auto")  # account 1
            await pg.wait_for_timeout(700)
            await pg.screenshot(path=f"{OUT}/challenge-reveal-{tag}.png", full_page=full)
            await pg.click(".c-primary")
            await pg.click(".c-choice.c-person")  # account 2 (has a hand label)
            await pg.wait_for_timeout(700)
            await pg.screenshot(path=f"{OUT}/challenge-reveal-handlabel-{tag}.png", full_page=full)
            await pg.click(".c-primary")
            await pg.click(".c-choice.c-auto")  # account 3
            await pg.wait_for_timeout(300)
            await pg.click(".c-secondary")
            await pg.wait_for_timeout(700)
            await pg.screenshot(path=f"{OUT}/challenge-final-{tag}.png", full_page=full)
            if tag == "1440":
                for v in ("nobots", "archetypes", "method"):
                    await pg.goto(f"{BASE}/story?mode=explore&view={v}", wait_until="networkidle")
                    await pg.wait_for_timeout(500)
                    await pg.screenshot(path=f"{OUT}/explore-{v}-{tag}.png", full_page=True)
            print(tag, "errors:", errs[:5])
            await ctx.close()
        await b.close()
    print("claim", cid)


asyncio.run(main())

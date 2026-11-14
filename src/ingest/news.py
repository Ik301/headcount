"""News baseline: what wire services and public broadcasters report about a story.

Usage:
    python -m src.ingest.news --q "jensen huang" --after 2026-11-04 --before 2026-11-14 --out data/raw/news_jensen.jsonl

Sources (no outlet is neutral; these are wire services and public broadcasters, labeled with their funding):
- Reuters, AP, AFP: no public RSS, so headlines come from Google News RSS search restricted to the site and dates
  (Google News terms are personal and non-commercial: fine for a demo, say so on the Devpost).
- BBC, NPR, PBS, DW, France24, Al Jazeera, The Guardian: their own RSS feeds (recent items only, about a day),
  plus the same Google News site search for the story window.
Output lines: {"source", "funding", "title", "link", "published", "summary", "via"}.
"""
import argparse
import json
import re
import time
import urllib.parse
from defusedxml import ElementTree as ET  # feeds are untrusted XML: no entity expansion
from pathlib import Path

import httpx

SOURCES = {
    "Reuters": ("reuters.com", "wire service, commercial"),
    "AP": ("apnews.com", "wire service, nonprofit cooperative"),
    "AFP": ("afp.com", "wire service, French state-chartered"),
    "BBC": ("bbc.com", "public broadcaster, UK licence fee"),
    "NPR": ("npr.org", "public radio, US nonprofit"),
    "PBS NewsHour": ("pbs.org", "public broadcaster, US nonprofit"),
    "DW": ("dw.com", "public broadcaster, German state-funded"),
    "France24": ("france24.com", "public broadcaster, French state-funded"),
    "Al Jazeera": ("aljazeera.com", "broadcaster, Qatar state-funded"),
    "The Guardian": ("theguardian.com", "newspaper, trust-owned"),
}
RSS = {
    "BBC": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "PBS NewsHour": "https://www.pbs.org/newshour/feeds/rss/headlines",
    "DW": "https://rss.dw.com/rdf/rss-en-all",
    "France24": "https://www.france24.com/en/rss",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "The Guardian": "https://www.theguardian.com/technology/rss",
}
UA = {"User-Agent": "socialnet-bot-tracker (HackPrinceton research; isaackang301@gmail.com)"}


def parse(xml: str) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        get = lambda name: next((c.text or "" for c in it if c.tag.split("}")[-1] == name), "")
        link = get("link") or next((c.get("href", "") for c in it if c.tag.split("}")[-1] == "link"), "")
        out.append({"title": re.sub(r"\s+", " ", get("title")).strip(), "link": link, "published": get("pubDate") or get("updated") or get("date"), "summary": re.sub(r"<[^>]+>", " ", get("description") or get("summary"))[:500].strip()})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    terms = [t.lower() for t in re.findall(r"\w+", a.q)]
    rows, seen = [], set()
    with httpx.Client(timeout=20, headers=UA, follow_redirects=True) as c:
        for name, (domain, funding) in SOURCES.items():
            q = urllib.parse.quote(f"{a.q} site:{domain} after:{a.after} before:{a.before}")
            r = c.get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
            items = parse(r.text) if r.status_code == 200 else []
            for it in items:
                if it["link"] in seen:
                    continue
                seen.add(it["link"])
                rows.append({"source": name, "funding": funding, "via": "google_news_rss", **it})
            print(f"{name}: {len(items)} via Google News", flush=True)
            time.sleep(1.5)
        for name, url in RSS.items():
            r = c.get(url)
            items = [it for it in (parse(r.text) if r.status_code == 200 else []) if all(t in (it["title"] + " " + it["summary"]).lower() for t in terms)]
            for it in items:
                if it["link"] in seen:
                    continue
                seen.add(it["link"])
                rows.append({"source": name, "funding": SOURCES[name][1], "via": "rss", **it})
            print(f"{name}: {len(items)} matching in own RSS", flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} headlines to {a.out}")


if __name__ == "__main__":
    main()

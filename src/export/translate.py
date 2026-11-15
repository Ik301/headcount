"""Language detection and English translation for the challenge game's posts (export step, H8).

The challenge shows each account's recent posts; some accounts post in Japanese, French, Czech or Italian. The export
asks DeepSeek, in one batched call per 20 posts, to name each post's language and translate the non-English ones.
Results are cached in data/processed/challenge_translations.json (gitignored), keyed by the sha256 of the masked text
the export ships, so a rerun only calls the API for new posts.

Privacy: the translator only ever sees text that already went through the export's mask (handles of accounts that are
not nameable are already "@[account]"). A translation is dropped unless every bracketed mask of the original
("[account]", "[link]", "@[a private account]") survives verbatim, and the English text is masked again by the caller.
If the API fails or no key is set, posts ship without translation; the export never fails on this step.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import warnings
from pathlib import Path
from typing import Callable

CACHE_NAME = "challenge_translations.json"
BATCH = 20
MASK_RE = re.compile(r"@?\[[^\]\n]{1,40}\]")  # [account], [link], @[account], @[a private account]

# ISO 639-1 -> English name; the model's own name is used for anything else.
LANG_NAMES = {
    "ja": "Japanese", "fr": "French", "cs": "Czech", "it": "Italian", "es": "Spanish", "pt": "Portuguese",
    "de": "German", "nl": "Dutch", "pl": "Polish", "sk": "Slovak", "ru": "Russian", "uk": "Ukrainian",
    "zh": "Chinese", "ko": "Korean", "tr": "Turkish", "sv": "Swedish", "da": "Danish", "no": "Norwegian",
    "nb": "Norwegian", "fi": "Finnish", "ca": "Catalan", "ro": "Romanian", "hu": "Hungarian", "el": "Greek",
    "ar": "Arabic", "he": "Hebrew", "hi": "Hindi", "id": "Indonesian", "vi": "Vietnamese", "th": "Thai",
}

# A translator takes [(i, text)] and returns [{"i", "lang", "lang_name", "text_en"}] (text_en None for English).
Translator = Callable[[list[tuple[int, str]]], list[dict]]

PROMPT = """You are given social media posts, each prefixed with [n]. For each post:
1. Identify the main language of the post as an ISO 639-1 code (e.g. "en", "ja", "fr", "cs", "it").
   A post that is mostly English with a foreign word or name is "en". Posts that are only links, emoji or names are "en".
2. If the language is not English, translate the whole post faithfully into natural English.
   - Keep URLs, hashtags, emoji, numbers and line breaks as they are.
   - Keep every bracketed placeholder such as [account], [link], @[account] or @[a private account] exactly as written.
   - Never add an @handle, an account name, a link or any commentary that is not in the post.
   - If the post ends mid-sentence or with "...", end the translation the same way.

Return JSON: {{"items": [{{"i": <n>, "lang": "<code>", "lang_name": "<English name of the language>", "text_en": "<translation, or null if English>"}}]}}

Posts:
{items}"""


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def masks_kept(src: str, out: str) -> bool:
    """Every mask token of the source appears in the translation at least as often."""
    need: dict[str, int] = {}
    for m in MASK_RE.findall(src):
        need[m] = need.get(m, 0) + 1
    return all(out.count(m) >= n for m, n in need.items())


def deepseek_translator(batch: list[tuple[int, str]]) -> list[dict]:
    import httpx

    from src.news.baseline import DEEPSEEK_URL, _deepseek_key

    items = "\n\n".join(f"[{i}] {t}" for i, t in batch)
    body = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": PROMPT.format(items=items)}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=120, headers={"Authorization": f"Bearer {_deepseek_key()}"}) as client:
        for attempt in range(4):
            try:
                r = client.post(DEEPSEEK_URL, json=body)
                if r.status_code == 200:
                    return json.loads(r.json()["choices"][0]["message"]["content"]).get("items", [])
                if r.status_code not in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"DeepSeek HTTP {r.status_code}")
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                pass
            time.sleep(2**attempt)
    raise RuntimeError("DeepSeek translation failed after retries")


def _clean(r: dict, src: str) -> dict | None:
    lang = str(r.get("lang") or "").strip().lower().split("-")[0][:3]
    if not re.fullmatch(r"[a-z]{2,3}", lang):
        return None
    if lang == "en":
        return {"lang": "en"}
    en = r.get("text_en")
    if not isinstance(en, str) or not en.strip() or en.strip() == src.strip():
        return {"lang": lang, "lang_name": LANG_NAMES.get(lang) or str(r.get("lang_name") or lang)[:30]}
    out = {"lang": lang, "lang_name": LANG_NAMES.get(lang) or str(r.get("lang_name") or lang)[:30], "text_en": en.strip()}
    if not masks_kept(src, out["text_en"]):
        out.pop("text_en")  # a translation that lost a privacy mask is not shipped
    return out


def load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def translate_texts(texts: list[str], cache_path: Path | None, translator: Translator | None) -> dict[str, dict]:
    """text -> {"lang", "lang_name"?, "text_en"?} for every text we have a result for (cache or translator)."""
    cache = load_cache(cache_path) if cache_path else {}
    todo = list(dict.fromkeys(t for t in texts if t and t.strip() and text_key(t) not in cache))
    if todo and translator is not None:
        added = 0
        for s in range(0, len(todo), BATCH):
            chunk = todo[s:s + BATCH]
            try:
                res = translator(list(enumerate(chunk)))
            except Exception as e:  # never fail the export on translation
                warnings.warn(f"challenge translation skipped: {e}")
                break
            for r in res or []:
                try:
                    i = int(r.get("i"))
                except (TypeError, ValueError):
                    continue
                if 0 <= i < len(chunk) and (got := _clean(r, chunk[i])) is not None:
                    cache[text_key(chunk[i])] = got
                    added += 1
        if added and cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
            os.replace(tmp, cache_path)
    return {t: cache[text_key(t)] for t in texts if t and text_key(t) in cache}


def translate_challenge(items: list[dict], cache_path: Path | None, translator: Translator | None,
                        mask: Callable[[str, int], str]) -> dict:
    """Add lang, lang_name and text_en to each non-English challenge post in place. Returns a small summary."""
    posts = [p for a in items for p in a.get("posts", []) if isinstance(p, dict) and p.get("text")]
    if not posts:
        return {}
    got = translate_texts([p["text"] for p in posts], cache_path, translator)
    langs: dict[str, int] = {}
    for p in posts:
        r = got.get(p["text"])
        if not r or r.get("lang") == "en":
            continue
        p["lang"] = r["lang"]
        p["lang_name"] = r.get("lang_name") or r["lang"]
        if r.get("text_en"):
            en = mask(r["text_en"], 800)  # mask again: a translation must never reintroduce a handle
            if masks_kept(p["text"], en):
                p["text_en"] = en
                langs[p["lang_name"]] = langs.get(p["lang_name"], 0) + 1
    return {"posts": len(posts), "detected": len(got), "translated": sum(langs.values()), "languages": langs}

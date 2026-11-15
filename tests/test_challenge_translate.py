"""Challenge post translation (src/export/translate.py) with a stubbed translator: no network, no keys."""
import json
from pathlib import Path

import pytest

from src.export import build_site_data as B
from src.export import translate as T
from tests.test_export import write_corpus

JA = "楽天モバイル、ローミング縮小の影響は軽微 @secret-feed.bsky.social https://example.jp/a"
FR = "Le FBI condamne un vol massif @[a private account]"
EN = "Bitcoin slips under $64,000"


@pytest.fixture(autouse=True)
def salt(monkeypatch):
    monkeypatch.setenv("SALT", "test-salt")


def stub(calls):
    def tr(batch):
        calls.append([t for _, t in batch])
        out = []
        for i, t in batch:
            if t.startswith("楽天"):
                # tries to "restore" the masked handle and keeps the mask
                out.append({"i": i, "lang": "ja", "lang_name": "japanese", "text_en": "Rakuten Mobile says the impact is minor @secret-feed.bsky.social @[account] https://example.jp/a"})
            elif t.startswith("Le FBI"):
                out.append({"i": i, "lang": "fr", "lang_name": "French", "text_en": "The FBI condemns a massive theft"})  # lost the mask
            else:
                out.append({"i": i, "lang": "en", "lang_name": "English", "text_en": None})
        return out
    return tr


def picks():
    return [{"account_ref": "famous.example.com", "public_handle": "famous.example.com", "tier": "human", "p_automated": 0.1,
             "posts": [{"t": "2026-11-12T10:00:00Z", "text": JA, "kind": "post"},
                       {"t": "2026-11-12T11:00:00Z", "text": FR, "kind": "post"},
                       {"t": "2026-11-12T12:00:00Z", "text": EN, "kind": "post"}, "a plain string post"]}]


def test_challenge_posts_translated_masked_and_cached(tmp_path):
    paths = write_corpus(tmp_path)
    sample = Path(paths["sample"])
    sample.mkdir(parents=True, exist_ok=True)
    (sample / "challenge.json").write_text(json.dumps({"accounts": picks()}))
    calls = []
    c = B.load(**paths)
    c.translator = stub(calls)
    site = B.build_from(c)
    ja, fr, en, s = site["challenge"][0]["posts"]
    # the export masked the private handle before the translator saw it
    assert "secret-feed" not in calls[0][0] and "@[account]" in calls[0][0]
    assert ja["lang"] == "ja" and ja["lang_name"] == "Japanese"
    assert ja["text_en"].startswith("Rakuten Mobile") and "secret-feed" not in ja["text_en"] and "@[account]" in ja["text_en"]
    assert ja["text"] == B.Ctx.mask(c, JA, 500)  # original kept
    assert fr["lang"] == "fr" and "text_en" not in fr  # translation that dropped a privacy mask is not shipped
    assert set(en) == {"t", "text", "kind"} and s == "a plain string post"  # English and string posts unchanged
    assert c.translation["translated"] == 1 and c.translation["languages"] == {"Japanese": 1}
    assert B.privacy_violations(site, c) == []
    assert "secret-feed.bsky.social" not in json.dumps(site)
    cache = json.loads((Path(paths["processed"]) / T.CACHE_NAME).read_text())
    assert T.text_key(ja["text"]) in cache and all(len(k) == 64 for k in cache)

    # rerun: everything comes from the cache, no translator call
    calls.clear()
    c2 = B.load(**paths)
    c2.translator = stub(calls)
    site2 = B.build_from(c2)
    assert calls == [] and site2["challenge"][0]["posts"][0]["text_en"] == ja["text_en"]


def test_translation_failure_ships_untranslated(tmp_path):
    paths = write_corpus(tmp_path)
    sample = Path(paths["sample"])
    sample.mkdir(parents=True, exist_ok=True)
    (sample / "challenge.json").write_text(json.dumps({"accounts": picks()}))

    def boom(batch):
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    c = B.load(**paths)
    c.translator = boom
    with pytest.warns(UserWarning):
        site = B.build_from(c)
    assert all("text_en" not in p and "lang" not in p for p in site["challenge"][0]["posts"] if isinstance(p, dict))
    assert B.privacy_violations(site, c) == []


def test_no_translator_never_calls_network(tmp_path):
    out = T.translate_texts([JA], tmp_path / "c.json", None)
    assert out == {} and not (tmp_path / "c.json").exists()


def test_masks_kept():
    assert T.masks_kept("a @[account] b [link]", "x [link] y @[account]")
    assert not T.masks_kept("a @[account] b", "x y")
    assert not T.masks_kept("@[account] @[account]", "@[account]")

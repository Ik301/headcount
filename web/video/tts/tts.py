"""ElevenLabs voiceover with character timestamps (for caption sync).

Usage:
    python3 web/video/tts/tts.py --id test --voice river --text "One short line."
    python3 web/video/tts/tts.py --script web/video/tts/script.json      # [{"id":..., "text":..., "voice":...}, ...]
Options: --voice river|eric|<voice_id>   --model eleven_multilingual_v2 (default) | eleven_v4 | eleven_v3
         --force (re-synthesize even if a cached file with the same text/voice/model exists)

Writes web/video/public/vo/<id>.mp3 and <id>.json:
    {"text", "voice_id", "model_id", "duration", "words": [{"text","start","end"}],
     "alignment": {characters, character_start_times_seconds, character_end_times_seconds}}
Reads ELEVENLABS_API_KEY from the environment or ~/.hermes/.env. Never prints it.
Credits: 1 character = 1 credit on these models; the script prints characters billed per call.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "public", "vo")
VOICES = {
    "river": "SAz9YHcvj6GT2YYXdXww",  # River - Relaxed, Neutral, Informative
    "eric": "cjVigY5qzO86Huf0OWal",   # Eric - Smooth, Trustworthy
}
DEFAULT_MODEL = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True, "speed": 1.0}


def api_key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if k:
        return k
    env = os.path.expanduser("~/.hermes/.env")
    for line in open(env):
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("ELEVENLABS_API_KEY not set")


def words_from_alignment(al):
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur = [], None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append(cur)
                cur = None
            continue
        if cur is None:
            cur = {"text": c, "start": s, "end": e}
        else:
            cur["text"] += c
            cur["end"] = e
    if cur:
        words.append(cur)
    return [{"text": w["text"], "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in words]


def synth(item, model, force=False):
    voice = VOICES.get(item.get("voice", "river").lower(), item.get("voice", "river"))
    text = item["text"].strip()
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(OUT, item["id"])
    sig = hashlib.sha1(f"{voice}|{model}|{json.dumps(SETTINGS, sort_keys=True)}|{text}".encode()).hexdigest()[:12]
    if not force and os.path.exists(base + ".json") and os.path.exists(base + ".mp3"):
        if json.load(open(base + ".json")).get("sig") == sig:
            print(f"{item['id']}: cached, 0 credits")
            return 0
    body = {"text": text, "model_id": model, "voice_settings": SETTINGS}
    for k in ("previous_text", "next_text"):
        if item.get(k):
            body[k] = item[k]
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"
           f"?output_format=mp3_44100_192")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": api_key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            billed = r.headers.get("x-character-count")
            data = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{item['id']}: HTTP {e.code} {e.read()[:400]!r}")
    with open(base + ".mp3", "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment")
    words = words_from_alignment(al)
    meta = {"id": item["id"], "sig": sig, "text": text, "voice_id": voice, "model_id": model,
            "duration": round(al["character_end_times_seconds"][-1], 3), "words": words,
            "alignment": al, "billed_characters": int(billed) if billed else len(text)}
    with open(base + ".json", "w") as f:
        json.dump(meta, f, indent=1)
    print(f"{item['id']}: {len(words)} words, {meta['duration']}s, billed {meta['billed_characters']} chars -> {base}.mp3")
    return meta["billed_characters"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--text")
    ap.add_argument("--voice", default="river")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--script", help="JSON list of {id, text, voice?, previous_text?, next_text?}")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    items = json.load(open(a.script)) if a.script else [{"id": a.id, "text": a.text, "voice": a.voice}]
    if any(not re.fullmatch(r"[\w.-]+", i["id"] or "") for i in items):
        sys.exit("each item needs an id made of letters, digits, - . _")
    total = sum(synth({**{"voice": a.voice}, **i}, i.get("model", a.model), a.force) for i in items)
    print(f"total billed: {total} characters")


if __name__ == "__main__":
    main()

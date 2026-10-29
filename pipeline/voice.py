"""ElevenLabs voiceover with word timings (Rohan voice, Eleven v4 with audio tags)."""
import base64, os
import requests

API = "https://api.elevenlabs.io/v1"
VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "dVIifp6W0jifqeThgNN0")  # "Rohan"
MODELS = [m for m in (os.environ.get("ELEVENLABS_MODEL", "eleven_v4"), "eleven_v3", "eleven_multilingual_v2") if m]


def _hdr():
    return {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}


def _words_from_alignment(al):
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, cs, ce, depth = [], "", None, None, 0
    for ch, s, e in zip(chars, starts, ends):
        if ch == "[": depth += 1
        if depth:
            if ch == "]": depth -= 1
            continue
        if ch.isspace():
            if cur: words.append((cur, cs, ce)); cur = ""
            continue
        if not cur: cs = s
        cur += ch; ce = e
    if cur: words.append((cur, cs, ce))
    return [w for w in words if any(c.isalnum() for c in w[0])]


def _stt_words(mp3_path):
    with open(mp3_path, "rb") as f:
        r = requests.post(f"{API}/speech-to-text", headers=_hdr(), data={"model_id": "scribe_v1", "timestamps_granularity": "word"},
                          files={"file": ("vo.mp3", f, "audio/mpeg")}, timeout=300)
    r.raise_for_status()
    out = []
    for w in r.json().get("words", []):
        if w.get("type") == "word" and not w["text"].startswith("["):
            out.append((w["text"], float(w["start"]), float(w["end"])))
    return out


def synthesize(text, mp3_path):
    """Returns list of (word, start, end). Writes the MP3."""
    last = None
    for model in MODELS:
        r = requests.post(f"{API}/text-to-speech/{VOICE}/with-timestamps", params={"output_format": "mp3_44100_128"},
                          headers=_hdr(), json={"text": text, "model_id": model}, timeout=600)
        if r.status_code >= 400:
            last = f"{model}: {r.status_code} {r.text[:300]}"
            if r.status_code in (400, 404, 422): continue  # model not available for this voice/account -> try next
            r.raise_for_status()
        js = r.json()
        with open(mp3_path, "wb") as f:
            f.write(base64.b64decode(js["audio_base64"]))
        al = js.get("normalized_alignment") or js.get("alignment")
        words = _words_from_alignment(al) if al else []
        if len(words) < 20:  # alignment missing/odd -> transcribe the audio instead
            words = _stt_words(mp3_path)
        return words, model
    raise RuntimeError(f"ElevenLabs TTS failed: {last}")

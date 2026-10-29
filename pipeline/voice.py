"""ElevenLabs voiceover with word timings (Rohan voice, Eleven v4 with audio tags)."""
import base64, os
import requests

API = "https://api.elevenlabs.io/v1"
VOICE = (os.environ.get("ELEVENLABS_VOICE_ID") or "dVIifp6W0jifqeThgNN0")  # "Rohan"
MODELS = [m for m in ((os.environ.get("ELEVENLABS_MODEL") or "eleven_v4"), "eleven_v3", "eleven_multilingual_v2") if m]


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


EDGE_VOICE = os.environ.get("EDGE_VOICE") or "hi-IN-MadhurNeural"


def _edge(text, mp3_path):
    """Free Microsoft neural Hindi voice (via edge-tts) with word timings. Audio tags are removed."""
    import asyncio, re
    import edge_tts
    clean = re.sub(r"\[[^\]]*\]", " ", text)
    clean = re.sub(r"[ \t]+", " ", clean).strip()
    words = []

    async def go():
        try:
            comm = edge_tts.Communicate(clean, EDGE_VOICE, rate="+6%", boundary="WordBoundary")
        except TypeError:  # older edge-tts versions emit word boundaries by default
            comm = edge_tts.Communicate(clean, EDGE_VOICE, rate="+6%")
        with open(mp3_path, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    s = chunk["offset"] / 1e7; d = chunk["duration"] / 1e7
                    words.append((chunk["text"], s, s + d))
    asyncio.run(go())
    words = [w for w in words if any(c.isalnum() for c in w[0])]
    if len(words) < 20:
        raise RuntimeError("edge-tts returned no word timings")
    return words


def _quota_error(status, body):
    b = body.lower()
    return status in (400, 401, 402, 429) and any(k in b for k in ("quota", "credit", "limit", "subscription", "payment"))


def synthesize(text, mp3_path):
    """Returns (words, voice_used). Uses ElevenLabs (Rohan) while credits last, else the free Microsoft voice."""
    if os.environ.get("VOICE_PROVIDER", "").lower() == "edge" or not os.environ.get("ELEVENLABS_API_KEY"):
        return _edge(text, mp3_path), f"edge:{EDGE_VOICE}"
    try:
        return _eleven(text, mp3_path)
    except QuotaError as e:
        print(f"      ElevenLabs out of credits ({e}) -> using free voice {EDGE_VOICE}", flush=True)
        return _edge(text, mp3_path), f"edge:{EDGE_VOICE}"


class QuotaError(RuntimeError):
    pass


_RESOLVED = {}


def _voice_id():
    """The Rohan voice: use ELEVENLABS_VOICE_ID if this key can see it, else look it up by name ("Rohan")."""
    if "id" in _RESOLVED: return _RESOLVED["id"]
    r = requests.get(f"{API}/voices/{VOICE}", headers=_hdr(), timeout=60)
    if r.status_code != 404:  # found it, or the key just isn't allowed to read voices -> use the configured id
        _RESOLVED["id"] = VOICE; return VOICE
    want = (os.environ.get("ELEVENLABS_VOICE_NAME") or "Rohan").lower()
    lst = requests.get(f"{API}/voices", headers=_hdr(), timeout=60)
    lst.raise_for_status()
    voices = lst.json().get("voices", [])
    print("      voices this ElevenLabs key can use: " + ", ".join(f"{v['name']} ({v['voice_id']})" for v in voices[:40]), flush=True)
    mine = [v for v in voices if v["name"].lower().startswith(want) and v.get("category") in ("cloned", "professional", "generated")]
    match = mine or [v for v in voices if v["name"].lower().startswith(want)]
    if not match:
        raise RuntimeError(f"ElevenLabs: voice '{want}' not found for this API key — create the key in the workspace that has the Rohan voice")
    _RESOLVED["id"] = match[0]["voice_id"]
    print(f"      using voice {match[0]['name']} ({match[0]['voice_id']})", flush=True)
    return _RESOLVED["id"]


def _diagnose():
    """Write what this ElevenLabs key can do into the run log (no secrets)."""
    try:
        u = requests.get(f"{API}/user/subscription", headers=_hdr(), timeout=30)
        print(f"      [eleven] subscription: {u.status_code} {u.text[:300]}", flush=True)
        m = requests.get(f"{API}/models", headers=_hdr(), timeout=30)
        ids = [x.get("model_id") for x in m.json()] if m.status_code == 200 else m.text[:200]
        print(f"      [eleven] models: {m.status_code} {ids}", flush=True)
    except Exception as e:
        print(f"      [eleven] diagnose failed: {e}", flush=True)


def _eleven(text, mp3_path):
    last = None
    vid = _voice_id()
    _diagnose()
    for model in MODELS:
        r = requests.post(f"{API}/text-to-speech/{vid}/with-timestamps", params={"output_format": "mp3_44100_128"},
                          headers=_hdr(), json={"text": text, "model_id": model}, timeout=600)
        if r.status_code >= 400:
            last = f"{model}: {r.status_code} {r.text[:300]}"
            print(f"      [eleven] with-timestamps {model}: {r.status_code} {r.text[:200]}", flush=True)
            if _quota_error(r.status_code, r.text): raise QuotaError(last)
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
    for model in MODELS:  # fallback: standard endpoint (no timestamps), timings via speech-to-text
        r = requests.post(f"{API}/text-to-speech/{vid}", params={"output_format": "mp3_44100_128"},
                          headers=_hdr(), json={"text": text, "model_id": model}, timeout=600)
        print(f"      [eleven] plain TTS {model}: {r.status_code} {'' if r.ok else r.text[:200]}", flush=True)
        if r.ok:
            with open(mp3_path, "wb") as f: f.write(r.content)
            return _stt_words(mp3_path), model
        last = f"{model}: {r.status_code} {r.text[:300]}"
        if _quota_error(r.status_code, r.text): raise QuotaError(last)
    raise RuntimeError(f"ElevenLabs TTS failed: {last}")

"""Check the ElevenLabs key + Rohan voice, and hear how tricky numbers/symbols come out.

Speaks one test script (as the pipeline would send it, after our spoken-number fixes), then transcribes the audio
back with ElevenLabs speech-to-text, so we can see what the voice actually SAID for each tricky item.
python -m pipeline.voice_check  -> voice_check/{test.mp3,report.txt}
"""
import os, sys, json
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import voice  # noqa: E402

LINES = [
    "बेड 77% भरे रहते हैं, टारगेट 55–65%।",
    "कमीशन 12-13% है, और 1–2 दिन में पैसा आता है।",
    "₹77.3 हज़ार, ₹1.2 करोड़, ₹8,000 से 12,000।",
    "100 शादी × ₹6 लाख = ₹3 करोड़। 2×4 करो।",
    "रोज़ 1300 मोमोज़, ₹2000 का पेट्रोल, 5000 लीटर।",
    "नवंबर 2018 में ₹50.58, और 2026 में ₹79,999।",
    "7:30 पे कोचिंग, 24/7 खुला, ₹500/महीना।",
    "EMI, MRP, QSR, ARPOB, GST.",
    "₹2L का स्टॉक, 10K फ़ॉलोअर्स, 1st साल, 3rd फ्लोर।",
]


def main():
    out = ROOT / "voice_check"; out.mkdir(exist_ok=True)
    rep = []
    u = requests.get(f"{voice.API}/user/subscription", headers=voice._hdr(), timeout=60)
    if u.ok:
        j = u.json(); rep.append(f"plan: {j.get('tier')} · characters used {j.get('character_count')} / {j.get('character_limit')}")
    vid = voice._voice_id(force_lookup=True)
    rep.append(f"Rohan voice id: {vid}")
    text = "\n".join(LINES)
    words, model = voice._eleven(voice.speakable(text), str(out / "test.mp3"))
    rep.append(f"model: {model}\n")
    heard = " ".join(w for w, _, _ in voice._stt_words(str(out / "test.mp3")))
    rep.append("SCRIPT:\n" + text + "\n\nSENT TO THE VOICE:\n" + voice.speakable(text) + "\n\nHEARD (speech-to-text):\n" + heard)
    (out / "report.txt").write_text("\n".join(rep), encoding="utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main()

"""Study another creator's reels (frames, cuts, audio hits, word-timed transcript) for style research.
Runs in GitHub Actions; output is encrypted (age) before it is committed, so nothing is published.

python tools/study_reels.py <username> <shortcode,shortcode,...> <outdir>
"""
import json, os, subprocess, sys
import requests

user, codes, out = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
os.makedirs(out, exist_ok=True)
run = lambda *a: subprocess.run(a, check=True, capture_output=True, text=True)

r = requests.post("https://api.apify.com/v2/acts/apify~instagram-reel-scraper/run-sync-get-dataset-items",
                  params={"token": os.environ["APIFY_TOKEN"], "timeout": 280},
                  json={"username": [user], "resultsLimit": 40}, timeout=320)
r.raise_for_status()
items = {it["shortCode"]: it for it in r.json() if it.get("shortCode")}
print("scraped", len(items), "reels", flush=True)

from faster_whisper import WhisperModel
model = WhisperModel(os.environ.get("WHISPER_MODEL", "large-v3-turbo"), device="cpu", compute_type="int8")

import numpy as np, librosa
from PIL import Image, ImageDraw, ImageFont
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
FONT = ImageFont.load_default()


def sheet(frames, path, cols=4, w=270):
    ims = [Image.open(f).convert("RGB") for f, _ in frames]
    if not ims: return
    h = int(ims[0].height * w / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * (h + 18)), (20, 20, 20)); d = ImageDraw.Draw(S)
    for i, (im, (_, t)) in enumerate(zip(ims, frames)):
        x, y = (i % cols) * w, (i // cols) * (h + 18)
        S.paste(im.resize((w, h)), (x, y + 18)); d.text((x + 4, y + 3), f"{t:5.2f}s", fill=(255, 220, 0), font=FONT)
    S.save(path, quality=72)


import traceback
LOG = open(os.path.join(out, "log.txt"), "a")


def study(code):
    it = items.get(code)
    if not it or not it.get("videoUrl"):
        print("missing", code, file=LOG); return
    d = os.path.join(out, code); os.makedirs(d + "/f", exist_ok=True)
    mp4 = f"/tmp/{code}.mp4"
    with open(mp4, "wb") as fh:
        fh.write(requests.get(it["videoUrl"], timeout=300).content)
    dur = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4).stdout)
    meta = {k: it.get(k) for k in ("shortCode", "caption", "videoPlayCount", "likesCount", "commentsCount", "videoDuration", "timestamp")}
    meta["duration"] = dur
    meta["probe"] = run("ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,sample_rate,channels", "-of", "json", mp4).stdout

    # frames: 4 fps for the first 8 s (hook), 1 fps after that
    run("ffmpeg", "-y", "-v", "error", "-i", mp4, "-t", "8", "-vf", "fps=4,scale=540:-1", f"{d}/f/h_%03d.jpg")
    run("ffmpeg", "-y", "-v", "error", "-ss", "8", "-i", mp4, "-vf", "fps=1,scale=540:-1", f"{d}/f/b_%03d.jpg")
    hook = sorted(f for f in os.listdir(d + "/f") if f.startswith("h_"))
    body = sorted(f for f in os.listdir(d + "/f") if f.startswith("b_"))
    hf = [(f"{d}/f/{f}", i / 4) for i, f in enumerate(hook)]
    bf = [(f"{d}/f/{f}", 8 + i) for i, f in enumerate(body)]
    for k in range(0, len(hf), 16): sheet(hf[k:k + 16], f"{d}/hook_{k // 16 + 1}.jpg")
    for k in range(0, len(bf), 20): sheet(bf[k:k + 20], f"{d}/body_{k // 20 + 1}.jpg", cols=5, w=216)
    # a few full-size stills for type/colour detail
    for t in (0.5, 3, dur * 0.35, dur * 0.65, dur - 3):
        run("ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-q:v", "3", f"{d}/still_{t:06.2f}.jpg")
    run("rm", "-rf", d + "/f")

    # scene cuts
    sc = subprocess.run(["ffmpeg", "-i", mp4, "-vf", "select='gt(scene,0.25)',showinfo", "-f", "null", "-"], capture_output=True, text=True).stderr
    cuts = [float(x.split("pts_time:")[1].split()[0]) for x in sc.splitlines() if "pts_time:" in x]
    meta["cuts"] = cuts

    # audio: transcript with word timings + onsets (SFX hits) + loudness
    wav = f"/tmp/{code}.wav"; run("ffmpeg", "-y", "-v", "error", "-i", mp4, "-ac", "1", "-ar", "22050", wav)
    segs, info = model.transcribe(wav, language=os.environ.get("LANG_CODE", "hi"), word_timestamps=True, vad_filter=False)
    words, lines = [], []
    for s in segs:
        lines.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        for w in s.words or []: words.append([w.word.strip(), round(w.start, 2), round(w.end, 2)])
    y, sr = librosa.load(wav, sr=22050)
    rms = librosa.feature.rms(y=y, hop_length=512)[0]; tt = librosa.times_like(rms, sr=sr, hop_length=512)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=512, units="time", backtrack=False)
    strong = [round(float(t), 2) for t in on if env[librosa.time_to_frames(t, sr=sr, hop_length=512)] > np.percentile(env, 97)]
    # music/bed estimate: energy in pauses between words
    speech = np.zeros_like(tt, dtype=bool)
    for _, a, b in words: speech |= (tt >= a) & (tt <= b)
    meta["rms_db_speech"] = float(20 * np.log10(np.median(rms[speech]) + 1e-9)) if speech.any() else None
    meta["rms_db_gaps"] = float(20 * np.log10(np.median(rms[~speech]) + 1e-9)) if (~speech).any() else None
    meta["strong_onsets"] = strong
    meta["words_per_sec"] = round(len(words) / max(1, dur), 2)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    meta["est_tempo"] = float(np.atleast_1d(tempo)[0])
    json.dump(meta, open(f"{d}/meta.json", "w"), ensure_ascii=False, indent=1)
    json.dump({"lines": lines, "words": words}, open(f"{d}/transcript.json", "w"), ensure_ascii=False, indent=0)

    fig, ax = plt.subplots(figsize=(22, 3.2))
    ax.plot(tt, 20 * np.log10(rms + 1e-9), lw=0.6, color="#333")
    ax.fill_between(tt, -80, 0, where=speech, color="#9cf", alpha=0.35, step="mid")
    for c in cuts: ax.axvline(c, color="red", lw=0.8, alpha=0.7)
    for o in strong: ax.axvline(o, color="orange", lw=0.8, ls="--", alpha=0.8)
    ax.set_ylim(-70, 0); ax.set_xlim(0, dur); ax.set_xticks(np.arange(0, dur, 2))
    ax.set_title(f"{code}: loudness (dB), blue=speech, red=visual cuts, orange=strong audio hits"); plt.tight_layout()
    plt.savefig(f"{d}/timeline.png", dpi=80); plt.close()
    print("done", code, f"{dur:.0f}s", len(cuts), "cuts", len(strong), "hits", flush=True)


for code in codes:
    try:
        study(code)
        print("ok", code, file=LOG, flush=True)
    except Exception:
        LOG.write(f"FAIL {code}\n{traceback.format_exc()}\n"); LOG.flush()

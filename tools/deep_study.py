"""Deep study of one or more reels: frame-accurate motion, every sound effect, and how tightly the two are synced.
Runs in GitHub Actions; the output is encrypted before it is committed (style research only, nothing is published).

python tools/deep_study.py <outdir> <reel_url> [<reel_url> ...]

Per reel:
  frames/sheet_XX.jpg  10 fps contact sheets (2 s per sheet, timestamps on each frame)
  motion_audio_XX.png  per 6 s: visual-change curve (30 fps), mel spectrogram, speech (blue), SFX hits (orange), cuts (red)
  hits.csv             every non-speech sound event: time, duration, loudness, centroid, flatness, sweep, label guess,
                       nearest visual-change peak offset (frames)
  sync.json            offset statistics (how many hits land within ±1/±2 frames of a visual event), hits per 10 s
  transcript.json      words with timings; meta.json
"""
import csv, io, json, os, subprocess, sys
import numpy as np, requests

out_root, urls = sys.argv[1], sys.argv[2:]
os.makedirs(out_root, exist_ok=True)
run = lambda *a: subprocess.run(a, check=True, capture_output=True)
FPS = 30


def fetch(url):
    r = requests.post("https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items",
                      params={"token": os.environ["APIFY_TOKEN"], "timeout": 240},
                      json={"directUrls": [url.split("?")[0]], "resultsType": "posts", "resultsLimit": 1}, timeout=300)
    r.raise_for_status()
    items = [i for i in r.json() if i.get("videoUrl")]
    if not items: raise RuntimeError(f"no video for {url}: {str(r.json())[:300]}")
    return items[0]


def study(url):
    it = fetch(url); code = it.get("shortCode") or url.rstrip("/").split("/")[-1]
    d = os.path.join(out_root, code); os.makedirs(d + "/frames", exist_ok=True)
    mp4 = f"/tmp/{code}.mp4"
    open(mp4, "wb").write(requests.get(it["videoUrl"], timeout=300).content)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4], capture_output=True, text=True).stdout)
    meta = {k: it.get(k) for k in ("shortCode", "ownerUsername", "caption", "videoPlayCount", "videoViewCount", "likesCount", "commentsCount", "videoDuration", "timestamp")}
    meta["duration"] = dur

    # ---- frames at 10 fps -> contact sheets (20 frames = 2 s each)
    from PIL import Image, ImageDraw
    run("ffmpeg", "-y", "-v", "error", "-i", mp4, "-vf", "fps=10,scale=216:-2", f"{d}/frames/f_%05d.jpg")
    fs = sorted(f for f in os.listdir(d + "/frames") if f.startswith("f_"))
    for k in range(0, len(fs), 20):
        ims = [Image.open(f"{d}/frames/{f}") for f in fs[k:k + 20]]
        w, h = ims[0].size; S = Image.new("RGB", (10 * w, 2 * (h + 16)), (15, 15, 15)); dr = ImageDraw.Draw(S)
        for i, im in enumerate(ims):
            x, y = (i % 10) * w, (i // 10) * (h + 16); S.paste(im, (x, y + 16)); dr.text((x + 3, y + 2), f"{(k + i) / 10:.1f}s", fill=(255, 220, 0))
        S.save(f"{d}/frames/sheet_{k // 20:02d}.jpg", quality=70)
    for f in fs: os.remove(f"{d}/frames/{f}")
    # a few full-res stills for design detail
    for t in np.linspace(0.3, dur - 0.5, 8):
        run("ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-q:v", "3", f"{d}/still_{t:06.2f}.jpg")

    # ---- visual change per frame at 30 fps (64x114 gray)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"fps={FPS},scale=64:114,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 114, 64).astype(np.float32)
    vchg = np.r_[0, np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))]
    vt = np.arange(len(vchg)) / FPS
    base = np.convolve(vchg, np.ones(15) / 15, mode="same")
    vpeaks = [i for i in range(1, len(vchg) - 1) if vchg[i] >= vchg[i - 1] and vchg[i] >= vchg[i + 1] and vchg[i] > base[i] * 1.6 + 0.6]
    cuts = [round(i / FPS, 3) for i in range(len(vchg)) if vchg[i] > 25]

    # ---- audio
    import librosa
    wav = f"/tmp/{code}.wav"; run("ffmpeg", "-y", "-v", "error", "-i", mp4, "-ac", "1", "-ar", "32000", wav)
    y, sr = librosa.load(wav, sr=32000)
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get("WHISPER_MODEL", "large-v3-turbo"), device="cpu", compute_type="int8")
    segs, _ = model.transcribe(librosa.resample(y, orig_sr=sr, target_sr=16000).astype("float32"), language=os.environ.get("LANG_CODE", "hi"), word_timestamps=True)
    words = [[w.word.strip(), round(w.start, 2), round(w.end, 2)] for s in segs for w in (s.words or [])]
    hop = 160  # 5 ms
    S_ = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop)); freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    t_ = librosa.frames_to_time(np.arange(S_.shape[1]), sr=sr, hop_length=hop)
    hi = S_[freqs > 2500].sum(0); lo = S_[freqs < 200].sum(0)
    env = librosa.onset.onset_strength(S=librosa.amplitude_to_db(S_), sr=sr, hop_length=hop)
    ons = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, units="frames", delta=0.25, backtrack=True)
    speech = np.zeros_like(t_, bool)
    for _, a, b in words: speech |= (t_ >= a) & (t_ <= b)
    rms = librosa.feature.rms(S=S_, frame_length=1024)[0]
    hits = []
    for o in ons:
        t0 = t_[o]; seg = slice(o, min(len(t_), o + int(0.9 * sr / hop)))
        e = rms[seg];
        if len(e) < 3: continue
        peak = e.max(); n_above = int(np.argmax(e < peak * 0.25)) if (e < peak * 0.25).any() else len(e)
        dur_h = n_above * hop / sr
        cen = float(np.mean(librosa.feature.spectral_centroid(S=S_[:, seg], sr=sr)))
        flat = float(np.mean(librosa.feature.spectral_flatness(S=S_[:, seg])))
        c = librosa.feature.spectral_centroid(S=S_[:, seg], sr=sr)[0]; sweep = float(c[min(len(c) - 1, max(1, n_above - 1))] - c[0]) if len(c) > 2 else 0.0
        in_speech = bool(speech[o])
        # SFX = transient strong enough relative to the local level, or anything in a speech gap
        loc = np.median(env[max(0, o - 200):o + 200]) + 1e-6
        strength = float(env[o] / loc)
        if in_speech and (strength < 2.6 and hi[o] < np.percentile(hi, 92) and lo[o] < np.percentile(lo, 97)): continue
        label = ("boom/thud" if cen < 900 else "whoosh" if flat > 0.25 and dur_h > 0.18 else "riser" if sweep > 1500 and dur_h > 0.4 else
                 "tick/click" if dur_h < 0.06 else "pop/blip" if flat < 0.15 and dur_h < 0.25 else "ding/chime" if flat < 0.12 else "swish/hit")
        vf = int(round(t0 * FPS)); near = [p - vf for p in vpeaks if abs(p - vf) <= 8]
        off = min(near, key=abs) if near else None
        hits.append({"t": round(float(t0), 3), "dur": round(dur_h, 3), "db": round(float(20 * np.log10(peak + 1e-9)), 1), "centroid": int(cen),
                     "flatness": round(flat, 3), "sweep": int(sweep), "strength": round(strength, 2), "in_speech": in_speech, "label": label,
                     "visual_offset_frames": off})
    with open(f"{d}/hits.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hits[0].keys()) if hits else ["t"]); w.writeheader(); w.writerows(hits)
    offs = [h["visual_offset_frames"] for h in hits if h["visual_offset_frames"] is not None]
    from collections import Counter
    sync = {"hits": len(hits), "hits_per_10s": round(len(hits) / dur * 10, 1), "labels": Counter(h["label"] for h in hits),
            "with_visual_event_within_8f": len(offs), "within_1f": sum(abs(o) <= 1 for o in offs), "within_2f": sum(abs(o) <= 2 for o in offs),
            "offset_histogram": dict(sorted(Counter(offs).items())), "visual_events": len(vpeaks), "visual_events_per_10s": round(len(vpeaks) / dur * 10, 1),
            "cuts": cuts, "words_per_sec": round(len(words) / dur, 2),
            "loudness_speech_db": float(20 * np.log10(np.median(rms[speech]) + 1e-9)) if speech.any() else None,
            "loudness_gaps_db": float(20 * np.log10(np.median(rms[~speech]) + 1e-9)) if (~speech).any() else None}
    json.dump(sync, open(f"{d}/sync.json", "w"), indent=1, default=str)
    json.dump({"words": words}, open(f"{d}/transcript.json", "w"), ensure_ascii=False)
    json.dump(meta, open(f"{d}/meta.json", "w"), ensure_ascii=False, indent=1)

    # ---- motion + audio strips, 6 s each
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    M = librosa.power_to_db(librosa.feature.melspectrogram(S=S_ ** 2, sr=sr, n_mels=96), ref=np.max)
    for k, a in enumerate(np.arange(0, dur, 6.0)):
        b = min(dur, a + 6)
        fig, ax = plt.subplots(2, 1, figsize=(20, 6), sharex=True, gridspec_kw={"height_ratios": [1, 2]})
        m = (vt >= a) & (vt < b); ax[0].plot(vt[m], vchg[m], lw=1, color="#222")
        for p in vpeaks:
            if a <= p / FPS < b: ax[0].axvline(p / FPS, color="green", lw=0.6, alpha=0.6)
        ax[0].set_ylabel("visual change")
        i0, i1 = np.searchsorted(t_, a), np.searchsorted(t_, b)
        ax[1].imshow(M[:, i0:i1], aspect="auto", origin="lower", extent=[a, b, 0, 96], cmap="magma")
        for _, wa, wb in words:
            if wb > a and wa < b: ax[1].axvspan(max(a, wa), min(b, wb), ymin=0.97, ymax=1, color="#6cf")
        for h in hits:
            if a <= h["t"] < b:
                ax[1].axvline(h["t"], color="orange", lw=0.9); ax[1].text(h["t"], 88, h["label"].split("/")[0], color="w", fontsize=7, rotation=90)
        for c in cuts:
            if a <= c < b: ax[0].axvline(c, color="red", lw=1)
        ax[1].set_xticks(np.arange(a, b + 0.01, 0.5)); plt.tight_layout(); plt.savefig(f"{d}/motion_audio_{k:02d}.png", dpi=70); plt.close()
    print("done", code, f"{dur:.0f}s", sync["hits"], "hits", sync["within_2f"], "within 2 frames", flush=True)


for u in urls:
    try:
        study(u)
    except Exception as e:
        import traceback; traceback.print_exc()
        open(os.path.join(out_root, "errors.txt"), "a").write(f"{u}\n{traceback.format_exc()}\n")

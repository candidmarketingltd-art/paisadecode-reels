"""Original sound design + final mix. Everything is synthesised, so nothing can be claimed or muted.

cues: dict from engine.render() -> open_lines, open_end, cuts, pops, duration
"""
import subprocess, wave
import numpy as np

SR = 44100


def _env(n, a=0.005, r=0.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def _lp(x, k):
    # one-pole low-pass, vectorised with an IIR via cumulative trick (good enough for noise shaping)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += k * (x[i] - acc); y[i] = acc
    return y


def build_sfx(cues, path, seed=1):
    rng = np.random.default_rng(seed)
    dur = cues["duration"] + 1.2
    N = int(dur * SR); out = np.zeros(N, np.float32)

    def add(sig, t, g):
        i = int(max(0, t) * SR); j = min(N, i + len(sig)); out[i:j] += sig[: j - i] * g

    def boom(d=2.0):
        t = np.arange(int(d * SR)) / SR
        return np.sin(2 * np.pi * np.cumsum(34 + 50 * np.exp(-t * 6)) / SR) * _env(len(t), 0.004, 0.7)

    noise_bank = _lp(rng.normal(0, 1, int(1.6 * SR)).astype(np.float32), 0.12)
    low_bank = _lp(noise_bank, 0.08)

    def whoosh(d=0.45):
        n = int(d * SR); x = noise_bank[:n] - _lp(noise_bank[:n], 0.01)
        return x * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.9

    def riser(d=1.4):
        n = int(d * SR); t = np.arange(n) / SR
        s = np.sin(2 * np.pi * np.cumsum(200 + 600 * (t / d) ** 2) / SR) * (t / d) ** 3 * 0.25
        return low_bank[:n] * (t / d) ** 2 * 0.8 + s

    def pop(f):
        t = np.arange(int(0.12 * SR)) / SR
        return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t)) * _env(len(t), 0.002, 0.04)

    def thud():
        t = np.arange(int(0.5 * SR)) / SR
        return np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 20)) * t) * _env(len(t), 0.002, 0.15)

    t = np.arange(N) / SR
    pad = np.zeros(N, np.float32)
    for f, g in ((55, .5), (110, .35), (164.8, .22), (220, .15), (261.6, .1)):
        pad += g * np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.07 * t * f / 55))
    pad *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t) ** 2
    oe = cues.get("open_end", 0)
    pad *= np.clip((t - max(0, oe - 0.7)) / 1.5, 0, 1) * np.clip((cues["duration"] + 0.8 - t) / 1.0, 0, 1)
    if not cues.get("music"):
        out += pad * 0.05  # only when no theme music is used

    for k, ot in enumerate(cues.get("open_lines", [])):
        add(boom(2.0 if k == 0 else 1.6), ot - 0.06, [0.9, 0.5, 0.65][min(k, 2)])
    if oe > 1.5:
        add(riser(), oe - 1.3, 0.35)
    add(thud(), oe, 0.8)
    for c in cues.get("cuts", []):
        add(whoosh(), c - 0.2, 0.28)
    tones = [880, 990, 1180, 1320, 660]
    for k, p in enumerate(cues.get("pops", [])):
        add(pop(tones[k % len(tones)]), p, 0.16)

    out /= max(1e-6, np.abs(out).max()) / 0.5
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())


MUSIC_DIR = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "music")


def theme_path():
    import os
    for n in ("theme_loop.wav", "theme_loop.mp3"):
        p = os.path.join(MUSIC_DIR, n)
        if os.path.exists(p): return p
    return None


def mix(video, voice, sfx, out, workdir, music_start=0.0, music_gain=0.30, duck_sfx=True, sfx_gain=0.9):
    """Voice on top; signature theme (+ sound design when duck_sfx) underneath, ducked whenever Rohan speaks.
    duck_sfx=False keeps UI hits at full level over the voice (Hisaab style)."""
    vo = f"{workdir}/vo_proc.wav"; mixed = f"{workdir}/mix.wav"
    run = lambda *a: subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)
    run("-i", voice, "-af", "aresample=48000,highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-15:TP=-1.5:LRA=9", "-ar", "48000", vo)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video], capture_output=True, text=True, check=True).stdout.strip())
    theme = theme_path()
    ins = ["-i", vo, "-i", sfx]
    fx = f"[1:a]aresample=48000,volume={sfx_gain}[fx];"
    if theme:
        ms = max(0.0, music_start - 0.4)
        ins += ["-stream_loop", "-1", "-i", theme]
        mus = (f"[2:a]aresample=48000,atrim=0:{dur - ms:.2f},afade=t=in:d=0.8,afade=t=out:st={max(0, dur - ms - 1.8):.2f}:d=1.8,"
               f"volume={music_gain},adelay={int(ms * 1000)}:all=1[mus];")
        bed = mus + fx + ("[mus][fx]amix=inputs=2:duration=longest:normalize=0[bed];" if duck_sfx else "[mus]anull[bed];")
    else:
        bed = fx + ("[fx]anull[bed];" if duck_sfx else "anullsrc=r=48000:cl=mono,atrim=0:1[bed];")
    tail = ("[vo][duck]amix=inputs=2:duration=longest:normalize=0" if duck_sfx else "[vo][duck][fx]amix=inputs=3:duration=longest:normalize=0")
    if not duck_sfx:
        bed = bed.replace(fx, "") ; bed = fx + bed
    run(*ins, "-filter_complex",
        bed + f"[0:a]apad=whole_dur={dur:.3f},asplit=2[vo][sc];"
        "[bed][sc]sidechaincompress=threshold=0.03:ratio=10:attack=8:release=300[duck];"
        + tail + ",alimiter=limit=0.95", "-t", f"{dur:.3f}", mixed)
    run("-i", video, "-i", mixed, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", "-movflags", "+faststart", out)


# ---------------------------------------------------------------- UI sound design for the Remotion ("Hisaab") style
def build_ui_sfx(hits, duration, path, seed=5):
    """Sound that follows the motion (learned from frame-by-frame study of top explainer reels):
    every visual event gets a matching sound on the frame it lands; counters and growing bars get a tone that rises
    with them and lands on a chime; transitions get a whoosh whose peak sits on the cut; continuous motion (coin rain,
    typing, dot grids) gets a continuous texture. `hits` = [(t, kind)] or [{"t","k","dur"?,"p"?}]. Everything is synthesised."""
    sr = 48000
    n_total = int(duration * sr); out = np.zeros(n_total, np.float32)
    rng = np.random.default_rng(seed)
    T = lambda d: np.arange(int(d * sr)) / sr

    def env(n, a, r):
        t = np.arange(n) / sr
        return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)

    def lp(x, k):
        y = np.empty_like(x); acc = 0.0
        for i in range(len(x)): acc += k * (x[i] - acc); y[i] = acc
        return y

    noise = rng.normal(0, 1, int(2.5 * sr)).astype(np.float32)
    soft = lp(noise, 0.2); dark = lp(noise, 0.05)

    def tone(f, d, a=0.002, r=0.08, h=(1, 0.35, 0.12)):
        t = T(d); return sum(g * np.sin(2 * np.pi * f * (k + 1) * t) for k, g in enumerate(h)) * env(len(t), a, r)

    def pop(p=1.0):
        t = T(0.08); return np.sin(2 * np.pi * np.cumsum(700 * p + 900 * p * np.exp(-t * 70)) / sr) * env(len(t), 0.001, 0.02)

    def tick(p=1.0):
        t = T(0.025); return (np.sin(2 * np.pi * 2900 * p * t) * 0.7 + rng.normal(0, 0.35, len(t))) * env(len(t), 0.0004, 0.004)

    def impact(p=1.0):
        t = T(0.7)
        body = np.sin(2 * np.pi * np.cumsum(48 + 110 * np.exp(-t * 22)) / sr) * env(len(t), 0.002, 0.22)
        crack = soft[:len(t)] * env(len(t), 0.0005, 0.012) * 0.6
        return body + crack + tone(220 * p, 0.7, r=0.25, h=(0.25, 0.1)) 

    def ding(p=1.0):
        return tone(1568 * p, 0.9, r=0.22, h=(1, 0.45, 0.2)) + tone(2349 * p, 0.9, r=0.15, h=(0.5,)) 

    def whoosh(d=0.42):  # peak in the middle: place it centred on the cut
        n = int(d * sr); x = noise[:n] - lp(noise[:n], 0.02)
        sweep = np.sin(np.linspace(0, np.pi, n)) ** 2
        return lp(x, 0.35) * sweep * 1.4

    def riser(d=0.8):
        n = int(d * sr); t = np.arange(n) / sr; k = (t / d)
        return (lp(noise[:n], 0.08 + 0.4 * k[-1]) * k ** 2 * 0.9 + np.sin(2 * np.pi * np.cumsum(180 + 900 * k ** 2) / sr) * k ** 3 * 0.25)

    def glide(d=0.9, p=1.0):  # rising tone + accelerating ticks, like a counter climbing
        n = int(d * sr); t = np.arange(n) / sr; k = t / max(d, 1e-3)
        f = (420 + 780 * k ** 1.3) * p
        y = np.sin(2 * np.pi * np.cumsum(f) / sr) * (0.18 + 0.25 * k) * np.minimum(1, (d - t) / 0.03 + 0.001).clip(0, 1)
        nt = int(6 + 10 * d); ts = (np.linspace(0, 1, nt) ** 0.8) * d
        for x in ts:
            i = int(x * sr); g = tick(1 + 0.6 * x / d); y[i:i + len(g)] += g[: max(0, n - i)] * 0.5
        return y

    def drop(p=1.0):
        t = T(0.12); return np.sin(2 * np.pi * np.cumsum(1300 * p * np.exp(-t * 14)) / sr) * env(len(t), 0.001, 0.05)

    def shutter():
        t = T(0.16); x = soft[:len(t)] * (env(len(t), 0.0005, 0.01) + 0.6 * np.roll(env(len(t), 0.0005, 0.012), int(0.07 * sr)))
        return x * 1.2

    def coins(d=2.0):
        n = int(d * sr); y = np.zeros(n, np.float32)
        for _ in range(int(14 * d)):
            i = rng.integers(0, max(1, n - 4000)); f = rng.uniform(2600, 5200)
            c = tone(f, 0.12, a=0.0005, r=0.035, h=(1, 0.5)) * rng.uniform(0.3, 1)
            y[i:i + len(c)] += c[: n - i]
        return y * np.sin(np.linspace(0, np.pi, n)) ** 0.5

    def keys(d=1.0):
        n = int(d * sr); y = np.zeros(n, np.float32); x = 0.0
        while x < d - 0.03:
            i = int(x * sr); g = tick(rng.uniform(0.6, 0.9)) * rng.uniform(0.5, 1); y[i:i + len(g)] += g[: n - i]; x += rng.uniform(0.045, 0.09)
        return y

    def scribble(d=0.3):
        n = int(d * sr); x = lp(noise[:n], 0.5) - lp(noise[:n], 0.05)
        return x * (0.5 + 0.5 * np.abs(np.sin(np.linspace(0, 9 * np.pi, n)))) * 0.5 * np.sin(np.linspace(0, np.pi, n))

    def swipe(d=0.25):
        n = int(d * sr); x = lp(noise[:n], 0.6) - lp(noise[:n], 0.1)
        return x * np.linspace(0.2, 1, n) * np.exp(-np.linspace(0, 3, n)) * 0.9

    def stamp():
        return impact(1.4)[: int(0.3 * sr)] * 0.8 + soft[: int(0.3 * sr)] * env(int(0.3 * sr), 0.0005, 0.02) * 0.5

    def sparkle():
        y = np.zeros(int(0.5 * sr), np.float32)
        for j, f in enumerate((2093, 2637, 3136, 4186)):
            c = tone(f, 0.3, a=0.001, r=0.07, h=(1,)); i = int(j * 0.045 * sr); y[i:i + len(c)] += c[: len(y) - i] * 0.6
        return y

    def boing():
        t = T(0.35); return np.sin(2 * np.pi * np.cumsum(260 + 380 * np.sin(t * 28) * np.exp(-t * 8)) / sr) * env(len(t), 0.003, 0.12) * 0.8

    def note(p=1.0):
        return tone(880 * p, 0.35, r=0.09, h=(1, 0.3))

    GAIN = {"pop": 0.30, "tick": 0.14, "impact": 0.75, "thud": 0.75, "ding": 0.26, "whoosh": 0.32, "riser": 0.30, "glide": 0.30,
            "drop": 0.16, "shutter": 0.45, "coins": 0.22, "keys": 0.30, "scribble": 0.35, "swipe": 0.42, "stamp": 0.7, "sparkle": 0.18,
            "boing": 0.30, "note": 0.24}
    for h in hits:
        if isinstance(h, (list, tuple)): h = {"t": h[0], "k": h[1]}
        k, t, d, p = h["k"], h["t"], h.get("dur"), h.get("p", 1.0)
        if k in ("whoosh",): sig = whoosh(d or 0.42); t -= len(sig) / sr / 2  # centre on the cut
        elif k == "riser": sig = riser(d or 0.8); t -= len(sig) / sr          # ends on the reveal
        elif k == "glide": sig = glide(d or 0.9, p)
        elif k == "coins": sig = coins(d or 2.0)
        elif k == "keys": sig = keys(d or 1.0)
        elif k == "scribble": sig = scribble(d or 0.3)
        elif k == "swipe": sig = swipe(d or 0.25)
        elif k in ("impact", "thud"): sig = impact(p)
        elif k in ("pop", "tick", "ding", "drop", "note"): sig = {"pop": pop, "tick": tick, "ding": ding, "drop": drop, "note": note}[k](p)
        else: sig = {"shutter": shutter, "stamp": stamp, "sparkle": sparkle, "boing": boing}.get(k, lambda: None)()
        if sig is None: continue
        i = int(max(0, t) * sr); j = min(n_total, i + len(sig))
        if j > i: out[i:j] += sig[: j - i].astype(np.float32) * GAIN.get(k, 0.3)
    out /= max(1e-6, np.abs(out).max()) / 0.7
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())

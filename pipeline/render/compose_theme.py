"""Compose the Paisa Decode signature theme (original, synthesised — owned outright, never claimable).

96 BPM, A minor with a Kafi/desi flavour: sitar-style Karplus-Strong plucks, tabla-flavoured percussion,
round bass, soft pad. Written to be talked over: sparse melody, nothing in the voice's 1–3 kHz pocket for long.
Output: music/theme_loop.wav — an 8-bar seamless loop (20 s). The mixer loops it under every reel.

To use a different track instead (e.g. one made in ElevenLabs Music), drop it at music/theme_loop.wav (or .mp3).
"""
import os, wave
import numpy as np

SR = 44100; BPM = 96; BEAT = 60 / BPM; BAR = 4 * BEAT; BARS = 8
N = int(BARS * BAR * SR)
rng = np.random.default_rng(11)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music", "theme_loop.wav")


def hz(note):
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    n, o = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o - 4)) / 12)


def place(buf, sig, t, g=1.0):
    i = int(t * SR) % N
    seg = sig * g
    end = i + len(seg)
    if end <= N: buf[i:end] += seg
    else:  # wrap around so the loop is seamless
        k = N - i; buf[i:] += seg[:k]; buf[:end - N] += seg[k:]


def pluck(f, dur=1.4, bright=0.6):
    """Karplus-Strong string, vectorised period by period; slight buzz for a sitar-ish edge."""
    p = int(SR / f); n = int(dur * SR)
    out = np.zeros(n + p, np.float32)
    out[:p] = rng.uniform(-1, 1, p) * (np.linspace(1, bright, p))
    decay = 0.996
    for s in range(p, n + p, p):
        prev = out[s - p:s]
        nxt = 0.5 * (prev + np.roll(prev, 1)) * decay
        out[s:s + p] = nxt[: len(out[s:s + p])]
    y = out[:n]
    y = y + 0.18 * np.tanh(4 * y)  # jawari-like buzz
    y *= np.exp(-np.arange(n) / SR * 1.8)
    return y / (np.abs(y).max() + 1e-9)


def sine_env(f, dur, a=0.01, r=0.4, drop=0.0):
    t = np.arange(int(dur * SR)) / SR
    ff = f * (1 + drop * np.exp(-t * 30))
    return np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.minimum(1, t / a) * np.exp(-t / r)


def kick():
    return sine_env(52, 0.45, 0.002, 0.16, drop=2.2) * 1.0


def tabla_dha():  # low "dha": pitched membrane with fast bend + a ringing "na"
    a = sine_env(95, 0.5, 0.002, 0.22, drop=0.6) * 0.7; b = sine_env(520, 0.35, 0.001, 0.09) * 0.25
    a[:len(b)] += b
    return a


def tabla_na():
    return sine_env(560, 0.25, 0.001, 0.07) * 0.35


def clap():
    n = int(0.25 * SR); x = rng.normal(0, 1, n).astype(np.float32)
    x = np.diff(np.concatenate([[0], x]))  # brighten
    return x * np.exp(-np.arange(n) / SR / 0.05) * 0.35


def hat():
    n = int(0.06 * SR); x = rng.normal(0, 1, n).astype(np.float32)
    x = np.diff(np.concatenate([[0], np.diff(np.concatenate([[0], x]))]))
    return x * np.exp(-np.arange(n) / SR / 0.012) * 0.12


def bass(f, dur):
    t = np.arange(int(dur * SR)) / SR
    y = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    return y * np.minimum(1, t / 0.01) * np.exp(-t / 0.5) * 0.5


def pad(freqs, dur):
    t = np.arange(int(dur * SR)) / SR
    y = sum(np.sin(2 * np.pi * f * t + 0.4 * np.sin(2 * np.pi * 0.3 * t)) for f in freqs) / len(freqs)
    env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.6)
    return y * env * 0.22


buf_drums = np.zeros(N, np.float32); buf_bass = np.zeros(N, np.float32)
buf_pluck = np.zeros(N, np.float32); buf_pad = np.zeros(N, np.float32)

prog = [("A2", ["A3", "C4", "E4"]), ("F2", ["F3", "A3", "C4"]), ("G2", ["G3", "B3", "D4"]), ("E2", ["E3", "G3", "B3"])] * 2
for b, (root, chord) in enumerate(prog):
    t0 = b * BAR
    # drums: kick 1 & 3 (+ "and" of 3), clap 2 & 4, tabla colour, 8th hats
    for k in (0, 2, 2.5): place(buf_drums, kick(), t0 + k * BEAT, 0.9)
    for k in (1, 3): place(buf_drums, clap(), t0 + k * BEAT, 0.8)
    for k in range(8): place(buf_drums, hat(), t0 + k * BEAT / 2, 1.0 if k % 2 else 0.6)
    place(buf_drums, tabla_dha(), t0 + 3.5 * BEAT, 0.8)
    if b % 2 == 1:
        place(buf_drums, tabla_na(), t0 + 3.75 * BEAT, 0.8); place(buf_drums, tabla_dha(), t0 + 1.5 * BEAT, 0.6)
    # bass: root on 1, octave pickup, root on 3
    f = hz(root)
    place(buf_bass, bass(f, BEAT * 1.4), t0, 1.0)
    place(buf_bass, bass(f * 2, BEAT * 0.45), t0 + 1.5 * BEAT, 0.6)
    place(buf_bass, bass(f, BEAT * 1.4), t0 + 2 * BEAT, 0.9)
    # pad
    place(buf_pad, pad([hz(c) for c in chord], BAR), t0, 1.0)

# sitar motif: 2-bar call & answer, sparse (rests leave room for the voice)
motif = [  # (bar offset in beats, note, gain)
    (0.0, "A4", 1.0), (0.5, "C5", .7), (1.0, "E5", .9), (2.0, "D5", .8), (2.75, "C5", .6),
    (4.0, "C5", .9), (4.5, "B4", .6), (5.0, "A4", .8), (6.5, "G4", .6), (7.0, "A4", .9),
]
answer = [(0.0, "E5", .9), (1.0, "G5", .7), (1.5, "F5", .6), (2.0, "E5", .9), (4.0, "D5", .7), (4.5, "C5", .6), (5.0, "B4", .7), (6.0, "A4", 1.0)]
for rep, phrase in enumerate([motif, answer, motif, answer]):
    for beat, note, g in phrase:
        place(buf_pluck, pluck(hz(note), 1.3), rep * 2 * BAR + beat * BEAT, g)
# drone: tanpura-like low A + E plucks every bar
for b in range(BARS):
    place(buf_pluck, pluck(hz("A2"), 2.2, 0.4), b * BAR, 0.35)
    place(buf_pluck, pluck(hz("E3"), 2.0, 0.4), b * BAR + 2 * BEAT, 0.25)


def norm(x): return x / (np.abs(x).max() + 1e-9)


mix = norm(buf_drums) * 0.55 + norm(buf_bass) * 0.5 + norm(buf_pluck) * 0.42 + norm(buf_pad) * 0.3
# gentle tilt EQ: soften highs a touch (one-pole low-pass blend)
lp = np.empty_like(mix); acc = 0.0
for i in range(len(mix)):
    acc += 0.35 * (mix[i] - acc); lp[i] = acc
mix = 0.65 * mix + 0.35 * lp
mix = np.tanh(1.2 * mix)
mix = mix / np.abs(mix).max() * 0.8
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with wave.open(OUT, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
print("theme written:", OUT, f"{N / SR:.1f}s loop")

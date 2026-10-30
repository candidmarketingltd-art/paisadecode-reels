"""Remotion renderer ("Hisaab" style): plan v2 + timed words -> props.json -> remotion render -> UI sound design -> final mix.

The plan's cue words (Devanagari, copied from the voiceover) are resolved to seconds here, so the
React side only ever sees numbers. Captions are Roman Hinglish tokens (written by the editor model,
1:1 with the spoken words) aligned to the voice's word timings.
"""
import difflib, json, os, re, subprocess
from pathlib import Path

from pipeline.render.engine import Timeline, _norm, HANDLE
from pipeline.render import audio

ROOT = Path(__file__).resolve().parents[2]
RDIR = ROOT / "remotion"
CATALOG = set(json.loads((RDIR / "illustrations.json").read_text()))
SERIES = os.environ.get("SERIES_NAME") or "HISAAB"
FPS = 30

TYPES = {"pill", "label", "headline", "stat_row", "big_number", "split_bar", "dot_grid", "vs", "arrow_pair", "strike_list",
         "steps", "ledger", "calculator", "title_slam", "illustration", "object3d", "money_rain"}
MOODS = {"neutral", "smirk", "shocked", "serious"}


def spoken_tokens(voiceover):
    """Spoken words of the voiceover in order (audio tags removed); the editor writes one caption token per entry."""
    txt = re.sub(r"\[[^\]]*\]", " ", voiceover)
    return [w for w in txt.split() if _norm(w)]


# ------------------------------------------------------------------ captions
def align_words(spoken, roman, timed):
    """Give every spoken word (and its Roman caption token) a start/end from the TTS word timings."""
    a = [_norm(w) for w in spoken]
    b = [_norm(w) for w, _, _ in timed]
    times = [None] * len(a)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1): times[i1 + k] = (timed[j1 + k][1], timed[j1 + k][2])
        elif j2 > j1:  # replaced/merged words: spread that stretch of time evenly
            s, e = timed[j1][1], timed[j2 - 1][2]
            n = i2 - i1
            for k in range(n): times[i1 + k] = (s + (e - s) * k / n, s + (e - s) * (k + 1) / n)
    # fill anything still missing by interpolation
    for i in range(len(times)):
        if times[i] is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev + 0.3)
            times[i] = (prev, max(prev + 0.05, min(nxt, prev + 0.3)))
    out = []
    for i, tok in enumerate(roman):
        s, e = times[min(i, len(times) - 1)]
        k = tok.startswith("*")
        out.append({"t": tok.lstrip("*").replace('"', "").replace("“", "").replace("”", ""), "k": k, "s": round(s, 3), "e": round(e, 3)})
    return out


def chunk(words, max_words=5, max_chars=24):
    chunks, cur = [], []
    for i, w in enumerate(words):
        if cur and sum(len(words[j]["t"]) + 1 for j in cur) + len(w["t"]) > max_chars:
            chunks.append(cur); cur = []
        cur.append(i)
        nxt = words[i + 1]["s"] if i + 1 < len(words) else 1e9
        if len(cur) >= max_words or w["t"].endswith((".", "?", ",", "...", ":", "!")) or nxt - w["e"] > 0.35:
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    return chunks


# ------------------------------------------------------------------ cue resolution
class _Resolver:
    def __init__(self, words, duration):
        self.tl = Timeline(words, duration); self.missing = []

    def t(self, phrase, after, default):
        if isinstance(phrase, (int, float)): return float(phrase)
        v = self.tl.at(phrase, after - 0.05) if phrase else None
        if v is None:
            if phrase: self.missing.append(phrase)
            return round(default, 3)
        return round(v, 3)

    def walk(self, o, after, default=None):
        """Resolve every 'at' / '*_at' in a nested element. Cues are searched from `after` (the parent's time);
        a missing cue falls back to `default` (or the parent's time)."""
        dflt = after if default is None else default
        if isinstance(o, dict):
            base = self.t(o.get("at"), after, dflt) if "at" in o else dflt
            r = {}
            for k, v in o.items():
                if k == "at": r[k] = base
                elif k.endswith("_at"): r[k] = self.t(v, base, base + 0.4)
                else: r[k] = self.walk(v, base)
            return r
        if isinstance(o, list):
            out, last = [], after
            for x in o:
                y = self.walk(x, last); out.append(y)
                if isinstance(y, dict) and "at" in y: last = y["at"]
            return out
        return o


def build_props(plan, words, duration, episode=None):
    spoken = spoken_tokens(plan["voiceover"])
    roman = plan.get("captions") or spoken
    if len(roman) != len(spoken):  # never block a render on captions: fall back to the script words
        print(f"      captions: {len(roman)} tokens for {len(spoken)} words -> using script words", flush=True)
        roman = spoken
    cw = align_words(spoken, roman, words)
    R = _Resolver(words, duration)
    end = round(max(e for _, _, e in words), 3)

    raw = plan["scenes"]
    starts, last = [], 0.0
    for i, s in enumerate(raw):
        st = 0.0 if i == 0 else R.t(s.get("at"), last, last + 3.0)
        starts.append(st); last = st
    cta = plan.get("cta") or {}
    cta_start = R.t(cta.get("at"), last, max(last + 2, end - 4))
    scenes, reacts = [], []
    for i, s in enumerate(raw):
        st, en = starts[i], (starts[i + 1] if i + 1 < len(raw) else cta_start)
        els = []
        for k, e in enumerate(s.get("elements", [])):
            if e.get("type") not in TYPES: continue
            r = R.walk(e, st, st + 0.05 + 0.25 * k)
            if "at" not in r: r["at"] = round(st + 0.05 + 0.25 * k, 3)
            els.append(r)
        scenes.append({"start": st, "end": en, "tint": s.get("tint") or "warm", "elements": els})
        for rc in s.get("react", []) or []:
            mood = rc.get("mood") if rc.get("mood") in MOODS else "neutral"
            reacts.append({"at": R.t(rc.get("at"), st, st + 0.5), "pose": f"{mood}_{'point' if rc.get('point') else 'down'}"})
    reacts.sort(key=lambda r: r["at"])
    for i, r in enumerate(reacts):
        nxt = reacts[i + 1]["at"] if i + 1 < len(reacts) else 1e9
        r["until"] = round(min(nxt - 0.4, r["at"] + 3.2, cta_start - 0.1), 3)
    reacts = [r for r in reacts if r["until"] > r["at"] + 0.8]
    reacts.append({"at": cta_start, "until": duration + 3, "pose": "neutral_point"})

    c = R.walk({k: v for k, v in cta.items() if k != "at"}, cta_start)
    cta_p = {"start": cta_start, "line1": cta.get("line1") or "Us dost ko bhejo", "line1_at": c.get("line1_at", cta_start + 0.3),
             "line2": cta.get("line2"), "line2_at": c.get("line2_at")}
    ec = plan.get("endcard") or {}
    props = {
        "duration": duration, "badge": f"{SERIES} · EP {int(episode):02d}" if episode else SERIES,
        "tag": (plan.get("tag") or "").upper()[:22], "handle": HANDLE,
        "disclaimer": "ILLUSTRATIVE NUMBERS · NOT FINANCIAL ADVICE" if plan.get("disclaimer", True) else None,
        "words": cw, "chunks": chunk(cw), "scenes": scenes, "reacts": reacts, "cta": cta_p,
        "endcard": {"at": end, "title": ec.get("title") or "Hisaab clear?", "terminal": ec.get("terminal") or "> hisaab.saved · 1 business decoded"},
    }
    if R.missing:
        print(f"      warning: {len(R.missing)} cue(s) not found in the voice timing, used defaults: {R.missing[:6]}", flush=True)
    return props


# ------------------------------------------------------------------ sound design (one hit per visual event)
def sfx_hits(props):
    H = []
    add = lambda t, k: H.append((round(t, 3), k)) if t is not None else None
    def roll(t, n=8):
        for i in range(n): add(t + i * 0.1, "tick")
    for i, s in enumerate(props["scenes"]):
        if i: add(s["start"] - 0.12, "whoosh")
        for e in s["elements"]:
            t, ty = e["at"], e["type"]
            if ty == "pill": add(t, "ding" if e.get("color") == "green" else "pop")
            elif ty == "label": add(t, "tick")
            elif ty == "headline": add(t, "thud" if e.get("size") == "l" else "pop"); add(e.get("sub_at"), "pop")
            elif ty == "stat_row":
                for c in e["cards"]: add(c["at"], "pop"); roll(c["at"], 5) if re.search(r"\d", str(c.get("value", ""))) else None
            elif ty == "big_number": add(t, "thud"); roll(t); add(e.get("note_at"), "pop")
            elif ty == "split_bar":
                for p in e["parts"]: add(p["at"], "pop")
            elif ty == "dot_grid":
                for k in range(12): add(t + k * 0.1, "tick")
                add(e.get("lost_at"), "thud")
            elif ty in ("vs", "arrow_pair"): add(t, "pop"); add(e["right"]["at"], "thud")
            elif ty == "strike_list":
                for it in e["items"]: add(it["at"], "pop"); add(it["at"] + 0.22, "tick")
            elif ty == "steps":
                for it in e["items"]: add(it["at"], "pop")
            elif ty == "ledger":
                for r in e["rows"]: add(r["at"], "tick"); add(r["at"] + 0.15, "thud") if r.get("mark") else None
            elif ty == "calculator":
                for k in range(8): add(t + k * 0.13, "tick")
                add(e.get("value_at", t + 0.8), "thud")
            elif ty == "title_slam": add(t, "thud")
            elif ty == "illustration": add(t, "pop")
            elif ty == "object3d": add(t - 0.1, "whoosh"); add(t + 0.3, "pop")
            elif ty == "money_rain": add(t, "ding")
    c = props["cta"]; add(c["start"] - 0.1, "whoosh"); add(c["line1_at"], "pop"); add(c.get("line2_at"), "pop")
    add(props["endcard"]["at"], "ding")
    return sorted(set(H))


# ------------------------------------------------------------------ render
def _npm_ready():
    if not (RDIR / "node_modules").exists():
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=RDIR, check=True)


def render(plan, words, duration, voice_mp3, out_path, workdir, episode=None):
    props = build_props(plan, words, duration, episode)
    pj = Path(workdir) / "props.json"; pj.write_text(json.dumps(props, ensure_ascii=False))
    _npm_ready()
    vid = str(Path(workdir) / "video_only.mp4")
    cmd = ["npx", "remotion", "render", "Reel", vid, f"--props={pj}", "--gl=swangle", f"--concurrency={os.environ.get('REMOTION_CONCURRENCY') or os.cpu_count() or 2}",
           "--crf=18", "--log=warn"]
    if os.environ.get("REMOTION_BROWSER"): cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    print("      remotion:", " ".join(cmd[3:5]), flush=True)
    subprocess.run(cmd, cwd=RDIR, check=True)
    hits = sfx_hits(props)
    sfx = str(Path(workdir) / "sfx.wav"); audio.build_ui_sfx(hits, duration + 3.0, sfx)
    audio.mix(vid, voice_mp3, sfx, out_path, workdir, music_start=0.0, music_gain=float(os.environ.get("MUSIC_GAIN") or 0.16), duck_sfx=False, sfx_gain=0.85)
    return props


def preview(plan, words, duration, times, out_dir, episode=None):
    """Render a few stills for checking a plan."""
    props = build_props(plan, words, duration, episode)
    os.makedirs(out_dir, exist_ok=True)
    pj = Path(out_dir) / "props.json"; pj.write_text(json.dumps(props, ensure_ascii=False))
    for t in times:
        cmd = ["npx", "remotion", "still", "Reel", str(Path(out_dir) / f"t{t:05.1f}.png"), f"--props={pj}", f"--frame={int(t * FPS)}", "--gl=swangle", "--log=error"]
        if os.environ.get("REMOTION_BROWSER"): cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
        subprocess.run(cmd, cwd=RDIR, check=True)
    return props

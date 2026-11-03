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
AROLL = json.loads((RDIR / "aroll.json").read_text()) if (RDIR / "aroll.json").exists() else {}
SERIES = os.environ.get("SERIES_NAME") or "HISAAB"
FPS = 30

TYPES = {"pill", "label", "headline", "stat_row", "big_number", "split_bar", "dot_grid", "vs", "arrow_pair", "strike_list",
         "steps", "ledger", "calculator", "title_slam", "illustration", "object3d", "money_rain", "photo_card"}
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
        scenes.append({"start": st, "end": en, "tint": s.get("tint") or "warm", "chapter": (s.get("chapter") or "")[:26], "elements": els,
                       **({"aroll": s["aroll"]} if s.get("aroll") in AROLL else {})})
        for rc in s.get("react", []) or []:
            mood = rc.get("mood") if rc.get("mood") in MOODS else "neutral"
            reacts.append({"at": R.t(rc.get("at"), st, st + 0.5), "pose": f"{mood}_{'point' if rc.get('point') else 'down'}",
                           **({"clip": rc["clip"]} if rc.get("clip") in AROLL else {})})
    # never open a scene on an empty screen: if its hero lands well after the scene's first words (only a pill/label
    # before it), start the scene with the hero and let the previous scene stay up a little longer instead.
    for i in range(1, len(scenes)):
        sc = scenes[i]
        hero = next((e for e in sc["elements"] if e["type"] not in ("pill", "label", "money_rain")), None)
        if hero and hero["at"] - sc["start"] > 0.8:
            new = round(hero["at"] - 0.12, 3)
            scenes[i - 1]["end"] = new; sc["start"] = new
            for e in sc["elements"]:
                if e["at"] < new: e["at"] = new
    reacts.sort(key=lambda r: r["at"])
    for i, r in enumerate(reacts):
        nxt = reacts[i + 1]["at"] if i + 1 < len(reacts) else 1e9
        r["until"] = round(min(nxt - 0.4, r["at"] + 3.2, cta_start - 0.1), 3)
    reacts = [r for r in reacts if r["until"] > r["at"] + 0.8]
    cta_clip = cta.get("clip") if cta.get("clip") in AROLL else ("face_point" if "face_point" in AROLL else None)
    reacts.append({"at": cta_start, "until": duration + 3, "pose": "neutral_point", **({"clip": cta_clip} if cta_clip else {})})

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
LAND = 0.07  # elements visibly "land" ~2 frames after they start (spring + blur-to-sharp), so hits sit there


def _one_number(v):
    return len(re.findall(r"\d[\d,]*", str(v or ""))) == 1


def obj_sfx(add, kind, t):
    """Sounds for the 3D hero objects, matched to their animation (see remotion/src/Object3D.tsx)."""
    fall = (2 * 5 / 22) ** 0.5  # time a dropped object takes to hit the floor
    if kind == "coin_stack":
        for i in range(12): add(t + i * 0.09 + 0.52, "tick", p=1.6 + 0.04 * i)
        add(t + 11 * 0.09 + 0.6, "ding")
    elif kind == "coin_rain":
        add(t, "coins", dur=2.2); add(t + 1.6, "ding", p=1.1)
    elif kind == "cash_stack":
        for i in range(7): add(t + i * 0.14 + 0.56, "thud", p=1.7)
    elif kind == "gold_bars":
        for i in range(6): add(t + i * 0.12 + 0.52, "stamp")
        add(t + 1.3, "sparkle")
    elif kind == "padlock":
        add(t + fall, "impact", p=1.3); add(t + 0.55, "tick", p=0.7); add(t + 0.58, "ding", p=0.8); add(t + 1.1, "whoosh", dur=0.6)
    elif kind == "vault":
        add(t + fall, "impact", p=0.8); add(t + 0.5, "glide", dur=0.8, p=0.5); add(t + 1.3, "ding", p=0.9); add(t + 1.35, "sparkle")
    elif kind == "funnel":
        add(t, "coins", dur=2.6)
    elif kind in ("chart_up", "chart_down"):
        for i in range(5): add(t + i * 0.15 + 0.1, "note", p=(1, 1.12, 1.26, 1.41, 1.6)[i] if kind == "chart_up" else (1.6, 1.41, 1.26, 1.12, 1)[i])
    elif kind == "building":
        add(t + fall, "impact"); [add(t + 0.25 + f * 0.12, "tick", p=1 + 0.08 * f) for f in range(7)]
    elif kind == "truck":
        add(t + 0.2, "whoosh", dur=0.9); add(t + 1.0, "thud", p=0.7)
    elif kind == "shop":
        add(t + fall, "impact"); add(t + 0.4, "scribble", dur=0.6); add(t + 1.0, "ding")
    elif kind == "pizza_box":
        add(t + fall, "thud"); add(t + 0.5, "swipe", dur=0.5); add(t + 1.1, "sparkle")
    elif kind == "coin":
        add(t + fall, "ding", p=0.9); add(t + 0.1, "glide", dur=0.5, p=1.4)
    else:
        add(t + fall, "impact"); add(t + fall + 0.05, "sparkle")


def sfx_hits(props):
    """One designed sound per visual event, timed to the frame it lands (see audio.build_ui_sfx)."""
    H = []
    def add(t, k, **kw):
        if t is not None: H.append({"t": round(float(t), 3), "k": k, **kw})
    def counter(t, dur=0.9, p=1.0, land="ding"):  # tone climbs with the rolling number, chime when it stops
        add(t, "glide", dur=dur, p=p); add(t + dur, land)
    for i, s in enumerate(props["scenes"]):
        if i: add(s["start"], "whoosh")
        if s.get("chapter"): add(s["start"] + 0.05, "tick", p=1.3)
        for e in s["elements"]:
            t, ty = e["at"], e["type"]; L = t + LAND
            if ty == "pill": add(L, "ding" if e.get("color") == "green" else "pop", p=1.1)
            elif ty == "label": add(L, "tick")
            elif ty == "headline":
                add(L, "impact" if e.get("size") == "l" else "pop")
                if _one_number(e.get("text")): counter(t, 0.9, land="tick")
                if e.get("ill") or e.get("photo"): add(L + 0.08, "sparkle")
                add(e.get("sub_at"), "pop")
            elif ty == "stat_row":
                for k, c in enumerate(e["cards"]):
                    add(c["at"] + LAND, "pop", p=1 + 0.12 * k)
                    if _one_number(c.get("value")): counter(c["at"], 0.75, p=1 + 0.1 * k, land="tick")
            elif ty == "big_number":
                if i: add(t, "riser", dur=0.7)
                add(L, "impact")
                if _one_number(e.get("value")): counter(t, 0.9, p=0.9)
                add(e.get("note_at"), "pop")
            elif ty == "split_bar":
                tot = sum(max(0.0001, float(x.get("value") or 1)) for x in e["parts"])
                for k, x in enumerate(e["parts"]):
                    add(x["at"], "glide", dur=0.5, p=0.8 + 0.6 * float(x.get("value") or 1) / tot); add(x["at"] + 0.5, "tick")
            elif ty == "dot_grid":
                for k in range(16): add(t + 1.2 * (k / 16) ** 0.8, "tick", p=0.9 + 0.5 * k / 16)
                if e.get("lost_at") is not None:
                    add(e["lost_at"], "impact", p=1.3)
                    for k in range(8): add(e["lost_at"] + 0.06 * k, "drop", p=1.2 - 0.06 * k)
            elif ty == "vs":
                add(L, "pop"); add(e["right"]["at"] + LAND, "impact"); add(e.get("strike_at") or e["right"]["at"] + 0.3, "swipe")
                if _one_number(e["right"].get("value")): counter(e["right"]["at"], 0.5, land="tick")
            elif ty == "arrow_pair":
                add(L, "pop"); add(e["right"]["at"] - 0.45, "swipe", dur=0.4); add(e["right"]["at"] + LAND, "impact", p=1.2)
            elif ty == "strike_list":
                for it in e["items"]:
                    add(it["at"] + LAND, "pop")
                    if it.get("strike", True) is not False: add(it["at"] + 0.2, "swipe")
            elif ty == "steps":
                for k, it in enumerate(e["items"]): add(it["at"] + LAND, "note", p=(1, 1.26, 1.5)[min(k, 2)])
            elif ty == "ledger":
                for r in e["rows"]:
                    add(r["at"], "scribble", dur=0.3)
                    if r.get("mark"): add(r["at"] + 0.2, "stamp")
            elif ty == "calculator":
                for k in range(8): add(t + k * 0.13, "tick", p=0.8)
                va = e.get("value_at", t + 0.8); counter(va - 0.8, 1.1, land="ding")
            elif ty == "title_slam": add(t, "riser", dur=0.8); add(L, "impact", p=0.8)
            elif ty == "illustration": add(L, "pop"); add(L + 0.1, "sparkle")
            elif ty == "photo_card": add(t, "whoosh", dur=0.3); add(L, "shutter")
            elif ty == "object3d": obj_sfx(add, e.get("kind", "box"), t)
            elif ty == "money_rain": add(t, "coins", dur=2.0); add(t, "ding", p=1.2)
    for r in props.get("reacts", []):
        if r.get("clip"): add(r["at"], "whoosh", dur=0.3); add(r["at"] + 0.12, "pop", p=0.8)
        else: add(r["at"] + 0.1, "boing")
    for s_ in props["scenes"]:
        if s_.get("aroll"): add(s_["start"], "whoosh", dur=0.5); add(s_["start"] + 0.05, "impact", p=1.6)
    # micro layer: a soft blip on every gold keyword and a faint tick when a new caption line appears
    for w in props.get("words", []):
        if w.get("k"): add(w["s"] + 0.02, "blip", p=1.45)
    for ch in props.get("chunks", []):
        add(props["words"][ch[0]]["s"] - 0.05, "softtick", p=1.2)
    c = props["cta"]; add(c["start"] + 0.3, "whoosh", dur=0.9); add(c["line1_at"] + LAND, "pop"); add(c.get("line2_at"), "pop", p=1.2)
    ec = props["endcard"]["at"]; add(ec + LAND, "impact", p=0.9); add(ec + 0.4, "keys", dur=1.0); add(ec + 1.0 + LAND, "ding")
    return sorted(H, key=lambda h: h["t"])


# ------------------------------------------------------------------ render
def _npm_ready():
    if not (RDIR / "node_modules").exists():
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=RDIR, check=True)


def render(plan, words, duration, voice_mp3, out_path, workdir, episode=None):
    props = build_props(plan, words, duration, episode)
    from pipeline.render import photos
    props["photo_credits"] = photos.resolve(props)  # real photos/logos (free licences only), else illustration fallback
    pj = Path(workdir) / "props.json"; pj.write_text(json.dumps(props, ensure_ascii=False))
    _npm_ready()
    vid = str(Path(workdir) / "video_only.mp4")
    cmd = ["npx", "remotion", "render", "Reel", vid, f"--props={pj}", "--gl=swangle", f"--concurrency={os.environ.get('REMOTION_CONCURRENCY') or os.cpu_count() or 2}",
           "--crf=18", "--log=warn"]
    if os.environ.get("REMOTION_BROWSER"): cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    print("      remotion:", " ".join(cmd[3:5]), flush=True)
    subprocess.run(cmd, cwd=RDIR, check=True)
    hits = sfx_hits(props)
    sfx = str(Path(workdir) / "sfx.wav"); audio.build_ui_sfx(hits, duration + 1.8, sfx)
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

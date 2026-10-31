"""Claude Sonnet writes the reel script; Claude Opus edits the video (scene plan). Every number is fact-checked against the transcript."""
import json, os, re
from pathlib import Path
import anthropic

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_MODEL = os.environ.get("SCRIPT_MODEL") or "claude-sonnet-5-5"   # writes the Hindi script
EDIT_MODEL = os.environ.get("EDIT_MODEL") or "claude-opus-5-5"         # edits the video: scenes, cards, timing, mascot
RENDERER = (os.environ.get("RENDERER") or "remotion").lower()            # remotion = HISAAB motion style; pil = original card renderer


def _chat(model, system, msgs, max_tokens=16000):
    resp = anthropic.Anthropic().messages.create(model=model, max_tokens=max_tokens, system=system, messages=msgs)
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    return re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()


def _ask_json(model, system, user, check, attempts=3):
    """Call Claude, parse JSON, run `check`; on any problem send it back with the error to fix."""
    msgs = [{"role": "user", "content": user}]
    err = None
    for _ in range(attempts):
        raw = _chat(model, system, msgs)
        try:
            data = json.loads(raw)
            check(data)
            return data
        except (ValueError, FactCheckError) as e:
            err = e
            msgs += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": f"Problem: {e}. Fix it and return the full corrected JSON only."}]
    raise FactCheckError(f"{model} output rejected after {attempts} attempts: {err}")


MIN_WORDS, MAX_WORDS = 150, int(os.environ.get("MAX_WORDS") or 190)  # ~190 Hindi words ≈ 75 s in Rohan's voice


class FactCheckError(Exception):
    pass


def _digits(s):
    """All numbers in a string, normalised (commas removed)."""
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", s)}


def fact_check(plan, transcript, title="", derived=False):
    src = _digits(transcript) | _digits(title)
    used = _digits(plan.get("voiceover", "")) | _digits(json.dumps(plan.get("scenes", []), ensure_ascii=False)) \
        | _digits(json.dumps(plan.get("cold_open", []), ensure_ascii=False))
    # counters store rupees as integers: ₹6 लाख -> 600000 is fine if "6" + लाख appear
    lakh = {str(int(float(x) * 100000)) for x in re.findall(r"(\d+(?:\.\d+)?)\s*लाख", transcript)}
    crore = {str(int(float(x) * 10000000)) for x in re.findall(r"(\d+(?:\.\d+)?)\s*करोड़", transcript)}
    allowed = src | lakh | crore | {str(i) for i in range(0, 11)}  # small counting words (1-10, steps) are fine
    if derived:  # on-screen graphics may show simple sums/differences of the video's numbers (300 - 50 = 250 jars left)
        nums = [float(x) for x in allowed if re.fullmatch(r"\d+(?:\.\d+)?", x)]
        allowed |= {f"{v:g}" for a in nums for b in nums for v in (a + b, abs(a - b))}
    bad = sorted(n for n in used if n not in allowed)
    if bad:
        raise FactCheckError(f"numbers not found in the transcript: {', '.join(bad)}")


def _spoken(voiceover):
    """Normalised spoken words of the voiceover (audio tags removed), for checking the editor's cue words."""
    from pipeline.render.engine import _norm
    txt = re.sub(r"\[[^\]]*\]", " ", voiceover)
    return [_norm(w) for w in txt.split() if _norm(w)]


def _check_cues(plan, voiceover):
    from pipeline.render.engine import _norm
    spoken = _spoken(voiceover); joined = " " + " ".join(spoken) + " "
    bad = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if (k == "at" or k.endswith("_at")) and isinstance(v, str):
                    toks = [_norm(x) for x in v.split() if _norm(x)]
                    if toks and (" " + " ".join(toks) + " ") not in joined: bad.append(v)
                else: walk(v)
        elif isinstance(o, list):
            for x in o: walk(x)
    walk(plan.get("cold_open", [])); walk(plan.get("scenes", []))
    if bad:
        raise ValueError("these cue words are not in the voiceover exactly as written: " + " | ".join(bad[:8]))


def write(transcript, title, angle_code, angle_brief, previous_hooks=()):
    example = json.loads((ROOT / "prompts" / "example_plan_water_jar.json").read_text(encoding="utf-8"))

    # 1) Sonnet writes the script
    sys1 = (ROOT / "prompts" / "script_writer.md").read_text(encoding="utf-8").replace(
        "{EXAMPLE}", json.dumps({k: example[k] for k in ("voiceover", "ig_caption", "hashtags")}, ensure_ascii=False, indent=1))
    user1 = (f"VIDEO TITLE: {title}\n\nANGLE {angle_code}: {angle_brief}\n\n"
             + ("Other reels from this video already used these hooks — pick a different hook and focus:\n- " + "\n- ".join(previous_hooks) + "\n\n" if previous_hooks else "")
             + f"TRANSCRIPT (auto-generated Hindi captions; may contain small recognition errors — ignore garbled numbers):\n{transcript}\n\n"
             "Return only the JSON.")

    def check1(d):
        if not d.get("voiceover"): raise ValueError("missing 'voiceover'")
        n = len(_spoken(d["voiceover"]))
        if n > MAX_WORDS:
            raise ValueError(f"the voiceover has {n} spoken words; the reel must stay under ~75 seconds, so cut it to "
                             f"{MIN_WORDS}-{MAX_WORDS} words (tighten the body, keep the hook, twist and share line)")
        fact_check({"voiceover": d["voiceover"]}, transcript, title)
    script = _ask_json(SCRIPT_MODEL, sys1, user1, check1)

    if RENDERER == "remotion":
        return edit_v2(script, transcript, title)

    # 2) Opus edits the video
    sys2 = (ROOT / "prompts" / "video_editor.md").read_text(encoding="utf-8").replace(
        "{EXAMPLE}", json.dumps({k: example[k] for k in ("voiceover", "cold_open", "scenes")}, ensure_ascii=False, indent=1))
    user2 = (f"VIDEO TOPIC: {title}\n\nVOICEOVER (already recorded — cue words must match it exactly):\n{script['voiceover']}\n\n"
             "Return only the JSON with `cold_open` and `scenes`.")

    def check2(d):
        if not d.get("scenes") or not d.get("cold_open"): raise ValueError("missing 'scenes' or 'cold_open'")
        _check_cues(d, script["voiceover"])
        fact_check({"voiceover": script["voiceover"], "scenes": d["scenes"], "cold_open": d["cold_open"]}, transcript, title)
    edit = _ask_json(EDIT_MODEL, sys2, user2, check2)

    plan = {**script, "cold_open": edit["cold_open"], "scenes": edit["scenes"],
            "models": {"script": SCRIPT_MODEL, "edit": EDIT_MODEL}}
    return plan


# ---------------------------------------------------------------------------------- HISAAB (Remotion) edit
V2_TYPES = {
    "pill": ["text"], "label": ["text"], "headline": ["text"], "stat_row": ["cards"], "big_number": ["value"], "split_bar": ["parts"],
    "dot_grid": ["total"], "vs": ["left", "right"], "arrow_pair": ["left", "right"], "strike_list": ["items"], "steps": ["items"],
    "ledger": ["rows"], "calculator": ["value"], "title_slam": ["text"], "illustration": ["name"], "object3d": ["kind"], "money_rain": [],
}


def _catalog():
    return json.loads((ROOT / "remotion" / "illustrations.json").read_text())


def _check_v2(d, voiceover):
    from pipeline.render.remo import spoken_tokens
    for k in ("scenes", "captions", "cta"):
        if not d.get(k): raise ValueError(f"missing '{k}'")
    spoken = spoken_tokens(voiceover)
    cat = set(_catalog()); bad = []
    if len(d["captions"]) != len(spoken):
        bad.append(f"`captions` has {len(d['captions'])} tokens but the voiceover has {len(spoken)} spoken words — "
                         "give exactly one Roman token per numbered word, same order")
    for i, sc in enumerate(d["scenes"]):
        if not sc.get("elements"): bad.append(f"scene {i + 1} has no elements")
        for e in sc.get("elements", []):
            t = e.get("type")
            if t not in V2_TYPES: bad.append(f"unknown element type '{t}'"); continue
            for f in V2_TYPES[t]:
                if f not in e: bad.append(f"{t} needs '{f}'")
            if "at" not in e: bad.append(f"{t} needs 'at'")
            if t in ("vs", "arrow_pair") and "at" not in (e.get("right") or {}): bad.append(f"{t}.right needs 'at'")
            if t == "object3d" and e.get("kind") not in ("jar", "coin", "box"): bad.append("object3d.kind must be jar, coin or box")
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("ill", "name") and isinstance(v, str) and v not in cat: bad.append(f"illustration '{v}' is not in the list")
                    else: walk(v)
            elif isinstance(o, list):
                for x in o: walk(x)
        walk(sc.get("elements", []))
    if bad: raise ValueError("; ".join(dict.fromkeys(bad))[:900])
    _check_cues({"scenes": d["scenes"], "cold_open": [d["cta"]]}, voiceover)


def edit_v2(script, transcript, title):
    """Opus plans the HISAAB motion-graphics edit (scenes of animated elements + Roman captions)."""
    from pipeline.render.remo import spoken_tokens
    example = json.loads((ROOT / "prompts" / "example_plan_v2.json").read_text(encoding="utf-8"))
    groups = {}
    for name, g in _catalog().items(): groups.setdefault(g, []).append(name)
    ill = "\n".join(f"- {g}: " + ", ".join(sorted(v)) for g, v in sorted(groups.items()))
    sysp = (ROOT / "prompts" / "video_editor_v2.md").read_text(encoding="utf-8").replace("{ILLUSTRATIONS}", ill).replace(
        "{EXAMPLE}", json.dumps(example, ensure_ascii=False))
    spoken = spoken_tokens(script["voiceover"])
    user = (f"VIDEO TOPIC: {title}\n\nVOICEOVER (already recorded — cue words must match it exactly):\n{script['voiceover']}\n\n"
            f"SPOKEN WORDS ({len(spoken)}) — write exactly one caption token for each, in this order:\n"
            + "\n".join(f"{i + 1}. {w}" for i, w in enumerate(spoken))
            + f"\n\nINSTAGRAM CAPTION (rewrite it in Roman Hinglish as `ig_caption` — same lines, emojis, share line, follow/YouTube lines; "
              "Hindi written in English letters like \"CCTV chal raha hai... par recording band hai\"; no Devanagari):\n" + (script.get("ig_caption") or "")
            + "\n\nReturn only the JSON with `tag`, `disclaimer`, `captions`, `scenes`, `cta`, `endcard`, `ig_caption`.")

    def check(d):
        _check_v2(d, script["voiceover"])
        if re.search(r"[\u0900-\u097F]", d.get("ig_caption") or "x"):
            raise ValueError("`ig_caption` must be Roman Hinglish (English letters) with no Devanagari")
        fact_check({"voiceover": script["voiceover"], "scenes": d["scenes"], "cold_open": [d["cta"]]}, transcript, title, derived=True)
    edit = _ask_json(EDIT_MODEL, sysp, user, check, attempts=4)
    return {**script, "style": "v2", **{k: edit.get(k) for k in ("tag", "disclaimer", "captions", "scenes", "cta", "endcard")},
            "ig_caption": edit.get("ig_caption") or script.get("ig_caption"),
            "models": {"script": SCRIPT_MODEL, "edit": EDIT_MODEL}}


def roman_caption(caption):
    """Rewrite an Instagram caption from Devanagari Hindi into Roman Hinglish (cheap Sonnet call)."""
    sysp = ("Rewrite this Instagram caption so every Hindi word is written in English letters the way Indians type Hinglish "
            "(e.g. 'CCTV chal raha hai... par recording band hai'). Keep English words, numbers, ₹, emojis, line breaks, "
            "@handles and the share line exactly. Return only the caption text.")
    out = _chat(SCRIPT_MODEL, sysp, [{"role": "user", "content": caption}], max_tokens=2000).strip()
    return caption if (not out or re.search(r"[\u0900-\u097F]", out)) else out

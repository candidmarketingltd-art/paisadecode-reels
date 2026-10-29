"""Claude Sonnet writes the reel script; Claude Opus edits the video (scene plan). Every number is fact-checked against the transcript."""
import json, os, re
from pathlib import Path
import anthropic

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_MODEL = os.environ.get("SCRIPT_MODEL") or "claude-sonnet-5-5"   # writes the Hindi script
EDIT_MODEL = os.environ.get("EDIT_MODEL") or "claude-opus-5-5"         # edits the video: scenes, cards, timing, mascot


def _chat(model, system, msgs, max_tokens=8000):
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


def fact_check(plan, transcript, title=""):
    src = _digits(transcript) | _digits(title)
    used = _digits(plan.get("voiceover", "")) | _digits(json.dumps(plan.get("scenes", []), ensure_ascii=False)) \
        | _digits(json.dumps(plan.get("cold_open", []), ensure_ascii=False))
    # counters store rupees as integers: ₹6 लाख -> 600000 is fine if "6" + लाख appear
    lakh = {str(int(float(x) * 100000)) for x in re.findall(r"(\d+(?:\.\d+)?)\s*लाख", transcript)}
    crore = {str(int(float(x) * 10000000)) for x in re.findall(r"(\d+(?:\.\d+)?)\s*करोड़", transcript)}
    allowed = src | lakh | crore | {str(i) for i in range(0, 11)}  # small counting words (1-10, steps) are fine
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

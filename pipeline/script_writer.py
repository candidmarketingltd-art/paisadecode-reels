"""Write the reel script + scene plan with the Claude API, then fact-check every number against the transcript."""
import json, os, re
from pathlib import Path
import anthropic

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")


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


def write(transcript, title, angle_code, angle_brief, previous_hooks=()):
    system = (ROOT / "prompts" / "script_writer.md").read_text(encoding="utf-8")
    example = (ROOT / "prompts" / "example_plan_water_jar.json").read_text(encoding="utf-8")
    system = system.replace("{EXAMPLE}", example)
    user = (f"VIDEO TITLE: {title}\n\nANGLE {angle_code}: {angle_brief}\n\n"
            + (f"Other reels from this video already used these hooks — pick a different hook and focus:\n- " + "\n- ".join(previous_hooks) + "\n\n" if previous_hooks else "")
            + f"TRANSCRIPT (auto-generated Hindi captions; may contain small recognition errors — ignore garbled numbers):\n{transcript}\n\n"
            "Return only the JSON plan.")
    client = anthropic.Anthropic()
    msgs = [{"role": "user", "content": user}]
    last_err = None
    for attempt in range(3):
        resp = client.messages.create(model=MODEL, max_tokens=8000, system=system, messages=msgs)
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
        try:
            plan = json.loads(raw)
            for k in ("voiceover", "scenes", "cold_open"):
                if k not in plan: raise ValueError(f"missing '{k}'")
            fact_check(plan, transcript, title)
            return plan
        except (ValueError, FactCheckError) as e:
            last_err = e
            msgs += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": f"Problem: {e}. Fix it and return the full corrected JSON only. Use only numbers that appear in the transcript."}]
    raise FactCheckError(f"script rejected after 3 attempts: {last_err}")

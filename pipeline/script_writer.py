"""Write the reel script + scene plan (Gemini free tier, or Claude if a key is set), then fact-check every number against the transcript."""
import json, os, re
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-flash-latest"


def _chat(system, msgs):
    """One model call. Uses Claude if ANTHROPIC_API_KEY is set, otherwise Gemini's free tier (GEMINI_API_KEY)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        resp = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=8000, system=system, messages=msgs)
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("set GEMINI_API_KEY (free) or ANTHROPIC_API_KEY")
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in msgs],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8, "maxOutputTokens": 8192}}
    for attempt in range(4):
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                          params={"key": key}, json=body, timeout=300)
        if r.status_code in (429, 500, 503) and attempt < 3:
            import time; time.sleep(30 * (attempt + 1)); continue
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini {r.status_code}: {r.text[:400]}")
        cands = r.json().get("candidates") or []
        if not cands:
            raise RuntimeError(f"Gemini returned no text: {r.text[:300]}")
        return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])).strip()


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
    msgs = [{"role": "user", "content": user}]
    last_err = None
    for attempt in range(3):
        raw = _chat(system, msgs)
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

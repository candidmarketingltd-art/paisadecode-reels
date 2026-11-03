"""Research brief for a reel that has no YouTube video behind it ("idea-*" calendar rows from the scout).

Claude searches the web (server-side web_search tool) and writes a sourced fact sheet. The brief then plays the
role of the transcript: the script writer may only use numbers that appear in it, and the fact-check enforces that.
Cached in transcripts/<idea-id>.json so each topic is researched once.
"""
import json, os, re
from pathlib import Path
import anthropic

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "transcripts"
IDEAS = ROOT / "scout" / "ideas.json"
MODEL = os.environ.get("RESEARCH_MODEL") or os.environ.get("SCRIPT_MODEL") or "claude-sonnet-5-5"
TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": int(os.environ.get("RESEARCH_MAX_SEARCHES") or 10)}

SYSTEM = """You are the researcher for HISAAB, an Instagram reel series that shows young Indians the real money behind businesses
they dream of owning. Research the topic on the web and write a FACT SHEET a scriptwriter will use.

Find, for India and as recent as possible: what it costs to start (licence/dealership/franchise fees, land, equipment, deposits),
how the owner earns (margin or commission per unit, rupees per sale), typical volumes and monthly revenue, running costs
(staff, rent, electricity, royalty), what the owner actually keeps, break-even time, eligibility rules, and the surprising
insider facts that make people say "I never knew that". Prefer official sources (company/franchise sites, government, regulators,
annual reports) and reputable news; note when figures are estimates or vary by city.

Rules: every number must come from a source you found — never invent or "estimate" one yourself; write numbers with digits and
₹ (₹4, ₹1.94 crore, 3.5%); cite the source URL right after each fact in brackets. Plain text, short bullet lines, English.
End with a line 'SOURCES:' followed by one URL per line."""


def _ideas():
    return json.loads(IDEAS.read_text(encoding="utf-8")) if IDEAS.exists() else {}


def brief(topic, angle="", queries=()):
    client = anthropic.Anthropic()
    user = (f"TOPIC: {topic}\nANGLE FOR THE REEL: {angle}\n"
            + (("Useful searches to start with: " + "; ".join(queries) + "\n") if queries else "")
            + "Write the fact sheet now.")
    msgs = [{"role": "user", "content": user}]
    for _ in range(6):  # continue through pause_turn
        r = client.messages.create(model=MODEL, max_tokens=6000, system=SYSTEM, messages=msgs, tools=[TOOL])
        if r.stop_reason != "pause_turn":
            break
        msgs = [msgs[0], {"role": "assistant", "content": r.content}]
    text = "".join(b.text for b in r.content if b.type == "text").strip()
    urls = []
    for b in r.content:
        for c in (getattr(b, "citations", None) or []):
            u = getattr(c, "url", None)
            if u and u not in urls: urls.append(u)
    if urls and "SOURCES:" not in text:
        text += "\n\nSOURCES:\n" + "\n".join(urls)
    searches = getattr(getattr(r.usage, "server_tool_use", None), "web_search_requests", 0)
    print(f"      research: {len(text)} chars, {len(re.findall(r'https?://', text))} source links, {searches} searches (last turn)", flush=True)
    return text


def get(idea_id):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{idea_id}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    idea = _ideas().get(idea_id)
    if not idea:
        raise RuntimeError(f"unknown idea {idea_id} (not in scout/ideas.json)")
    text = brief(idea["topic"], idea.get("angle", ""), idea.get("search_queries", []))
    if len(re.findall(r"\d", text)) < 15:
        raise RuntimeError(f"research for {idea_id} found too few numbers to make an honest reel")
    data = {"video_id": idea_id, "title": idea["title"], "description": idea.get("why_it_works", ""), "text": text, "research": True}
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data

"""Weekly idea scout: find reels in our niche that already proved themselves, turn them into NEW, original HISAAB topics.

1. Apify scrapes recent reels for our hashtags / keywords / niche creator accounts (scout/config.json).
2. Keep the proven ones: lots of views and old enough that it isn't a one-day spike.
3. Claude reads what worked (topics, hooks, captions + numbers) and proposes evergreen "dream-to-own business" ideas we
   haven't covered — our own angle and research, never a copy of someone's script.
4. Ideas go to scout/ideas.json and the calendar ("idea-*" rows), interleaved with the priority video reels.
   Each idea is researched on the web when its turn comes (pipeline/research.py).

python -m pipeline.scout            (weekly workflow)
python -m pipeline.scout --dry-run  (report only, no calendar changes)
"""
import csv, datetime as dt, json, os, re, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import script_writer  # noqa: E402

SCOUT = ROOT / "scout"; CFG = json.loads((SCOUT / "config.json").read_text())
CAL = ROOT / "calendar" / "calendar.csv"
IDEAS = SCOUT / "ideas.json"
APIFY = "https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items"


def _apify(actor, payload):
    r = requests.post(APIFY.format(actor), params={"token": os.environ["APIFY_TOKEN"], "timeout": 280}, json=payload, timeout=320)
    if r.status_code >= 400:
        print(f"  apify {actor}: {r.status_code} {r.text[:300]}", flush=True); return []
    items = r.json()
    print(f"  apify {actor} {list(payload)[0]}: {len(items)} items", flush=True)
    if items:
        it = items[0]
        print("    sample keys:", sorted(it.keys())[:60], flush=True)
        print("    sample:", {k: it.get(k) for k in ("type", "productType", "shortCode", "videoPlayCount", "videoViewCount", "playCount", "likesCount", "timestamp", "error", "errorDescription")}, flush=True)
    return items


def scrape():
    n = CFG.get("results_per_source", 30); items = []
    if CFG.get("hashtags"):
        items += _apify("apify~instagram-hashtag-scraper", {"hashtags": CFG["hashtags"], "resultsType": "reels", "resultsLimit": n})
    if CFG.get("keywords"):
        items += _apify("apify~instagram-hashtag-scraper", {"hashtags": CFG["keywords"], "keywordSearch": True, "resultsType": "reels", "resultsLimit": n})
    if CFG.get("accounts"):
        items += _apify("apify~instagram-reel-scraper", {"username": CFG["accounts"], "resultsLimit": n})
    now = dt.datetime.now(dt.timezone.utc); out = {}
    for it in items:
        code = it.get("shortCode") or it.get("code")
        views = it.get("videoPlayCount") or it.get("videoViewCount") or it.get("playCount") or 0
        if not code or not views: continue
        try: age = (now - dt.datetime.fromisoformat(str(it.get("timestamp")).replace("Z", "+00:00"))).days
        except Exception: age = None
        out[code] = {"code": code, "owner": it.get("ownerUsername"), "views": int(views), "likes": it.get("likesCount") or 0,
                     "comments": it.get("commentsCount") or 0, "age_days": age, "duration": round(it.get("videoDuration") or 0),
                     "caption": re.sub(r"\s+", " ", it.get("caption") or "")[:500]}
    print(f"scraped {len(items)} items -> {len(out)} reels with view counts", flush=True)
    return list(out.values())


def proven(reels):
    keep = [r for r in reels if r["views"] >= CFG.get("min_views", 50000) and (r["age_days"] is None or r["age_days"] >= CFG.get("min_age_days", 10))]
    keep.sort(key=lambda r: r["views"], reverse=True)
    return keep[:60]


SYSTEM = """You plan topics for HISAAB, an Instagram reel series by Rohan (@rohandecoder) about the real money behind businesses.
Audience: Indian men 18-34, discovering us in the Reels tab. What works for us: the insider money secrets of a business people DREAM
of owning but know nothing about (our best reel: what a petrol pump owner earns on ₹100 of petrol — 38k views, 401 shares).

You get reels in our niche that already went viral. Find the TOPICS and HOOK PATTERNS that made them work, then propose NEW ideas
for our series. Rules:
- Our own angle on the topic — never copy another creator's script, hook wording or structure.
- Evergreen only: no news, budgets, sales, price changes or anything that expires.
- Dream-to-own businesses / insider economics people are curious about (franchises, fuel stations, cinemas, hotels, hospitals, schools,
  fleets, dealerships, licences, platforms). Must be researchable with public numbers in India.
- Skip anything already covered (list given).
Return ONLY JSON: {"ideas": [{"slug": "kebab-case-id", "title": "short English title", "topic": "what to research, one line",
"angle": "the reel's angle: hook idea + payoff, one or two lines", "hook_pattern": "the pattern borrowed (not the wording)",
"why_it_works": "evidence from the viral reels, one line", "evidence": ["shortCode", ...], "search_queries": ["...", "..."]}]}"""


def covered():
    rows = list(csv.DictReader(open(CAL, encoding="utf-8")))
    titles = sorted({r["title"] for r in rows})
    old = json.loads(IDEAS.read_text(encoding="utf-8")) if IDEAS.exists() else {}
    return titles + [i["title"] for i in old.values()], old


def ideas_from(reels, n):
    titles, old = covered()
    user = ("VIRAL REELS IN OUR NICHE (views, likes, comments, age in days, duration s, owner, caption):\n"
            + "\n".join(f"- [{r['code']}] {r['views']:,} views · {r['likes']:,} likes · {r['comments']} comments · {r['age_days']}d · {r['duration']}s · @{r['owner']}: {r['caption'][:300]}" for r in reels)
            + "\n\nALREADY COVERED (don't repeat):\n- " + "\n- ".join(titles[-150:])
            + f"\n\nPropose the {n} strongest new ideas. Return only the JSON.")
    def check(d):
        if not isinstance(d.get("ideas"), list) or not d["ideas"]: raise ValueError("no 'ideas' list")
    return script_writer._ask_json(script_writer.SCRIPT_MODEL, SYSTEM, user, check)["ideas"], old


def add_to_calendar(new):
    rows = list(csv.DictReader(open(CAL, encoding="utf-8"))); fields = list(rows[0].keys())
    today = dt.datetime.now().strftime("%Y-%m-%d")
    for idea in new:
        rows.append({**{k: "" for k in fields}, "date": today, "time_ist": "08:30", "slot": "1", "category": "economics",
                     "video_id": idea["id"], "title": idea["title"], "angle": "R", "status": "queued",
                     "angle_brief": (idea["angle"] + " (Research reel, no YouTube video: build it only from the fact sheet; in the caption "
                                     "replace the 'Full video' line with 'Numbers from public sources, approximate'.)"),
                     "notes": "scout idea: " + idea.get("why_it_works", "")[:150]})
    # interleave: one proven-video reel, one scout idea, ... (both lists keep their own order)
    pri = sorted([r for r in rows if r["status"] == "queued" and str(r.get("priority", "")).isdigit()], key=lambda r: int(r["priority"]))
    vids = [r for r in pri if not r["video_id"].startswith("idea-")]
    ideas = [r for r in pri if r["video_id"].startswith("idea-")] + [r for r in rows if r["video_id"] in {i["id"] for i in new}]
    merged = []
    while vids or ideas:
        if vids: merged.append(vids.pop(0))
        if ideas: merged.append(ideas.pop(0))
    for k, r in enumerate(merged, 1): r["priority"] = str(k)
    with open(CAL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


class _Tee:
    def __init__(self, *s): self.s = s
    def write(self, x):
        for t in self.s: t.write(x)
    def flush(self):
        for t in self.s: t.flush()


def main():
    SCOUT.mkdir(exist_ok=True)
    sys.stdout = _Tee(sys.__stdout__, open(SCOUT / "last_run.log", "w", encoding="utf-8"))
    dry = "--dry-run" in sys.argv
    reels = scrape(); top = proven(reels)
    stamp = dt.datetime.now().strftime("%Y-%m-%d")
    (SCOUT / "raw").mkdir(parents=True, exist_ok=True)
    (SCOUT / "raw" / f"{stamp}.json").write_text(json.dumps(top, ensure_ascii=False, indent=0), encoding="utf-8")
    if not top:
        print("no proven reels found this week — nothing to add"); return
    ideas, old = ideas_from(top, CFG.get("ideas_per_week", 6))
    new = []
    for i in ideas:
        iid = "idea-" + re.sub(r"[^a-z0-9]+", "-", (i.get("slug") or i["title"]).lower()).strip("-")[:40]
        if iid in old: continue
        i["id"] = iid; i["added"] = stamp; old[iid] = i; new.append(i)
    rep = [f"# Idea scout {stamp}", "", f"Proven reels scanned: {len(top)} (of {len(reels)} scraped; ≥{CFG.get('min_views')} views, ≥{CFG.get('min_age_days')} days old)", "",
           "## Top reels this week", ""] + [f"- {r['views']:,} views · @{r['owner']} · instagram.com/reel/{r['code']} · {r['caption'][:120]}" for r in top[:15]] + \
          ["", "## New ideas added", ""] + [f"- **{i['title']}** — {i['angle']} _(pattern: {i.get('hook_pattern', '')}; evidence: {', '.join(i.get('evidence', [])[:3])})_" for i in new]
    (SCOUT / "reports").mkdir(exist_ok=True)
    (SCOUT / "reports" / f"{stamp}.md").write_text("\n".join(rep), encoding="utf-8")
    print("\n".join(rep), flush=True)
    if dry: return
    IDEAS.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
    add_to_calendar(new)
    print(f"added {len(new)} ideas to the calendar", flush=True)
    # research each idea now (cached), so a topic without solid public numbers is dropped before its slot comes up
    from pipeline import research
    rows = list(csv.DictReader(open(CAL, encoding="utf-8"))); fields = list(rows[0].keys()); bad = 0
    for i in new:
        try:
            research.get(i["id"]); print(f"  researched {i['id']}", flush=True)
        except Exception as e:
            bad += 1; print(f"  research failed for {i['id']}: {e}", flush=True)
            for r in rows:
                if r["video_id"] == i["id"]: r.update(status="skipped_research", priority="", notes=str(e)[:200])
    if bad:
        with open(CAL, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()

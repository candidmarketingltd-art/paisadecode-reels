"""Build / extend the reel calendar from calendar/videos.json.

Three posting slots per day (IST):
  slot 1  08:30  business economics  ("how much does the owner really make")
  slot 2  13:30  money math          (personal finance, comparisons)
  slot 3  19:30  business ideas      (one business from a "5 boring businesses" list)
Each video becomes several reels, one per angle. Angle A of every video is used
before any angle B, so the same video never repeats close together.

Usage: python -m pipeline.build_calendar [--start 2026-10-30]
Existing rows (posted/skipped/queued) are kept; only new video×angle pairs are appended.
"""
import csv, json, re, sys, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "calendar" / "videos.json"
CAL = ROOT / "calendar" / "calendar.csv"
SLOTS = [("08:30", "economics"), ("13:30", "money"), ("19:30", "ideas")]
FIELDS = ["date", "time_ist", "slot", "category", "video_id", "title", "angle", "angle_brief", "status", "ig_media_id", "notes", "posted_at", "priority", "attempts"]

ANGLES = {
    "economics": [
        ("A", "Full story arc: the dream number, the 3 hidden costs that hit, the twist, and what to do instead."),
        ("B", "The one mistake new owners make (and the smarter move from the video). Lead with the mistake as the hook."),
        ("C", "Where every rupee goes: break the headline price into its parts and reveal what the owner actually keeps."),
    ],
    "money": [
        ("A", "The core math answer to the video's question, told as a quick story with one surprising number."),
        ("B", "The hidden cost / trap most people miss, and the simple rule to avoid it."),
    ],
}


def category(title):
    t = title.lower()
    if re.search(r"\b\d+ (boring|low investment|tricks)", t):
        return "ideas"
    if re.search(r"owner|economics|business|profit|break even|stall|tapri|dhaba|kirana|plant|café|cafe|gym|preschool|blinkit|fastag|multiplex|banquet|laundry|detailing|charger|lehenga|tent house|petrol pump|poultry", t):
        return "economics"
    return "money"


def list_size(title):
    m = re.search(r"\b(\d+) (boring|low investment|tricks)", title.lower())
    n = int(m.group(1)) if m else 5
    return 3 if "tricks" in title.lower() else n


def angles_for(v):
    cat = category(v["title"])
    if cat == "ideas":
        n = list_size(v["title"])
        if "tricks" in v["title"].lower():
            return cat, [(f"T{i+1}", f"Trick group {i+1} of 3 from the list (2-3 tricks), framed as 'check this before you buy'.") for i in range(n)]
        return cat, [(f"I{i+1}", f"Business #{i+1} from the list only: what it is, the real startup cost, how it earns, and why it's boring-but-profitable.") for i in range(n)]
    return cat, ANGLES[cat]


PRIORITY = set()  # video ids that should jump the queue (new uploads)


def load_rows():
    if not CAL.exists():
        return []
    with open(CAL, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    start = dt.date.today() + dt.timedelta(days=1)
    if "--start" in sys.argv:
        start = dt.date.fromisoformat(sys.argv[sys.argv.index("--start") + 1])
    if "--priority" in sys.argv:
        PRIORITY.update(sys.argv[sys.argv.index("--priority") + 1].split(","))
    videos = json.loads(VIDEOS.read_text(encoding="utf-8"))
    rows = load_rows()
    have = {(r["video_id"], r["angle"]) for r in rows}

    # queues per category: angle-major, most-viewed videos first
    queues = {c: [] for _, c in SLOTS}
    per_cat = {c: [] for _, c in SLOTS}
    for v in videos:
        cat, angs = angles_for(v)
        per_cat[cat].append((v, angs))
    for cat, items in per_cat.items():
        items.sort(key=lambda x: -x[0]["views"])
        depth = max((len(a) for _, a in items), default=0)
        for k in range(depth):
            for v, angs in items:
                if k < len(angs) and (v["id"], angs[k][0]) not in have:
                    queues[cat].append((v, angs[k]))

    # next free date/slot after the last scheduled row
    if rows:
        last = max(dt.date.fromisoformat(r["date"]) for r in rows)
        day = max(last + dt.timedelta(days=1), start)
    else:
        day = start
    added = 0
    while any(queues.values()):
        for si, (time, cat) in enumerate(SLOTS, 1):
            q = queues[cat] or max(queues.values(), key=len)  # borrow from the fullest queue when one runs dry
            if not q:
                continue
            v, (code, brief) = q.pop(0)
            rows.append({"date": day.isoformat(), "time_ist": time, "slot": si, "category": category(v["title"]),
                         "video_id": v["id"], "title": v["title"], "angle": code, "angle_brief": brief,
                         "status": "queued", "ig_media_id": "", "notes": "", "posted_at": "",
                         "priority": "1" if v["id"] in PRIORITY else "", "attempts": ""})
            added += 1
        day += dt.timedelta(days=1)

    with open(CAL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore"); w.writeheader()
        w.writerows([{k: r.get(k, "") for k in FIELDS} for r in rows])
    print(f"added {added} reels; calendar has {len(rows)} rows through {rows[-1]['date'] if rows else '-'}")


if __name__ == "__main__":
    main()

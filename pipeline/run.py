"""One run = one reel: pick the next calendar slot, write, voice, render, publish, update the calendar.

python -m pipeline.run                 # normal scheduled run (slot chosen from current IST time)
python -m pipeline.run --dry-run       # everything except posting to Instagram
python -m pipeline.run --row 12        # force a specific calendar row (0-based)
python -m pipeline.run --slot 3        # force a slot's category
"""
import csv, datetime as dt, json, os, sys, tempfile, traceback
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import transcript, script_writer, voice, publish  # noqa: E402
from pipeline.render import engine, audio  # noqa: E402

CAL = ROOT / "calendar" / "calendar.csv"
OUT = ROOT / "out"; PLANS = ROOT / "logs" / "plans"; MEDIA = ROOT / "media"
RUNLOG = ROOT / "logs" / "runs.csv"
IST = ZoneInfo("Asia/Kolkata")
SLOT_CAT = {1: "economics", 2: "money", 3: "ideas"}
SLOT_TIME = {1: (8, 30), 2: (13, 30), 3: (19, 30)}


def load():
    with open(CAL, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r.setdefault("posted_at", ""); r.setdefault("priority", ""); r.setdefault("attempts", "")
    return rows


def save(rows):
    fields = list(rows[0].keys())
    for extra in ("posted_at", "priority", "attempts"):
        if extra not in fields: fields.append(extra)
    with open(CAL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def current_slot(now):
    mins = now.hour * 60 + now.minute
    return min(SLOT_TIME, key=lambda s: abs(SLOT_TIME[s][0] * 60 + SLOT_TIME[s][1] - mins))


def pick(rows, slot):
    open_rows = [(i, r) for i, r in enumerate(rows) if r["status"] in ("queued", "rendered")]
    key = lambda x: (0 if x[1].get("priority") else 1, x[1]["date"], x[1]["time_ist"])
    same = sorted([x for x in open_rows if x[1]["category"] == SLOT_CAT[slot]], key=key)
    return (same or sorted(open_rows, key=key) or [(None, None)])[0]


def previous_hooks(video_id, angle):
    hooks = []
    for p in PLANS.glob(f"{video_id}_*.json"):
        if p.stem.endswith(f"_{angle}"): continue
        try:
            hooks.append(" / ".join(x["text"] for x in json.loads(p.read_text(encoding="utf-8")).get("cold_open", [])))
        except Exception:
            pass
    return hooks


def log(row, status, note=""):
    RUNLOG.parent.mkdir(parents=True, exist_ok=True)
    new = not RUNLOG.exists()
    with open(RUNLOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["run_at_ist", "video_id", "angle", "status", "note"])
        w.writerow([dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M"), row["video_id"], row["angle"], status, note])


def make_reel(row, workdir):
    """Returns (mp4_path, caption)."""
    vid, angle = row["video_id"], row["angle"]
    pre = MEDIA / f"{vid}_{angle}.mp4"
    plan_path = PLANS / f"{vid}_{angle}.json"
    if row["status"] == "rendered" and pre.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
        return str(pre), caption_of(plan, row)
    tr = transcript.get(vid)
    print(f"[1/4] script  {vid} {angle}: {row['title']}", flush=True)
    plan = script_writer.write(tr["text"], tr.get("title") or row["title"], angle, row["angle_brief"], previous_hooks(vid, angle))
    PLANS.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[2/4] voice", flush=True)
    mp3 = f"{workdir}/vo.mp3"
    words, model = voice.synthesize(plan["voiceover"], mp3)
    dur = max(e for _, _, e in words) + 0.1
    print(f"      {len(words)} words, {dur:.1f}s, model {model}", flush=True)
    print("[3/4] render", flush=True)
    vid_only = f"{workdir}/video_only.mp4"
    cues = engine.render(plan, words, dur, vid_only)
    cues["music"] = bool(audio.theme_path())
    sfx = f"{workdir}/sfx.wav"; audio.build_sfx(cues, sfx)
    OUT.mkdir(exist_ok=True)
    final = str(OUT / f"{row['date']}_{row['time_ist'].replace(':', '')}_{vid}_{angle}.mp4")
    audio.mix(vid_only, mp3, sfx, final, workdir, music_start=cues["open_end"])
    return final, caption_of(plan, row)


def fail(row, note):
    """Two failed attempts on the same reel -> mark it failed so the queue moves on."""
    n = int(row.get("attempts") or 0) + 1
    row["attempts"] = str(n); row["notes"] = note
    if n >= 2: row["status"] = "failed"


def caption_of(plan, row):
    cap = plan.get("ig_caption") or row["title"]
    tags = " ".join(plan.get("hashtags", []) or ["#PaisaDecode"])
    return f"{cap}\n\n{tags}"[:2150]


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args or os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    rows = load()
    if "--refill" in args:
        return refill(rows, int(args[args.index("--refill") + 1]), dry)
    now = dt.datetime.now(IST)
    slot = int(args[args.index("--slot") + 1]) if "--slot" in args else current_slot(now)
    if "--row" in args:
        i = int(args[args.index("--row") + 1]); row = rows[i]
    else:
        i, row = pick(rows, slot)
    if row is None:
        print("calendar is empty — nothing to do"); return
    print(f"slot {slot} ({SLOT_CAT[slot]}) -> row {i}: {row['video_id']} {row['angle']} | dry_run={dry}", flush=True)
    with tempfile.TemporaryDirectory() as wd:
        try:
            mp4, caption = make_reel(row, wd)
        except script_writer.FactCheckError as e:
            row["status"] = "skipped_factcheck"; row["notes"] = str(e)[:300]; save(rows); log(row, "skipped_factcheck", str(e)[:300])
            print("SKIPPED:", e); return
        except Exception as e:
            traceback.print_exc()
            fail(row, f"render failed: {str(e)[:250]}"); save(rows); log(row, "error", str(e)[:300])
            sys.exit(1)
        if dry:
            print(f"DRY RUN — reel at {mp4}\n--- caption ---\n{caption}")
            log(row, "dry_run", mp4); return
        print("[4/4] publish", flush=True)
        try:
            mid, link = publish.publish_reel(mp4, caption)
        except Exception as e:
            traceback.print_exc()
            fail(row, f"publish failed: {str(e)[:250]}"); save(rows); log(row, "publish_error", str(e)[:300])
            sys.exit(1)
        row.update(status="posted", ig_media_id=mid, notes=link, posted_at=dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M"))
        save(rows); log(row, "posted", link)
        print(f"POSTED {mid} {link}")


def refill(rows, target, dry):
    """Buffer mode: keep `target` reels waiting in Buffer's queue (stays inside the free plan's queue limit)."""
    from pipeline import buffer
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "APIFY_TOKEN", "BUFFER_API_KEY", "BUFFER_CHANNEL_ID"):
        print(f"  {k}: {'set' if os.environ.get(k) else 'MISSING'}", flush=True)
    level, how = buffer.queued_count()
    need = max(0, target - level)
    print(f"Buffer queue: {level} waiting ({how}); target {target} -> making {need}", flush=True)
    st_path = ROOT / "logs" / "rotation.json"
    try: k = json.loads(st_path.read_text())["next"]
    except Exception: k = 0
    made = 0; tries = 0
    while made < need and tries < need + 4:
        tries += 1
        slot = k % 3 + 1
        i, row = pick(rows, slot)
        if row is None: print("calendar empty"); break
        print(f"--- reel {made + 1}/{need}: slot {slot} ({SLOT_CAT[slot]}) row {i}: {row['video_id']} {row['angle']}", flush=True)
        with tempfile.TemporaryDirectory() as wd:
            try:
                mp4, caption = make_reel(row, wd)
            except script_writer.FactCheckError as e:
                row["status"] = "skipped_factcheck"; row["notes"] = str(e)[:300]; save(rows); log(row, "skipped_factcheck", str(e)[:300]); continue
            except Exception as e:
                traceback.print_exc(); fail(row, f"render failed: {str(e)[:250]}"); save(rows); log(row, "error", str(e)[:300]); continue
            if dry:
                print(f"DRY RUN — reel at {mp4}"); log(row, "dry_run", mp4); made += 1; k += 1; continue
            try:
                tag = f"reel-{row['video_id']}-{row['angle']}".replace("_", "-")
                url = buffer.host_video(mp4, tag)
                pid = buffer.add_to_queue(url, caption)
            except Exception as e:
                traceback.print_exc(); fail(row, f"buffer failed: {str(e)[:250]}"); save(rows); log(row, "publish_error", str(e)[:300]); break
            row.update(status="in_buffer", ig_media_id=pid, notes=url, posted_at=f"queued {dt.datetime.now(IST):%Y-%m-%d %H:%M}")
            save(rows); log(row, "in_buffer", pid)
            made += 1; k += 1
            st_path.write_text(json.dumps({"next": k}))
    if not dry:
        buffer.remember_level(level + made)
    print(f"added {made} reel(s) to Buffer")


if __name__ == "__main__":
    main()

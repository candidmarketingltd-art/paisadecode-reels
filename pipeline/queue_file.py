"""Queue an already-made reel in Buffer and mark its calendar row (no script/voice/render).

python -m pipeline.queue_file <mp4> <video_id> <angle>
"""
import datetime as dt, json, sys
from pipeline import buffer
from pipeline.run import load, save, log, caption_of, PLANS, IST

mp4, vid, angle = sys.argv[1:4]
rows = load()
row = next(r for r in rows if r["video_id"] == vid and r["angle"] == angle)
pf = PLANS / f"{vid}_{angle}.json"
plan = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
level, how = buffer.queued_count()
print(f"Buffer has {level} waiting ({how})", flush=True)
url = buffer.host_video(mp4, f"reel-{vid}-{angle}".replace("_", "-"))
pid = buffer.add_to_queue(url, caption_of(plan, row))
row.update(status="in_buffer", ig_media_id=pid, notes=url, posted_at=f"queued {dt.datetime.now(IST):%Y-%m-%d %H:%M}")
save(rows); log(row, "in_buffer", pid); buffer.remember_level(level + 1)
print("queued", vid, angle, pid, url)

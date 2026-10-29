"""Weekly: find new uploads on the channel and queue their reels at the front of the line."""
import json, os, subprocess, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "calendar" / "videos.json"
CHANNEL = (os.environ.get("YT_CHANNEL_URL") or "https://www.youtube.com/@PaisaDecodeHQ/videos")


def views(v):
    try: return int(v)
    except Exception: return 0


def main():
    r = requests.post("https://api.apify.com/v2/acts/streamers~youtube-channel-scraper/run-sync-get-dataset-items",
                      params={"token": os.environ["APIFY_TOKEN"], "timeout": 240},
                      json={"startUrls": [{"url": CHANNEL}], "maxResults": 30, "maxResultsShorts": 0, "maxResultStreams": 0}, timeout=300)
    r.raise_for_status()
    have = json.loads(VIDEOS.read_text(encoding="utf-8"))
    ids = {v["id"] for v in have}
    new = [{"id": it["id"], "title": it["title"], "dur": it.get("duration", ""), "views": views(it.get("viewCount"))}
           for it in r.json() if it.get("type", "video") == "video" and it.get("id") and it["id"] not in ids]
    # skip Shorts / very short uploads
    new = [v for v in new if ":" in str(v["dur"]) and int(str(v["dur"]).split(":")[0]) >= 4]
    if not new:
        print("no new videos"); return
    VIDEOS.write_text(json.dumps(have + new, ensure_ascii=False, indent=0), encoding="utf-8")
    print("new:", [v["title"] for v in new])
    subprocess.run([sys.executable, "-m", "pipeline.build_calendar", "--priority", ",".join(v["id"] for v in new)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

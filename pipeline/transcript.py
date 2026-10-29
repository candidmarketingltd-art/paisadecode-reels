"""Fetch a YouTube transcript through Apify (YouTube blocks most cloud IPs, Apify doesn't get blocked).
Transcripts are cached in transcripts/<video_id>.json so each video is fetched only once."""
import json, os
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "transcripts"
ACTOR = os.environ.get("APIFY_TRANSCRIPT_ACTOR", "johnvc~YoutubeTranscripts")


def get(video_id):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{video_id}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
    r = requests.post(url, params={"token": os.environ["APIFY_TOKEN"], "timeout": 240},
                      json={"youtube_url": f"https://www.youtube.com/watch?v={video_id}", "languages": ["hi", "en"],
                            "output_formats": ["text"], "include_metadata": True}, timeout=300)
    r.raise_for_status()
    items = r.json()
    text = title = description = ""
    for it in items:
        text = text or it.get("non_timestamped") or it.get("text") or ""
        title = title or it.get("title") or ""
        description = description or it.get("description") or ""
    if len(text) < 200:
        raise RuntimeError(f"no usable transcript for {video_id}")
    data = {"video_id": video_id, "title": title, "description": description, "text": text}
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data

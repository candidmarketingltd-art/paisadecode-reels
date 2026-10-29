"""Publish a Reel to Instagram (Instagram API with Facebook Login, resumable upload — no public hosting needed).

Needs: IG_USER_ID (Instagram professional account id) and IG_ACCESS_TOKEN (a non-expiring System User token
from Meta Business Manager with instagram_basic + instagram_content_publish + pages_read_engagement).
"""
import os, time
import requests

VER = os.environ.get("META_API_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{VER}"


def _tok(): return os.environ["IG_ACCESS_TOKEN"]
def _ig(): return os.environ["IG_USER_ID"]


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text[:500]}")
    return r.json()


def publish_reel(mp4_path, caption, share_to_feed=True):
    size = os.path.getsize(mp4_path)
    c = _check(requests.post(f"{GRAPH}/{_ig()}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true" if share_to_feed else "false",
        "audio_name": os.environ.get("IG_AUDIO_NAME", "Paisa Decode Theme"), "access_token": _tok()}, timeout=60))
    cid = c["id"]
    up_url = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VER}/{cid}"
    with open(mp4_path, "rb") as f:
        _check(requests.post(up_url, headers={"Authorization": f"OAuth {_tok()}", "offset": "0", "file_size": str(size)}, data=f, timeout=900))
    for _ in range(40):  # up to ~10 min of processing
        st = _check(requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": _tok()}, timeout=60))
        code = st.get("status_code")
        if code == "FINISHED": break
        if code in ("ERROR", "EXPIRED"): raise RuntimeError(f"Instagram processing failed: {st}")
        time.sleep(15)
    else:
        raise RuntimeError("Instagram processing timed out")
    pub = _check(requests.post(f"{GRAPH}/{_ig()}/media_publish", data={"creation_id": cid, "access_token": _tok()}, timeout=120))
    mid = pub["id"]
    try:
        link = _check(requests.get(f"{GRAPH}/{mid}", params={"fields": "permalink", "access_token": _tok()}, timeout=60)).get("permalink", "")
    except Exception:
        link = ""
    return mid, link


def quota():
    return _check(requests.get(f"{GRAPH}/{_ig()}/content_publishing_limit", params={"fields": "quota_usage,config", "access_token": _tok()}, timeout=60))

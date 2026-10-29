"""Publish a Reel to Instagram.

Two ways, picked automatically:
  1. Upload-Post (easy): set UPLOAD_POST_API_KEY (+ UPLOAD_POST_USER = your Upload-Post profile name).
     Instagram is connected with one click in app.upload-post.com — no Facebook Page or Meta app needed.
  2. Meta Graph API (free): IG_USER_ID + IG_ACCESS_TOKEN, see below.

Meta route: Instagram API with Facebook Login, resumable upload — no public hosting needed.

Needs: IG_USER_ID (Instagram professional account id) and IG_ACCESS_TOKEN (a non-expiring System User token
from Meta Business Manager with instagram_basic + instagram_content_publish + pages_read_engagement).
"""
import json, os, time
import requests

VER = (os.environ.get("META_API_VERSION") or "v26.0")
GRAPH = f"https://graph.facebook.com/{VER}"


def _tok(): return os.environ["IG_ACCESS_TOKEN"]
def _ig(): return os.environ["IG_USER_ID"]


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text[:500]}")
    return r.json()


def publish_reel(mp4_path, caption, share_to_feed=True):
    if os.environ.get("UPLOAD_POST_API_KEY"):
        return _upload_post(mp4_path, caption, share_to_feed)
    return _meta(mp4_path, caption, share_to_feed)


UP = "https://api.upload-post.com/api"


def _find(obj, keys):
    """Search a nested JSON response for the first value under any of `keys`."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, (str, int)) and v: return v
        for v in obj.values():
            r = _find(v, keys)
            if r: return r
    if isinstance(obj, list):
        for v in obj:
            r = _find(v, keys)
            if r: return r
    return None


def _upload_post(mp4_path, caption, share_to_feed):
    hdr = {"Authorization": f"Apikey {os.environ['UPLOAD_POST_API_KEY']}"}
    data = {"user": (os.environ.get("UPLOAD_POST_USER") or "paisadecode"), "platform[]": "instagram", "media_type": "REELS",
            "title": caption, "instagram_title": caption, "share_to_feed": "true" if share_to_feed else "false",
            "audio_name": (os.environ.get("IG_AUDIO_NAME") or "Paisa Decode Theme"), "async_upload": "true"}
    with open(mp4_path, "rb") as f:
        r = requests.post(f"{UP}/upload", headers=hdr, data=data, files={"video": (os.path.basename(mp4_path), f, "video/mp4")}, timeout=900)
    js = _check(r)
    if js.get("success") is False:
        raise RuntimeError(f"Upload-Post rejected the upload: {js}")
    rid = js.get("request_id")
    if not rid:  # finished synchronously
        return str(_find(js, ("post_id", "id", "media_id")) or "upload-post"), str(_find(js, ("url", "post_url", "permalink")) or "")
    for _ in range(60):  # up to ~15 min
        time.sleep(15)
        st = _check(requests.get(f"{UP}/uploadposts/status", headers=hdr, params={"request_id": rid}, timeout=60))
        txt = json.dumps(st).lower()
        url = _find(st, ("url", "post_url", "permalink"))
        if url or '"success": true' in txt and ('"completed"' in txt or '"published"' in txt or '"finished"' in txt):
            return str(_find(st, ("post_id", "media_id")) or rid), str(url or "")
        if '"failed"' in txt or '"error"' in txt and '"success": false' in txt:
            raise RuntimeError(f"Upload-Post failed: {st}")
    return rid, "pending — check app.upload-post.com"


def _meta(mp4_path, caption, share_to_feed=True):
    size = os.path.getsize(mp4_path)
    c = _check(requests.post(f"{GRAPH}/{_ig()}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true" if share_to_feed else "false",
        "audio_name": (os.environ.get("IG_AUDIO_NAME") or "Paisa Decode Theme"), "access_token": _tok()}, timeout=60))
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

"""Buffer (free plan) as the Instagram publisher.

Buffer pulls videos from a public URL, so each reel is first attached to a GitHub Release
(free, public download link), then added to the Buffer queue for the Instagram channel.
Buffer's posting schedule (set in Buffer to 08:30 / 13:30 / 19:30 IST) decides when each one goes out.

Env: BUFFER_API_KEY (secret), BUFFER_CHANNEL_ID (variable; from the channel URL in publish.buffer.com),
     optional BUFFER_ORG_ID. Hosting: MEDIA_REPO (owner/repo, public) + MEDIA_TOKEN or GITHUB_TOKEN.
"""
import os, json, time
import requests

API = "https://api.buffer.com"


class Enum(str):
    """A GraphQL enum value (written without quotes)."""


def lit(v):
    """Python value -> GraphQL literal (inline input, exactly like Buffer's own examples)."""
    if isinstance(v, Enum): return str(v)
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return "[" + ", ".join(lit(x) for x in v) + "]"
    if isinstance(v, dict): return "{ " + ", ".join(f"{k}: {lit(x)}" for k, x in v.items()) + " }"
    raise TypeError(type(v))


def _gql(query, variables=None):
    r = requests.post(API, headers={"Authorization": f"Bearer {os.environ['BUFFER_API_KEY']}", "Content-Type": "application/json"},
                      json={"query": query, "variables": variables or {}}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Buffer {r.status_code}: {r.text[:400]}")
    js = r.json()
    if js.get("errors"):
        raise RuntimeError(f"Buffer error: {json.dumps(js['errors'])[:400]}")
    return js["data"]


def org_id():
    if os.environ.get("BUFFER_ORG_ID"):
        return os.environ["BUFFER_ORG_ID"]
    return _gql("query { account { organizations { id name } } }")["account"]["organizations"][0]["id"]


STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "buffer_state.json")
POSTS_PER_DAY = 3


def queued_count():
    """Posts currently waiting in Buffer. Asks Buffer; if that query isn't available, estimates from our own log
    (3 go out per day)."""
    q = "query { posts(input: { organizationId: %s, filter: { status: [scheduled] } }) { edges { node { id } } } }" % lit(org_id())
    try:
        return len(_gql(q)["posts"]["edges"]), "buffer"
    except Exception as e:
        print(f"      (couldn't read Buffer queue: {str(e)[:120]}; estimating)")
    try:
        st = json.load(open(STATE))
    except Exception:
        return 0, "estimate"
    days = (time.time() - st["at"]) / 86400
    return max(0, round(st["level"] - POSTS_PER_DAY * days)), "estimate"


def remember_level(level):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump({"level": level, "at": time.time()}, open(STATE, "w"))


def host_video(path, tag):
    """Upload the MP4 as a GitHub Release asset and return its public download URL."""
    repo = os.environ.get("MEDIA_REPO") or os.environ["GITHUB_REPOSITORY"]
    tok = os.environ.get("MEDIA_TOKEN") or os.environ["GITHUB_TOKEN"]
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    r = requests.post(f"https://api.github.com/repos/{repo}/releases", headers=h,
                      json={"tag_name": tag, "name": tag, "body": "Reel video for Buffer", "prerelease": True}, timeout=60)
    if r.status_code == 422:  # tag exists -> reuse
        r = requests.get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=h, timeout=60)
    r.raise_for_status()
    rel = r.json()
    name = os.path.basename(path)
    for a in rel.get("assets", []):
        if a["name"] == name:
            return a["browser_download_url"]
    up = rel["upload_url"].split("{")[0]
    with open(path, "rb") as f:
        r = requests.post(up, headers={**h, "Content-Type": "video/mp4"}, params={"name": name}, data=f, timeout=900)
    r.raise_for_status()
    url = r.json()["browser_download_url"]
    # make sure the link is publicly reachable before handing it to Buffer
    for _ in range(10):
        if requests.head(url, allow_redirects=True, timeout=30).status_code == 200:
            break
        time.sleep(6)
    return url


def add_to_queue(video_url, caption):
    inp = {"text": caption, "channelId": os.environ["BUFFER_CHANNEL_ID"], "schedulingType": Enum("automatic"), "mode": Enum("addToQueue"),
           "assets": [{"video": {"url": video_url, "metadata": {"thumbnailOffset": 6000}}}],
           "metadata": {"instagram": {"type": Enum("reel"), "shouldShareToFeed": True}}}
    m = ("mutation CreatePost { createPost(input: %s) { ... on PostActionSuccess { post { id } } ... on MutationError { message } } }" % lit(inp))
    res = _gql(m)["createPost"]
    if not res.get("post"):
        raise RuntimeError(f"Buffer rejected the post: {res.get('message')}")
    return res["post"]["id"]

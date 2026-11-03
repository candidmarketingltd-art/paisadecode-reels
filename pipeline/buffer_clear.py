"""Take back every reel still scheduled in Buffer for our Instagram channel, so it can be refilled with fresh ones.

- deletes the channel's future (not yet sent) posts in Buffer
- puts their calendar rows back to "queued" and deletes their saved plans, so they are rewritten later under the current rules

python -m pipeline.buffer_clear [--dry-run]
"""
import datetime as dt, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import buffer  # noqa: E402
from pipeline.run import load, save, log, PLANS  # noqa: E402


def scheduled_posts():
    q = ("query { posts(first: 100, input: { organizationId: %s }) { edges { node { id status channelId dueAt text } } } }" % buffer.lit(buffer.org_id()))
    now = dt.datetime.now(dt.timezone.utc); ch = os.environ.get("BUFFER_CHANNEL_ID"); out = []
    for e in buffer._gql(q)["posts"]["edges"]:
        n = e["node"]; st = ",".join(n["status"]) if isinstance(n.get("status"), list) else str(n.get("status"))
        if ch and n.get("channelId") != ch: continue
        due = n.get("dueAt")
        if due and dt.datetime.fromisoformat(due.replace("Z", "+00:00")) > now and not any(w in st.lower() for w in ("sent", "error", "fail")):
            out.append(n)
    return out


def _delete_mutation():
    """Find Buffer's delete-post mutation and its input shape (introspection, so we don't guess the schema)."""
    q = "query { __schema { mutationType { fields { name args { name type { name kind ofType { name kind } } } } } } }"
    fields = buffer._gql(q)["__schema"]["mutationType"]["fields"]
    f = next((x for x in fields if x["name"].lower() == "deletepost"), None) or next(x for x in fields if "delete" in x["name"].lower() and "post" in x["name"].lower())
    return f


def delete(post_id, f):
    args = f["args"]
    if any(a["name"] == "input" for a in args):
        arg = "input: { id: %s }" % buffer.lit(post_id)
    else:
        arg = "%s: %s" % (args[0]["name"], buffer.lit(post_id))
    m = "mutation { %s(%s) { __typename } }" % (f["name"], arg)
    return buffer._gql(m)


def main():
    dry = "--dry-run" in sys.argv
    posts = scheduled_posts()
    print(f"{len(posts)} reel(s) scheduled in Buffer for this channel", flush=True)
    for p in posts: print(f"  {p['dueAt']}  {p['id']}  {(p.get('text') or '')[:70]!r}", flush=True)
    if dry or not posts: return
    f = _delete_mutation(); print("delete mutation:", f["name"], [a["name"] for a in f["args"]], flush=True)
    ids = set()
    for p in posts:
        try:
            delete(p["id"], f); ids.add(p["id"]); print("  deleted", p["id"], flush=True)
        except Exception as e:
            print("  could not delete", p["id"], str(e)[:200], flush=True)
    rows = load(); n = 0
    for r in rows:
        if r["status"] == "in_buffer" and r.get("ig_media_id") in ids:
            pf = PLANS / f"{r['video_id']}_{r['angle']}.json"
            if pf.exists(): pf.unlink()  # rewrite under the current hook/length/edit rules when its turn comes
            r.update(status="queued", ig_media_id="", notes="taken back from Buffer for a remake", posted_at="", attempts="")
            log(r, "taken_back", ""); n += 1
    save(rows); buffer.remember_level(0)
    print(f"took back {len(ids)} post(s); {n} calendar row(s) re-queued", flush=True)


if __name__ == "__main__":
    main()

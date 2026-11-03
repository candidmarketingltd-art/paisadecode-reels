"""Real photos and logos for reels (a Fortuner when we talk about a Fortuner, Amul's logo when we talk about Amul).

Only freely licensed images are used, so reels can't be hit with copyright claims:
1. remotion/public/brands/<slug>.(png|jpg|webp) — files Rohan adds himself (he is responsible for having the rights);
2. Wikimedia Commons — public domain / CC0 / CC BY / CC BY-SA files only, credited on screen and in the caption.
Logos are shown only to identify the brand the reel is about (no endorsement implied).
If nothing suitable is found, the element falls back to its 3D illustration.
"""
import hashlib, html, json, re
from pathlib import Path
import requests

RDIR = Path(__file__).resolve().parents[2] / "remotion"
PUB = RDIR / "public"
UA = {"User-Agent": "HisaabReels/1.0 (https://github.com/candidmarketingltd-art/paisadecode-reels)"}
API = "https://commons.wikimedia.org/w/api.php"
FREE = re.compile(r"^(cc0|cc[- ]by(-sa)?([- ][\d.]+)?|cc-by(-sa)?-[\d.]+.*|public domain|pd.*)$", re.I)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60]


def _local(query):
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = PUB / "brands" / f"{slug(query)}.{ext}"
        if p.exists():
            return {"src": f"brands/{p.name}", "credit": ""}
    return None


def _clean(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h or ""))).strip()[:60]


def _commons(query, kind):
    q = query + (" logo" if kind == "logo" and "logo" not in query.lower() else "")
    r = requests.get(API, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrnamespace": 6, "gsrlimit": 15,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 900})
    r.raise_for_status()
    pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2 and w != "logo"]
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata") or {}
        lic = (md.get("LicenseShortName") or {}).get("value", "") or (md.get("License") or {}).get("value", "")
        title = p.get("title", "").lower()
        if not FREE.match(lic.strip()): continue
        if words and not all(w in title for w in words[:2]): continue  # file name must mention the brand/product
        if kind == "logo" and "logo" not in title and not ii.get("mime", "").endswith("svg+xml"): continue
        if kind != "logo" and ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"): continue
        if kind != "logo" and (ii.get("width") or 0) < 600: continue
        url = ii.get("thumburl") or ii.get("url")
        if not url: continue
        artist = _clean((md.get("Artist") or {}).get("value", ""))
        credit = ("Wikimedia Commons" + (f" / {artist}" if artist and "unknown" not in artist.lower() else "") + f" · {lic}").strip()
        return url, credit
    return None


def fetch(query, kind="product"):
    """-> {"src": path under public/, "credit": str} or None."""
    if not query: return None
    hit = _local(query)
    if hit: return hit
    try:
        found = _commons(query, kind)
    except Exception as e:
        print(f"      photo search failed for '{query}': {e}", flush=True); return None
    if not found:
        print(f"      no free image for '{query}' ({kind}) -> illustration", flush=True); return None
    url, credit = found
    ext = ".png" if ".png" in url.lower() or url.lower().endswith(".svg.png") else ".jpg"
    name = hashlib.md5(url.encode()).hexdigest()[:12] + ext
    out = PUB / "photos" / name; out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        r = requests.get(url, headers=UA, timeout=60); r.raise_for_status(); out.write_bytes(r.content)
    print(f"      photo '{query}' -> {name} ({credit})", flush=True)
    return {"src": f"photos/{name}", "credit": credit}


def resolve(props):
    """Fill in every `photo` request in the props; returns the list of credits used."""
    credits = []
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("photo"), str):
                hit = fetch(o["photo"], o.get("photo_kind") or ("logo" if o.get("type") == "logo" else "product"))
                if hit:
                    o["photo"] = hit["src"]; o["photo_credit"] = hit["credit"]
                    if hit["credit"] and hit["credit"] not in credits: credits.append(hit["credit"])
                else:
                    o.pop("photo")
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(props["scenes"])
    return credits

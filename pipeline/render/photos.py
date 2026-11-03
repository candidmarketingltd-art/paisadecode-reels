"""Real photos / logos for named things (a Toyota Fortuner, the Amul logo, a Domino's store) from Wikimedia Commons.

Only freely licensed files are used (public domain, CC0, CC BY, CC BY-SA). Each pick returns a credit line that is
added to the Instagram caption, as those licences require. No photos of people are requested (the editor is told so,
and files whose description mentions a person are skipped where we can tell).
"""
import hashlib, html, io, json, os, re
from pathlib import Path
import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "HisaabReels/1.0 (https://github.com/candidmarketingltd-art/paisadecode-reels; reels automation)"}
OK_LICENCE = re.compile(r"^(public domain|pd\b|cc0|cc[ -]by(-sa)?([ -][0-9.]+)?)", re.I)
PEOPLE = re.compile(r"\b(portrait|selfie|politician|actor|actress|minister|ceo|founder|chairman|wedding|people|crowd|man|woman|boy|girl)\b", re.I)


def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def search(query, kind="product", limit=12):
    q = query + (" logo" if kind == "logo" and "logo" not in query.lower() else "")
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:bitmap|drawing",
              "gsrnamespace": 6, "gsrlimit": limit, "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 900}
    r = requests.get(API, params=params, headers=UA, timeout=30); r.raise_for_status()
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]; m = ii.get("extmetadata", {})
        lic = _clean(m.get("LicenseShortName", {}).get("value"))
        desc = _clean(m.get("ImageDescription", {}).get("value")) + " " + p["title"]
        if not OK_LICENCE.match(lic or ""): continue
        if kind != "logo" and PEOPLE.search(desc): continue
        if ii.get("width", 0) < 300 and kind != "logo": continue
        out.append({"title": p["title"].replace("File:", ""), "url": ii.get("thumburl") or ii.get("url"), "mime": ii.get("mime"),
                    "licence": lic, "artist": _clean(m.get("Artist", {}).get("value"))[:80] or "unknown",
                    "page": ii.get("descriptionurl"), "w": ii.get("width"), "h": ii.get("height")})
    # words of the query should appear in the file title (avoids random matches)
    words = [w for w in re.findall(r"[a-z0-9']+", query.lower()) if len(w) > 2 and w != "logo"]
    good = [c for c in out if all(w in c["title"].lower() for w in words[:2])]
    return good or out[:0]


def fetch(query, kind, dest_dir):
    """Download the best free image for `query` into dest_dir; returns {file, credit, kind} or None."""
    try:
        cands = search(query, kind)
    except Exception as e:
        print(f"      photo search failed for {query!r}: {e}", flush=True); return None
    for c in cands[:4]:
        try:
            r = requests.get(c["url"], headers=UA, timeout=60); r.raise_for_status()
            from PIL import Image
            im = Image.open(io.BytesIO(r.content)).convert("RGBA")
            im.thumbnail((900, 900))
            name = hashlib.md5(c["url"].encode()).hexdigest()[:12] + ".png"
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
            im.save(Path(dest_dir) / name)
            credit = f"{c['title']} by {c['artist']} ({c['licence']}, Wikimedia Commons)"
            return {"file": name, "credit": credit, "kind": kind, "w": im.width, "h": im.height}
        except Exception as e:
            print(f"      photo download failed {c['url']}: {e}", flush=True)
    print(f"      no free image found for {query!r}", flush=True)
    return None


if __name__ == "__main__":  # python -m pipeline.render.photos "Toyota Fortuner:product" "Amul:logo" ... -> test report
    import sys
    out = Path(os.environ.get("PHOTO_TEST_DIR") or "photo_test"); res = {}
    for arg in sys.argv[1:]:
        q, _, k = arg.partition(":")
        res[q] = fetch(q, k or "product", out)
        print(q, "->", res[q], flush=True)
    (out / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))

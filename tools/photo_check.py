"""Check what the photo search finds: python tools/photo_check.py "Toyota Fortuner:product" "Amul:logo" ..."""
import sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.render import photos
out = Path("photo_check"); out.mkdir(exist_ok=True)
for arg in sys.argv[1:]:
    q, _, kind = arg.partition(":")
    hit = photos.fetch(q, kind or "product")
    print(f"{q} [{kind}] -> {hit}", flush=True)
    if hit: shutil.copy(photos.PUB / hit["src"], out / (photos.slug(q) + Path(hit["src"]).suffix))

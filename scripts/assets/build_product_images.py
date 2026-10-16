"""Build the web product images served by the React frontend (lean MVP, Option B).

    python scripts/assets/build_product_images.py --library <aayna-website-assets folder>

Reads the verified, byte-identical copies listed in <library>/product-photos/MANIFEST.csv
(never the read-only originals), re-checks every SHA-256, and for each SKU in
scripts/assets/product_image_map.json writes two WebP renditions per photo:

    frontend/public/product-images/<group>/<group>-<NN>-480.webp    (cards, thumbnails)
    frontend/public/product-images/<group>/<group>-<NN>-1200.webp   (product page)

(never upscaled), plus frontend/src/data/productGallery.json - the SKU -> ordered gallery
map the storefront uses for products whose database record has no images yet.
URLs are keyed by photo group, so they stay stable if a SKU is corrected later.
Refuses: excluded files, checksum mismatches, unknown groups/variations.
Deterministic: same inputs -> same file list, order and dimensions.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WIDTHS = (480, 1200)
QUALITY = 80


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", required=True, help="folder that contains product-photos/MANIFEST.csv")
    ap.add_argument("--map", default=os.path.join(REPO, "scripts", "assets", "product_image_map.json"))
    ap.add_argument("--out-public", default=os.path.join(REPO, "frontend", "public", "product-images"))
    ap.add_argument("--out-json", default=os.path.join(REPO, "frontend", "src", "data", "productGallery.json"))
    a = ap.parse_args()

    spec = json.load(open(a.map, encoding="utf-8"))
    rows = list(csv.DictReader(open(os.path.join(a.library, spec["source_manifest"].split("/", 1)[1]), encoding="utf-8")))
    by_key = {(r["group_slug"], int(r["variation"])): r for r in rows}
    excluded = set(spec["excluded_files"])
    if os.path.isdir(a.out_public):
        shutil.rmtree(a.out_public)          # generated output only; rebuilt from the verified copies
    gallery, total = {}, 0
    for p in spec["products"]:
        images = []
        for v in p["variations"]:
            r = by_key.get((p["group"], v))
            if not r:
                sys.exit(f"{p['sku']}: no photo {p['group']} #{v} in the manifest")
            if r["original_filename"] in excluded:
                sys.exit(f"{p['sku']}: {r['original_filename']} is excluded")
            src = os.path.join(a.library, r["asset_path"])
            if hashlib.sha256(open(src, "rb").read()).hexdigest() != r["sha256"]:
                sys.exit(f"checksum mismatch for {r['asset_path']} - copy is not the verified original")
            im = Image.open(src)
            im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
            out_dir = os.path.join(a.out_public, p["group"])
            os.makedirs(out_dir, exist_ok=True)
            variants = []
            for w in WIDTHS:
                tw = min(w, im.width)
                th = round(im.height * tw / im.width)
                name = f"{p['group']}-{v:02d}-{w}.webp"
                im.resize((tw, th), Image.LANCZOS).save(os.path.join(out_dir, name), "WEBP", quality=QUALITY, method=6)
                total += os.path.getsize(os.path.join(out_dir, name))
                variants.append({"url": f"/product-images/{p['group']}/{name}", "w": tw, "h": th})
            images.append({"variation": v, "src": variants[-1]["url"],
                           "srcSet": ", ".join(f"{x['url']} {x['w']}w" for x in variants),
                           "width": variants[-1]["w"], "height": variants[-1]["h"], "source_sha256": r["sha256"]})
        gallery[p["sku"]] = {"group": p["group"], "images": images}
    os.makedirs(os.path.dirname(a.out_json), exist_ok=True)
    with open(a.out_json, "w", encoding="utf-8") as fh:
        json.dump({"_generated_by": "scripts/assets/build_product_images.py", "products": gallery}, fh, indent=1, sort_keys=True)
        fh.write("\n")
    n = sum(len(g["images"]) for g in gallery.values())
    print(f"{len(gallery)} SKUs, {n} photos, {n * len(WIDTHS)} WebP files, {total / 1048576:.2f} MB -> {a.out_public}")


if __name__ == "__main__":
    main()

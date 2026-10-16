"""READ-ONLY inventory of every image reference in an AAYNA database.

Purpose: size an image-storage migration before choosing a provider. Prints, per
collection and field, how many image URLs point at which host and which kind of
storage, so nothing is guessed. It never writes, updates or deletes anything
(only find()/count on the collections below).

Usage:
    MONGO_URL=... DB_NAME=aayna_dev python scripts/storage/audit_image_refs.py [--json out.json]

Safe to point at development or production data (read-only), but use a
read-only database user where possible.

Kinds reported:
  app_files      .../api/files/aayna/uploads/...  (uploaded via Admin or the
                  inventory importer; bytes live in Emergent object storage and
                  are proxied by this backend; host is baked into the URL)
  emergent_cdn   static.prod-images.emergentagent.com/...  (Emergent-hosted
                  scaffold/demo images; not under AAYNA's control)
  relative       /api/files/... with no host
  other          any other absolute URL (e.g. a CDN the founder added by hand)
  empty          blank image_url
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

import pymongo


def kind(url: str) -> str:
    if not url:
        return "empty"
    u = urlparse(url)
    if "/api/files/" in u.path:
        return "relative" if not u.netloc else "app_files"
    if u.netloc.endswith("prod-images.emergentagent.com"):
        return "emergent_cdn"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="also write the full report to this file")
    a = ap.parse_args()
    db = pymongo.MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)[os.environ["DB_NAME"]]

    report = {"database": os.environ["DB_NAME"], "refs": defaultdict(Counter), "hosts": defaultdict(Counter),
              "products_without_image": 0, "products_by_status": Counter(), "files_records": 0, "files_deleted": 0}

    def add(where, url):
        k = kind(url or "")
        report["refs"][where][k] += 1
        if url:
            report["hosts"][k][urlparse(url).netloc or "(relative)"] += 1

    for p in db.products.find({}, {"images": 1, "status": 1}):
        report["products_by_status"][p.get("status", "?")] += 1
        imgs = p.get("images") or []
        if not imgs:
            report["products_without_image"] += 1
        for im in imgs:
            add("products.images[].image_url", (im or {}).get("image_url"))
    for c in db.categories.find({}, {"image_url": 1}):
        if c.get("image_url"):
            add("categories.image_url", c["image_url"])
    for s in db.website_settings.find({"setting_key": {"$regex": "image|logo|og_", "$options": "i"}}, {"setting_value": 1, "setting_key": 1}):
        if isinstance(s.get("setting_value"), str) and s["setting_value"].startswith(("http", "/")):
            add(f"website_settings.{s['setting_key']}", s["setting_value"])
    for o in db.orders.find({}, {"items.image": 1}):
        for it in o.get("items") or []:
            if it.get("image"):
                add("orders.items[].image (snapshot)", it["image"])
    report["files_records"] = db.files.count_documents({})
    report["files_deleted"] = db.files.count_documents({"is_deleted": True})

    print(f"Image references in database '{report['database']}' (read-only scan)\n")
    for where, cnt in report["refs"].items():
        print(f"  {where}: " + ", ".join(f"{k}={v}" for k, v in sorted(cnt.items())))
    print("\n  hosts:")
    for k, hosts in report["hosts"].items():
        for h, n in hosts.most_common():
            print(f"    {k:13s} {h}  x{n}")
    print(f"\n  products by status: {dict(report['products_by_status'])}")
    print(f"  products without any image: {report['products_without_image']}")
    print(f"  db.files upload records: {report['files_records']} (deleted: {report['files_deleted']})")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(report, f, indent=2, default=dict)
        print(f"\n  full report: {a.json}")


if __name__ == "__main__":
    sys.exit(main())

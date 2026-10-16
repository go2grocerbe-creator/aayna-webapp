"""READ-ONLY inventory of every image reference in an AAYNA database.

Purpose: size an image-storage migration before choosing a provider. Prints, per
collection and field, how many image URLs point at which host and which kind of
storage, so nothing is guessed. It never writes, updates or deletes anything
(only find()/count on the collections below).

Usage:
    MONGO_URL=... DB_NAME=aayna_dev python scripts/storage/audit_image_refs.py [--json out.json]
        [--manifest manifest.csv] [--check-reachable]

--manifest writes one row per image reference (the export/migration manifest):
  collection, record id, sku/slug, field, position, url, kind, host,
  storage_path, upload_record (ok / missing / deleted / n/a), shared_by (how
  many references use the same URL), export_from (where the original bytes
  must be fetched), proposed_url (host-independent form; NOT applied), and
  reachable (only with --check-reachable: an HTTP HEAD/GET probe, read-only).
It also lists db.files uploads that no record references (orphans).

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
import csv
import json
import os
import sys
import urllib.request
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
    ap.add_argument("--manifest", help="write the per-reference export/migration manifest (CSV)")
    ap.add_argument("--check-reachable", action="store_true", help="probe each distinct URL (read-only HTTP)")
    a = ap.parse_args()
    db = pymongo.MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)[os.environ["DB_NAME"]]

    report = {"database": os.environ["DB_NAME"], "refs": defaultdict(Counter), "hosts": defaultdict(Counter),
              "products_without_image": 0, "products_by_status": Counter(), "files_records": 0, "files_deleted": 0}

    rows = []

    def add(where, url, rec_id="", ident="", pos=""):
        k = kind(url or "")
        report["refs"][where][k] += 1
        if url:
            report["hosts"][k][urlparse(url).netloc or "(relative)"] += 1
        rows.append({"collection_field": where, "record_id": rec_id, "sku_or_slug": ident, "position": pos,
                     "url": url or "", "kind": k, "host": urlparse(url or "").netloc})

    for p in db.products.find({}, {"images": 1, "status": 1, "id": 1, "sku": 1}):
        report["products_by_status"][p.get("status", "?")] += 1
        imgs = p.get("images") or []
        if not imgs:
            report["products_without_image"] += 1
        for i, im in enumerate(imgs):
            add("products.images[].image_url", (im or {}).get("image_url"), p.get("id"), p.get("sku"), i)
    for c in db.categories.find({}, {"image_url": 1, "id": 1, "slug": 1}):
        if c.get("image_url"):
            add("categories.image_url", c["image_url"], c.get("id"), c.get("slug"))
    for s in db.website_settings.find({"setting_key": {"$regex": "image|logo|og_", "$options": "i"}}, {"setting_value": 1, "setting_key": 1}):
        if isinstance(s.get("setting_value"), str) and s["setting_value"].startswith(("http", "/")):
            add(f"website_settings.{s['setting_key']}", s["setting_value"], s["setting_key"])
    for o in db.orders.find({}, {"items.image": 1, "order_number": 1}):
        for i, it in enumerate(o.get("items") or []):
            if it.get("image"):
                add("orders.items[].image (snapshot)", it["image"], o.get("order_number"), "", i)
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
    if a.manifest:
        files = {d.get("storage_path"): d for d in db.files.find({}, {"_id": 0})}
        shared = Counter(r["url"] for r in rows if r["url"])
        reach = {}
        if a.check_reachable:
            for url in sorted({r["url"] for r in rows if r["url"].startswith("http")}):
                try:
                    req = urllib.request.Request(url, method="HEAD")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        reach[url] = f"yes ({resp.status})"
                except Exception as exc:  # noqa: BLE001
                    reach[url] = f"no ({type(exc).__name__}: {str(exc)[:60]})"
        referenced = set()
        for r in rows:
            path = urlparse(r["url"]).path
            sp = path.split("/api/files/", 1)[1] if "/api/files/" in path else ""
            r["storage_path"] = sp
            if sp:
                referenced.add(sp)
                rec = files.get(sp)
                r["upload_record"] = "missing" if not rec else ("deleted" if rec.get("is_deleted") else "ok")
            else:
                r["upload_record"] = "n/a"
            r["shared_by"] = shared.get(r["url"], 0) if r["url"] else 0
            r["export_from"] = {
                "app_files": "Emergent object storage (via storage.get_object / GET /api/files/<storage_path>)",
                "relative": "Emergent object storage (via storage.get_object)",
                "emergent_cdn": "Emergent CDN URL (download over HTTP while reachable)",
                "other": "the external host in the URL (not Emergent-managed)",
                "empty": "nothing to export (blank URL)",
            }[r["kind"]]
            r["proposed_url"] = f"/api/files/{sp}" if sp else ("(re-host, then /api/files/<new path>)" if r["kind"] == "emergent_cdn" else "")
            r["reachable"] = reach.get(r["url"], "not checked" if r["url"] else "")
        orphans = [{"collection_field": "files (unreferenced upload)", "record_id": d.get("id", ""), "sku_or_slug": "",
                    "position": "", "url": "", "kind": "app_files", "host": "", "storage_path": sp,
                    "upload_record": "deleted" if d.get("is_deleted") else "ok", "shared_by": 0,
                    "export_from": "Emergent object storage (orphan: export for safety, review before re-use)",
                    "proposed_url": "", "reachable": ""} for sp, d in files.items() if sp not in referenced]
        cols = ["collection_field", "record_id", "sku_or_slug", "position", "url", "kind", "host", "storage_path",
                "upload_record", "shared_by", "export_from", "proposed_url", "reachable"]
        with open(a.manifest, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows + orphans:
                w.writerow({c: r.get(c, "") for c in cols})
        need = sorted({r["storage_path"] for r in rows if r["storage_path"]} | {o["storage_path"] for o in orphans})
        cdn = sorted({r["url"] for r in rows if r["kind"] == "emergent_cdn"})
        print(f"\n  manifest: {a.manifest}  ({len(rows)} references, {len(orphans)} unreferenced uploads)")
        print(f"  originals to retrieve from Emergent object storage: {len(need)}")
        print(f"  distinct Emergent-CDN images to download: {len(cdn)}")
        print(f"  references whose upload record is missing/deleted: "
              f"{sum(1 for r in rows if r['upload_record'] in ('missing', 'deleted'))}")
        print(f"  URLs used by more than one reference: {sum(1 for u, n in shared.items() if n > 1)}")
        if a.check_reachable:
            print(f"  unreachable URLs: {sum(1 for v in reach.values() if v.startswith('no'))} of {len(reach)}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(report, f, indent=2, default=dict)
        print(f"\n  full report: {a.json}")


if __name__ == "__main__":
    sys.exit(main())

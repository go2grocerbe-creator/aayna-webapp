#!/usr/bin/env python3
"""
Guarded first import of the 10 genuine AAYNA products into the PRODUCTION
catalogue database, using the existing importer (scripts/import_inventory.py).

    python scripts/prod_catalogue_import.py preflight --env-file .env.prod-import --xlsx <workbook> --photos <folder>
    python scripts/prod_catalogue_import.py import    --env-file ... --xlsx ... --photos ... --confirm aayna_prod
    python scripts/prod_catalogue_import.py verify    --env-file ... --xlsx ... --photos ...

The env file is the ONLY place the connection string lives. It is outside the
repository, never printed, never committed. It must contain:

    MONGO_URL=<Atlas connection string for the aayna_prod_app user>
    DB_NAME=aayna_prod
    AAYNA_PRICE_EXTRA_BDT=<confidential>
    AAYNA_PRICE_MULTIPLIER=<confidential>

preflight and verify are READ-ONLY. import writes only through
import_inventory.import_products(static_images=True): new products as DRAFT, no
image uploads, plus the importer's own stock_in inventory log per new product.
Nothing else is created or changed: no indexes, users, categories or settings.
Output never contains the connection string, purchase costs or the rule values.
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

TARGET_DB = "aayna_prod"
APP_USER = "aayna_prod_app"
REQUIRED_CATEGORIES = {"earrings", "necklaces", "rings", "bracelets"}
EXPECTED_UNITS = 46
# Founder-confirmed PUBLIC selling prices (docs/audits/PRODUCT_PRICING_UPDATE.md).
CONFIRMED_PRICES = {
    "AYN-NKL-LUN-GLD": 1350, "AYN-NKL-AUR-GLD": 1350, "AYN-CUF-CRS-GLD": 1050, "AYN-CUF-STN-GLD": 990,
    "AYN-EAR-CHK-GLD": 870, "AYN-EAR-FLR-GLD": 1410, "AYN-EAR-FLR-SLV": 1410, "AYN-BRC-FLR-GLD": 1310,
    "AYN-BRC-FLR-SLV": 1310, "AYN-RNG-CLS-GLD": 1290,
}
PUBLIC_SECRETS = ("cost_price", "pricing", "price_history", "previous_selling_price", "internal_notes",
                  "source", "price_is_temporary", "supplier", "unrounded_price", "adjusted_cost", "multiplier")
REQUIRED_KEYS = ("MONGO_URL", "DB_NAME", "AAYNA_PRICE_EXTRA_BDT", "AAYNA_PRICE_MULTIPLIER")


class Stop(Exception):
    """A check failed; nothing (further) is written."""


def out(msg=""):
    print(msg, flush=True)


# --- environment ------------------------------------------------------------------
def load_env_file(path):
    """Parse KEY=VALUE lines. Values are never printed."""
    p = Path(path)
    if not p.is_file():
        raise Stop(f"env file not found: {p.name} (create it from the template; never commit it)")
    vals = {}
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in REQUIRED_KEYS if not vals.get(k)]
    if missing:
        raise Stop(f"env file is missing: {', '.join(missing)}")
    return vals


def check_target(vals, confirm=None):
    if vals["DB_NAME"] != TARGET_DB:
        raise Stop(f"DB_NAME must be exactly '{TARGET_DB}'")
    if confirm is not None and confirm != TARGET_DB:
        raise Stop(f"--confirm must be exactly '{TARGET_DB}'")
    u = urlsplit(vals["MONGO_URL"])
    if u.scheme not in ("mongodb", "mongodb+srv"):
        raise Stop("MONGO_URL is not a MongoDB connection string")
    user = unquote(u.username or "")
    if user != APP_USER:
        raise Stop(f"MONGO_URL must use the application user '{APP_USER}' (not an admin user)")
    return u.hostname or "?"


def apply_env(vals):
    for k in REQUIRED_KEYS:
        os.environ[k] = vals[k]
    # CLI only - never serves requests. Keep the app out of production boot checks.
    os.environ.setdefault("APP_ENV", "development")


def redact(text, vals):
    t = str(text)
    for k in ("MONGO_URL",):
        if vals.get(k):
            t = t.replace(vals[k], "<MONGO_URL>")
    return re.sub(r"(mongodb(\+srv)?://)[^@/\s]+@", r"\1<credentials>@", t)


# --- manifest -----------------------------------------------------------------------
def build_checked_manifest(xlsx, photos):
    import import_inventory as imp
    import pricing
    rule = pricing.rule_from_env()
    man = imp.build_manifest(xlsx, photos, price_rule=rule)
    prods = man["products"]
    skus = [p.get("sku") for p in prods]
    problems = []
    if sorted(skus) != sorted(CONFIRMED_PRICES):
        problems.append(f"SKU set differs from the 10 confirmed SKUs: {sorted(set(skus) ^ set(CONFIRMED_PRICES))}")
    if len(skus) != len(set(skus)):
        problems.append("duplicate SKU in workbook")
    if any(s.startswith("REJ-") for s in skus):
        problems.append("a rejected row is in the import set")
    units = sum(p.get("stock_quantity") or 0 for p in prods)
    if units != EXPECTED_UNITS:
        problems.append(f"sellable units {units} != {EXPECTED_UNITS}")
    gallery = imp.static_gallery_skus()
    for p in prods:
        sku = p.get("sku")
        if p.get("selling_price") != CONFIRMED_PRICES.get(sku):
            problems.append(f"{sku}: computed price differs from the confirmed price")
        blockers = [b for b in p["blockers"] if b != "No matched images"]
        if blockers:
            problems.append(f"{sku}: {blockers}")
        if sku not in gallery:
            problems.append(f"{sku}: no static gallery entry")
    return man, units, problems


def print_manifest(man, units):
    s = man["summary"]
    out(f"Workbook: sheet '{s['sheet']}', {s['products']} active rows (rejected block excluded by the importer)")
    out(f"Sellable units: {units}")
    out(f"{'SKU':<17} {'Product':<40} {'Category':<10} {'Colour':<7} {'Qty':>3}  Price   Photos")
    for p in man["products"]:
        out(f"{p['sku']:<17} {p['display_name']:<40} {p['category_slug']:<10} {str(p.get('color')):<7} "
            f"{p['stock_quantity']:>3}  ৳{p['selling_price']:<6} {p['image_match']}")


# --- read-only database inspection (sync pymongo) -------------------------------------
def sync_db(vals):
    from pymongo import MongoClient
    client = MongoClient(vals["MONGO_URL"], serverSelectionTimeoutMS=15000, appname="aayna-catalogue-import")
    return client, client[vals["DB_NAME"]]


def inspect_db(db):
    info = {"collections": {}, "indexes": {}}
    for name in sorted(db.list_collection_names()):
        info["collections"][name] = db[name].estimated_document_count()
        info["indexes"][name] = [(ix["name"], dict(ix["key"]), bool(ix.get("unique"))) for ix in db[name].list_indexes()]
    info["categories"] = list(db.categories.find({}, {"_id": 0, "slug": 1, "name": 1, "status": 1}))
    info["products"] = list(db.products.find({}, {"_id": 0, "sku": 1, "status": 1, "source.type": 1}))
    return info


def print_db(info):
    out("Collections (document counts):")
    for n, c in info["collections"].items():
        out(f"  {n:<22} {c}")
    out("Indexes:")
    for n, ixs in info["indexes"].items():
        out(f"  {n}: " + "; ".join(f"{name} {key}{' UNIQUE' if u else ''}" for name, key, u in ixs))
    out("Categories: " + ", ".join(f"{c.get('slug')} ({c.get('status')})" for c in info["categories"]))


def preflight_db(info, allow_existing_import=False):
    problems = []
    slugs = {c.get("slug") for c in info["categories"]}
    if not REQUIRED_CATEGORIES <= slugs:
        problems.append(f"missing categories: {sorted(REQUIRED_CATEGORIES - slugs)}")
    inactive = [c.get("slug") for c in info["categories"] if c.get("slug") in REQUIRED_CATEGORIES
                and c.get("status") not in (None, "active")]
    if inactive:
        problems.append(f"categories not active: {inactive}")
    prods = info["products"]
    if prods:
        foreign = [p.get("sku") for p in prods if p.get("sku") not in CONFIRMED_PRICES
                   or (p.get("source") or {}).get("type") != "inventory_xlsx"]
        if foreign:
            problems.append(f"database already holds other products: {foreign[:5]}")
        elif not allow_existing_import:
            problems.append(f"{len(prods)} of these products already exist (import already ran)")
        dup = [s for s, n in Counter(p.get("sku") for p in prods).items() if n > 1]
        if dup:
            problems.append(f"duplicate SKUs already in database: {dup}")
    return problems


# --- verification -------------------------------------------------------------------
def verify_records(db, man):
    """Read back every product directly from the database. Returns (lines, problems)."""
    import import_inventory as imp
    gallery = json.loads(Path(imp.STATIC_GALLERY).read_text(encoding="utf-8"))["products"]
    by_sku = {p["sku"]: p for p in man["products"]}
    lines, problems = [], []
    total = db.products.count_documents({})
    if total != len(CONFIRMED_PRICES):
        problems.append(f"products in database: {total} (expected {len(CONFIRMED_PRICES)})")
    cats = {c["slug"]: c for c in db.categories.find({}, {"_id": 0})}
    for sku, price in CONFIRMED_PRICES.items():
        docs = list(db.products.find({"sku": sku}, {"_id": 0}))
        if len(docs) != 1:
            problems.append(f"{sku}: {len(docs)} records (expected exactly 1)")
            continue
        d, m = docs[0], by_sku[sku]
        g = gallery.get(sku, {})
        checks = {
            "price": d.get("selling_price") == price and d.get("discount_price") in (None, 0),
            "stock": d.get("stock_quantity") == m["stock_quantity"],
            "category": d.get("category_slug") == m["category_slug"]
                        and d.get("category_name") == cats.get(m["category_slug"], {}).get("name"),
            "draft": d.get("status") == "draft",
            "source": (d.get("source") or {}).get("type") == "inventory_xlsx"
                      and (d.get("source") or {}).get("row") == m["source_row"],
            "cost_kept": d.get("cost_price") == float(m.get("cost_price") or 0),
            "pricing_meta": (d.get("pricing") or {}).get("selling_price") == price,
            "no_db_images": d.get("images") == [],
            "static_gallery": bool(g.get("images")) and g.get("group") is not None,
            "colour_size": d.get("color") == (m.get("color") or "") and d.get("size") == (m.get("size") or ""),
            "slug": bool(d.get("slug")) and db.products.count_documents({"slug": d.get("slug")}) == 1,
            "stock_log": db.inventory_logs.count_documents({"product_id": d.get("id"), "change_type": "stock_in"}) == 1,
        }
        bad = [k for k, ok in checks.items() if not ok]
        if bad:
            problems.append(f"{sku}: failed {bad}")
        lines.append(f"{sku:<17} ৳{d.get('selling_price'):<6} qty {d.get('stock_quantity'):>2}  {d.get('category_slug'):<10} "
                     f"{d.get('status'):<6} source row {(d.get('source') or {}).get('row')}  "
                     f"gallery {g.get('group')} ({len(g.get('images', []))} photos)  "
                     f"{'OK' if not bad else 'FAIL ' + ','.join(bad)}")
    return lines, problems


def verify_public(db):
    """Drafts are not public; the public projection never carries internal fields."""
    import server
    from fastapi.testclient import TestClient
    # The app's startup handlers seed data, the admin user and indexes. They must
    # NEVER run against production from this script: remove them before the
    # client opens (one event loop for all requests, nothing else).
    server.app.router.on_startup.clear()
    server.app.router.on_shutdown.clear()
    problems = []
    public_count = db.products.count_documents({"status": {"$in": list(server.PUBLIC_PRODUCT_STATUSES)}})
    if public_count:
        problems.append(f"{public_count} products are publicly visible")
    with TestClient(server.app) as c:
        return _public_checks(db, server, c, public_count, problems)


def _public_checks(db, server, c, public_count, problems):
    r = c.get("/api/products", params={"limit": 100})
    listed = [p.get("sku") for p in r.json()] if r.status_code == 200 else None
    if listed is None or any(s in CONFIRMED_PRICES for s in listed):
        problems.append(f"public product list exposes drafts or failed: HTTP {r.status_code}")
    leaked = [s for s in PUBLIC_SECRETS if f'"{s}"' in r.text]
    for d in db.products.find({}, {"_id": 0, "slug": 1, "id": 1}):
        rr = c.get(f"/api/products/{d['slug']}")
        if rr.status_code != 404:
            problems.append(f"draft {d['slug']} reachable publicly: HTTP {rr.status_code}")
        leaked += [s for s in PUBLIC_SECRETS if f'"{s}"' in rr.text]
        v = c.post("/api/cart/validate", json={"items": [{"product_id": d["id"], "quantity": 1}]})
        if v.status_code != 200 or v.json()["items"][0].get("available") is not False:
            problems.append(f"draft {d['slug']} purchasable via cart")
    # the projection the public API uses, applied to the real records: no internal field survives
    for d in db.products.find({}, server.PUBLIC_PRODUCT_FIELDS):
        leaked += [k for k in d if k in PUBLIC_SECRETS or k not in server.PUBLIC_PRODUCT_FIELDS]
    if leaked:
        problems.append(f"internal fields exposed: {sorted(set(leaked))}")
    return [f"public list: HTTP {r.status_code}, {len(listed or [])} products, none of the drafts",
            f"publicly visible products in DB: {public_count}",
            "every draft: product page 404, not purchasable; public projection carries no internal field"], problems


def verify_idempotent(db, man):
    """Re-run of the importer would create nothing: every SKU exists exactly once."""
    would_create = [p["sku"] for p in man["products"] if db.products.count_documents({"sku": p["sku"]}) == 0]
    dups = [p["sku"] for p in man["products"] if db.products.count_documents({"sku": p["sku"]}) > 1]
    problems = []
    if would_create:
        problems.append(f"re-run would create: {would_create}")
    if dups:
        problems.append(f"duplicated: {dups}")
    return [f"re-run plan: 0 creates, {len(man['products'])} existing (updated in place, admin-owned fields untouched)"], problems


# --- commands -------------------------------------------------------------------------
def cmd_preflight(a, vals, import_mode=False):
    host = check_target(vals, a.confirm if import_mode else None)
    apply_env(vals)
    out(f"Target: {host} / {vals['DB_NAME']} as {APP_USER}")
    man, units, problems = build_checked_manifest(a.xlsx, a.photos)
    print_manifest(man, units)
    client, db = sync_db(vals)
    try:
        db.command("ping")
        out(f"Connected. MongoDB {client.server_info().get('version')}")
        info = inspect_db(db)
        print_db(info)
        problems += preflight_db(info)
    finally:
        client.close()
    if problems:
        raise Stop("PRE-FLIGHT FAILED:\n  - " + "\n  - ".join(problems))
    out("\nPRE-FLIGHT PASSED: 10 eligible SKUs, 46 units, confirmed prices, categories present, 0 existing products.")
    return man


def cmd_import(a, vals):
    man = cmd_preflight(a, vals, import_mode=True)
    import import_inventory as imp
    import storage
    import db as dbmod
    out("\nImporting as DRAFT with --static-images (no uploads) ...")
    rep = asyncio.run(imp.import_products(man, a.photos, "", db=dbmod.db, storage=storage,
                                          static_images=True, gallery_skus=imp.static_gallery_skus()))
    out(f"Importer report: created {len(rep['created'])}, updated {len(rep['updated'])}, "
        f"skipped {len(rep['skipped'])}, failed {len(rep['failed'])}, images uploaded {rep['images_uploaded']}")
    for f in rep["failed"]:
        out(f"  FAILED {f['sku']}: {redact(f['error'], vals)}")
    for s in rep["skipped"]:
        out(f"  SKIPPED {s['sku']}: {s['blockers']}")
    out("\nReading back from the database (separate process) ...")
    r = subprocess.run([sys.executable, __file__, "verify", "--env-file", a.env_file, "--xlsx", a.xlsx,
                        "--photos", a.photos])
    if rep["failed"] or rep["skipped"] or r.returncode:
        raise Stop("IMPORT NOT VERIFIED - see above")


def cmd_verify(a, vals):
    check_target(vals)
    apply_env(vals)
    man, _, problems = build_checked_manifest(a.xlsx, a.photos)
    client, db = sync_db(vals)
    try:
        lines, p1 = verify_records(db, man)
        out("Products read back from aayna_prod:")
        for line in lines:
            out("  " + line)
        plines, p2 = verify_public(db)
        ilines, p3 = verify_idempotent(db, man)
        for line in plines + ilines:
            out("  " + line)
        info = inspect_db(db)
        out("Collections after import: " + ", ".join(f"{n}={c}" for n, c in info["collections"].items()))
        problems += p1 + p2 + p3
    finally:
        client.close()
    if problems:
        raise Stop("VERIFY FAILED:\n  - " + "\n  - ".join(problems))
    out("\nVERIFY PASSED: 10 drafts, confirmed prices, stock, categories, source, static photos; "
        "nothing public; no internal fields exposed; no duplicates.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["preflight", "import", "verify"])
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--photos", required=True)
    ap.add_argument("--confirm", help=f"import only: must be exactly '{TARGET_DB}'")
    a = ap.parse_args(argv)
    vals = {}
    try:
        vals = load_env_file(a.env_file)
        {"preflight": cmd_preflight, "import": cmd_import, "verify": cmd_verify}[a.cmd](a, vals)
    except Stop as exc:
        out(f"\nSTOPPED: {redact(exc, vals)}")
        return 2
    except Exception as exc:  # noqa: BLE001 - never echo a connection string
        out(f"\nERROR ({type(exc).__name__}): {redact(exc, vals)}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
TEST PREVIEW ONLY: show the genuine AAYNA catalogue on the isolated aayna_preview
deployment so the founder can review the real products and photos before launch.

    PREVIEW_CATALOGUE=real   (branch-scoped Vercel variable, preview only)

Refused unless DB_NAME == "aayna_preview" AND PUBLIC_SITE_URL is a *.vercel.app
host - so it can never run against aayna_prod or the real domain.

Source: the customer-facing fields of the 10 products in aayna_prod, checked
field by field against a read-only read of aayna_prod on 2026-10-19 (names, slugs,
categories, colours, sizes, selling prices, stock). No purchase cost, supplier,
source-row or internal field is copied, and the app never reads aayna_prod here.
Founder-authorised on 2026-10-19 for the protected preview only. Photos come from the reviewed static gallery by exact SKU
(frontend/src/data/productGallery.json), exactly as on the live site.

What it does (idempotent, reversible):
- upserts the 10 products by SKU: identity fields are refreshed each start, stock
  is set only when the product is first created (test orders then reduce it);
- hides every other (demo) product by setting status "draft" and marking it
  preview_hidden_demo=True. PREVIEW_CATALOGUE=demo restores those products.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("aayna")

PREVIEW_DB = "aayna_preview"

# Customer-facing fields only. Prices = founder-confirmed public selling prices.
REAL_CATALOGUE = [
    {"sku": "AYN-NKL-LUN-GLD", "product_name": "Aayna Luna Statement Locket", "slug": "aayna-luna-statement-locket",
     "category_slug": "necklaces", "color": "Golden", "size": '1" diameter', "selling_price": 1350, "stock_quantity": 1},
    {"sku": "AYN-NKL-AUR-GLD", "product_name": "Aayna Aura Statement Locket", "slug": "aayna-aura-statement-locket",
     "category_slug": "necklaces", "color": "Golden", "size": '1" diameter', "selling_price": 1350, "stock_quantity": 1},
    {"sku": "AYN-CUF-CRS-GLD", "product_name": "Aayna Golden Crossline Cuff", "slug": "aayna-golden-crossline-cuff",
     "category_slug": "bracelets", "color": "Golden", "size": '2.5" diameter', "selling_price": 1050, "stock_quantity": 2},
    {"sku": "AYN-CUF-STN-GLD", "product_name": "Aayna Crystal Stone Cuff", "slug": "aayna-crystal-stone-cuff",
     "category_slug": "bracelets", "color": "Golden", "size": '2.5" diameter', "selling_price": 990, "stock_quantity": 12},
    {"sku": "AYN-EAR-CHK-GLD", "product_name": "Aayna Bold Chunky Earrings", "slug": "aayna-bold-chunky-earrings",
     "category_slug": "earrings", "color": "Golden", "size": '1" per earring', "selling_price": 870, "stock_quantity": 6},
    {"sku": "AYN-EAR-FLR-GLD", "product_name": "Aayna Floral Bloom Earrings - Golden", "slug": "aayna-floral-bloom-earrings-golden",
     "category_slug": "earrings", "color": "Golden", "size": '1" per earring', "selling_price": 1410, "stock_quantity": 5},
    {"sku": "AYN-EAR-FLR-SLV", "product_name": "Aayna Floral Bloom Earrings - Silver", "slug": "aayna-floral-bloom-earrings-silver",
     "category_slug": "earrings", "color": "Silver", "size": '1" per earring', "selling_price": 1410, "stock_quantity": 5},
    {"sku": "AYN-BRC-FLR-GLD", "product_name": "Aayna Floral Charm Bracelet - Golden", "slug": "aayna-floral-charm-bracelet-golden",
     "category_slug": "bracelets", "color": "Golden", "size": '2.5" diameter', "selling_price": 1310, "stock_quantity": 5},
    {"sku": "AYN-BRC-FLR-SLV", "product_name": "Aayna Floral Charm Bracelet - Silver", "slug": "aayna-floral-charm-bracelet-silver",
     "category_slug": "bracelets", "color": "Silver", "size": '2.5" diameter', "selling_price": 1310, "stock_quantity": 4},
    {"sku": "AYN-RNG-CLS-GLD", "product_name": "Aayna Classic Statement Ring", "slug": "aayna-classic-statement-ring",
     "category_slug": "rings", "color": "Golden", "size": '0.7" diameter', "selling_price": 1290, "stock_quantity": 5},
]
REAL_SKUS = {p["sku"] for p in REAL_CATALOGUE}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _allowed() -> bool:
    db_name = (os.environ.get("DB_NAME") or "").strip()
    site = (os.environ.get("PUBLIC_SITE_URL") or "").strip().lower()
    host = site.split("://", 1)[-1].split("/", 1)[0]
    return db_name == PREVIEW_DB and host.endswith(".vercel.app")


async def apply_preview_catalogue(db) -> dict:
    mode = (os.environ.get("PREVIEW_CATALOGUE") or "").strip().lower()
    if mode not in ("real", "demo"):
        return {"mode": "off"}
    if not _allowed():
        logger.warning("PREVIEW_CATALOGUE refused: only allowed on %s with a *.vercel.app site", PREVIEW_DB)
        return {"refused": True}
    if mode == "demo":
        res = await db.products.update_many({"preview_hidden_demo": True},
                                            {"$set": {"status": "active", "updated_at": _now()}, "$unset": {"preview_hidden_demo": ""}})
        await db.products.update_many({"sku": {"$in": list(REAL_SKUS)}}, {"$set": {"status": "draft", "updated_at": _now()}})
        logger.warning("PREVIEW_CATALOGUE=demo: %d demo products restored", res.modified_count)
        return {"mode": "demo", "restored": res.modified_count}

    cats = {c["slug"]: c for c in await db.categories.find({}, {"_id": 0, "slug": 1, "name": 1}).to_list(100)}
    created = updated = 0
    for p in REAL_CATALOGUE:
        cat = cats.get(p["category_slug"])
        if not cat:
            logger.warning("PREVIEW_CATALOGUE: category %s missing; %s skipped", p["category_slug"], p["sku"])
            continue
        existing = await db.products.find_one({"sku": p["sku"]}, {"_id": 0, "stock_quantity": 1})
        stock = int(existing["stock_quantity"]) if existing else p["stock_quantity"]
        fields = {
            "product_name": p["product_name"], "slug": p["slug"], "category_slug": cat["slug"], "category_name": cat["name"],
            "color": p["color"], "size": p["size"], "selling_price": float(p["selling_price"]), "discount_price": None,
            "images": [], "status": "active" if stock > 0 else "out_of_stock", "preview_snapshot": True, "updated_at": _now(),
        }
        if existing:
            await db.products.update_one({"sku": p["sku"]}, {"$set": fields})
            updated += 1
        else:
            await db.products.insert_one({
                "id": str(uuid.uuid4()), "sku": p["sku"], **fields, "stock_quantity": p["stock_quantity"], "low_stock_alert": 3,
                "short_description": "", "full_description": "", "material": "", "weight": None,
                "is_featured": False, "is_best_seller": False, "is_new_arrival": False, "tags": [],
                "created_at": _now(),
            })
            created += 1
    hidden = await db.products.update_many(
        {"sku": {"$nin": list(REAL_SKUS)}, "status": {"$in": ["active", "out_of_stock"]}},
        {"$set": {"status": "draft", "preview_hidden_demo": True, "updated_at": _now()}})
    logger.warning("PREVIEW_CATALOGUE=real: %d created, %d refreshed, %d demo products hidden", created, updated, hidden.modified_count)
    return {"mode": "real", "created": created, "updated": updated, "hidden": hidden.modified_count}

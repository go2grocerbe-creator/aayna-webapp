"""READ-ONLY data-integrity diagnostics for an AAYNA database.

Safe to run against development or production data: it only reads (find /
aggregate / count / index_information). Use a read-only database user where
possible. Nothing is fixed automatically; every finding needs a human decision.

    MONGO_URL=... DB_NAME=aayna_dev python scripts/diagnostics/data_integrity.py [--json report.json] [--aggregate-only]

--aggregate-only prints counts only (no SKUs, order numbers or values) - use it for
real data. Phone numbers are never printed in any mode (shown as a short hash).

Exit code: 2 if any BLOCKER finding, 1 if only REVIEW findings, 0 if clean.

Checks
  BLOCKER  duplicate product id / sku / slug        (slug: wrong product page; sku: import updates the wrong row)
  BLOCKER  duplicate order id / order_number        (order lookup, admin edits and tracking hit the wrong order)
  BLOCKER  duplicate orders.client_request_id       (double-submitted orders that were created twice)
  BLOCKER  order-number counter behind existing numbers (the next checkout would reuse a number)
  BLOCKER  negative or non-integer stock_quantity
  BLOCKER  invalid product status (not active/draft/inactive/out_of_stock)
  BLOCKER  public product with selling_price <= 0 or missing, or discount >= price
  REVIEW   drafts possibly published by the pre-Phase-4 stock bug (B-01)
  REVIEW   duplicate customer phone records (exact, and after normalizing to +880...)
  REVIEW   customer phones not stored in the normalized form checkout looks up
  REVIEW   orders whose customer_id has no customer record
  REVIEW   products without a SKU; public products without an image
  REVIEW   orders referencing products that no longer exist
  REVIEW   order totals that do not add up
  REVIEW   stock that does not match the inventory-log history
  REVIEW   checkout_requests stuck in 'processing' for > 15 minutes
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import hashlib
import re

import pymongo

PHONE_RE = re.compile(r'^(?:\+?880|0)1[3-9]\d{8}$')   # same as backend/server.py


def normalize_phone(phone):
    p = re.sub(r'[\s\-]', '', phone or '')
    if not PHONE_RE.match(p):
        return None
    digits = re.sub(r'\D', '', p)
    if digits.startswith('880'):
        digits = digits[3:]
    if digits.startswith('0'):
        digits = digits[1:]
    return '+880' + digits


def mask(phone):
    return "phone#" + hashlib.sha256(str(phone).encode()).hexdigest()[:8]

STATUSES = {"active", "draft", "inactive", "out_of_stock"}
PUBLIC = {"active", "out_of_stock"}


def dupes(coll, field, match=None):
    pipeline = ([{"$match": match}] if match else []) + [
        {"$group": {"_id": f"${field}", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]
    return [{"value": d["_id"], "count": d["n"]} for d in coll.aggregate(pipeline)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--aggregate-only", action="store_true")
    a = ap.parse_args()
    db = pymongo.MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)[os.environ["DB_NAME"]]
    findings = []

    def add(level, check, items, note=""):
        findings.append({"level": level, "check": check, "count": len(items), "items": items[:50], "note": note})

    products = list(db.products.find({}, {"_id": 0, "images": 0, "full_description": 0, "short_description": 0}))
    orders = list(db.orders.find({}, {"_id": 0, "id": 1, "order_number": 1, "client_request_id": 1, "items": 1,
                                       "subtotal": 1, "delivery_charge": 1, "discount_amount": 1, "total_amount": 1,
                                       "order_status": 1, "created_at": 1}))
    by_id = {p.get("id"): p for p in products}

    # ---- duplicates
    for f in ("id", "sku", "slug"):
        add("BLOCKER", f"duplicate products.{f}", dupes(db.products, f))
    add("BLOCKER", "duplicate orders.id", dupes(db.orders, "id"))
    add("BLOCKER", "duplicate orders.order_number", dupes(db.orders, "order_number"))
    add("BLOCKER", "duplicate orders.client_request_id",
        dupes(db.orders, "client_request_id", {"client_request_id": {"$type": "string"}}))
    add("REVIEW", "duplicate customers.phone", [dict(d, value=mask(d["value"])) for d in dupes(db.customers, "phone")],
        "checkout matches customers by phone; duplicates split one person's history")
    custs = list(db.customers.find({}, {"_id": 0, "id": 1, "phone": 1}))
    norm_groups = defaultdict(int)
    for c in custs:
        n = normalize_phone(c.get("phone"))
        if n:
            norm_groups[n] += 1
    add("REVIEW", "duplicate customers after phone normalization",
        [{"value": mask(k), "count": v} for k, v in norm_groups.items() if v > 1],
        "merge with scripts/diagnostics/merge_duplicate_customers.py before the unique index")
    add("REVIEW", "customer phones not stored in normalized form",
        [{"customer_id": c["id"]} for c in custs if c.get("phone") and normalize_phone(c["phone"])
         and c["phone"] != normalize_phone(c["phone"])],
        "checkout looks up +880...; these records are invisible to it")
    add("REVIEW", "customer phones that are not valid BD mobile numbers",
        [{"customer_id": c["id"]} for c in custs if not normalize_phone(c.get("phone"))])
    cust_ids = {c["id"] for c in custs}
    add("REVIEW", "orders whose customer_id has no customer record",
        [{"order_number": o.get("order_number")} for o in db.orders.find({}, {"_id": 0, "order_number": 1, "customer_id": 1})
         if o.get("customer_id") not in cust_ids])
    add("REVIEW", "products without a SKU", [{"id": p.get("id")} for p in products if not (p.get("sku") or "").strip()])
    imgs = {p["id"]: p.get("images") for p in db.products.find({}, {"_id": 0, "id": 1, "images": 1})}
    add("REVIEW", "public products without an image",
        [{"sku": p.get("sku")} for p in products if p.get("status") in PUBLIC
         and not any((i or {}).get("image_url") for i in (imgs.get(p.get("id")) or []))])

    # ---- order-number counter
    nums = []
    for o in orders:
        try:
            nums.append(int(str(o.get("order_number", "")).split("-")[-1]))
        except ValueError:
            pass
    seq = (db.counters.find_one({"_id": "order_number"}) or {}).get("seq", 0)
    highest = max(nums) if nums else None
    behind = highest is not None and 1000 + seq < highest
    add("BLOCKER", "order-number counter behind highest existing order number",
        [{"counter_next": f"ORD-{1000 + seq + 1}", "highest_existing": f"ORD-{highest}"}] if behind else [])

    # ---- product values
    add("BLOCKER", "negative or non-integer stock_quantity",
        [{"sku": p.get("sku"), "stock_quantity": p.get("stock_quantity")} for p in products
         if not isinstance(p.get("stock_quantity"), int) or isinstance(p.get("stock_quantity"), bool) or p["stock_quantity"] < 0])
    add("BLOCKER", "invalid product status",
        [{"sku": p.get("sku"), "status": p.get("status")} for p in products if p.get("status") not in STATUSES])
    bad_price = []
    for p in products:
        if p.get("status") not in PUBLIC:
            continue
        sp, dp = p.get("selling_price"), p.get("discount_price")
        if not isinstance(sp, (int, float)) or sp <= 0 or (isinstance(dp, (int, float)) and dp != 0 and not 0 < dp < sp):
            bad_price.append({"sku": p.get("sku"), "status": p.get("status"), "selling_price": sp, "discount_price": dp})
    add("BLOCKER", "public product with invalid price", bad_price)

    # ---- drafts possibly published by the old stock bug (B-01)
    sales = defaultdict(int)
    for o in orders:
        for it in o.get("items") or []:
            sales[it.get("product_id")] += 1
    last_zeroing = {}
    for log in db.inventory_logs.find({"change_type": {"$ne": "sale"}, "new_stock": {"$lte": 0}}, {"_id": 0}).sort("created_at", 1):
        last_zeroing[log["product_id"]] = log
    suspects = []
    for p in products:
        imported = (p.get("source") or {}).get("type") == "inventory_xlsx"
        if p.get("status") in PUBLIC and (imported or (p.get("status") == "out_of_stock" and p.get("id") in last_zeroing and not sales[p.get("id")])):
            z = last_zeroing.get(p.get("id"))
            suspects.append({"sku": p.get("sku"), "name": p.get("product_name"), "status": p.get("status"),
                             "imported_as_draft": imported, "price_is_temporary": p.get("price_is_temporary"),
                             "orders": sales[p.get("id")],
                             "zeroed_by_admin_at": z and z.get("created_at"), "zeroing_reason": z and z.get("reason")})
    add("REVIEW", "drafts possibly published by the pre-Phase-4 stock bug", suspects,
        "Status changes are not logged, so this cannot prove how a product became public. Imported products start "
        "as draft; any now public were published either deliberately in Admin or by the bug. Confirm each in Admin.")

    # ---- orders
    add("REVIEW", "orders referencing missing products",
        [{"order_number": o.get("order_number"), "product_id": it.get("product_id")}
         for o in orders for it in (o.get("items") or []) if it.get("product_id") not in by_id])
    bad_tot = []
    for o in orders:
        items = o.get("items") or []
        if not items:
            continue
        line_sum = sum((it.get("unit_price") or 0) * (it.get("quantity") or 0) for it in items)
        exp_total = (o.get("subtotal") or 0) + (o.get("delivery_charge") or 0) - (o.get("discount_amount") or 0)
        if abs(line_sum - (o.get("subtotal") or 0)) > 0.01 or abs(exp_total - (o.get("total_amount") or 0)) > 0.01 \
                or any((it.get("quantity") or 0) <= 0 for it in items):
            bad_tot.append({"order_number": o.get("order_number"), "subtotal": o.get("subtotal"), "items_sum": line_sum,
                            "total_amount": o.get("total_amount")})
    add("REVIEW", "order totals that do not add up", bad_tot)

    # ---- stock vs inventory history (only where a complete history exists)
    hist = defaultdict(list)
    for log in db.inventory_logs.find({}, {"_id": 0, "product_id": 1, "quantity_change": 1, "previous_stock": 1,
                                           "new_stock": 1, "created_at": 1}).sort("created_at", 1):
        hist[log["product_id"]].append(log)
    mism = []
    for pid, logs in hist.items():
        p = by_id.get(pid)
        if not p:
            continue
        if logs[-1].get("new_stock") != p.get("stock_quantity"):
            mism.append({"sku": p.get("sku"), "stock_quantity": p.get("stock_quantity"),
                         "last_logged_new_stock": logs[-1].get("new_stock"), "last_log_at": logs[-1].get("created_at")})
    add("REVIEW", "stock differs from the latest inventory-log entry", mism,
        "Expected after CSV imports (they set stock without a log) or direct database edits.")

    # ---- stuck idempotency claims
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    add("REVIEW", "checkout_requests stuck in 'processing' > 15 min",
        [{"client_request_id": d["_id"], "created_at": d.get("created_at")}
         for d in db.checkout_requests.find({"status": "processing", "created_at": {"$lt": cutoff}})],
        "A crash mid-checkout leaves the key claimed; the customer sees 'already being processed'. Safe to delete after checking no order exists.")

    # ---- report
    print(f"AAYNA data-integrity diagnostics — database '{os.environ['DB_NAME']}' (read-only)")
    by_status = defaultdict(int)
    for p in products:
        by_status[p.get("status", "?")] += 1
    print(f"products={len(products)} orders={len(orders)} customers={db.customers.count_documents({})}")
    print(f"products by status: {dict(sorted(by_status.items()))} | variants: not modelled (one SKU per product)\n")
    for f in findings:
        mark = "ok " if f["count"] == 0 else f["level"]
        print(f"[{mark:7s}] {f['check']}: {f['count']}")
        for it in ([] if a.aggregate_only else f["items"][:10]):
            print(f"            {json.dumps(it, default=str)}")
        if f["count"] and f["note"]:
            print(f"            note: {f['note']}")
    print("\nindexes:")
    for coll in ("products", "orders", "customers", "users", "files", "categories", "inventory_logs", "checkout_requests"):
        info = db[coll].index_information() if coll in db.list_collection_names() else {}
        print(f"  {coll}: " + ", ".join(f"{n}{' (unique)' if i.get('unique') else ''}" for n, i in info.items()))
    if a.json:
        with open(a.json, "w") as fh:
            out = [dict(f, items=[]) for f in findings] if a.aggregate_only else findings
            json.dump({"database": os.environ["DB_NAME"], "findings": out}, fh, indent=2, default=str)
    blockers = sum(f["count"] for f in findings if f["level"] == "BLOCKER")
    reviews = sum(f["count"] for f in findings if f["level"] == "REVIEW")
    print(f"\nBLOCKER findings: {blockers}   REVIEW findings: {reviews}")
    return 2 if blockers else (1 if reviews else 0)


if __name__ == "__main__":
    sys.exit(main())

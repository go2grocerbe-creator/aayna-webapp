"""Index migration plan for AAYNA — DRY RUN by default.

Prints, for every recommended index, whether it already exists, can be created,
or is BLOCKED by duplicate data (with the duplicates), and the exact operations
that would run. Nothing is changed unless --apply is given, and --apply is
refused unless DB_NAME contains "test" (so it can be rehearsed on a disposable
copy, never run against real data from this script).

    MONGO_URL=... DB_NAME=aayna_dev   python scripts/diagnostics/index_migration.py            # plan only
    MONGO_URL=... DB_NAME=aayna_pytest python scripts/diagnostics/index_migration.py --apply   # rehearsal

Production rollout (founder-approved, after a backup and after data_integrity.py
reports no BLOCKER): run the printed operations in a maintenance window. The app
does not create these indexes at startup on purpose: auth.ensure_indexes swallows
errors, so a unique index blocked by duplicates would fail silently there.
"""
import argparse
import os
import sys

import pymongo

# (collection, keys, options, why)
PLAN = [
    ("products", [("id", 1)], {"unique": True}, "every admin/checkout lookup is by id"),
    ("products", [("sku", 1)], {"unique": True}, "CSV/inventory import match on SKU"),
    ("products", [("slug", 1)], {"unique": True}, "public product URL; replaces the non-unique slug index"),
    ("orders", [("id", 1)], {"unique": True}, "order identity"),
    ("orders", [("order_number", 1)], {"unique": True}, "lookup, tracking, admin edits; replaces the non-unique index"),
    ("orders", [("client_request_id", 1)],
     {"unique": True, "partialFilterExpression": {"client_request_id": {"$type": "string"}}},
     "second line of defence for idempotency (orders without a key are allowed)"),
    ("orders", [("customer_id", 1), ("created_at", -1)], {}, "customer detail / last order date"),
    ("orders", [("created_at", -1)], {}, "admin order list and dashboard"),
    ("customers", [("id", 1)], {"unique": True}, "customer identity"),
    ("customers", [("phone", 1)], {"unique": True}, "checkout matches customers by phone; replaces the non-unique index"),
    ("categories", [("slug", 1)], {"unique": True}, "public category URL"),
    ("files", [("storage_path", 1)], {"unique": True}, "/api/files lookup"),
    ("inventory_logs", [("product_id", 1), ("created_at", -1)], {}, "inventory history per product"),
    ("users", [("email", 1)], {"unique": True}, "already created at startup"),
]


def dup_values(coll, field, partial=None):
    match = partial or {field: {"$exists": True}}
    return [d["_id"] for d in coll.aggregate([{"$match": match}, {"$group": {"_id": f"${field}", "n": {"$sum": 1}}},
                                              {"$match": {"n": {"$gt": 1}}}, {"$limit": 20}])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="apply the plan (only allowed on a database whose name contains 'test')")
    a = ap.parse_args()
    name = os.environ["DB_NAME"]
    if a.apply and "test" not in name.lower():
        sys.exit(f"Refusing --apply on '{name}': this script only applies to disposable test databases.")
    db = pymongo.MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)[name]
    blocked = 0
    failed = []
    print(f"Index plan for '{name}' ({'APPLY' if a.apply else 'dry run'})\n")
    for coll_name, keys, opts, why in PLAN:
        coll = db[coll_name]
        existing = coll.index_information() if coll_name in db.list_collection_names() else {}
        same_keys = {n: i for n, i in existing.items() if i.get("key") == keys}
        want_unique = bool(opts.get("unique"))
        label = f"{coll_name} {{{', '.join(f'{k}: {d}' for k, d in keys)}}}{' unique' if want_unique else ''}"
        ok = [n for n, i in same_keys.items() if bool(i.get("unique")) == want_unique
              and i.get("partialFilterExpression") == opts.get("partialFilterExpression")]
        if ok:
            print(f"  OK       {label}  (exists as {ok[0]})")
            continue
        ops = [f"db.{coll_name}.dropIndex('{n}')" for n in same_keys]
        if want_unique and len(keys) == 1:
            d = dup_values(coll, keys[0][0], opts.get("partialFilterExpression"))
            if d:
                blocked += 1
                print(f"  BLOCKED  {label}: {len(d)}+ duplicate values, e.g. {d[:5]}  — resolve in data first ({why})")
                continue
        ops.append(f"db.{coll_name}.createIndex({dict(keys)}, {opts})")
        print(f"  CREATE   {label}  — {why}\n           " + "; ".join(ops))
        if a.apply:
            old = {n: i for n, i in same_keys.items()}
            for n in old:
                coll.drop_index(n)
            try:
                coll.create_index(keys, **opts)
                print("           applied")
            except pymongo.errors.OperationFailure as exc:
                failed.append(label)
                print(f"           FAILED on this server: {exc.details.get('errmsg', exc) if exc.details else exc}")
                for n, i in old.items():  # put the previous index back so nothing is left unindexed
                    extra = {k: v for k, v in i.items() if k in ("unique", "partialFilterExpression", "sparse")}
                    coll.create_index(i["key"], name=n, **extra)
                    print(f"           restored previous index {n}")
    print(f"\nblocked: {blocked}   failed: {len(failed)} {failed if failed else ''}")
    return 1 if blocked or failed else 0


if __name__ == "__main__":
    sys.exit(main())

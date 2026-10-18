#!/usr/bin/env python3
"""
Small, guarded operations on the PRODUCTION database (aayna_prod).

    python scripts/prod_db_ops.py inspect          --env-file .env.prod-import
    python scripts/prod_db_ops.py ensure-sku-index --env-file .env.prod-import --confirm aayna_prod
    python scripts/prod_db_ops.py drop-sku-index   --env-file .env.prod-import --confirm aayna_prod   (rollback)

inspect is READ-ONLY: counts, indexes, duplicate SKUs/slugs, catalogue totals and
a summary of admin users (role, status, masked email - never a password hash).

ensure-sku-index creates ONE unique index `sku_unique` on products.sku, only if
no product lacks a SKU and no SKU is duplicated. It never modifies a document.
Idempotent: if an index on {sku: 1} already exists it does nothing.
Rollback: drop-sku-index removes exactly that index.

Same safety rules as prod_catalogue_import.py: the connection string comes only
from the git-ignored env file, must target aayna_prod as aayna_prod_app, and is
never printed.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prod_catalogue_import import Stop, load_env_file, check_target, redact, sync_db, out  # noqa: E402

SKU_INDEX = "sku_unique"
EXPECTED_SKUS = 10


def mask_email(email):
    e = str(email or "")
    if "@" not in e:
        return "?"
    user, dom = e.split("@", 1)
    return (user[:2] + "***@" + dom) if user else "***@" + dom


def inspect(db):
    problems = []
    out("Collections:")
    for n in sorted(db.list_collection_names()):
        ix = "; ".join(f"{i['name']} {dict(i['key'])}{' UNIQUE' if i.get('unique') else ''}"
                       for i in db[n].list_indexes())
        out(f"  {n:<16} {db[n].count_documents({}):>4} docs | {ix}")
    skus = Counter(p.get("sku") for p in db.products.find({}, {"_id": 0, "sku": 1}))
    dups = {s: n for s, n in skus.items() if n > 1}
    missing = skus.get(None, 0) + skus.get("", 0)
    slugs = Counter(p.get("slug") for p in db.products.find({}, {"_id": 0, "slug": 1}))
    dup_slugs = {s: n for s, n in slugs.items() if n > 1}
    status = Counter(p.get("status") for p in db.products.find({}, {"_id": 0, "status": 1}))
    units = sum(int(p.get("stock_quantity") or 0) for p in db.products.find({}, {"_id": 0, "stock_quantity": 1}))
    rejected = db.products.count_documents({"sku": {"$regex": "^REJ-"}})
    out(f"Products: {sum(skus.values())} | by status {dict(status)} | units {units} | "
        f"duplicate SKUs {dups or 'none'} | missing SKU {missing} | duplicate slugs {dup_slugs or 'none'} | REJ- rows {rejected}")
    out("Admin users (no password data):")
    for u in db.users.find({}, {"_id": 0, "password_hash": 0}):
        out(f"  role={u.get('role')} status={u.get('status')} name={u.get('name')!r} email={mask_email(u.get('email'))} "
            f"created={str(u.get('created_at'))[:19]} has_session_version={'session_version' in u}")
    if dups:
        problems.append(f"duplicate SKUs: {dups}")
    if missing:
        problems.append(f"{missing} products without SKU")
    return problems


def ensure_sku_index(db):
    existing = {i["name"]: i for i in db.products.list_indexes()}
    for name, ix in existing.items():
        if dict(ix["key"]) == {"sku": 1}:
            out(f"Index on products.sku already exists ({name}, unique={bool(ix.get('unique'))}); nothing to do.")
            return
    problems = inspect(db)
    if problems:
        raise Stop("NOT CREATED: " + "; ".join(problems))
    before = db.products.count_documents({})
    db.products.create_index("sku", unique=True, name=SKU_INDEX)
    after = db.products.count_documents({})
    ix = {i["name"]: i for i in db.products.list_indexes()}.get(SKU_INDEX)
    if not ix or not ix.get("unique") or before != after:
        raise Stop("index verification failed")
    out(f"Created unique index {SKU_INDEX} on products.sku. Products before/after: {before}/{after}.")


def drop_sku_index(db):
    names = [i["name"] for i in db.products.list_indexes()]
    if SKU_INDEX not in names:
        out(f"{SKU_INDEX} not present; nothing to do.")
        return
    db.products.drop_index(SKU_INDEX)
    out(f"Dropped {SKU_INDEX}. Remaining: {[i['name'] for i in db.products.list_indexes()]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["inspect", "ensure-sku-index", "drop-sku-index"])
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--confirm")
    a = ap.parse_args(argv)
    vals = {}
    try:
        vals = load_env_file(a.env_file)
        write = a.cmd != "inspect"
        host = check_target(vals, a.confirm if write else None)
        if write and a.confirm is None:
            raise Stop("--confirm aayna_prod is required for this command")
        client, db = sync_db(vals)
        try:
            db.command("ping")
            out(f"Target: {host} / {vals['DB_NAME']} ({'WRITE: ' + a.cmd if write else 'read-only'})")
            if a.cmd == "inspect":
                problems = inspect(db)
                out("INSPECT: " + ("problems: " + "; ".join(problems) if problems else "no duplicate or missing SKUs"))
            elif a.cmd == "ensure-sku-index":
                ensure_sku_index(db)
            else:
                drop_sku_index(db)
        finally:
            client.close()
    except Stop as exc:
        out(f"\nSTOPPED: {redact(exc, vals)}")
        return 2
    except Exception as exc:  # noqa: BLE001
        out(f"\nERROR ({type(exc).__name__}): {redact(exc, vals)}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

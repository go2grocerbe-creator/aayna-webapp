#!/usr/bin/env python3
"""
Founder-approved +৳100 selling-price update (2026-10-19) for the 10 launch products.

    # 1. Dry run (READ-ONLY, the default): shows current -> target per SKU, changes nothing
    python scripts/prices/apply_price_update_20261019.py --env-file <path to .env.prod-import>

    # 2. Apply (writes selling prices only), then a read-back verification
    python scripts/prices/apply_price_update_20261019.py --env-file <...> --apply --confirm aayna_prod

    # 3. Verify only (READ-ONLY): every product at its target
    python scripts/prices/apply_price_update_20261019.py --env-file <...> --verify

Target prices live in backend/price_targets.py (SKU -> before, target).

What --apply writes, per product, and nothing else:
    selling_price           -> the approved target
    previous_selling_price  -> the price before this update
    price_history           -> one appended entry {from, to, reason, at, by}
    updated_at
It never touches cost_price, pricing (the admin cost-rule breakdown), stock,
status/publication, images, descriptions, orders, customers or settings. Orders
keep the unit price they were placed at.

Safety:
  * Same connection guard as the catalogue import: the URL comes only from the
    git-ignored env file, must target aayna_prod as aayna_prod_app, never printed.
  * All-or-nothing pre-check: if any of the 10 SKUs is missing, duplicated, has a
    discount price, or has a price that is neither its "before" nor its target,
    nothing is written.
  * Idempotent: each write is conditional on the product STILL having its "before"
    price, so a second run (or two runs at once) can never add ৳200; products
    already at their target are reported "already" and left alone.
  * Rollback: the same command with --rollback --confirm aayna_prod puts back the
    "before" prices for products that are still exactly at their target.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from price_targets import PRICE_TARGETS, PRICE_UPDATE_ID, plan  # noqa: E402

BY = "scripts/prices/apply_price_update_20261019.py"
REASON = "Founder-approved +100 BDT price update (2026-10-19)"


def read_products(db):
    docs = list(db.products.find({"sku": {"$in": sorted(PRICE_TARGETS)}},
                                 {"_id": 0, "id": 1, "sku": 1, "selling_price": 1, "discount_price": 1, "status": 1}))
    by_sku = {}
    for d in docs:
        by_sku.setdefault(d["sku"], []).append(d)
    return by_sku


def make_plans(by_sku):
    plans, problems = [], []
    for sku in sorted(PRICE_TARGETS):
        found = by_sku.get(sku, [])
        if len(found) != 1:
            problems.append(f"{sku}: {'missing' if not found else 'duplicated'}")
            plans.append({"sku": sku, "action": "flag", "reason": "missing" if not found else "duplicated"})
            continue
        p = found[0]
        pl = plan(sku, p.get("selling_price"), p.get("discount_price"))
        pl["id"], pl["status"] = p.get("id"), p.get("status")
        if pl["action"] == "flag":
            problems.append(f"{sku}: {pl['reason']}")
        plans.append(pl)
    return plans, problems


def show(plans, out):
    out(f"{'SKU':<17} {'status':<8} {'current':>8} {'before':>7} {'target':>7}  action")
    for p in plans:
        out(f"{p['sku']:<17} {str(p.get('status', '')):<8} {str(p.get('current', '')):>8} {str(p.get('before', '')):>7} "
            f"{str(p.get('target', '')):>7}  {p['action']}{'  - ' + p['reason'] if p.get('reason') else ''}")


def apply(db, plans, out):
    at = datetime.now(timezone.utc).isoformat()
    changed = 0
    for p in plans:
        if p["action"] != "update":
            continue
        res = db.products.update_one(
            {"id": p["id"], "sku": p["sku"], "selling_price": p["before"]},  # still at the old price -> never twice
            {"$set": {"selling_price": p["target"], "previous_selling_price": p["before"], "updated_at": at},
             "$push": {"price_history": {"from": p["before"], "to": p["target"], "reason": REASON,
                                         "update_id": PRICE_UPDATE_ID, "at": at, "by": BY}}})
        changed += res.modified_count
        out(f"  {p['sku']}: {'updated' if res.modified_count else 'NOT updated (price changed meanwhile)'}")
    return changed


def rollback(db, out):
    at = datetime.now(timezone.utc).isoformat()
    n = 0
    for sku, (old, new) in sorted(PRICE_TARGETS.items()):
        res = db.products.update_one(
            {"sku": sku, "selling_price": new},
            {"$set": {"selling_price": old, "previous_selling_price": new, "updated_at": at},
             "$push": {"price_history": {"from": new, "to": old, "reason": "Rollback of " + PRICE_UPDATE_ID,
                                         "update_id": PRICE_UPDATE_ID + "-rollback", "at": at, "by": BY}}})
        n += res.modified_count
        out(f"  {sku}: {'restored to ' + str(old) if res.modified_count else 'left as is'}")
    return n


def run(db, mode, out=print):
    """mode: dry-run | apply | verify | rollback. Returns process exit code."""
    plans, problems = make_plans(read_products(db))
    show(plans, out)
    if mode == "verify":
        ok = all(p["action"] == "already" for p in plans)
        out("VERIFIED: all 10 products are at their approved target price." if ok else "NOT VERIFIED: see the table.")
        return 0 if ok else 1
    if mode == "rollback":
        out(f"Rolled back {rollback(db, out)} product(s).")
        return 0
    if problems:
        out("STOPPED - nothing written: " + "; ".join(problems))
        return 2
    todo = sum(p["action"] == "update" for p in plans)
    if mode == "dry-run":
        out(f"DRY RUN - nothing written. {todo} product(s) would change, {10 - todo} already at target.")
        return 0
    changed = apply(db, plans, out)
    after, _ = make_plans(read_products(db))
    ok = all(p["action"] == "already" for p in after)
    out(f"Applied: {changed} product(s) changed. Read-back: {'all 10 at target' if ok else 'MISMATCH - see table'}")
    if not ok:
        show(after, out)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", required=True, help="git-ignored env file with MONGO_URL and DB_NAME=aayna_prod")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--rollback", action="store_true")
    ap.add_argument("--confirm", help="must be exactly aayna_prod for --apply/--rollback")
    a = ap.parse_args(argv)
    from prod_catalogue_import import Stop, load_env_file, check_target, redact, sync_db  # noqa: E402
    mode = "apply" if a.apply else "verify" if a.verify else "rollback" if a.rollback else "dry-run"
    vals = None
    try:
        vals = load_env_file(a.env_file)
        host = check_target(vals, confirm=a.confirm if mode in ("apply", "rollback") else None)
        if mode in ("apply", "rollback") and a.confirm != "aayna_prod":
            raise Stop("--apply/--rollback need --confirm aayna_prod")
        print(f"Target: {vals['DB_NAME']} on {host} | mode: {mode}")
        client, db = sync_db(vals)
        try:
            return run(db, mode)
        finally:
            client.close()
    except Stop as e:
        print("STOPPED:", e)
        return 2
    except Exception as e:  # noqa: BLE001
        print("ERROR:", redact(f"{type(e).__name__}: {e}", vals or {}))
        return 1


if __name__ == "__main__":
    sys.exit(main())

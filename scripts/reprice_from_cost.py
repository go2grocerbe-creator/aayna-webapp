#!/usr/bin/env python3
"""
Re-derive selling prices of existing products from their recorded cost.

    selling_price = (cost_price + extra) * multiplier        (backend/pricing.py)

The two values are business-confidential (with a public price they reveal the
cost) and are read from AAYNA_PRICE_EXTRA_BDT / AAYNA_PRICE_MULTIPLIER in
backend/.env on the machine that runs this script - never from the repository.

Dry run (default, read-only - prints the table, writes nothing):
    python scripts/reprice_from_cost.py

Apply (writes the DB configured in backend/.env):
    python scripts/reprice_from_cost.py --apply --target-db <exact DB_NAME> [--sku AYN-RNG-CLS-GLD]

Safety rules:
  * Source is ONLY `cost_price` (the per-unit purchase cost recorded from the
    inventory spreadsheet). The rule is never applied to a selling price, and
    cost_price is never written, so re-running cannot stack the extra amount or
    the markup: a second run reports every product as "unchanged".
  * Only real inventory products are eligible: records created by the
    inventory importer (`source.type == "inventory_xlsx"`) with status draft,
    active or out_of_stock. Demo/seed or other-origin records are reported and
    skipped. Missing/invalid costs are flagged, never guessed.
  * A product whose existing discount price would be >= the new selling price is
    flagged and skipped (it would fail Admin validation).
  * A price changed manually in Admin after the last rule run is flagged, not
    overwritten, unless --override-manual is given.
  * The previous selling price is kept (`previous_selling_price` plus an
    append-only `price_history`), the breakdown is stored in `pricing`. All three
    are admin-only: the public API whitelist (server.PUBLIC_PRODUCT_FIELDS)
    does not include them, nor cost_price.
  * Orders store unit_price at checkout time, so historical orders never change.
  * --apply requires --target-db to repeat DB_NAME and refuses synthetic/test
    databases (same guard as the importer).
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pricing  # noqa: E402

ELIGIBLE_STATUSES = {"draft", "active", "out_of_stock"}
SOURCE_TYPE = "inventory_xlsx"


def plan_product(p, rule, override_manual=False):
    """Decide what to do with one product document. Pure function."""
    row = {"id": p.get("id"), "sku": p.get("sku"), "product_name": p.get("product_name"),
           "status": p.get("status"), "current_price": p.get("selling_price")}
    if (p.get("source") or {}).get("type") != SOURCE_TYPE:
        return {**row, "action": "skip", "reason": "not real inventory (demo/seed or unknown origin)"}
    if p.get("status") not in ELIGIBLE_STATUSES:
        return {**row, "action": "skip", "reason": f"status '{p.get('status')}' not eligible"}
    try:
        bd = pricing.price_from_cost(p.get("cost_price"), *rule)
    except pricing.PricingError as exc:
        return {**row, "action": "flag", "reason": f"cost: {exc}"}
    row.update({k: bd[k] for k in ("cost", "extra", "adjusted_cost", "selling_price",
                                   "gross_profit", "gross_margin_pct")})
    dp = p.get("discount_price")
    if dp not in (None, 0) and float(dp) >= bd["selling_price"]:
        return {**row, "action": "flag", "reason": f"discount price {dp} >= new selling price"}
    meta = p.get("pricing") or {}
    last_rule_price = meta.get("selling_price") if meta.get("rule") == bd["rule"] else None
    same_rule = all(meta.get(k) == bd[k] for k in ("rule", "cost", "extra", "multiplier"))
    if (not override_manual and last_rule_price is not None and p.get("selling_price") is not None
            and float(p["selling_price"]) != float(last_rule_price)):
        return {**row, "action": "flag",
                "reason": f"price set manually in Admin after the last rule run (rule gave {last_rule_price}); "
                          "use --override-manual to reset it"}
    same_price = p.get("selling_price") is not None and float(p["selling_price"]) == float(bd["selling_price"])
    if same_price and same_rule:
        return {**row, "action": "unchanged", "breakdown": bd}
    return {**row, "action": "metadata" if same_price else "update", "breakdown": bd}


async def reprice(db, now_iso, rule, apply=False, only=None, override_manual=False):
    """rule: (extra_bdt, multiplier), see pricing.rule_from_env()."""
    plans = []
    async for p in db.products.find({}, {"_id": 0}):
        if only and p.get("sku") not in only:
            continue
        plans.append((p, plan_product(p, rule, override_manual)))
    if apply:
        at = now_iso()
        for p, plan in plans:
            if plan["action"] not in ("update", "metadata"):
                continue
            bd = plan["breakdown"]
            upd = {"$set": {"pricing": {**bd, "computed_at": at}, "updated_at": at}}
            if plan["action"] == "update":
                upd["$set"].update({"selling_price": bd["selling_price"],
                                    "previous_selling_price": p.get("selling_price")})
                upd["$push"] = {"price_history": {"from": p.get("selling_price"), "to": bd["selling_price"],
                                                  "rule": bd["rule"], "cost": bd["cost"], "extra": bd["extra"],
                                                  "multiplier": bd["multiplier"], "at": at,
                                                  "by": "scripts/reprice_from_cost.py"}}
            # optimistic: only if price and cost are still what we planned from
            res = await db.products.update_one(
                {"id": p["id"], "selling_price": p.get("selling_price"), "cost_price": p.get("cost_price")}, upd)
            plan["applied"] = res.modified_count == 1
            if not plan["applied"]:
                plan["action"] = "flag"
                plan["reason"] = "product changed during run; re-run"
    return [plan for _, plan in plans]


def print_table(plans):
    print(f"{'SKU':<18} {'status':<12} {'cost':>7} {'+':>4} {'adjusted':>8} {'current':>8} {'new':>8} "
          f"{'profit':>7} {'margin':>7}  action")
    for r in sorted(plans, key=lambda x: (x["action"] == "skip", x.get("sku") or "")):
        f = lambda k: "" if r.get(k) is None else f"{r[k]:g}" if isinstance(r[k], (int, float)) else str(r[k])
        print(f"{(r.get('sku') or '-'):<18} {(r.get('status') or '-'):<12} {f('cost'):>7} {f('extra'):>4} "
              f"{f('adjusted_cost'):>8} {f('current_price'):>8} {f('selling_price'):>8} {f('gross_profit'):>7} "
              f"{(f('gross_margin_pct') + '%') if r.get('gross_margin_pct') else '':>7}  "
              f"{r['action']}{(' - ' + r['reason']) if r.get('reason') else ''}")
    counts = {}
    for r in plans:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    print("\nSummary:", json.dumps(counts))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--target-db", help="required with --apply; must equal DB_NAME; test databases refused")
    ap.add_argument("--sku", action="append", help="limit to these SKUs (repeatable)")
    ap.add_argument("--report", help="write the full JSON report (contains admin-only cost data) to this path")
    ap.add_argument("--override-manual", action="store_true",
                    help="also reset prices that were changed manually in Admin after the last rule run")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    import os
    from dotenv import load_dotenv
    from import_inventory import check_import_target
    load_dotenv(ROOT / "backend" / ".env")
    try:
        rule = pricing.rule_from_env()
    except pricing.PricingError as exc:
        sys.exit(f"Pricing rule not configured: {exc} (set it in backend/.env; never commit it)")
    if a.apply:
        # check before importing db: nothing is opened for a refused target
        try:
            target = check_import_target(os.environ.get("DB_NAME"), a.target_db)
        except ValueError as exc:
            sys.exit(f"Refused: {exc}")
    import db as dbmod  # noqa: E402  (loads backend/.env)
    print(f"DB: {os.environ.get('DB_NAME')}  |  rule: {pricing.RULE_ID}  |  "
          f"{'APPLY' if a.apply else 'DRY RUN (nothing written)'}")
    if a.apply:
        plans = asyncio.run(reprice(dbmod.db, dbmod.now_iso, rule, apply=False, only=set(a.sku or []), override_manual=a.override_manual))
        print_table(plans)
        if not a.yes and input(f"\nApply to '{target}'? Type REPRICE to continue: ").strip() != "REPRICE":
            sys.exit("Aborted.")
    plans = asyncio.run(reprice(dbmod.db, dbmod.now_iso, rule, apply=a.apply, only=set(a.sku or []), override_manual=a.override_manual))
    print_table(plans)
    if a.report:
        Path(a.report).write_text(json.dumps(plans, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"Report: {a.report} (admin-only: contains costs)")


if __name__ == "__main__":
    main()

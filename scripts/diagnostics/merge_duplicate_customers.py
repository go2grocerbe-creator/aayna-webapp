"""Deterministic, auditable merge of duplicate AAYNA customer records (one per phone).

Why: checkout finds customers by the NORMALIZED phone (+8801XXXXXXXXX). Two records
for one phone (concurrent first orders before the unique index existed, or legacy
records stored in another format) split a person's order history, and the unique
index on customers.phone cannot be built until they are merged.

    python merge_duplicate_customers.py plan    [--plan-out plan.json]      # read-only (default)
    python merge_duplicate_customers.py apply   --plan plan.json --confirm <plan_hash>
    python merge_duplicate_customers.py rollback --run-id <run_id>
    python merge_duplicate_customers.py verify                              # read-only

Rules (deterministic):
  * group customers by normalize_phone(phone); invalid phones are reported, never touched
  * survivor = earliest created_at (missing sorts last), then smallest id
  * every order of a merged record is re-pointed to the survivor and keeps
    `merged_from_customer_id`; survivor counters are recomputed from its orders
    (total = all orders, successful = Delivered, cancelled = Cancelled)
  * empty survivor fields (name, email, address, district) are filled from the most
    recently updated merged record; non-empty survivor fields are never overwritten
  * merged records are copied to `customers_merged_archive` before removal
  * every step is logged in `customer_merge_log` (full before-images) so `rollback`
    restores the exact previous documents
  * singleton customers whose stored phone is not normalized are normalized (logged)

Safety:
  * `plan` and `verify` only read. Output is aggregate; the plan file holds ids,
    order numbers and phone HASHES only (no names, phones, emails or addresses).
  * `apply` / `rollback` run only on an allowlisted TEST target
    (scripts/verify/release_target_guard.py). Running on real data needs a
    founder-approved change to this gate, a verified backup and a maintenance window
    (checkout closed: the merge is not transactional).
  * `apply` recomputes the plan and refuses unless its hash equals --confirm, so the
    data cannot have changed between review and apply.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone

import pymongo

PHONE_RE = re.compile(r'^(?:\+?880|0)1[3-9]\d{8}$')   # keep identical to backend/server.py
FILL_FIELDS = ("full_name", "email", "default_address", "district")


def normalize_phone(phone):
    """Same logic as backend/server.py normalize_phone (tested for equivalence)."""
    p = re.sub(r'[\s\-]', '', phone or '')
    if not PHONE_RE.match(p):
        return None
    digits = re.sub(r'\D', '', p)
    if digits.startswith('880'):
        digits = digits[3:]
    if digits.startswith('0'):
        digits = digits[1:]
    return '+880' + digits


def phone_hash(p):
    return hashlib.sha256((p or "").encode()).hexdigest()[:12]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_plan(db):
    customers = list(db.customers.find({}, {"_id": 0}))
    groups, invalid = {}, 0
    for c in customers:
        n = normalize_phone(c.get("phone"))
        if n is None:
            invalid += 1
            continue
        groups.setdefault(n, []).append(c)
    merges, phone_updates = [], []
    for norm in sorted(groups):
        members = sorted(groups[norm], key=lambda c: (c.get("created_at") or "9999", c.get("id") or ""))
        survivor, losers = members[0], members[1:]
        if not losers:
            if survivor.get("phone") != norm:
                phone_updates.append({"id": survivor["id"], "phone_hash": phone_hash(norm)})
            continue
        ids = [m["id"] for m in members]
        orders = sorted(db.orders.find({"customer_id": {"$in": ids}},
                                       {"_id": 0, "order_number": 1, "customer_id": 1, "order_status": 1}),
                        key=lambda o: o.get("order_number") or "")
        newest_first = sorted(losers, key=lambda c: (c.get("updated_at") or c.get("created_at") or ""), reverse=True)
        fill = {}
        for f in FILL_FIELDS:
            if not survivor.get(f):
                src = next((l["id"] for l in newest_first if l.get(f)), None)
                if src:
                    fill[f] = src
        merges.append({
            "phone_hash": phone_hash(norm),
            "survivor": survivor["id"],
            "losers": [l["id"] for l in losers],
            "repoint_orders": [{"order_number": o.get("order_number"), "from": o["customer_id"]}
                               for o in orders if o["customer_id"] != survivor["id"]],
            "fill_from": fill,
            "counters": {"total_orders": len(orders),
                         "successful_orders": sum(1 for o in orders if o.get("order_status") == "Delivered"),
                         "cancelled_orders": sum(1 for o in orders if o.get("order_status") == "Cancelled")},
            "set_phone": survivor.get("phone") != norm,
        })
    body = {"database": db.name, "customers": len(customers), "invalid_phone_customers": invalid,
            "merges": merges, "phone_updates": phone_updates}
    body["plan_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body


def summarize(plan):
    m = plan["merges"]
    return {"customers": plan["customers"], "duplicate_phone_groups": len(m),
            "records_to_merge_away": sum(len(x["losers"]) for x in m),
            "orders_to_repoint": sum(len(x["repoint_orders"]) for x in m),
            "fields_to_fill": sum(len(x["fill_from"]) for x in m),
            "singleton_phones_to_normalize": len(plan["phone_updates"]),
            "invalid_phone_customers": plan["invalid_phone_customers"], "plan_hash": plan["plan_hash"]}


def _phone_for(db, customer_id):
    c = db.customers.find_one({"id": customer_id}, {"_id": 0, "phone": 1})
    return normalize_phone((c or {}).get("phone"))


def apply_plan(db, plan, confirm):
    current = build_plan(db)
    if current["plan_hash"] != plan["plan_hash"] or plan["plan_hash"] != confirm:
        raise SystemExit("Refusing: the data or plan changed since review (plan hash mismatch). Re-run `plan`.")
    run_id = uuid.uuid4().hex
    for g in plan["merges"]:
        survivor_before = db.customers.find_one({"id": g["survivor"]}, {"_id": 0})
        losers_before = list(db.customers.find({"id": {"$in": g["losers"]}}, {"_id": 0}))
        log_id = uuid.uuid4().hex
        db.customer_merge_log.insert_one({
            "id": log_id, "run_id": run_id, "type": "merge", "plan_hash": plan["plan_hash"], "status": "started",
            "survivor_before": survivor_before, "losers_before": losers_before,
            "orders_before": g["repoint_orders"], "started_at": now_iso()})
        for l in losers_before:
            db.customers_merged_archive.insert_one(dict(l, merged_into=g["survivor"], run_id=run_id,
                                                        archived_at=now_iso()))
        for loser in g["losers"]:
            db.orders.update_many({"customer_id": loser},
                                  {"$set": {"customer_id": g["survivor"], "merged_from_customer_id": loser}})
        by_id = {l["id"]: l for l in losers_before}
        sets = {f: by_id[src][f] for f, src in g["fill_from"].items()}
        sets.update(g["counters"])
        sets["updated_at"] = now_iso()
        if g["set_phone"]:
            sets["phone"] = _phone_for(db, g["survivor"])
        db.customers.update_one({"id": g["survivor"]},
                                {"$set": sets, "$addToSet": {"merged_customer_ids": {"$each": g["losers"]}}})
        db.customers.delete_many({"id": {"$in": g["losers"]}})
        db.customer_merge_log.update_one({"id": log_id}, {"$set": {"status": "done", "finished_at": now_iso()}})
    for u in plan["phone_updates"]:
        before = db.customers.find_one({"id": u["id"]}, {"_id": 0})
        log_id = uuid.uuid4().hex
        db.customer_merge_log.insert_one({"id": log_id, "run_id": run_id, "type": "normalize", "customer_id": u["id"],
                                          "customer_before": before, "status": "started",
                                          "started_at": now_iso()})
        db.customers.update_one({"id": u["id"]}, {"$set": {"phone": normalize_phone(before.get("phone")),
                                                          "updated_at": now_iso()}})
        db.customer_merge_log.update_one({"id": log_id}, {"$set": {"status": "done", "finished_at": now_iso()}})
    return run_id


def rollback(db, run_id):
    entries = list(db.customer_merge_log.find({"run_id": run_id, "status": {"$in": ["started", "done"]}})
                   .sort([("started_at", -1), ("id", -1)]))
    if not entries:
        raise SystemExit(f"Nothing to roll back for run {run_id}")
    for e in entries:
        if e["type"] == "normalize":
            db.customers.replace_one({"id": e["customer_id"]}, dict(e["customer_before"]))
        else:
            for l in e["losers_before"]:
                if not db.customers.find_one({"id": l["id"]}):
                    db.customers.insert_one(dict(l))
            for o in e["orders_before"]:
                db.orders.update_one({"order_number": o["order_number"]},
                                     {"$set": {"customer_id": o["from"]}, "$unset": {"merged_from_customer_id": ""}})
            if e.get("survivor_before"):
                db.customers.replace_one({"id": e["survivor_before"]["id"]}, dict(e["survivor_before"]))
            db.customers_merged_archive.delete_many({"run_id": run_id, "id": {"$in": [l["id"] for l in e["losers_before"]]}})
        db.customer_merge_log.update_one({"_id": e["_id"]}, {"$set": {"status": "rolled_back", "rolled_back_at": now_iso()}})
    return len(entries)


def verify(db):
    """Read-only post-conditions. Returns {check: count_of_problems}."""
    customers = list(db.customers.find({}, {"_id": 0, "id": 1, "phone": 1, "total_orders": 1,
                                             "successful_orders": 1, "cancelled_orders": 1}))
    ids = {c["id"] for c in customers}
    norm_counts = {}
    for c in customers:
        n = normalize_phone(c.get("phone"))
        if n:
            norm_counts[n] = norm_counts.get(n, 0) + 1
    orders = list(db.orders.find({}, {"_id": 0, "customer_id": 1, "order_status": 1}))
    per = {}
    for o in orders:
        per.setdefault(o.get("customer_id"), []).append(o.get("order_status"))
    counter_mismatch = 0
    for c in customers:
        st = per.get(c["id"], [])
        if (c.get("total_orders", 0), c.get("successful_orders", 0), c.get("cancelled_orders", 0)) != \
                (len(st), st.count("Delivered"), st.count("Cancelled")):
            counter_mismatch += 1
    return {"duplicate_normalized_phones": sum(1 for v in norm_counts.values() if v > 1),
            "non_normalized_phones": sum(1 for c in customers if c.get("phone") and normalize_phone(c["phone"])
                                         and c["phone"] != normalize_phone(c["phone"])),
            "orders_with_missing_customer": sum(1 for o in orders if o.get("customer_id") not in ids),
            "customer_counter_mismatch": counter_mismatch}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", default="plan", choices=["plan", "apply", "rollback", "verify"])
    ap.add_argument("--plan-out")
    ap.add_argument("--plan")
    ap.add_argument("--confirm")
    ap.add_argument("--run-id")
    a = ap.parse_args()
    url, name = os.environ["MONGO_URL"], os.environ["DB_NAME"]
    client = pymongo.MongoClient(url, serverSelectionTimeoutMS=15000)
    if a.action in ("apply", "rollback"):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verify"))
        from release_target_guard import require_safe
        require_safe(url, name, client)   # test targets only in this phase
    db = client[name]
    if a.action == "plan":
        plan = build_plan(db)
        if a.plan_out:
            with open(a.plan_out, "w", encoding="utf-8") as fh:
                json.dump(plan, fh, indent=2, sort_keys=True)
        print(json.dumps(summarize(plan), indent=2))
    elif a.action == "apply":
        if not (a.plan and a.confirm):
            sys.exit("apply needs --plan and --confirm <plan_hash>")
        with open(a.plan, encoding="utf-8") as fh:
            plan = json.load(fh)
        run_id = apply_plan(db, plan, a.confirm)
        print(json.dumps({"run_id": run_id, **summarize(plan), "after": verify(db)}, indent=2))
    elif a.action == "rollback":
        if not a.run_id:
            sys.exit("rollback needs --run-id")
        print(json.dumps({"rolled_back_steps": rollback(db, a.run_id), "after": verify(db)}, indent=2))
    else:
        result = verify(db)
        print(json.dumps(result, indent=2))
        return 1 if any(result.values()) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

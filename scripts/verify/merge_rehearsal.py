"""Rehearse the duplicate-customer merge + unique phone index on an allowlisted TEST database.

Plants synthetic duplicates (fake names, reserved 0139 phones), then:
  1. index_migration-style check: customers.phone unique is BLOCKED by duplicates
  2. plan -> apply (hash-confirmed) -> verify all zero
  3. rollback -> every touched collection identical to before (exact documents)
  4. apply again -> unique customers.phone index builds -> a duplicate insert is rejected
Run by run_isolated_mongo_checks.py (suite "merge") on a freshly reset test database.
"""
import json
import os
import sys

import pymongo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "diagnostics"))
from release_target_guard import require_safe  # noqa: E402
import merge_duplicate_customers as m  # noqa: E402

url, name = os.environ["MONGO_URL"], os.environ["DB_NAME"]
client = pymongo.MongoClient(url, serverSelectionTimeoutMS=15000)
TARGET = require_safe(url, name, client)
db = client[name]
results = []


def rec(label, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL':5s} {label}" + (f"  — {detail}" if detail else ""))


def snap():
    out = {}
    for c in ("customers", "orders", "customers_merged_archive"):
        out[c] = sorted(json.dumps({k: v for k, v in d.items() if k != "_id"}, sort_keys=True, default=str)
                        for d in db[c].find({"rehearsal": True}))
    return out


# --- plant synthetic duplicates (reserved fake numbers 0139xxxxxxx, never real customers)
db.customers.delete_many({"rehearsal": True})
db.orders.delete_many({"rehearsal": True})
db.customers_merged_archive.delete_many({"rehearsal": True})
base = {"rehearsal": True, "successful_orders": 0, "cancelled_orders": 0, "district": "Dhaka"}
db.customers.insert_many([
    dict(base, id="rh-1a", phone="+8801390000001", full_name="", email="", default_address="A", total_orders=1,
         created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00"),
    dict(base, id="rh-1b", phone="01390000001", full_name="Test One", email="t1@example.test", default_address="B",
         total_orders=2, created_at="2026-01-02T00:00:00", updated_at="2026-01-03T00:00:00"),
    dict(base, id="rh-1c", phone="+8801390000001", full_name="Test One B", email="", default_address="",
         total_orders=1, created_at="2026-01-02T00:00:00", updated_at="2026-01-02T00:00:00"),
    dict(base, id="rh-2a", phone="+8801390000002", full_name="Test Two", total_orders=1,
         created_at="2026-01-01T00:00:00"),
    dict(base, id="rh-2b", phone="+8801390000002", full_name="Test Two", total_orders=1,
         created_at="2026-01-01T00:00:01"),
    dict(base, id="rh-3", phone="01390000003", full_name="Test Three", total_orders=0, created_at="2026-01-01T00:00:00"),
])
db.orders.insert_many([
    {"rehearsal": True, "order_number": "RH-1", "customer_id": "rh-1a", "order_status": "Delivered", "total_amount": 260},
    {"rehearsal": True, "order_number": "RH-2", "customer_id": "rh-1b", "order_status": "Cancelled", "total_amount": 260},
    {"rehearsal": True, "order_number": "RH-3", "customer_id": "rh-1b", "order_status": "New", "total_amount": 260},
    {"rehearsal": True, "order_number": "RH-4", "customer_id": "rh-1c", "order_status": "New", "total_amount": 260},
    {"rehearsal": True, "order_number": "RH-5", "customer_id": "rh-2a", "order_status": "New", "total_amount": 260},
    {"rehearsal": True, "order_number": "RH-6", "customer_id": "rh-2b", "order_status": "Delivered", "total_amount": 260},
])
for i, idx in db.customers.index_information().items():   # start from the app's non-unique phone index
    if idx.get("key") == [("phone", 1)] and idx.get("unique"):
        db.customers.drop_index(i)
if not any(i.get("key") == [("phone", 1)] for i in db.customers.index_information().values()):
    db.customers.create_index("phone")
before = snap()
totals_before = sorted(o["total_amount"] for o in db.orders.find({"rehearsal": True}))

dup_exact = list(db.customers.aggregate([{"$group": {"_id": "$phone", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
rec("before: unique customers.phone is blocked by duplicates", len(dup_exact) >= 1, f"{len(dup_exact)} exact duplicate value(s)")
v0 = m.verify(db)
rec("before: verify() sees the duplicates", v0["duplicate_normalized_phones"] == 2, json.dumps(v0))

plan = m.build_plan(db)
s = m.summarize(plan)
rec("plan: 2 groups, 3 records merged away, 4 orders re-pointed, 2 phones normalized",
    (s["duplicate_phone_groups"], s["records_to_merge_away"], s["orders_to_repoint"], s["singleton_phones_to_normalize"]) == (2, 3, 4, 1),
    json.dumps({k: v for k, v in s.items() if k != "plan_hash"}))
rec("plan: deterministic (same hash twice)", m.build_plan(db)["plan_hash"] == plan["plan_hash"])

run1 = m.apply_plan(db, plan, plan["plan_hash"])
v1 = m.verify(db)
rec("apply: verify() all zero", not any(v1.values()), json.dumps(v1))
s1 = db.customers.find_one({"id": "rh-1a"})
rec("apply: survivor keeps all 4 orders and correct counters",
    (s1["total_orders"], s1["successful_orders"], s1["cancelled_orders"]) == (4, 1, 1)
    and db.orders.count_documents({"customer_id": "rh-1a"}) == 4 and s1["full_name"] == "Test One"
    and s1["default_address"] == "A",
    f"counters=({s1['total_orders']},{s1['successful_orders']},{s1['cancelled_orders']})")
rec("apply: order totals unchanged",
    sorted(o["total_amount"] for o in db.orders.find({"rehearsal": True})) == totals_before)

steps = m.rollback(db, run1)
rec("rollback: documents identical to before", snap() == before, f"{steps} step(s) undone")

plan2 = m.build_plan(db)
run2 = m.apply_plan(db, plan2, plan2["plan_hash"])
for i, idx in db.customers.index_information().items():
    if idx.get("key") == [("phone", 1)]:
        db.customers.drop_index(i)
try:
    db.customers.create_index("phone", unique=True)
    built = True
except pymongo.errors.OperationFailure as exc:
    built = False
    print("   index error:", exc.details.get("errmsg") if exc.details else exc)
rec("after merge: unique customers.phone index builds", built)
try:
    db.customers.insert_one(dict(base, id="rh-x", phone="+8801390000001", total_orders=0))
    rejected = False
except pymongo.errors.DuplicateKeyError:
    rejected = True
rec("after index: a second record for the same phone is rejected", rejected)

# clean up the rehearsal's own documents (test DB only); the unique index stays for the suites that follow
db.customers.delete_many({"rehearsal": True})
db.orders.delete_many({"rehearsal": True})
db.customers_merged_archive.delete_many({"rehearsal": True})
db.customers_merged_archive.delete_many({"run_id": {"$in": [run1, run2]}})
db.customer_merge_log.delete_many({"run_id": {"$in": [run1, run2]}})
print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed (merge rehearsal on {TARGET['kind']} / {name})")
sys.exit(0 if all(results) else 1)

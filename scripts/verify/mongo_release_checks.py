"""Release checks for checkout and inventory safety — written to run on REAL MongoDB.

Covers (Phase 4B brief):
  A. admin aggregations: dashboard, low-stock filter, customer list/detail (values
     cross-checked against counts computed in Python from raw documents)
  B. 10 concurrent orders for 3 units -> exactly 3 orders, stock 0, out_of_stock
  C. partial reservations: multi-item orders that fail leave every product as it was;
     concurrent multi-item orders never oversell any line
  D. duplicate orders: 8 concurrent submissions with one client_request_id -> 1 order
  E. rollback when the order insert itself fails after stock was reserved
  F. no negative stock anywhere afterwards

Items that depend on MongoDB features FerretDB lacks (atomic conditional updates,
$first / $expr) are reported as NOT VERIFIED when the backend's database is FerretDB.

Usage (TEST backend only; DB_NAME must contain "test"):
    API=http://localhost:8001/api ADMIN_EMAIL=... ADMIN_PASSWORD=... MONGO_URL=... DB_NAME=aayna_pytest \
    python scripts/verify/mongo_release_checks.py
Exit code 0 only if every applicable check passed AND nothing was NOT VERIFIED.
"""
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pymongo
import requests

API = os.environ.get("API", "http://localhost:8001/api")
DB_NAME = os.environ["DB_NAME"]
if "test" not in DB_NAME.lower():
    sys.exit(f"Refusing to run: DB_NAME={DB_NAME!r} is not a test database")
db = pymongo.MongoClient(os.environ["MONGO_URL"])[DB_NAME]
build = db.command("buildInfo")
FERRET = "ferretdbVersion" in build
ENGINE = f"FerretDB {build['ferretdbVersion']}" if FERRET else f"MongoDB {build.get('version')}"
print(f"database engine: {ENGINE}\n")

results = []  # (name, status) status in PASS/FAIL/NOT VERIFIED


def rec(name, ok, detail="", needs_mongo=False):
    status = "PASS" if ok else ("NOT VERIFIED" if (needs_mongo and FERRET) else "FAIL")
    results.append((name, status))
    print(f"{status:12s} {name}" + (f"  — {detail}" if detail else ""))


s = requests.Session()
TOKEN = s.post(f"{API}/admin/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}).json()["token"]
H = {"Authorization": f"Bearer {TOKEN}"}
tag = uuid.uuid4().hex[:6]


def product(stock, alert=3, status=None, price=200):
    body = {"product_name": f"REL {tag} {uuid.uuid4().hex[:4]}", "sku": f"REL-{uuid.uuid4().hex[:8]}", "category_slug": "earrings",
            "selling_price": price, "stock_quantity": stock, "low_stock_alert": alert}
    if status:
        body["status"] = status
    r = s.post(f"{API}/admin/products", json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def checkout(items, phone="01700000021", rid=None):
    return requests.post(f"{API}/checkout", json={
        "customer_name": "Release QA", "customer_phone": phone, "district": "Dhaka",
        "delivery_address": "House 21, Road 2, Test Area", "payment_method": "cod",
        "items": items, "client_request_id": rid or uuid.uuid4().hex}, timeout=60)


def stock(p):
    return db.products.find_one({"id": p["id"]})["stock_quantity"]


# ------------------------------------------------------------------ A. aggregations
phone_a = f"0171{uuid.uuid4().int % 10**7:07d}"
pa = product(10)
o1 = checkout([{"product_id": pa["id"], "quantity": 1}], phone=phone_a).json()
o2 = checkout([{"product_id": pa["id"], "quantity": 2}], phone=phone_a).json()
s.put(f"{API}/admin/orders/{o2['order_number']}", json={"order_status": "Cancelled"}, headers=H)
product(1, alert=3)                    # low stock (counted)
product(2, alert=3, status="draft")    # low stock but draft (not counted)

r = s.get(f"{API}/admin/dashboard", headers=H)
if r.status_code == 200:
    d = r.json()
    day0 = (datetime.now(timezone.utc) + timedelta(hours=6)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=6)
    todays = [o for o in db.orders.find({}) if o["created_at"] >= day0.isoformat()]
    exp_sales = sum(o["total_amount"] for o in todays if o.get("order_status") != "Cancelled")
    exp_low = sum(1 for p in db.products.find({}) if p.get("status") != "draft"
                  and p.get("low_stock_alert") is not None and p.get("stock_quantity", 0) <= p["low_stock_alert"])
    keys = {"todays_orders", "new_orders", "total_sales_today", "low_stock_count", "total_orders", "total_customers"}
    rec("dashboard: keys present", keys <= set(d), str(sorted(keys - set(d))))
    rec("dashboard: today's orders and sales (cancelled excluded) match raw data",
        d["todays_orders"] == len(todays) and abs(d["total_sales_today"] - exp_sales) < 0.01,
        f"api={d['todays_orders']}/{d['total_sales_today']} raw={len(todays)}/{exp_sales}")
    rec("dashboard: low_stock_count matches raw data (drafts excluded)", d["low_stock_count"] == exp_low, f"api={d['low_stock_count']} raw={exp_low}")
else:
    rec("dashboard aggregation", False, f"HTTP {r.status_code} {r.text[:80]}", needs_mongo=True)

r = s.get(f"{API}/admin/inventory", params={"low_only": "true"}, headers=H)
if r.status_code == 200:
    got = {p["id"] for p in r.json()}
    exp = {p["id"] for p in db.products.find({}) if p.get("status") != "draft"
           and p.get("low_stock_alert") is not None and p.get("stock_quantity", 0) <= p["low_stock_alert"]}
    rec("inventory low_only: exactly the non-draft products at/below their alert", got == exp, f"api={len(got)} raw={len(exp)}")
    rec("inventory: no cost_price in response", "cost_price" not in r.text)
else:
    rec("inventory low-stock filter", False, f"HTTP {r.status_code}", needs_mongo=True)

r = s.get(f"{API}/admin/customers", params={"search": phone_a[-7:]}, headers=H)
if r.status_code == 200 and r.json():
    c = r.json()[0]
    exp_last = max(o["created_at"] for o in db.orders.find({"customer_id": c["id"]}))
    rec("customers list: last_order_date is the newest order", c.get("last_order_date") == exp_last, f"api={c.get('last_order_date')} raw={exp_last}")
    det = s.get(f"{API}/admin/customers/{c['id']}", headers=H).json()
    nums = [o["order_number"] for o in det.get("orders", [])]
    rec("customer detail: all orders, newest first", set(nums) == {o1["order_number"], o2["order_number"]}
        and [o["created_at"] for o in det["orders"]] == sorted([o["created_at"] for o in det["orders"]], reverse=True), str(nums))
else:
    rec("customer list/detail aggregation", False, f"HTTP {r.status_code}", needs_mongo=True)

# ------------------------------------------------------------------ E. rollback when the order insert fails (runs before the concurrent tests)
# Force a genuine insert failure on the TEST db: unique index on order_number plus a
# placeholder that already holds the next number the counter will hand out.
existing_idx = db.orders.index_information()
already_unique = any(i.get("key") == [("order_number", 1)] and i.get("unique") for i in existing_idx.values())
dropped = [] if already_unique else [n for n, i in existing_idx.items() if i.get("key") == [("order_number", 1)]]
for n in dropped:  # the app's non-unique order_number index (TEST db only)
    db.orders.drop_index(n)
if not already_unique:
    db.orders.create_index("order_number", unique=True, name="test_unique_order_number")
counter = db.counters.find_one({"_id": "order_number"}) or {"seq": 0}
next_num = f"ORD-{1000 + counter['seq'] + 1}"
db.orders.insert_one({"order_number": next_num, "placeholder": True, "items": []})
pe = product(4)
phone_e = "01700000099"
rid_e = uuid.uuid4().hex
cust_e = db.customers.find_one({"phone": {"$regex": "1700000099$"}})
r = checkout([{"product_id": pe["id"], "quantity": 2}], phone=phone_e, rid=rid_e)
cust_after = db.customers.find_one({"phone": {"$regex": "1700000099$"}})
rec("rollback: insert failure -> HTTP 500 JSON, stock restored, no customer left behind, key released",
    r.status_code == 500 and r.headers.get("content-type", "").startswith("application/json") and stock(pe) == 4
    and (cust_after is None if cust_e is None else cust_after.get("total_orders") == cust_e.get("total_orders"))
    and db.checkout_requests.find_one({"_id": rid_e}) is None,
    f"HTTP {r.status_code} stock={stock(pe)} customer={'none' if cust_after is None else cust_after.get('total_orders')}")
db.orders.delete_one({"order_number": next_num, "placeholder": True})
r = checkout([{"product_id": pe["id"], "quantity": 2}], phone=phone_e, rid=rid_e)
rec("rollback: the same request succeeds on retry", r.status_code == 200 and stock(pe) == 2, f"HTTP {r.status_code} stock={stock(pe)}")
if not already_unique:
    db.orders.drop_index("test_unique_order_number")
if dropped:
    db.orders.create_index("order_number")  # restore the app's index on the TEST db

# ------------------------------------------------------------------ B. concurrent single-item
p3 = product(3)
with ThreadPoolExecutor(max_workers=10) as ex:
    codes = list(ex.map(lambda _: checkout([{"product_id": p3["id"], "quantity": 1}]).status_code, range(10)))
doc = db.products.find_one({"id": p3["id"]})
n_orders = db.orders.count_documents({"items.product_id": p3["id"]})
n_logs = db.inventory_logs.count_documents({"product_id": p3["id"], "change_type": "sale"})
rec("concurrency: 10 orders for 3 units -> exactly 3 orders, stock 0, out_of_stock, 3 sale logs",
    codes.count(200) == 3 and n_orders == 3 and doc["stock_quantity"] == 0 and doc["status"] == "out_of_stock" and n_logs == 3,
    f"200s={codes.count(200)} orders={n_orders} stock={doc['stock_quantity']} status={doc['status']} logs={n_logs}", needs_mongo=True)

# ------------------------------------------------------------------ C. partial reservations
pa, pb = product(5), product(1)
cust_before = db.customers.count_documents({})
r = checkout([{"product_id": pa["id"], "quantity": 2}, {"product_id": pb["id"], "quantity": 2}], phone="01700000077")
rec("partial: failing multi-item order leaves every product unchanged, no order, no customer",
    r.status_code == 400 and stock(pa) == 5 and stock(pb) == 1
    and db.orders.count_documents({"items.product_id": pa["id"]}) == 0 and db.customers.count_documents({}) == cust_before,
    f"HTTP {r.status_code} A={stock(pa)} B={stock(pb)}")
pa, pb = product(10), product(3)
with ThreadPoolExecutor(max_workers=10) as ex:
    codes = list(ex.map(lambda _: checkout([{"product_id": pa["id"], "quantity": 1}, {"product_id": pb["id"], "quantity": 1}]).status_code, range(10)))
n = db.orders.count_documents({"items.product_id": pb["id"]})
rec("partial (concurrent): 10 two-item orders, scarce item has 3 -> 3 orders, A=7, B=0",
    codes.count(200) == 3 and n == 3 and stock(pa) == 7 and stock(pb) == 0,
    f"200s={codes.count(200)} orders={n} A={stock(pa)} B={stock(pb)}", needs_mongo=True)

# ------------------------------------------------------------------ D. duplicate orders
pd = product(20)
rid = uuid.uuid4().hex
with ThreadPoolExecutor(max_workers=8) as ex:
    resps = list(ex.map(lambda _: checkout([{"product_id": pd["id"], "quantity": 1}], rid=rid), range(8)))
nums = {x.json().get("order_number") for x in resps if x.status_code == 200}
rec("idempotency: 8 concurrent submissions with one key -> exactly 1 order, all answers name it",
    db.orders.count_documents({"client_request_id": rid}) == 1 and len(nums) == 1 and all(x.status_code == 200 for x in resps),
    f"orders={db.orders.count_documents({'client_request_id': rid})} distinct numbers={nums} codes={sorted({x.status_code for x in resps})}")
rec("idempotency: stock decremented once", stock(pd) == 19, f"stock={stock(pd)}", needs_mongo=True)

# ------------------------------------------------------------------ F. global invariants
neg = db.products.count_documents({"stock_quantity": {"$lt": 0}})
rec("invariant: no product has negative stock", neg == 0, f"{neg} negative")
dupes = list(db.orders.aggregate([{"$match": {"client_request_id": {"$type": "string"}}},
                                   {"$group": {"_id": "$client_request_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
rec("invariant: no duplicate client_request_id", not dupes, f"{len(dupes)} duplicated keys")

passed = sum(1 for _, st in results if st == "PASS")
nv = [n for n, st in results if st == "NOT VERIFIED"]
failed = [n for n, st in results if st == "FAIL"]
print(f"\n{passed} passed, {len(failed)} failed, {len(nv)} NOT VERIFIED on {ENGINE}")
sys.exit(1 if failed or nv else 0)

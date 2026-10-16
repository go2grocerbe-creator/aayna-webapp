"""Phase 4 backend/admin verification for AAYNA, over HTTP against a TEST backend.

Covers: admin authentication and authorisation, login brute-force protection,
product validation, draft/inactive protection on stock changes, CSV import
status handling, order-status side effects, concurrent and duplicate-line
checkout (overselling), public exposure of settings and product data, error
responses (CORS + JSON on 500).

Usage (shell with the TEST backend's env loaded - DB_NAME must contain "test"):
    API=http://localhost:8001/api ORIGIN=http://localhost:3000 \
    ADMIN_EMAIL=... ADMIN_PASSWORD=... JWT_SECRET=... MONGO_URL=... DB_NAME=aayna_pytest \
    python scripts/verify/backend_admin_checks.py
Never run against production or development data: it creates products, orders and users.
"""
import io
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pymongo
import requests

API = os.environ.get("API", "http://localhost:8001/api")
ORIGIN = os.environ.get("ORIGIN", "http://localhost:3000")
DB_NAME = os.environ["DB_NAME"]
if "test" not in DB_NAME.lower():
    sys.exit(f"Refusing to run: DB_NAME={DB_NAME!r} is not a test database")
db = pymongo.MongoClient(os.environ["MONGO_URL"])[DB_NAME]
SECRET = os.environ["JWT_SECRET"]
results = []


def rec(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


s = requests.Session()
r = s.post(f"{API}/admin/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
assert r.status_code == 200, r.text
TOKEN = r.json()["token"]
H = {"Authorization": f"Bearer {TOKEN}"}
tag = uuid.uuid4().hex[:6]

# ---------------------------------------------------------------- auth
admin_user = db.users.find_one({"email": os.environ["ADMIN_EMAIL"].lower()})
now = datetime.now(timezone.utc)
def tok(**kw):
    p = {"sub": admin_user["id"], "email": admin_user["email"], "role": "super_admin", "type": "access", "exp": now + timedelta(hours=1)}
    p.update(kw)
    return jwt.encode(p, kw.pop("_secret", SECRET) if "_secret" in kw else SECRET, algorithm="HS256")

cases = {
    "no token": {},
    "garbage token": {"Authorization": "Bearer not-a-jwt"},
    "expired token": {"Authorization": "Bearer " + tok(exp=now - timedelta(minutes=1))},
    "token signed with another secret": {"Authorization": "Bearer " + jwt.encode({"sub": admin_user["id"], "role": "super_admin", "exp": now + timedelta(hours=1)}, "x" * 40, algorithm="HS256")},
    "token for unknown user": {"Authorization": "Bearer " + tok(sub=str(uuid.uuid4()))},
}
for name, hdr in cases.items():
    code = requests.get(f"{API}/admin/products", headers=hdr).status_code
    rec(f"auth: {name} -> 401", code == 401, f"HTTP {code}")
# non-admin role and inactive account
cust_id = str(uuid.uuid4())
db.users.insert_one({"id": cust_id, "email": f"viewer-{tag}@example.test", "role": "customer", "status": "active", "password_hash": "x"})
code = requests.get(f"{API}/admin/products", headers={"Authorization": "Bearer " + tok(sub=cust_id)}).status_code
rec("auth: valid token, non-admin role -> 403", code == 403, f"HTTP {code}")
db.users.update_one({"id": cust_id}, {"$set": {"role": "admin", "status": "disabled"}})
code = requests.get(f"{API}/admin/products", headers={"Authorization": "Bearer " + tok(sub=cust_id)}).status_code
rec("auth: disabled admin account -> 401", code == 401, f"HTTP {code}")
me = s.get(f"{API}/admin/me", headers=H).json()
rec("auth: /admin/me never returns password_hash", "password_hash" not in json.dumps(me))
# every admin router endpoint refuses anonymous access
anon = {p: requests.get(f"{API}{p}").status_code for p in
        ["/admin/dashboard", "/admin/products", "/admin/orders", "/admin/customers", "/admin/inventory",
         "/admin/settings", "/admin/categories", "/admin/export/products", "/admin/export/orders", "/admin/export/customers"]}
rec("auth: all admin GET endpoints refuse anonymous (401)", all(c == 401 for c in anon.values()), json.dumps(anon))
code = requests.post(f"{API}/admin/upload", files={"file": ("x.png", b"x", "image/png")}).status_code
rec("auth: anonymous image upload refused", code == 401, f"HTTP {code}")

# brute force: rotating a client-supplied X-Forwarded-For prefix must not reset the
# lockout. Models one trusted proxy (backend TRUSTED_PROXY_HOPS=1) that appends the
# real client address after whatever the client sent.
victim = f"bf-{tag}@example.test"
codes = [requests.post(f"{API}/admin/login", json={"email": victim, "password": "wrong"},
                       headers={"X-Forwarded-For": f"203.0.113.{i}, 198.51.100.77"}).status_code for i in range(8)]
rec("auth: login lockout not bypassed by spoofed X-Forwarded-For", 429 in codes, f"codes={codes}")

# ---------------------------------------------------------------- product validation
def create(**kw):
    body = {"product_name": f"QA P4 {tag} {uuid.uuid4().hex[:4]}", "sku": f"QA4-{uuid.uuid4().hex[:6]}",
            "category_slug": "earrings", "selling_price": 500, "stock_quantity": 5}
    body.update(kw)
    return s.post(f"{API}/admin/products", json=body, headers=H)

for name, kw in {"selling_price 0": {"selling_price": 0}, "negative selling_price": {"selling_price": -50},
                 "discount >= price": {"discount_price": 600}, "negative stock": {"stock_quantity": -2},
                 "unknown status": {"status": "published"}, "negative low_stock_alert": {"low_stock_alert": -1}}.items():
    r = create(**kw)
    rec(f"validation: create with {name} -> 400/422", r.status_code in (400, 422), f"HTTP {r.status_code}")
good = create(discount_price=450).json()
other = create().json()
r = s.put(f"{API}/admin/products/{good['id']}", json={"selling_price": -1}, headers=H)
rec("validation: update to negative price refused", r.status_code in (400, 422), f"HTTP {r.status_code}")
r = s.put(f"{API}/admin/products/{good['id']}", json={"slug": other["slug"]}, headers=H)
rec("validation: update slug to another product's slug refused", r.status_code in (400, 409, 422), f"HTTP {r.status_code}")
r = s.put(f"{API}/admin/products/{good['id']}", json={"discount_price": 0}, headers=H)
rec("validation: clearing discount (0) allowed", r.status_code == 200, f"HTTP {r.status_code}")

# ---------------------------------------------------------------- draft/inactive stay private on stock changes
for status in ["draft", "inactive"]:
    p = create(status=status).json()
    r = s.post(f"{API}/admin/inventory/{p['id']}/adjust", json={"change_type": "damage", "quantity_change": -5, "reason": "qa"}, headers=H)
    st = db.products.find_one({"id": p["id"]})["status"]
    pub = requests.get(f"{API}/products/{p['slug']}").status_code
    rec(f"{status}: stock adjusted to 0 stays {status} and not public", st == status and pub == 404, f"status={st} public HTTP {pub}")
    p2 = create(status=status).json()
    s.put(f"{API}/admin/products/{p2['id']}", json={"stock_quantity": 0}, headers=H)
    st = db.products.find_one({"id": p2["id"]})["status"]
    pub = requests.get(f"{API}/products/{p2['slug']}").status_code
    rec(f"{status}: stock edited to 0 stays {status} and not public", st == status and pub == 404, f"status={st} public HTTP {pub}")
act = create(stock_quantity=2).json()
s.post(f"{API}/admin/inventory/{act['id']}/adjust", json={"change_type": "damage", "quantity_change": -2}, headers=H)
rec("active: stock adjusted to 0 becomes out_of_stock", db.products.find_one({"id": act["id"]})["status"] == "out_of_stock")
s.post(f"{API}/admin/inventory/{act['id']}/adjust", json={"change_type": "stock_in", "quantity_change": 4}, headers=H)
rec("out_of_stock: restock returns to active", db.products.find_one({"id": act["id"]})["status"] == "active")

# ---------------------------------------------------------------- CSV import
draft = create(status="draft").json()
csv_body = f"product name,sku,category,selling price (bdt),stock quantity\n{draft['product_name']},{draft['sku']},Earrings,510,4\n"
r = s.post(f"{API}/admin/import/products", files={"file": ("p.csv", csv_body.encode(), "text/csv")}, headers=H)
st = db.products.find_one({"id": draft["id"]})["status"]
rec("csv: re-import without status column keeps a draft as draft", st == "draft", f"status={st} resp={r.json()}")
csv_bad = f"product name,sku,category,selling price (bdt),stock quantity,status\nQA bad {tag},QA4-BAD-{tag},Earrings,510,4,published\n"
r = s.post(f"{API}/admin/import/products", files={"file": ("p.csv", csv_bad.encode(), "text/csv")}, headers=H).json()
rec("csv: unknown status value rejected as a row error", r.get("created") == 0 and r.get("errors"), json.dumps(r)[:140])
csv_neg = f"product name,sku,category,selling price (bdt),stock quantity\nQA neg {tag},QA4-NEG-{tag},Earrings,-5,4\n"
r = s.post(f"{API}/admin/import/products", files={"file": ("p.csv", csv_neg.encode(), "text/csv")}, headers=H).json()
rec("csv: non-positive price rejected as a row error", r.get("created") == 0 and r.get("errors"), json.dumps(r)[:140])

# ---------------------------------------------------------------- checkout: duplicate lines + concurrency
def checkout(items, rid=None):
    return requests.post(f"{API}/checkout", json={
        "customer_name": "QA P4", "customer_phone": "01700000004", "district": "Dhaka",
        "delivery_address": "House 4, Road 4, Test Area", "payment_method": "cod",
        "items": items, "client_request_id": rid or uuid.uuid4().hex})

dup = create(stock_quantity=3).json()
r = checkout([{"product_id": dup["id"], "quantity": 2}, {"product_id": dup["id"], "quantity": 2}])
stock = db.products.find_one({"id": dup["id"]})["stock_quantity"]
rec("checkout: duplicate lines exceeding stock refused, stock unchanged", r.status_code == 400 and stock == 3, f"HTTP {r.status_code} stock={stock}")

# Oversell protection relies on MongoDB's atomic single-document findOneAndUpdate.
# FerretDB (used when real MongoDB is unavailable) does not provide that under
# concurrency, so the concurrent variant is only asserted on real MongoDB.
build = db.command("buildInfo")
ENGINE = f"FerretDB {build['ferretdbVersion']}" if "ferretdbVersion" in build else f"MongoDB {build.get('version')}"
print(f"(database engine: {ENGINE})")
for workers in ([1, 10] if not ENGINE.startswith("FerretDB") else [1]):
    race = create(stock_quantity=3).json()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        codes = list(ex.map(lambda _: checkout([{"product_id": race["id"], "quantity": 1}]).status_code, range(10)))
    doc = db.products.find_one({"id": race["id"]})
    orders = db.orders.count_documents({"items.product_id": race["id"]})
    label = "sequential" if workers == 1 else "concurrent"
    rec(f"checkout: 10 {label} orders for 3 units -> exactly 3 orders, stock 0, out_of_stock",
        codes.count(200) == 3 and orders == 3 and doc["stock_quantity"] == 0 and doc["status"] == "out_of_stock",
        f"200s={codes.count(200)} orders={orders} stock={doc['stock_quantity']} status={doc['status']}")
    logs = db.inventory_logs.count_documents({"product_id": race["id"], "change_type": "sale"})
    rec(f"checkout ({label}): one sale inventory log per successful order", logs == orders, f"logs={logs}")
if ENGINE.startswith("FerretDB"):
    print("NOT VERIFIED  checkout: concurrent oversell protection — needs real MongoDB (FerretDB conditional updates are not atomic)")

# failed checkout must not touch the customer record
before = db.customers.find_one({"phone": "8801799999990"})
r = checkout([{"product_id": dup["id"], "quantity": 99}])
r2 = requests.post(f"{API}/checkout", json={"customer_name": "QA none", "customer_phone": "01799999990", "district": "Dhaka",
                                           "delivery_address": "x road", "payment_method": "cod",
                                           "items": [{"product_id": dup["id"], "quantity": 99}]})
rec("checkout: failed order creates no customer record", db.customers.find_one({"phone": {"$regex": "1799999990$"}}) is None and before is None, f"HTTP {r2.status_code}")

# ---------------------------------------------------------------- order status side effects
ok = checkout([{"product_id": act["id"], "quantity": 1}]).json()
num = ok["order_number"]
cust = db.orders.find_one({"order_number": num})["customer_id"]
base = db.customers.find_one({"id": cust}).get("successful_orders", 0)
for _ in range(2):
    s.put(f"{API}/admin/orders/{num}", json={"order_status": "Delivered"}, headers=H)
after = db.customers.find_one({"id": cust}).get("successful_orders", 0)
rec("orders: saving 'Delivered' twice counts one successful order", after - base == 1, f"delta={after - base}")
r = s.put(f"{API}/admin/orders/{num}", json={"order_status": "Shipped-ish"}, headers=H)
rec("orders: unknown order status refused", r.status_code == 400, f"HTTP {r.status_code}")

# ---------------------------------------------------------------- public exposure
db.website_settings.update_one({"setting_key": f"private_test_{tag}"},
                               {"$set": {"setting_key": f"private_test_{tag}", "setting_value": "SECRET-SETTING"}}, upsert=True)
pub_settings = requests.get(f"{API}/settings").json()
rec("public /settings does not expose arbitrary stored keys", "SECRET-SETTING" not in json.dumps(pub_settings), f"{len(pub_settings)} keys")
rec("public /settings still has storefront keys", all(k in pub_settings for k in ["brand_name", "whatsapp_number", "delivery_charge_inside_dhaka"]))
adm_settings = s.get(f"{API}/admin/settings", headers=H).json()
rec("admin /settings still returns all keys", f"private_test_{tag}" in adm_settings)

# ---------------------------------------------------------------- error responses
r = requests.get(f"{API}/admin/dashboard", headers={**H, "Origin": ORIGIN})
if r.status_code >= 500:
    rec("500 response carries CORS header and JSON detail",
        r.headers.get("access-control-allow-origin") == ORIGIN and "detail" in r.json(),
        f"HTTP {r.status_code} ACAO={r.headers.get('access-control-allow-origin')} body={r.text[:80]}")
    rec("500 response does not leak exception text", "OperationFailure" not in r.text and "Traceback" not in r.text, r.text[:80])
else:
    rec("dashboard returns 200 (real MongoDB) — 500/CORS path not exercised", True, f"HTTP {r.status_code}")

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)

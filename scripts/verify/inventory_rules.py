"""Inventory/purchase safety checks for AAYNA, run over HTTP against a TEST backend.

Verifies:
  * draft / inactive products are invisible on the storefront and cannot be
    validated in a cart or bought at checkout, even when the product id is known;
  * active products can be bought, stock decrements by the ordered quantity,
    overselling is refused, and selling out flips status to out_of_stock;
  * admin-only fields (cost_price, internal_notes, supplier/margin data,
    price_is_temporary) never appear in public product, category or order responses;
  * admin endpoints refuse unauthenticated requests.

Usage (shell with the TEST backend's env loaded - DB_NAME must contain "test"):
    API=http://localhost:8001/api ADMIN_EMAIL=... ADMIN_PASSWORD=... \
    MONGO_URL=... DB_NAME=aayna_pytest python scripts/verify/inventory_rules.py
Never run against production: it creates products and orders.
"""
import json
import os
import sys
import uuid

import pymongo
import requests

API = os.environ.get("API", "http://localhost:8001/api")
DB_NAME = os.environ["DB_NAME"]
if "test" not in DB_NAME.lower():
    sys.exit(f"Refusing to run: DB_NAME={DB_NAME!r} is not a test database")
db = pymongo.MongoClient(os.environ["MONGO_URL"])[DB_NAME]

PRIVATE = ["cost_price", "internal_notes", "supplier_url", "supplier_price", "landed_cost",
           "purchase_cost", "margin", "price_is_temporary", "SECRET-INTERNAL"]
results = []


def rec(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def leaks(obj):
    text = json.dumps(obj)
    return [k for k in PRIVATE if k in text]


s = requests.Session()
r = s.post(f"{API}/admin/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
assert r.status_code == 200, r.text
H = {"Authorization": f"Bearer {r.json()['token']}"} if "token" in r.json() else {}

# Admin auth required
for path in ["/admin/products", "/admin/orders", "/admin/customers", "/admin/dashboard"]:
    code = requests.get(f"{API}{path}").status_code
    rec(f"unauthenticated GET {path} refused", code in (401, 403), f"HTTP {code}")

tag = uuid.uuid4().hex[:6]


def make(status, stock=5, price=500):
    payload = {"product_name": f"QA {status} {tag}", "sku": f"QA-{status[:3].upper()}-{tag}",
               "category_slug": "earrings", "selling_price": price, "stock_quantity": stock,
               "cost_price": 123, "status": status, "short_description": "QA fixture"}
    r = s.post(f"{API}/admin/products", json=payload, headers=H)
    assert r.status_code in (200, 201), r.text
    p = r.json()
    # Simulate BuyOS/importer private fields directly on the TEST db.
    db.products.update_one({"id": p["id"]}, {"$set": {
        "internal_notes": "SECRET-INTERNAL note", "supplier_url": "https://supplier.example/x",
        "margin": 0.6, "landed_cost": 140, "price_is_temporary": True}})
    return p


def checkout(pid, qty=1):
    return requests.post(f"{API}/checkout", json={
        "customer_name": "QA Rules", "customer_phone": "01700000000", "district": "Dhaka",
        "delivery_address": "House 1, Road 1, Test Area", "payment_method": "cod",
        "items": [{"product_id": pid, "quantity": qty}], "client_request_id": uuid.uuid4().hex})


# ---- draft & inactive ----
for status in ["draft", "inactive"]:
    p = make(status)
    slug = p["slug"]
    rec(f"{status}: product detail is 404", requests.get(f"{API}/products/{slug}").status_code == 404)
    listed = requests.get(f"{API}/products", params={"search": f"QA {status} {tag}"}).json()
    rec(f"{status}: not in public product list", all(x["id"] != p["id"] for x in listed), f"{len(listed)} hits")
    cv = requests.post(f"{API}/cart/validate", json={"items": [{"product_id": p["id"], "quantity": 1}]}).json()
    line = (cv.get("lines") or cv.get("items") or [{}])[0]
    rec(f"{status}: cart/validate marks unavailable", line.get("available") is False, json.dumps(line)[:120])
    r = checkout(p["id"])
    rec(f"{status}: checkout by known id refused", r.status_code == 400, f"HTTP {r.status_code} {r.text[:80]}")
    after = db.products.find_one({"id": p["id"]})
    rec(f"{status}: stock untouched", after["stock_quantity"] == 5 and after["status"] == status)

# ---- active: stock handling ----
p = make("active", stock=3, price=700)
d = requests.get(f"{API}/products/{p['slug']}").json()
rec("active: public detail has no private fields", not leaks(d), f"leaks={leaks(d)}")
lst = requests.get(f"{API}/products").json()
rec("public product list has no private fields", not leaks(lst), f"leaks={leaks(lst)}")
cats = requests.get(f"{API}/categories").json()
rec("public categories have no private fields", not leaks(cats))

r = checkout(p["id"], 2)
rec("active: checkout qty 2 succeeds", r.status_code in (200, 201), f"HTTP {r.status_code}")
order = r.json()
rec("order response has no private fields", not leaks(order), f"leaks={leaks(order)}")
num = order.get("order_number") or order.get("order", {}).get("order_number")
after = db.products.find_one({"id": p["id"]})
rec("stock decremented 3 -> 1", after["stock_quantity"] == 1, f"stock={after['stock_quantity']}")

r = checkout(p["id"], 2)
after = db.products.find_one({"id": p["id"]})
rec("oversell (qty 2 of 1 left) refused, stock unchanged", r.status_code == 400 and after["stock_quantity"] == 1,
    f"HTTP {r.status_code}, stock={after['stock_quantity']}")

r = checkout(p["id"], 1)
after = db.products.find_one({"id": p["id"]})
rec("last unit sells; status flips to out_of_stock", r.status_code in (200, 201) and after["stock_quantity"] == 0
    and after["status"] == "out_of_stock", f"stock={after['stock_quantity']} status={after['status']}")
r = checkout(p["id"], 1)
rec("out_of_stock product cannot be bought", r.status_code == 400, f"HTTP {r.status_code}")

if num:
    no_tok = requests.get(f"{API}/orders/{num}")
    rec("order confirmation without token is 404", no_tok.status_code == 404, f"HTTP {no_tok.status_code}")
    pub = requests.get(f"{API}/orders/{num}", params={"token": order.get("order_confirmation_token")})
    rec("order confirmation (with token) has no private fields",
        pub.status_code == 200 and not leaks(pub.json()), f"HTTP {pub.status_code} leaks={leaks(pub.json())}")

# ---- admin safeguard: real price clears temporary-price marker ----
r = s.put(f"{API}/admin/products/{p['id']}", json={"selling_price": 950}, headers=H)
after = db.products.find_one({"id": p["id"]})
rec("admin price change clears price_is_temporary", r.status_code == 200 and after.get("price_is_temporary") is False,
    f"HTTP {r.status_code} flag={after.get('price_is_temporary')}")
# admin restock flips out_of_stock back to active
r = s.put(f"{API}/admin/products/{p['id']}", json={"stock_quantity": 4}, headers=H)
after = db.products.find_one({"id": p["id"]})
rec("admin restock returns product to active", after["status"] == "active" and after["stock_quantity"] == 4,
    f"status={after['status']}")
# admin restock must NOT publish a draft
dr = db.products.find_one({"sku": f"QA-DRA-{tag}"})
s.put(f"{API}/admin/products/{dr['id']}", json={"stock_quantity": 9}, headers=H)
dr2 = db.products.find_one({"id": dr["id"]})
rec("admin restock keeps a draft as draft", dr2["status"] == "draft", f"status={dr2['status']}")

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)

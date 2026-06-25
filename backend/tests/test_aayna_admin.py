"""AAYNA Milestone 2 backend tests — admin auth + dashboard + products + categories +
orders + inventory + customers + settings + CSV export/import + storage upload.

Also runs a regression smoke against M1 storefront endpoints.
"""
import io
import os
import uuid
import time
import csv
import pytest
import requests

try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
except Exception:
    pass

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

# Read admin credentials from the environment (no hardcoded production secrets).
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@aayna.xyz").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "token" in d and isinstance(d["token"], str) and len(d["token"]) > 10
    assert d["user"]["role"] == "super_admin"
    assert d["user"]["email"] == ADMIN_EMAIL
    return d["token"]


@pytest.fixture(scope="module")
def admin(session, admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


# ============================================================
# AUTH
# ============================================================
class TestAdminAuth:
    def test_login_success(self, session):
        r = session.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["role"] == "super_admin"
        # no password leak
        assert "password_hash" not in d["user"]

    def test_login_wrong_password(self, session):
        r = session.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"}, timeout=30)
        assert r.status_code == 401

    def test_login_unknown_email(self, session):
        r = session.post(f"{API}/admin/login", json={"email": "nobody@aayna.xyz", "password": "x"}, timeout=30)
        assert r.status_code == 401

    def test_login_generic_error_message(self, session):
        # Must not reveal whether the email or the password was wrong.
        r1 = session.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": "definitely-wrong"}, timeout=30)
        r2 = session.post(f"{API}/admin/login", json={"email": f"ghost-{uuid.uuid4().hex}@x.com", "password": "y"}, timeout=30)
        assert r1.status_code == 401 and r2.status_code == 401
        assert r1.json().get("detail") == r2.json().get("detail")

    def test_login_rate_limit_lockout(self, session):
        # Use a unique email so we don't lock out the real admin account.
        email = f"bruteforce-{uuid.uuid4().hex}@example.com"
        last = None
        for _ in range(5):
            last = session.post(f"{API}/admin/login", json={"email": email, "password": "wrong"}, timeout=30)
            assert last.status_code == 401
        # After 5 failures the next attempt is temporarily blocked.
        blocked = session.post(f"{API}/admin/login", json={"email": email, "password": "wrong"}, timeout=30)
        assert blocked.status_code == 429
        assert "try again" in blocked.json().get("detail", "").lower()

    def test_me_requires_auth(self, session):
        r = session.get(f"{API}/admin/me", timeout=30)
        assert r.status_code == 401

    def test_me_with_token(self, admin):
        r = admin.get(f"{API}/admin/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == ADMIN_EMAIL
        assert d["role"] == "super_admin"

    def test_admin_route_without_token(self, session):
        r = session.get(f"{API}/admin/dashboard", timeout=30)
        assert r.status_code == 401

    def test_invalid_token(self, session):
        r = session.get(f"{API}/admin/dashboard", headers={"Authorization": "Bearer abc.def.ghi"}, timeout=30)
        assert r.status_code == 401


# ============================================================
# DASHBOARD
# ============================================================
class TestDashboard:
    def test_dashboard_keys(self, admin):
        r = admin.get(f"{API}/admin/dashboard", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in [
            "todays_orders", "new_orders", "confirmed_orders", "packed_orders",
            "delivered_orders", "cancelled_orders", "total_sales_today",
            "low_stock_count", "failed_notifications", "total_orders",
            "total_products", "total_customers",
        ]:
            assert k in d, f"missing key {k}"
        assert isinstance(d["total_products"], int) and d["total_products"] >= 10


# ============================================================
# PRODUCTS
# ============================================================
class TestProducts:
    def test_admin_list_products_has_cost(self, admin):
        r = admin.get(f"{API}/admin/products", timeout=30)
        assert r.status_code == 200
        ps = r.json()
        assert len(ps) >= 10
        assert any("cost_price" in p for p in ps)

    def test_filter_search(self, admin):
        r = admin.get(f"{API}/admin/products?search=pearl", timeout=30)
        assert r.status_code == 200

    def test_create_edit_delete_no_history(self, admin):
        sku = f"TEST-SKU-{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "product_name": "TEST_AdminProduct",
            "sku": sku,
            "category_slug": "earrings",
            "selling_price": 999,
            "stock_quantity": 5,
            "is_new_arrival": True,
        }
        r = admin.post(f"{API}/admin/products", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["product_name"] == "TEST_AdminProduct"
        assert d["sku"] == sku
        assert d["is_new_arrival"] is True
        assert d["status"] == "active"
        pid = d["id"]
        slug = d["slug"]

        # Storefront should show it (active)
        sf = requests.get(f"{API}/products/{slug}", timeout=30)
        assert sf.status_code == 200

        # Edit: change price, discount, stock
        upd = admin.put(f"{API}/admin/products/{pid}", json={
            "selling_price": 1200, "discount_price": 1100,
            "stock_quantity": 3, "is_featured": True,
        }, timeout=30)
        assert upd.status_code == 200, upd.text
        u = upd.json()
        assert u["selling_price"] == 1200
        assert u["discount_price"] == 1100
        assert u["stock_quantity"] == 3
        assert u["is_featured"] is True

        # GET to verify persistence
        g = admin.get(f"{API}/admin/products/{pid}", timeout=30).json()
        assert g["selling_price"] == 1200 and g["stock_quantity"] == 3

        # Delete (no order history) => deleted
        de = admin.delete(f"{API}/admin/products/{pid}", timeout=30)
        assert de.status_code == 200
        assert de.json().get("deleted") is True

        # 404 after delete
        g2 = admin.get(f"{API}/admin/products/{pid}", timeout=30)
        assert g2.status_code == 404

    def test_delete_with_history_deactivates(self, admin, session):
        # Create product, place an order against it, then attempt delete -> deactivate
        sku = f"TEST-HIST-{uuid.uuid4().hex[:6].upper()}"
        payload = {"product_name": "TEST_HistProduct", "sku": sku,
                   "category_slug": "earrings", "selling_price": 500, "stock_quantity": 5}
        cr = admin.post(f"{API}/admin/products", json=payload, timeout=30)
        assert cr.status_code == 200
        pid = cr.json()["id"]

        # Place order via public checkout
        order = session.post(f"{API}/checkout", json={
            "customer_name": "TEST History",
            "customer_phone": "01712345678",
            "district": "Dhaka",
            "delivery_address": "TEST address",
            "payment_method": "cod",
            "items": [{"product_id": pid, "quantity": 1}],
            "client_request_id": f"TEST_{uuid.uuid4()}",
        }, timeout=60)
        assert order.status_code == 200, order.text

        de = admin.delete(f"{API}/admin/products/{pid}", timeout=30)
        assert de.status_code == 200
        body = de.json()
        assert body.get("deactivated") is True and body.get("deleted") is False
        g = admin.get(f"{API}/admin/products/{pid}", timeout=30).json()
        assert g["status"] == "inactive"


# ============================================================
# CATEGORIES
# ============================================================
class TestCategories:
    def test_list_with_counts(self, admin):
        r = admin.get(f"{API}/admin/categories", timeout=30)
        assert r.status_code == 200
        cats = r.json()
        assert any(c.get("product_count", 0) > 0 for c in cats)

    def test_create_and_update_category(self, admin):
        name = f"TEST_Cat_{uuid.uuid4().hex[:5]}"
        r = admin.post(f"{API}/admin/categories", json={"name": name, "description": "test", "sort_order": 99}, timeout=30)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        # update name and deactivate
        u = admin.put(f"{API}/admin/categories/{cid}", json={"name": name + "_upd", "status": "inactive"}, timeout=30)
        assert u.status_code == 200
        assert u.json()["status"] == "inactive"
        # Public categories list should NOT show inactive
        pub = requests.get(f"{API}/categories", timeout=30).json()
        assert all(c["id"] != cid for c in pub)


# ============================================================
# ORDERS
# ============================================================
class TestOrders:
    @pytest.fixture(scope="class")
    def test_order_number(self, session):
        prods = session.get(f"{API}/products", timeout=30).json()
        p = next(p for p in prods if p.get("stock_quantity", 0) > 0)
        r = session.post(f"{API}/checkout", json={
            "customer_name": "TEST OrderFlow",
            "customer_phone": "01712345678",
            "district": "Dhaka",
            "delivery_address": "TEST OrderFlow Addr",
            "payment_method": "cod",
            "items": [{"product_id": p["id"], "quantity": 1}],
            "client_request_id": f"TEST_{uuid.uuid4()}",
        }, timeout=60)
        assert r.status_code == 200
        return r.json()["order_number"]

    def test_list_orders(self, admin):
        r = admin.get(f"{API}/admin/orders", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_update_order_full_flow(self, admin, test_order_number):
        r = admin.get(f"{API}/admin/orders/{test_order_number}", timeout=30)
        assert r.status_code == 200
        o = r.json()
        assert "notifications" in o

        # Update to Confirmed
        u = admin.put(f"{API}/admin/orders/{test_order_number}", json={
            "order_status": "Confirmed",
            "courier_name": "Pathao",
            "courier_tracking_code": "TRACK-123",
            "admin_note": "Test note",
        }, timeout=30)
        assert u.status_code == 200, u.text
        d = u.json()
        assert d["order_status"] == "Confirmed"
        assert d["courier_name"] == "Pathao"
        assert d["courier_tracking_code"] == "TRACK-123"
        assert d["admin_note"] == "Test note"

        # Reflected on public track
        track = requests.post(f"{API}/track", json={"order_number": test_order_number}, timeout=30).json()
        assert any(o["order_status"] == "Confirmed" for o in track)

    def test_update_order_invalid_status(self, admin, test_order_number):
        r = admin.put(f"{API}/admin/orders/{test_order_number}", json={"order_status": "Invalid"}, timeout=30)
        assert r.status_code == 400


# ============================================================
# INVENTORY
# ============================================================
class TestInventory:
    def test_list_and_adjust(self, admin):
        r = admin.get(f"{API}/admin/inventory", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert len(items) > 0
        # cost_price hidden in inventory listing
        for p in items:
            assert "cost_price" not in p
        pid = items[0]["id"]
        prev = items[0]["stock_quantity"]
        adj = admin.post(f"{API}/admin/inventory/{pid}/adjust", json={
            "change_type": "stock_in", "quantity_change": 2, "reason": "TEST stock_in"
        }, timeout=30)
        assert adj.status_code == 200, adj.text
        assert adj.json()["stock_quantity"] == prev + 2

        # Negative
        adj2 = admin.post(f"{API}/admin/inventory/{pid}/adjust", json={
            "change_type": "adjustment", "quantity_change": -2, "reason": "TEST revert"
        }, timeout=30)
        assert adj2.status_code == 200
        assert adj2.json()["stock_quantity"] == prev

        logs = admin.get(f"{API}/admin/inventory/{pid}/logs", timeout=30)
        assert logs.status_code == 200
        assert len(logs.json()) >= 2

    def test_low_stock_only(self, admin):
        r = admin.get(f"{API}/admin/inventory?low_only=true", timeout=30)
        assert r.status_code == 200


# ============================================================
# CUSTOMERS
# ============================================================
class TestCustomers:
    def test_list_and_detail(self, admin):
        r = admin.get(f"{API}/admin/customers", timeout=30)
        assert r.status_code == 200
        cs = r.json()
        if cs:
            cid = cs[0]["id"]
            d = admin.get(f"{API}/admin/customers/{cid}", timeout=30)
            assert d.status_code == 200
            assert "orders" in d.json()


# ============================================================
# SETTINGS
# ============================================================
class TestSettings:
    def test_get_settings(self, admin):
        r = admin.get(f"{API}/admin/settings", timeout=30)
        assert r.status_code == 200

    def test_update_settings_reflects_public(self, admin):
        new_ann = f"TEST announcement {uuid.uuid4().hex[:5]}"
        r = admin.put(f"{API}/admin/settings", json={
            "announcement_bar_text": new_ann,
            "delivery_charge_inside_dhaka": 80,
        }, timeout=30)
        assert r.status_code == 200
        # Reflected on public settings
        pub = requests.get(f"{API}/settings", timeout=30).json()
        # Key naming may vary; check value present in any string value of dict
        flat = " ".join(str(v) for v in pub.values())
        assert new_ann in flat or pub.get("announcement_bar_text") == new_ann


# ============================================================
# EXPORT / IMPORT CSV
# ============================================================
class TestCSV:
    def test_export_products(self, admin):
        r = admin.get(f"{API}/admin/export/products", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "product_name" in r.text.splitlines()[0]

    def test_export_orders(self, admin):
        r = admin.get(f"{API}/admin/export/orders", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_customers(self, admin):
        r = admin.get(f"{API}/admin/export/customers", timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_import_products(self, admin):
        sku = f"TEST-IMP-{uuid.uuid4().hex[:5].upper()}"
        csv_text = (
            "Product Name,SKU,Category,Selling Price (BDT),Stock Quantity,Status\n"
            f"TEST Imported,{sku},earrings,750,4,active\n"
        )
        files = {"file": ("import.csv", csv_text, "text/csv")}
        # Override Content-Type by using a fresh requests call with token from admin
        token = admin.headers["Authorization"]
        r = requests.post(f"{API}/admin/import/products", files=files,
                          headers={"Authorization": token}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["created"] + d["updated"] >= 1
        assert isinstance(d["errors"], list)


# ============================================================
# STORAGE UPLOAD
# ============================================================
class TestStorageUpload:
    def test_upload_requires_admin(self):
        # tiny png
        png = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
            "890000000A49444154789C6300010000000500010D0A2DB40000000049454E44"
            "AE426082"
        )
        files = {"file": ("tiny.png", png, "image/png")}
        r = requests.post(f"{API}/admin/upload", files=files, timeout=60)
        assert r.status_code == 401

    def test_upload_returns_path_and_public_get(self, admin):
        png = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
            "890000000A49444154789C6300010000000500010D0A2DB40000000049454E44"
            "AE426082"
        )
        files = {"file": ("tiny.png", png, "image/png")}
        token = admin.headers["Authorization"]
        r = requests.post(f"{API}/admin/upload", files=files,
                          headers={"Authorization": token}, timeout=60)
        if r.status_code != 200:
            pytest.skip(f"Object storage not configured (status={r.status_code}): {r.text[:200]}")
        d = r.json()
        # response shape: { url or path }
        assert isinstance(d, dict)
        path = d.get("path") or d.get("url") or d.get("file_path")
        assert path, f"no path/url in upload response: {d}"
        # Public fetch (no auth)
        if path.startswith("http"):
            public = path
        else:
            rel = path.lstrip("/")
            if rel.startswith("api/files/"):
                public = f"{BASE_URL}/{rel}"
            else:
                public = f"{API}/files/{rel.split('files/')[-1]}"
        g = requests.get(public, timeout=30)
        assert g.status_code == 200


# ============================================================
# M1 REGRESSION
# ============================================================
class TestM1Regression:
    def test_products_no_cost_leak(self):
        r = requests.get(f"{API}/products", timeout=30)
        assert r.status_code == 200
        ps = r.json()
        # M1 said exactly 10; admin tests above may have created some inactive/active
        # Just ensure all listed products are sanitized
        for p in ps:
            assert "cost_price" not in p
            assert "internal_notes" not in p
            assert "_id" not in p

    def test_districts_and_settings_public(self):
        d = requests.get(f"{API}/districts", timeout=30)
        assert d.status_code == 200 and len(d.json()) == 64
        s = requests.get(f"{API}/settings", timeout=30)
        assert s.status_code == 200

    def test_guest_checkout_still_works(self):
        prods = requests.get(f"{API}/products", timeout=30).json()
        p = next(p for p in prods if p.get("stock_quantity", 0) > 0)
        r = requests.post(f"{API}/checkout", json={
            "customer_name": "TEST M1 Regression",
            "customer_phone": "01712345678",
            "district": "Dhaka",
            "delivery_address": "TEST regression addr",
            "payment_method": "cod",
            "items": [{"product_id": p["id"], "quantity": 1}],
            "client_request_id": f"TEST_{uuid.uuid4()}",
        }, timeout=60)
        assert r.status_code == 200
        assert r.json()["order_number"].startswith("ORD-")

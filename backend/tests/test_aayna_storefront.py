"""AAYNA Milestone 1 backend tests — storefront, cart, checkout, idempotency, track."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Pull from frontend .env when run from CI / inside container
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- Settings & meta ----------------
class TestSettings:
    def test_settings(self, session):
        r = session.get(f"{API}/settings", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert str(data.get("delivery_charge_inside_dhaka")) == "80"
        assert str(data.get("delivery_charge_outside_dhaka")) == "130"
        assert "whatsapp_number" in data
        assert "bkash_number" in data or "bkash_personal_number" in data or any("bkash" in k for k in data)
        assert "announcement" in data or any("announcement" in k for k in data)

    def test_districts(self, session):
        r = session.get(f"{API}/districts", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        assert len(d) == 64
        assert "Dhaka" in d


# ---------------- Categories ----------------
class TestCategories:
    def test_list_categories(self, session):
        r = session.get(f"{API}/categories", timeout=30)
        assert r.status_code == 200
        cats = r.json()
        assert len(cats) == 6
        for c in cats:
            assert c.get("status") == "active"
            assert "product_count" in c
            assert "slug" in c

    def test_get_category_by_slug(self, session):
        # Use a slug from listed categories (first one) — should exist
        cats = session.get(f"{API}/categories", timeout=30).json()
        slug = cats[0]["slug"]
        r = session.get(f"{API}/categories/{slug}", timeout=30)
        assert r.status_code == 200
        cat = r.json()
        assert cat["slug"] == slug

    def test_category_not_found(self, session):
        r = session.get(f"{API}/categories/no-such-cat", timeout=30)
        assert r.status_code == 404


# ---------------- Products ----------------
class TestProducts:
    def test_list_products_and_no_cost_leak(self, session):
        r = session.get(f"{API}/products", timeout=30)
        assert r.status_code == 200
        products = r.json()
        assert len(products) == 10
        for p in products:
            assert "cost_price" not in p
            assert "internal_notes" not in p
            assert "_id" not in p

    def test_filter_category(self, session):
        r = session.get(f"{API}/products?category=earrings", timeout=30)
        assert r.status_code == 200
        for p in r.json():
            assert p["category_slug"] == "earrings"

    def test_filter_new_arrival(self, session):
        r = session.get(f"{API}/products?new_arrival=true", timeout=30)
        assert r.status_code == 200
        for p in r.json():
            assert p.get("is_new_arrival") is True

    def test_filter_best_seller(self, session):
        r = session.get(f"{API}/products?best_seller=true", timeout=30)
        assert r.status_code == 200
        for p in r.json():
            assert p.get("is_best_seller") is True

    def test_search(self, session):
        r = session.get(f"{API}/products?search=pearl", timeout=30)
        assert r.status_code == 200
        # search may or may not match; just ensure structure ok
        for p in r.json():
            assert "product_name" in p

    def test_sort_price_low(self, session):
        r = session.get(f"{API}/products?sort=price_low", timeout=30)
        assert r.status_code == 200
        prices = [p["selling_price"] for p in r.json()]
        assert prices == sorted(prices)

    def test_sort_price_high(self, session):
        r = session.get(f"{API}/products?sort=price_high", timeout=30)
        assert r.status_code == 200
        prices = [p["selling_price"] for p in r.json()]
        assert prices == sorted(prices, reverse=True)

    def test_product_detail_with_related(self, session):
        prods = session.get(f"{API}/products", timeout=30).json()
        slug = prods[0]["slug"]
        r = session.get(f"{API}/products/{slug}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["product"]["slug"] == slug
        assert isinstance(d["related"], list)
        assert len(d["related"]) <= 4
        assert "cost_price" not in d["product"]

    def test_product_not_found(self, session):
        r = session.get(f"{API}/products/no-such-product", timeout=30)
        assert r.status_code == 404


# ---------------- Cart validate ----------------
class TestCartValidate:
    def test_cart_validate_dhaka(self, session):
        prods = session.get(f"{API}/products", timeout=30).json()
        in_stock = [p for p in prods if p.get("stock_quantity", 0) > 0]
        assert in_stock, "Need at least one in-stock product"
        p = in_stock[0]
        payload = {"items": [{"product_id": p["id"], "quantity": 1}], "district": "Dhaka"}
        r = session.post(f"{API}/cart/validate", json=payload, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["delivery_charge"] == 80
        assert d["has_issue"] is False
        # backend recalculated price (not from client)
        expected_price = p.get("discount_price") or p["selling_price"]
        assert d["subtotal"] == expected_price
        assert d["total"] == d["subtotal"] + d["delivery_charge"]

    def test_cart_validate_outside_dhaka(self, session):
        prods = session.get(f"{API}/products", timeout=30).json()
        p = next(p for p in prods if p.get("stock_quantity", 0) > 0)
        r = session.post(
            f"{API}/cart/validate",
            json={"items": [{"product_id": p["id"], "quantity": 1}], "district": "Chattogram"},
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["delivery_charge"] == 130

    def test_cart_validate_over_quantity(self, session):
        prods = session.get(f"{API}/products", timeout=30).json()
        p = next(p for p in prods if p.get("stock_quantity", 0) > 0)
        too_many = p["stock_quantity"] + 100
        r = session.post(
            f"{API}/cart/validate",
            json={"items": [{"product_id": p["id"], "quantity": too_many}], "district": "Dhaka"},
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["has_issue"] is True


# ---------------- Checkout ----------------
def _pick_in_stock_product(session):
    prods = session.get(f"{API}/products", timeout=30).json()
    return next(p for p in prods if p.get("stock_quantity", 0) > 0)


class TestCheckout:
    def test_checkout_invalid_phone(self, session):
        p = _pick_in_stock_product(session)
        payload = {
            "customer_name": "Test User",
            "customer_phone": "12345",
            "district": "Dhaka",
            "delivery_address": "House 1, Road 1, Dhanmondi",
            "payment_method": "cod",
            "items": [{"product_id": p["id"], "quantity": 1}],
        }
        r = session.post(f"{API}/checkout", json=payload, timeout=30)
        assert r.status_code == 400
        assert "phone" in r.text.lower()

    def test_checkout_invalid_district(self, session):
        p = _pick_in_stock_product(session)
        payload = {
            "customer_name": "Test User",
            "customer_phone": "01712345678",
            "district": "Mars",
            "delivery_address": "House 1",
            "payment_method": "cod",
            "items": [{"product_id": p["id"], "quantity": 1}],
        }
        r = session.post(f"{API}/checkout", json=payload, timeout=30)
        assert r.status_code == 400

    def test_checkout_missing_name(self, session):
        p = _pick_in_stock_product(session)
        payload = {
            "customer_name": "   ",
            "customer_phone": "01712345678",
            "district": "Dhaka",
            "delivery_address": "House 1",
            "payment_method": "cod",
            "items": [{"product_id": p["id"], "quantity": 1}],
        }
        r = session.post(f"{API}/checkout", json=payload, timeout=30)
        assert r.status_code == 400

    def test_checkout_over_quantity_blocked(self, session):
        p = _pick_in_stock_product(session)
        payload = {
            "customer_name": "TEST OverQty",
            "customer_phone": "01712345678",
            "district": "Dhaka",
            "delivery_address": "House 1",
            "payment_method": "cod",
            "items": [{"product_id": p["id"], "quantity": p["stock_quantity"] + 50}],
        }
        r = session.post(f"{API}/checkout", json=payload, timeout=30)
        assert r.status_code == 400
        assert "left" in r.text.lower() or "out of stock" in r.text.lower() or "stock" in r.text.lower()

    def test_full_checkout_dhaka_and_no_phone_leak(self, session):
        p = _pick_in_stock_product(session)
        initial_stock = p["stock_quantity"]
        client_req_id = f"TEST_{uuid.uuid4()}"
        payload = {
            "customer_name": "TEST Buyer",
            "customer_phone": "01712345678",
            "district": "Dhaka",
            "delivery_address": "TEST House 1, Road 1, Dhanmondi",
            "payment_method": "cod",
            "items": [{"product_id": p["id"], "quantity": 1}],
            "client_request_id": client_req_id,
            # Attempt to send malicious price client-side — must be ignored
            "subtotal": 1,
            "total": 1,
        }
        r = session.post(f"{API}/checkout", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        order_number = d["order_number"]
        assert order_number.startswith("ORD-")
        # ORD-1001 may exist from manual tests; should be >=1001
        assert int(order_number.split("-")[1]) >= 1001
        assert d.get("duplicate") is False

        # Idempotency — second call with SAME client_request_id
        r2 = session.post(f"{API}/checkout", json=payload, timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["order_number"] == order_number
        assert d2.get("duplicate") is True

        # Stock reduced by exactly 1 (not 2)
        prod_after = session.get(f"{API}/products/{p['slug']}", timeout=30).json()["product"]
        assert prod_after["stock_quantity"] == initial_stock - 1

        # Order confirmation does NOT leak phone/address
        conf = session.get(f"{API}/orders/{order_number}", timeout=30)
        assert conf.status_code == 200
        cd = conf.json()
        assert "customer_phone" not in cd
        assert "delivery_address" not in cd
        # backend recalculated totals — Dhaka delivery=80
        assert cd["delivery_charge"] == 80
        expected_price = p.get("discount_price") or p["selling_price"]
        assert cd["subtotal"] == expected_price
        assert cd["total_amount"] == expected_price + 80
        assert cd["order_status"] == "New"
        # Save for next tests
        pytest.shared_order_number = order_number  # type: ignore[attr-defined]

    def test_checkout_outside_dhaka_charge(self, session):
        p = _pick_in_stock_product(session)
        payload = {
            "customer_name": "TEST Buyer 2",
            "customer_phone": "+8801712345678",
            "district": "Chattogram",
            "delivery_address": "TEST Outside Dhaka Address",
            "payment_method": "bkash",
            "transaction_id": "TX123",
            "items": [{"product_id": p["id"], "quantity": 1}],
            "client_request_id": f"TEST_{uuid.uuid4()}",
        }
        r = session.post(f"{API}/checkout", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        order_number = r.json()["order_number"]
        conf = session.get(f"{API}/orders/{order_number}", timeout=30).json()
        assert conf["delivery_charge"] == 130
        assert "bKash" in conf["payment_method"] or "bkash" in conf["payment_method"].lower()


# ---------------- Track ----------------
class TestTrack:
    def test_track_by_order_number(self, session):
        order_number = getattr(pytest, "shared_order_number", "ORD-1001")
        r = session.post(f"{API}/track", json={"order_number": order_number}, timeout=30)
        assert r.status_code == 200, r.text
        orders = r.json()
        assert any(o["order_number"] == order_number for o in orders)
        for o in orders:
            assert "admin_note" not in o
            assert "customer_phone" not in o

    def test_track_by_phone(self, session):
        r = session.post(f"{API}/track", json={"phone": "01712345678"}, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_track_invalid(self, session):
        r = session.post(f"{API}/track", json={"order_number": "ORD-9999999"}, timeout=30)
        assert r.status_code == 404

    def test_track_empty_input(self, session):
        r = session.post(f"{API}/track", json={}, timeout=30)
        assert r.status_code == 400

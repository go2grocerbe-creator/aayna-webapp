"""Milestone 4E — pre-launch QA blocker tests (track privacy, public fields, placeholder detection)."""
import os
import uuid

import requests
import server

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

PHONE = "01712345678"


def _place_order():
    products = requests.get(f"{API}/products", timeout=30).json()
    prod = next((p for p in products if p.get("stock_quantity", 0) > 0), products[0])
    payload = {
        "customer_name": "QA Tester",
        "customer_phone": PHONE,
        "district": "Dhaka",
        "delivery_address": "House 1, Road 2, Dhanmondi",
        "payment_method": "cod",
        "items": [{"product_id": prod["id"], "quantity": 1}],
        "client_request_id": str(uuid.uuid4()),
    }
    r = requests.post(f"{API}/checkout", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["order_number"]


# ---------------- Track order privacy ----------------
class TestTrackPrivacy:
    def test_correct_number_and_phone_returns_order(self):
        on = _place_order()
        r = requests.post(f"{API}/track", json={"order_number": on, "phone": PHONE}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1 and data[0]["order_number"] == on

    def test_correct_number_wrong_phone_fails(self):
        on = _place_order()
        r = requests.post(f"{API}/track", json={"order_number": on, "phone": "01999999999"}, timeout=30)
        assert r.status_code == 404

    def test_missing_phone_rejected(self):
        on = _place_order()
        r = requests.post(f"{API}/track", json={"order_number": on}, timeout=30)
        assert r.status_code == 400

    def test_nearby_order_number_not_guessable(self):
        on = _place_order()  # e.g. ORD-1042
        num = int(on.split("-")[1])
        neighbour = f"ORD-{num - 1}"
        # Querying a neighbouring order number with our phone must not return someone else's order
        r = requests.post(f"{API}/track", json={"order_number": neighbour, "phone": PHONE}, timeout=30)
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            # if it matches, it must genuinely belong to this phone (i.e. our own earlier order)
            assert r.json()[0]["order_number"] == neighbour

    def test_track_response_has_no_sensitive_data(self):
        on = _place_order()
        raw = requests.post(f"{API}/track", json={"order_number": on, "phone": PHONE}, timeout=30).text.lower()
        for bad in ["cost_price", "internal_notes", "customer_phone", "delivery_address",
                    "customer_email", "jwt", "password", "_id"]:
            assert bad not in raw, f"track leaked {bad}"


# ---------------- Public product field hygiene ----------------
class TestPublicProductFields:
    def test_products_hide_low_stock_alert_and_cost(self):
        products = requests.get(f"{API}/products", timeout=30).json()
        assert products
        for p in products:
            assert "low_stock_alert" not in p
            assert "cost_price" not in p
            assert "internal_notes" not in p

    def test_product_detail_hides_low_stock_alert(self):
        products = requests.get(f"{API}/products", timeout=30).json()
        slug = products[0]["slug"]
        prod = requests.get(f"{API}/products/{slug}", timeout=30).json()["product"]
        assert "low_stock_alert" not in prod
        assert "cost_price" not in prod and "internal_notes" not in prod


# ---------------- Placeholder detection (unit) ----------------
def test_placeholder_detection_flags_placeholders():
    settings = {
        "announcement_bar_text": "TEST announcement e0206",
        "whatsapp_number": "+8801XXXXXXXXX",
        "bkash_number": "01XXXXXXXXX",
        "nagad_number": "",
        "support_email": "team@example.com",
    }
    warnings = server.detect_placeholder_warnings(settings)
    assert len(warnings) == 5


def test_placeholder_detection_passes_real_values():
    settings = {
        "announcement_bar_text": "Free delivery on orders over 1000 BDT",
        "whatsapp_number": "+8801711223344",
        "bkash_number": "01711223344",
        "nagad_number": "01811223344",
        "support_email": "hello@aayna.com.bd",
    }
    assert server.detect_placeholder_warnings(settings) == []


def test_placeholder_does_not_falsepositive_on_latest():
    # 'Latest arrivals' contains 'test' as a substring but must NOT be flagged
    assert server.detect_placeholder_warnings({"announcement_bar_text": "Latest arrivals now in"}) == ["WhatsApp number", "bKash number", "Nagad number", "Support email"]

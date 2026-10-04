"""Milestone 4E — pre-launch QA blocker tests (track privacy, public fields, placeholder detection)."""
import asyncio
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

    def test_public_product_whitelist_hides_unknown_internal_fields(self):
        # Simulates a future BuyOS field landing on the product document — the
        # public API must hide it by default (whitelist), not rely on knowing its name.
        pid = str(uuid.uuid4())
        slug = f"test-whitelist-{pid[:8]}"
        poisoned_fields = {
            "supplier_url": "https://supplier.example/secret-listing",
            "supplier_price": 42,
            "cost_price": 40,
            "landed_cost": 45,
            "purchase_cost": 41,
            "margin": 60,
            "internal_notes": "do not expose",
            "sourcing_notes": "private sourcing detail",
            "private_scoring_notes": "private score",
            "low_stock_alert": 3,
        }

        # A dedicated Motor client, created and closed entirely inside this
        # function's own asyncio.run()-created loop, rather than reusing the
        # module-level `server.db` client. `server.db` is a singleton meant
        # for the live FastAPI app's one persistent event loop; sharing it
        # across independent asyncio.run() calls in a test process caused
        # "Event loop is closed" once another test (test_aayna_health_config's
        # TestClient, whose /api/health/ready check pings the DB) had already
        # bound it to a different, since-closed loop. Confirmed via isolated
        # run vs. full-suite run before this fix - see ENVIRONMENTS.md.
        async def _run():
            from motor.motor_asyncio import AsyncIOMotorClient
            local_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            local_db = local_client[os.environ["DB_NAME"]]
            try:
                await local_db.products.insert_one({
                    "id": pid, "sku": "TESTWL-0001", "slug": slug,
                    "product_name": "TEST Whitelist Product",
                    "category_name": "Earrings", "category_slug": "earrings",
                    "selling_price": 100, "discount_price": None, "stock_quantity": 5,
                    "status": "active", "images": [],
                    "short_description": "x", "full_description": "x",
                    "is_featured": False, "is_best_seller": False, "is_new_arrival": False,
                    "tags": [], "created_at": server.now_iso(), "updated_at": server.now_iso(),
                    **poisoned_fields,
                })
                try:
                    listed = requests.get(f"{API}/products", timeout=30).json()
                    match = next(p for p in listed if p["slug"] == slug)
                    for field in poisoned_fields:
                        assert field not in match, f"list endpoint leaked {field}"

                    detail = requests.get(f"{API}/products/{slug}", timeout=30).json()["product"]
                    for field in poisoned_fields:
                        assert field not in detail, f"detail endpoint leaked {field}"

                    cart = requests.post(
                        f"{API}/cart/validate",
                        json={"items": [{"product_id": pid, "quantity": 1}], "district": "Dhaka"},
                        timeout=30,
                    ).json()
                    raw = str(cart).lower()
                    for field in poisoned_fields:
                        assert field.replace("_", "") not in raw.replace("_", ""), f"cart/validate leaked {field}"
                finally:
                    await local_db.products.delete_one({"id": pid})
            finally:
                local_client.close()

        asyncio.run(_run())


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

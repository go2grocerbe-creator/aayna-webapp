"""Milestone 3B — order notification webhook tests.

These are fast, isolated unit tests for `server.send_order_notification`:
- httpx is replaced with a fake client (no real network calls).
- the DB is replaced with a fake collection (no real Mongo writes, so the
  admin dashboard's failed_notifications card is never polluted).
"""
import asyncio
import json
import hmac
import hashlib
import uuid

import server


def run(coro):
    return asyncio.run(coro)


def make_order():
    return {
        "id": str(uuid.uuid4()),
        "order_number": "WEBHOOKTEST-" + uuid.uuid4().hex[:8],
        "customer_name": "Test User",
        "customer_phone": "+8801712345678",
        "customer_email": "t@example.com",
        "delivery_address": "House 1, Road 2, Dhaka",
        "district": "Dhaka",
        "payment_method": "Cash on Delivery",
        "subtotal": 800,
        "delivery_charge": 80,
        "total_amount": 880,
        "order_status": "New",
        "created_at": "2026-01-01T00:00:00+00:00",
        # Extra sensitive-looking fields that must NEVER leak into the payload:
        "items": [
            {
                "product_name_snapshot": "Gold Pearl Hoop Earrings",
                "sku_snapshot": "EAR-GD-0001",
                "quantity": 2,
                "unit_price": 400,
                "total_price": 800,
                "cost_price": 160,
                "internal_notes": "supplier ABC",
            }
        ],
    }


class FakeResp:
    def __init__(self, code):
        self.status_code = code


class FakeClient:
    calls = []
    code = 200
    raise_exc = False

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, content=None, headers=None, **k):
        FakeClient.calls.append({"url": url, "content": content, "headers": headers})
        if FakeClient.raise_exc:
            raise RuntimeError("connection refused to " + url)  # contains url on purpose
        return FakeResp(FakeClient.code)


class FakeColl:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)


class FakeDB:
    def __init__(self):
        self.notification_logs = FakeColl()


def _setup(monkeypatch, enabled, url="https://hooks.example.com/aayna", secret=None, code=200, raise_exc=False):
    FakeClient.calls = []
    FakeClient.code = code
    FakeClient.raise_exc = raise_exc
    fake_db = FakeDB()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeClient)
    monkeypatch.setenv("ORDER_WEBHOOK_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("ORDER_WEBHOOK_URL", url)
    if secret is not None:
        monkeypatch.setenv("ORDER_WEBHOOK_SECRET", secret)
    else:
        monkeypatch.delenv("ORDER_WEBHOOK_SECRET", raising=False)
    return fake_db


def test_webhook_disabled_no_call(monkeypatch):
    fake_db = _setup(monkeypatch, enabled=False)
    run(server.send_order_notification(make_order()))
    assert FakeClient.calls == []            # no webhook attempted
    assert fake_db.notification_logs.docs == []  # nothing logged


def test_webhook_enabled_success_sends_payload(monkeypatch):
    fake_db = _setup(monkeypatch, enabled=True, secret="topsecret", code=200)
    order = make_order()
    run(server.send_order_notification(order))

    assert len(FakeClient.calls) == 1
    call = FakeClient.calls[0]
    assert call["url"] == "https://hooks.example.com/aayna"

    payload = json.loads(call["content"])
    for f in ["order_id", "order_number", "customer_name", "customer_phone", "district",
              "delivery_address", "payment_method", "order_total", "delivery_fee",
              "order_status", "created_at", "items"]:
        assert f in payload, f"missing {f}"
    assert payload["order_total"] == 880 and payload["delivery_fee"] == 80
    assert set(payload["items"][0].keys()) == {"product_name", "quantity", "unit_price", "subtotal"}

    # Logged as success
    assert len(fake_db.notification_logs.docs) == 1
    log = fake_db.notification_logs.docs[0]
    assert log["status"] == "success" and log["notification_type"] == "order_created"
    assert log["response_code"] == 200


def test_webhook_signature(monkeypatch):
    _setup(monkeypatch, enabled=True, secret="topsecret")
    run(server.send_order_notification(make_order()))
    call = FakeClient.calls[0]
    sig = call["headers"].get("X-AAYNA-Signature")
    expected = "sha256=" + hmac.new(b"topsecret", call["content"], hashlib.sha256).hexdigest()
    assert sig == expected


def test_webhook_no_signature_without_secret(monkeypatch):
    _setup(monkeypatch, enabled=True, secret=None)
    run(server.send_order_notification(make_order()))
    assert "X-AAYNA-Signature" not in FakeClient.calls[0]["headers"]


def test_webhook_payload_has_no_sensitive_data(monkeypatch):
    _setup(monkeypatch, enabled=True, secret="topsecret")
    run(server.send_order_notification(make_order()))
    raw = FakeClient.calls[0]["content"].decode()
    for bad in ["cost_price", "internal_notes", "password", "password_hash",
                "token", "jwt", "sku_snapshot"]:
        assert bad not in raw, f"payload leaked {bad}"
    assert '"_id"' not in raw  # no raw DB id key


def test_items_summary_helper():
    items = [
        {"product_name_snapshot": "Gold Pearl Hoop Earrings", "quantity": 2},
        {"product_name_snapshot": "Heart Pendant Necklace", "quantity": 1},
    ]
    assert server._items_summary(items) == "Gold Pearl Hoop Earrings x2, Heart Pendant Necklace x1"


def test_webhook_message_templates(monkeypatch):
    _setup(monkeypatch, enabled=True, secret="topsecret")
    order = make_order()
    run(server.send_order_notification(order))
    payload = json.loads(FakeClient.calls[0]["content"])

    # Both message fields present
    assert "admin_message" in payload and "customer_message" in payload
    assert "items_summary" in payload
    assert payload["items_summary"] == "Gold Pearl Hoop Earrings x2"

    admin_msg = payload["admin_message"]
    customer_msg = payload["customer_message"]

    # Admin message: operational details
    assert order["order_number"] in admin_msg
    assert order["customer_name"] in admin_msg
    assert order["customer_phone"] in admin_msg
    assert order["district"] in admin_msg
    assert "৳880" in admin_msg
    assert "Gold Pearl Hoop Earrings x2" in admin_msg
    assert "admin dashboard" in admin_msg.lower()

    # Customer message: polite, includes order number/total/payment/district
    assert "Thank you" in customer_msg
    assert order["order_number"] in customer_msg
    assert "৳880" in customer_msg
    assert order["payment_method"] in customer_msg
    assert order["district"] in customer_msg
    # Customer message must NOT expose the phone/address
    assert order["customer_phone"] not in customer_msg


def test_webhook_messages_have_no_sensitive_data(monkeypatch):
    _setup(monkeypatch, enabled=True, secret="topsecret")
    run(server.send_order_notification(make_order()))
    payload = json.loads(FakeClient.calls[0]["content"])
    blob = (payload["admin_message"] + " " + payload["customer_message"]).lower()
    for bad in ["cost_price", "internal_notes", "password", "token", "jwt",
                "secret", "api_key", "topsecret", "160"]:  # 160 = the cost_price value
        assert bad not in blob, f"message leaked {bad}"


def test_webhook_failure_http_still_logged(monkeypatch):
    fake_db = _setup(monkeypatch, enabled=True, code=500)
    # Must not raise even though the webhook returns 500
    run(server.send_order_notification(make_order()))
    log = fake_db.notification_logs.docs[0]
    assert log["status"] == "failed"
    assert log["response_code"] == 500


def test_webhook_failure_exception_does_not_leak_url(monkeypatch):
    fake_db = _setup(monkeypatch, enabled=True, secret="topsecret", raise_exc=True)
    # Must not raise — order creation is unaffected
    run(server.send_order_notification(make_order()))
    log = fake_db.notification_logs.docs[0]
    assert log["status"] == "failed"
    # error message must not expose the URL or secret
    err = log.get("error_message") or ""
    assert "example.com" not in err and "topsecret" not in err



# ---------------------------------------------------------------------------
# Milestone 3D — notification router readiness
# ---------------------------------------------------------------------------
def test_router_helper_defaults(monkeypatch):
    monkeypatch.delenv("NOTIFICATION_ROUTER_NAME", raising=False)
    monkeypatch.delenv("NOTIFICATION_ROUTER_MODE", raising=False)
    assert server._router_name() == "generic_webhook"
    assert server._router_mode() == "webhook"


def test_router_helper_blank_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_ROUTER_NAME", "   ")
    monkeypatch.setenv("NOTIFICATION_ROUTER_MODE", "")
    assert server._router_name() == "generic_webhook"
    assert server._router_mode() == "webhook"


def test_router_helper_custom(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_ROUTER_NAME", "blackbox")
    monkeypatch.setenv("NOTIFICATION_ROUTER_MODE", "webhook")
    assert server._router_name() == "blackbox"
    assert server._router_mode() == "webhook"


def test_router_metadata_logged_with_defaults(monkeypatch):
    monkeypatch.delenv("NOTIFICATION_ROUTER_NAME", raising=False)
    monkeypatch.delenv("NOTIFICATION_ROUTER_MODE", raising=False)
    fake_db = _setup(monkeypatch, enabled=True, secret="topsecret")
    run(server.send_order_notification(make_order()))
    log = fake_db.notification_logs.docs[0]
    assert log["router_name"] == "generic_webhook"
    assert log["router_mode"] == "webhook"


def test_router_metadata_logged_custom(monkeypatch):
    fake_db = _setup(monkeypatch, enabled=True)
    monkeypatch.setenv("NOTIFICATION_ROUTER_NAME", "make")
    monkeypatch.setenv("NOTIFICATION_ROUTER_MODE", "webhook")
    run(server.send_order_notification(make_order()))
    log = fake_db.notification_logs.docs[0]
    assert log["router_name"] == "make"
    assert log["router_mode"] == "webhook"


def test_router_metadata_never_leaks_secrets(monkeypatch):
    fake_db = _setup(monkeypatch, enabled=True, secret="topsecret")
    run(server.send_order_notification(make_order()))
    log = fake_db.notification_logs.docs[0]
    blob = (str(log.get("router_name")) + str(log.get("router_mode"))).lower()
    for bad in ["topsecret", "example.com", "http"]:
        assert bad not in blob

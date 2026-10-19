"""Steadfast courier integration against the deterministic simulator (no network).

These tests prove AAYNA's own logic (claims, reconciliation, COD, status mapping,
permissions). They are NOT proof that real Steadfast bookings work: the real
API's response schemas still have to be confirmed with Steadfast.
"""
import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_customer_accounts import env, client, admin_h, checkout, run, verified_client, _add_priced  # noqa: E402,F401

import steadfast  # noqa: E402
import emailer  # noqa: E402


@pytest.fixture()
def sf(env, monkeypatch):
    monkeypatch.setattr(steadfast, "db", env["db"])
    import courier_finance
    monkeypatch.setattr(courier_finance, "db", env["db"])
    monkeypatch.setenv("STEADFAST_MODE", "mock")
    for k in ("STEADFAST_API_KEY", "STEADFAST_SECRET_KEY", "STEADFAST_REAL_BOOKINGS", "CRON_SECRET", "STEADFAST_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    steadfast.MockSteadfast.FAULTS.clear()
    for c in ("steadfast_mock_parcels", "courier_state", "steadfast_mock_payments", "courier_finance_events", "courier_payment_imports"):
        run(env["db"][c].delete_many({}))
    run(steadfast.ensure_courier_indexes())
    return env


def packed_order(env, items=(("p1", 1),), phone="01712345678", email="", coupon=None, c=None, status="Packed"):
    c = c or client()
    r = checkout(c, items=items, phone=phone, email=email, coupon=coupon)
    assert r.status_code == 200, r.text
    n = r.json()["order_number"]
    if status:
        assert client().put(f"/api/admin/orders/{n}", headers=admin_h(env), json={"order_status": status}).status_code == 200
    return n


def book(env, n, role="super_admin", confirm=True):
    return client().post(f"/api/admin/orders/{n}/courier/book", headers=admin_h(env, role), json={"confirm": confirm})


def sync(env, n, role="super_admin"):
    # bypass the 60-second provider cache between simulated updates
    run(env["db"].orders.update_one({"order_number": n}, {"$set": {"courier.last_sync_at": "2000-01-01T00:00:00+00:00"}}))
    return client().post(f"/api/admin/orders/{n}/courier/sync", headers=admin_h(env, role))


def set_mock(env, n, status=None, return_status=None):
    body = {"action": "set_status", "status": status}
    if return_status is not None:
        body["return_status"] = return_status
    r = client().post(f"/api/admin/orders/{n}/courier/mock", headers=admin_h(env), json=body)
    assert r.status_code == 200, r.text


def order(env, n):
    return run(env["db"].orders.find_one({"order_number": n}, {"_id": 0}))


def parcels(env):
    return run(env["db"].steadfast_mock_parcels.count_documents({}))


# ---------------------------------------------------------------------------
def test_modes_and_real_booking_gate(sf, monkeypatch):
    n = packed_order(sf)
    monkeypatch.setenv("STEADFAST_MODE", "off")
    assert book(sf, n).status_code == 503
    monkeypatch.setenv("STEADFAST_MODE", "mock")
    monkeypatch.setenv("DB_NAME", "aayna_prod")  # the simulator is never used with production data
    assert steadfast.config()["mode"] == "off" and book(sf, n).status_code == 503
    monkeypatch.setenv("DB_NAME", "aayna_import_test")
    monkeypatch.setenv("STEADFAST_MODE", "live")
    assert steadfast.config()["mode"] == "off"  # no keys
    monkeypatch.setenv("STEADFAST_API_KEY", "test-api-key-value-1234")
    monkeypatch.setenv("STEADFAST_SECRET_KEY", "test-secret-key-value-5678")
    cfg = client().get("/api/admin/courier/config", headers=admin_h(sf)).json()
    assert cfg["mode"] == "live" and cfg["real_bookings"] is False and cfg["keys_present"] is True
    assert "test-api-key" not in str(cfg) and "test-secret" not in str(cfg)
    r = book(sf, n)
    assert r.status_code == 403 and "founder" in r.json()["detail"]
    monkeypatch.setenv("STEADFAST_REAL_BOOKINGS", "true")  # still refused: not the production database
    assert book(sf, n).status_code == 403
    assert order(sf, n).get("courier") is None


def test_successful_booking_is_explicit_and_uses_server_cod(sf):
    n = packed_order(sf, status="Confirmed")
    r = book(sf, n)
    assert r.status_code == 400 and "Packed" in r.json()["detail"]  # confirmed but not prepared yet
    assert client().put(f"/api/admin/orders/{n}", headers=admin_h(sf), json={"order_status": "Packed"}).status_code == 200
    assert book(sf, n, confirm=False).status_code == 400
    view = client().get(f"/api/admin/orders/{n}/courier", headers=admin_h(sf)).json()
    assert view["booking_preview"]["ok"] and view["booking_preview"]["recipient_phone"] == "01712345678"
    assert view["booking_preview"]["cod"]["amount"] == 1290 + 100  # ৳1,290 + ৳100 delivery
    r = book(sf, n)
    assert r.status_code == 200, r.text
    c = r.json()["courier"]
    assert c["state"] == "booked" and c["consignment_id"] and c["tracking_code"].startswith("SFM")
    assert c["cod_amount"] == 1390 and r.json()["order_status"] == "Packed"  # booking is not dispatch
    o = order(sf, n)
    assert o["courier_name"] == "Steadfast" and o["courier_tracking_code"] == c["tracking_code"]
    p = run(sf["db"].steadfast_mock_parcels.find_one({"invoice": n}))
    assert p["cod_amount"] == o["total_amount"] == 1390
    # a second click cannot book again
    assert book(sf, n).status_code == 409 and parcels(sf) == 1
    # the courier name / tracking code can no longer be overwritten by hand
    assert client().put(f"/api/admin/orders/{n}", headers=admin_h(sf), json={"courier_tracking_code": "X"}).status_code == 409
    # customer tracking: safe label only, no courier internals
    t = client().post("/api/track", json={"order_number": n, "phone": "01712345678"}).json()[0]
    assert t["courier_status"] == "Booked with Steadfast courier" and t["courier_tracking_code"] == c["tracking_code"]
    assert "consignment" not in str(t) and "cod_amount" not in str(t) and "claim" not in str(t)


def test_validation_failure_and_retry(sf):
    n = packed_order(sf)
    steadfast.MockSteadfast.FAULTS["create_order"] = "validation"
    r = book(sf, n)
    c = r.json()["courier"]
    assert c["state"] == "failed" and "not serviceable" in c["last_error"] and parcels(sf) == 0
    r = book(sf, n)  # fixed -> retry is allowed after a clean refusal
    assert r.json()["courier"]["state"] == "booked" and r.json()["courier"]["attempts"] == 2 and parcels(sf) == 1
    # problems found before sending never reach Steadfast
    n2 = packed_order(sf, phone="01812345678")
    run(sf["db"].orders.update_one({"order_number": n2}, {"$set": {"delivery_address": "x" * 600}}))
    r = book(sf, n2)
    assert r.status_code == 400 and "490" in r.json()["detail"] and parcels(sf) == 1


def test_timeout_after_acceptance_is_reconciled_never_rebooked(sf):
    n = packed_order(sf)
    steadfast.MockSteadfast.FAULTS["create_order"] = "timeout_after_accept"
    c = book(sf, n).json()["courier"]
    assert c["state"] == "needs_reconciliation" and parcels(sf) == 1
    assert book(sf, n).status_code == 409 and parcels(sf) == 1  # never blindly resent
    r = client().post(f"/api/admin/orders/{n}/courier/reconcile", headers=admin_h(sf)).json()["courier"]
    assert r["state"] == "needs_reconciliation" and r["found_at_provider"] and "Do not book again" in r["last_error"]
    view = client().get(f"/api/admin/orders/{n}/courier", headers=admin_h(sf)).json()
    assert view["simulated_portal"]["consignment_id"]  # simulator shows what the portal would show
    real = run(sf["db"].steadfast_mock_parcels.find_one({"invoice": n}))
    bad = client().post(f"/api/admin/orders/{n}/courier/link", headers=admin_h(sf), json={"consignment_id": "123456", "tracking_code": "NOPE1234"})
    assert bad.status_code == 400
    ok = client().post(f"/api/admin/orders/{n}/courier/link", headers=admin_h(sf),
                       json={"consignment_id": real["consignment_id"], "tracking_code": real["tracking_code"]}).json()["courier"]
    assert ok["state"] == "booked" and ok["linked_by_hand"] and ok["consignment_id"] == real["consignment_id"] and parcels(sf) == 1


def test_timeout_before_acceptance_and_downtime_allow_safe_retry(sf):
    n = packed_order(sf)
    steadfast.MockSteadfast.FAULTS["create_order"] = "timeout_before_accept"
    assert book(sf, n).json()["courier"]["state"] == "needs_reconciliation"
    r = client().post(f"/api/admin/orders/{n}/courier/reconcile", headers=admin_h(sf)).json()["courier"]
    assert r["state"] == "failed" and "safe to book again" in r["last_error"]
    assert book(sf, n).json()["courier"]["state"] == "booked" and parcels(sf) == 1
    # provider unreachable before sending -> clean failure, retry allowed
    n2 = packed_order(sf, phone="01812345678")
    steadfast.MockSteadfast.FAULTS["create_order"] = "down"
    assert book(sf, n2).json()["courier"]["state"] == "failed"
    # 5xx is ambiguous -> reconcile required
    steadfast.MockSteadfast.FAULTS["create_order"] = "server_error"
    assert book(sf, n2).json()["courier"]["state"] == "needs_reconciliation"
    # an OK answer without ids is also ambiguous
    n3 = packed_order(sf, phone="01912345678")
    steadfast.MockSteadfast.FAULTS["create_order"] = "ok_without_ids"
    assert book(sf, n3).json()["courier"]["state"] == "needs_reconciliation"
    # a duplicate invoice at Steadfast means "link it", not "failed"
    n4 = packed_order(sf, phone="01612345678")
    run(sf["db"].steadfast_mock_parcels.insert_one({"invoice": n4, "consignment_id": "9555555", "tracking_code": "SFMDUP1",
                                                    "delivery_status": "pending", "cod_amount": 1}))
    assert book(sf, n4).json()["courier"]["state"] == "needs_reconciliation"


def test_concurrent_clicks_create_one_consignment(sf):
    n = packed_order(sf)

    async def both():
        async def one(who):
            try:
                await steadfast.book(n, who)
                return "ok"
            except steadfast.HTTPException as e:
                return e.status_code
        return await asyncio.gather(one("a@example.test"), one("b@example.test"), one("c@example.test"))
    res = run(both())
    assert res.count("ok") == 1 and all(r == 409 for r in res if r != "ok"), res
    assert parcels(sf) == 1 and order(sf, n)["courier"]["state"] == "booked"


def test_status_updates_move_forward_only_and_email_once(sf):
    n = packed_order(sf, email="maya@example.test")
    book(sf, n)
    set_mock(sf, n, "pending")
    r = sync(sf, n).json()
    assert r["courier"]["status_raw"] == "pending" and r["order_status"] == "Packed"
    # hand-over is the team's action (existing "Handed to courier" email)
    client().put(f"/api/admin/orders/{n}", headers=admin_h(sf), json={"order_status": "Sent to Courier"})
    set_mock(sf, n, "delivered_approval_pending")
    r = sync(sf, n).json()
    assert r["order_status"] == "Sent to Courier" and r["courier"]["status_kind"] == "confirming"  # not delivered yet
    set_mock(sf, n, "delivered")
    r = sync(sf, n).json()
    assert r["order_status"] == "Delivered" and r["courier"]["status_raw"] == "delivered"
    events = run(sf["db"].order_events.find({"order_number": n}, {"_id": 0}).to_list(20))
    assert [e["status"] for e in events][-1] == "Delivered" and events[-1]["source"] == "steadfast"
    # stale answer and repeated polls change nothing and send nothing again
    set_mock(sf, n, "pending")
    r = sync(sf, n).json()
    assert r["order_status"] == "Delivered" and r["courier"]["status_raw"] == "delivered" and "ignored" in r["courier"]["last_sync_result"]
    set_mock(sf, n, "delivered")
    sync(sf, n)
    sync(sf, n)
    delivered_mails = [m for m in emailer.CAPTURED if m["template"] == "order_status" and "Delivered" in m["subject"]]
    assert len(delivered_mails) == 1
    hist = order(sf, n)["courier"]["history"]
    assert sum(1 for h in hist if h.get("event") == "status_applied" and h.get("status") == "delivered") == 1
    # live mode: 60-second cache, an immediate second check does not call Steadfast again
    import os as _os
    _os.environ["STEADFAST_MODE"] = "live"; _os.environ["STEADFAST_API_KEY"] = "k-1"; _os.environ["STEADFAST_SECRET_KEY"] = "s-1"
    try:
        run(sf["db"].orders.update_one({"order_number": n}, {"$set": {"courier.last_sync_at": steadfast.now_iso()}}))
        r = client().post(f"/api/admin/orders/{n}/courier/sync", headers=admin_h(sf)).json()
        assert r["note"] and "less than a minute" in r["note"]
    finally:
        _os.environ["STEADFAST_MODE"] = "mock"
        _os.environ.pop("STEADFAST_API_KEY"); _os.environ.pop("STEADFAST_SECRET_KEY")


def test_cancelled_partial_and_returns_never_touch_stock(sf):
    stock0 = run(sf["db"].products.find_one({"id": "p1"}))["stock_quantity"]
    n = packed_order(sf)
    stock1 = run(sf["db"].products.find_one({"id": "p1"}))["stock_quantity"]
    assert stock1 == stock0 - 1
    book(sf, n)
    set_mock(sf, n, "cancelled")
    r = sync(sf, n).json()
    assert r["order_status"] == "Packed" and r["courier"]["status_kind"] == "attention" and r["courier"]["attention"]
    set_mock(sf, n, None, return_status="cancelled_return_received")
    r = sync(sf, n).json()
    assert r["courier"]["status_raw"] == "cancelled_return_received" and "Inspect" in r["courier"]["attention"]
    assert run(sf["db"].products.find_one({"id": "p1"}))["stock_quantity"] == stock1  # no automatic restock
    assert r["order_status"] == "Packed"  # never auto-cancelled / returned
    # partial delivery is not success
    n2 = packed_order(sf, phone="01812345678")
    book(sf, n2)
    set_mock(sf, n2, "partial_delivered")
    r = sync(sf, n2).json()
    assert r["order_status"] == "Sent to Courier" and r["courier"]["status_kind"] == "attention"
    # an unrecognised status is recorded, never applied
    set_mock(sf, n2, "unknown")
    r = sync(sf, n2).json()
    assert r["courier"]["status_raw"] == "partial_delivered" and "unrecognised" in r["courier"]["attention"]


def test_provider_auth_failure_pauses_calls(sf):
    n = packed_order(sf)
    steadfast.MockSteadfast.FAULTS["create_order"] = "auth"
    c = book(sf, n).json()["courier"]
    assert c["state"] == "failed" and "401" in c["last_error"]
    r = book(sf, n)
    assert r.status_code == 429 and "paused" in r.json()["detail"]  # no retry loop into a lockout
    cfg = client().get("/api/admin/courier/config", headers=admin_h(sf)).json()
    assert cfg["paused_until"]


def test_cod_amounts(sf):
    _add_priced(sf, {"d1090": 1090, "d1510": 1510})
    # discount + delivery: ৳1,090 - 10% (৳109) + ৳100 = ৳1,081
    c = client()
    assert c.put("/api/admin/promotions/campaigns/welcome", headers=admin_h(sf),
                 json={"enabled": True, "min_subtotal": 1000, "max_discount_bdt": 150, "confirm": True}).status_code == 200
    a = verified_client(email="maya@example.test", phone="01712345678")
    code = a.get("/api/account/rewards").json()["coupons"][0]["code"]
    n = packed_order(sf, items=(("d1090", 1),), coupon=code, c=a)
    assert book(sf, n).json()["courier"]["cod_amount"] == 1081
    # free delivery: ৳1,510 - ৳150 cap = ৳1,360
    b = verified_client(email="rina@example.test", phone="01812345678")
    code_b = b.get("/api/account/rewards").json()["coupons"][0]["code"]
    n2 = packed_order(sf, items=(("d1510", 1),), phone="01812345678", coupon=code_b, c=b)
    assert book(sf, n2).json()["courier"]["cod_amount"] == 1360
    assert run(sf["db"].steadfast_mock_parcels.find_one({"invoice": n2}))["cod_amount"] == 1360
    c.put("/api/admin/promotions/campaigns/welcome", headers=admin_h(sf), json={"enabled": False})
    # unverified prepaid order is blocked; a verified prepaid order collects nothing
    o = {"order_status": "Packed", "subtotal": 990, "discount_amount": 0, "delivery_charge": 100, "total_amount": 1090,
         "payment_method": "bKash Manual", "payment_status": "pending"}
    assert steadfast.cod_amount(o)["ok"] is False
    assert steadfast.cod_amount({**o, "payment_status": "paid"})["amount"] == 0
    assert steadfast.cod_amount({**o, "payment_method": "Cash on Delivery", "payment_status": "COD_pending"})["amount"] == 1090
    assert steadfast.cod_amount({**o, "total_amount": 999, "payment_method": "Cash on Delivery"})["ok"] is False  # inconsistent totals


def test_permissions_and_no_public_webhook(sf, monkeypatch):
    n = packed_order(sf)
    assert book(sf, n, role="product_manager").status_code == 403
    assert client().post(f"/api/admin/orders/{n}/courier/book", json={"confirm": True}).status_code in (401, 403)
    assert client().get(f"/api/admin/orders/{n}/courier", headers=admin_h(sf, "product_manager")).status_code == 403
    assert book(sf, n, role="order_manager").status_code == 200
    assert client().post(f"/api/admin/orders/{n}/courier/mock", headers=admin_h(sf, "product_manager"),
                         json={"action": "set_status", "status": "delivered"}).status_code == 403
    # no unauthenticated callback can change an order (webhook auth is undocumented)
    for path in ("/api/steadfast/webhook", "/api/webhooks/steadfast", "/api/courier/webhook"):
        r = client().post(path, json={"invoice": n, "status": "delivered"})
        assert r.status_code in (404, 405)
    assert order(sf, n)["order_status"] == "Packed"
    # scheduled sync endpoint: off without a secret, refuses a wrong one
    assert client().get("/api/internal/courier/sync").status_code == 404
    run(sf["db"].orders.update_one({"order_number": n}, {"$set": {"courier.last_sync_at": "2000-01-01T00:00:00+00:00"}}))
    monkeypatch.setenv("CRON_SECRET", "cron-secret-for-tests-0123456789")
    assert client().get("/api/internal/courier/sync", headers={"Authorization": "Bearer wrong"}).status_code == 404
    r = client().get("/api/internal/courier/sync", headers={"Authorization": "Bearer cron-secret-for-tests-0123456789"})
    assert r.status_code == 200 and r.json()["checked"] == 1
    # the simulator controls do not exist outside mock mode
    monkeypatch.setenv("STEADFAST_MODE", "off")
    assert client().post(f"/api/admin/orders/{n}/courier/mock", headers=admin_h(sf),
                         json={"action": "set_status", "status": "delivered"}).status_code == 404


def test_live_transport_headers_and_timeouts(sf, monkeypatch, caplog):
    """The real HTTP client sends the keys only as headers to the https base URL and
    classifies failures conservatively (no real network: httpx MockTransport)."""
    monkeypatch.setenv("STEADFAST_API_KEY", "live-key-AAAA")
    monkeypatch.setenv("STEADFAST_SECRET_KEY", "live-secret-BBBB")
    seen = {}

    def handler(request):
        seen["url"], seen["headers"] = str(request.url), dict(request.headers)
        if request.url.path.endswith("/timeout"):
            raise httpx.ReadTimeout("slow", request=request)
        if request.url.path.endswith("/refused"):
            raise httpx.ConnectError("no route", request=request)
        return httpx.Response(200, json={"status": 200, "delivery_status": "pending"})

    real = httpx.AsyncClient
    monkeypatch.setattr(steadfast.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    ans = run(steadfast._live_call("GET", "/status_by_cid/123"))
    assert ans.status == 200 and seen["url"] == "https://portal.packzy.com/api/v1/status_by_cid/123"
    assert seen["headers"]["api-key"] == "live-key-AAAA" and seen["headers"]["secret-key"] == "live-secret-BBBB"
    assert run(steadfast._live_call("POST", "/timeout", {})).outcome == "ambiguous"
    assert run(steadfast._live_call("POST", "/refused", {})).outcome == "not_sent"
    monkeypatch.setenv("STEADFAST_BASE_URL", "http://insecure.example.test/api/v1")
    assert run(steadfast._live_call("GET", "/status_by_cid/1")).outcome == "not_sent"
    assert "live-key-AAAA" not in caplog.text and "live-secret-BBBB" not in caplog.text


def test_scheduled_tracking_polls_only_open_parcels_with_backoff(sf, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "cron-secret-for-tests-0123456789")
    H = {"Authorization": "Bearer cron-secret-for-tests-0123456789"}
    a = packed_order(sf); book(sf, a)                              # open parcel
    b = packed_order(sf, phone="01812345678"); book(sf, b)         # will be delivered (final)
    c = packed_order(sf, phone="01912345678"); book(sf, c)         # cancelled, return not yet received
    set_mock(sf, b, "delivered"); sync(sf, b)
    set_mock(sf, c, "cancelled"); sync(sf, c)
    old = "2000-01-01T00:00:00+00:00"
    run(sf["db"].orders.update_many({}, {"$set": {"courier.last_sync_at": old}}))
    set_mock(sf, a, "pending")
    r = client().get("/api/internal/courier/sync", headers=H).json()
    assert r["checked"] == 2 and r["failed"] == 0                  # a + c; delivered b is never polled again
    assert order(sf, a)["courier"]["status_raw"] == "pending"
    # nothing is re-polled within 10 minutes
    assert client().get("/api/internal/courier/sync", headers=H).json()["checked"] == 0
    # provider failure -> back-off, then skipped until the back-off ends
    run(sf["db"].orders.update_many({}, {"$set": {"courier.last_sync_at": old}}))
    steadfast.MockSteadfast.FAULTS["status_by_cid"] = "server_error"
    r = client().get("/api/internal/courier/sync", headers=H).json()
    fa = order(sf, a)["courier"]
    assert fa["sync_failures"] == 1 and fa["next_sync_after"] > steadfast.now_iso()
    run(sf["db"].orders.update_many({}, {"$set": {"courier.last_sync_at": old}}))
    r = client().get("/api/internal/courier/sync", headers=H).json()
    assert r["checked"] == 1  # only c; a waits for its back-off
    # the result of the last scheduled run is visible to admins
    cfg = client().get("/api/admin/courier/config", headers=admin_h(sf)).json()
    assert cfg["last_bulk_sync_by"] == "scheduled sync" and cfg["scheduled_sync"].startswith("daily")
    # unconfigured: quiet no-op
    monkeypatch.setenv("STEADFAST_MODE", "off")
    assert client().get("/api/internal/courier/sync", headers=H).json() == {"skipped": "Steadfast is not configured"}

"""Order-level Steadfast financials: expected vs actual settlement, audit, idempotency, permissions.
All against the simulator - none of this is proof of the real provider's payout format."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_customer_accounts import env, client, admin_h, run, _add_priced, verified_client  # noqa: E402,F401
from test_steadfast import sf, packed_order, book, sync, set_mock, order  # noqa: E402,F401

import courier_finance  # noqa: E402


def fin(env, n, role="super_admin"):
    return client().get(f"/api/admin/orders/{n}/courier/finance", headers=admin_h(env, role))


def act(env, n, role="super_admin", **body):
    body.setdefault("key", uuid.uuid4().hex)
    return client().post(f"/api/admin/orders/{n}/courier/finance", headers=admin_h(env, role), json=body)


def booked_delivered(sf, items=(("p1", 1),), phone="01712345678"):
    n = packed_order(sf, items=items, phone=phone)
    book(sf, n)
    set_mock(sf, n, "delivered")
    sync(sf, n)
    return n


def test_unknown_fees_are_pending_not_zero_and_customer_payable_from_snapshot(sf):
    n = packed_order(sf)                          # ৳1,290 + ৳100 delivery
    r = fin(sf, n).json()["finance"]
    assert r["status"] == "NOT_AVAILABLE" and r["cod_requested"] is None   # not booked yet
    book(sf, n)
    # a later catalogue price change must not change what the customer owes for this order
    run(sf["db"].products.update_one({"id": "p1"}, {"$set": {"selling_price": 9999}}))
    r = fin(sf, n).json()["finance"]
    assert r["customer_payable"]["amount"] == 1390 and r["cod_requested"] == 1390
    assert r["fees"]["delivery_fee"]["amount"] is None and r["fees"]["delivery_fee"]["basis"] == "not_available"
    assert r["expected_settlement"]["amount"] is None and r["status"] == "NOT_AVAILABLE"


def test_estimates_only_from_founder_settings_and_labelled(sf):
    n = booked_delivered(sf)
    client().put("/api/admin/settings", headers=admin_h(sf), json={"steadfast_estimated_delivery_fee_bdt": 110, "steadfast_estimated_cod_fee_pct": 1})
    r = fin(sf, n).json()["finance"]
    assert r["cod_collected"]["basis"] == "estimated" and r["cod_collected"]["amount"] == 1390
    assert r["fees"]["delivery_fee"] == {"amount": 110, "basis": "estimated", "note": "founder's estimate setting"}
    assert r["fees"]["cod_fee"]["amount"] == 13.9 and r["fees"]["cod_fee"]["basis"] == "estimated"
    assert r["expected_settlement"] == {"amount": 1266.1, "basis": "estimate"} and r["status"] == "ESTIMATED"


def test_statement_amounts_payout_mismatch_and_reconciliation(sf):
    n = booked_delivered(sf)
    r = act(sf, n, action="record_amounts", cod_collected=1390, delivery_fee=110, cod_fee=14, source="steadfast_statement", reference="ST-1")
    assert r.status_code == 200, r.text
    f = r.json()["finance"]
    assert f["status"] == "PROVIDER_CONFIRMED" and f["expected_settlement"] == {"amount": 1266, "basis": "confirmed"}
    # extra verified deduction + manual adjustment are both audited
    act(sf, n, action="add_deduction", amount=20, label="Weight surcharge", reference="ST-1")
    f = act(sf, n, action="add_adjustment", amount=-6, label="Rounding", note="statement rounding").json()["finance"]
    assert f["expected_settlement"]["amount"] == 1240
    # payout differs -> mismatch view, reconcile needs an explanation
    f = act(sf, n, action="record_payout", amount=1230, reference="PAY-77", paid_on="2026-10-25").json()["finance"]
    assert f["status"] == "SETTLED" and f["difference"] == -10
    rows = client().get("/api/admin/courier/finance?view=mismatch", headers=admin_h(sf)).json()
    assert [x["order_number"] for x in rows] == [n]
    assert act(sf, n, action="reconcile").status_code == 400
    f = act(sf, n, action="reconcile", note="Steadfast kept ৳10 for packaging, confirmed by phone").json()["finance"]
    assert f["status"] == "RECONCILED"
    assert [x["order_number"] for x in client().get("/api/admin/courier/finance?view=settled", headers=admin_h(sf)).json()] == [n]
    events = fin(sf, n).json()["events"]
    assert [e["action"] for e in events][::-1] == ["record_amounts", "add_deduction", "add_adjustment", "record_payout", "reconcile"]
    assert all(e["actor"] == "super_admin@example.test" for e in events)


def test_history_is_preserved_and_changes_need_a_reason(sf):
    n = booked_delivered(sf)
    act(sf, n, action="record_amounts", delivery_fee=110, cod_fee=14, cod_collected=1390)
    r = act(sf, n, action="record_amounts", delivery_fee=130)
    assert r.status_code == 400 and "reason" in r.json()["detail"]
    f = act(sf, n, action="record_amounts", delivery_fee=130, note="corrected from the final statement").json()["finance"]
    assert f["fees"]["delivery_fee"]["amount"] == 130
    stored = order(sf, n)["courier_finance"]["delivery_fee"]
    assert stored["previous"]["amount"] == 110  # previous value kept on the record
    ev = [e for e in fin(sf, n).json()["events"] if e["action"] == "record_amounts"][0]
    assert ev["before"]["delivery_fee"]["amount"] == 110 and ev["after"]["delivery_fee"]["amount"] == 130
    # voiding a deduction keeps it, marked void with a reason
    d = act(sf, n, action="add_deduction", amount=50, label="Mistake").json()["finance"]["deductions"][0]
    assert act(sf, n, action="void_entry", entry_id=d["id"]).status_code == 400
    f = act(sf, n, action="void_entry", entry_id=d["id"], note="entered twice").json()["finance"]
    assert f["deductions_total"] == 0
    assert order(sf, n)["courier_finance"]["deductions"][0]["voided"] is True


def test_duplicate_submissions_and_payment_events_are_idempotent(sf):
    n = booked_delivered(sf)
    key = uuid.uuid4().hex
    a = act(sf, n, key=key, action="add_deduction", amount=20, label="Surcharge").json()
    b = act(sf, n, key=key, action="add_deduction", amount=20, label="Surcharge").json()
    assert a["duplicate"] is False and b["duplicate"] is True and b["finance"]["deductions_total"] == 20
    act(sf, n, action="record_payout", amount=1000, reference="PAY-1")
    again = act(sf, n, action="record_payout", amount=1000, reference="PAY-1").json()
    assert again["duplicate"] is True
    assert act(sf, n, action="record_payout", amount=900, reference="PAY-2").status_code == 409  # needs a reason


def test_partial_cancelled_failed_cod_and_return(sf):
    # partial delivery: COD unknown until Steadfast's figures arrive
    n = packed_order(sf)
    book(sf, n)
    set_mock(sf, n, "partial_delivered")
    sync(sf, n)
    f = fin(sf, n).json()["finance"]
    assert f["cod_collected"]["amount"] is None and f["status"] == "NOT_AVAILABLE"
    assert n in [x["order_number"] for x in client().get("/api/admin/courier/finance?view=return_pending", headers=admin_h(sf)).json()]
    f = act(sf, n, action="record_amounts", cod_collected=600, delivery_fee=110, cod_fee=6, return_fee=55).json()["finance"]
    assert f["expected_settlement"]["amount"] == 429
    # cancelled: no COD expected; failed collection recorded as 0; return charge makes the balance negative
    n2 = packed_order(sf, phone="01812345678")
    book(sf, n2)
    set_mock(sf, n2, "cancelled")
    sync(sf, n2)
    f = fin(sf, n2).json()["finance"]
    assert f["cod_collected"] == {"amount": 0, "basis": "estimated", "note": "cancelled: no COD expected"}
    assert f["fees"]["return_fee"]["amount"] is None  # unknown return charge is pending, not 0
    f = act(sf, n2, action="record_amounts", cod_collected=0, delivery_fee=110, cod_fee=0, return_fee=55).json()["finance"]
    assert f["expected_settlement"] == {"amount": -165, "basis": "confirmed"}
    assert n2 in [x["order_number"] for x in client().get("/api/admin/courier/finance?view=exception", headers=admin_h(sf)).json()]


def test_finance_is_admin_only_and_never_customer_visible(sf):
    n = booked_delivered(sf)
    act(sf, n, action="record_amounts", delivery_fee=110, cod_fee=14, cod_collected=1390)
    for role in ("order_manager", "product_manager"):
        assert fin(sf, n, role).status_code == 403
        assert act(sf, n, role, action="record_payout", amount=1, reference="X").status_code == 403
    assert client().get(f"/api/admin/orders/{n}/courier/finance").status_code in (401, 403)
    # order managers still handle the order, without the money fields
    om = client().get(f"/api/admin/orders/{n}", headers=admin_h(sf, "order_manager")).json()
    assert "courier_finance" not in om
    lst = client().get("/api/admin/orders", headers=admin_h(sf, "order_manager")).json()
    assert all("courier_finance" not in o for o in lst)
    assert "courier_finance" in client().get(f"/api/admin/orders/{n}", headers=admin_h(sf)).json()
    t = client().post("/api/track", json={"order_number": n, "phone": "01712345678"}).json()[0]
    text = str(t)
    for word in ("courier_finance", "delivery_fee", "cod_fee", "payout", "settlement", "110"):
        assert word not in text


def test_payout_import_from_simulator_matches_by_consignment(sf):
    n = booked_delivered(sf)
    c = client()
    r = c.post(f"/api/admin/orders/{n}/courier/mock", headers=admin_h(sf), json={"action": "create_payout", "delivery_charge": 110, "cod_charge": 13.9})
    assert r.status_code == 200, r.text
    imp = c.post("/api/admin/courier/finance/import-payouts", headers=admin_h(sf)).json()
    assert [a["order_number"] for a in imp["applied"]] == [n]
    f = fin(sf, n).json()["finance"]
    assert f["status"] == "SETTLED" and f["actual_settlement"]["amount"] == 1266.1 and f["difference"] == 0
    assert f["fees"]["delivery_fee"]["basis"] == "provider_confirmed"
    # importing again changes nothing (duplicate payment event)
    again = c.post("/api/admin/courier/finance/import-payouts", headers=admin_h(sf)).json()
    assert again["applied"] == [] and again["already_imported"] == 1
    assert len([e for e in fin(sf, n).json()["events"] if e["action"] == "record_payout"]) == 1
    # an answer in an unexpected shape is reported, never guessed
    n2 = booked_delivered(sf, phone="01812345678")
    c.post(f"/api/admin/orders/{n2}/courier/mock", headers=admin_h(sf), json={"action": "create_payout", "delivery_charge": 110, "cod_charge": 13.9, "unreadable": True})
    imp = c.post("/api/admin/courier/finance/import-payouts", headers=admin_h(sf)).json()
    assert len(imp["unreadable"]) == 1 and fin(sf, n2).json()["finance"]["actual_settlement"] is None
    # simulator never assumes a fee
    assert c.post(f"/api/admin/orders/{n2}/courier/mock", headers=admin_h(sf), json={"action": "create_payout"}).status_code == 400


def test_live_payout_import_stays_off_until_schema_verified(sf, monkeypatch):
    monkeypatch.setenv("STEADFAST_MODE", "live")
    monkeypatch.setenv("STEADFAST_API_KEY", "k")
    monkeypatch.setenv("STEADFAST_SECRET_KEY", "s")
    r = client().post("/api/admin/courier/finance/import-payouts", headers=admin_h(sf))
    assert r.status_code == 409 and "checked" in r.json()["detail"]
    assert courier_finance.parse_payment_detail({"payment": {"id": 1}, "consignments": [{"consignment_id": 5}]}) is None
    assert courier_finance.parse_payment_detail({"data": []}) is None


def test_booking_cod_examples(sf):
    _add_priced(sf, {"d970": 970, "d1090": 1090, "d1510": 1510})
    for pid, phone, cod in (("d970", "01712000970", 1070), ("d1090", "01712001090", 1190), ("d1510", "01712001510", 1510)):
        n = packed_order(sf, items=((pid, 1),), phone=phone)
        assert book(sf, n).json()["courier"]["cod_amount"] == cod
        o = order(sf, n)
        assert o["total_amount"] == cod  # booking never changes the order total
        assert run(sf["db"].steadfast_mock_parcels.find_one({"invoice": n}))["cod_amount"] == cod

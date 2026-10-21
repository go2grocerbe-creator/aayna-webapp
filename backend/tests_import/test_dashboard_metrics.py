"""Dashboard order counters (21 Oct 2026): one counter per real order_status, nothing folded
into "New", counts follow status changes, and "today" uses the Asia/Dhaka calendar day."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_customer_accounts import env, client, admin_h, run  # noqa: E402,F401

import dashboard_metrics  # noqa: E402


def _orders(env, statuses, created_at="2026-10-01T00:00:00+00:00"):
    run(env["db"].orders.delete_many({}))
    for i, s in enumerate(statuses):
        run(env["db"].orders.insert_one({"order_number": f"AYN-T{i}", "order_status": s, "total_amount": 1000 + i,
                                         "payment_status": "Pending", "customer_name": "Test", "created_at": created_at}))


def dash(env):
    r = client().get("/api/admin/dashboard", headers=admin_h(env))
    assert r.status_code == 200, r.text
    return r.json()


def test_screenshot_fixture_three_new_one_confirmed_one_packed(env):
    _orders(env, ["New", "New", "New", "Confirmed", "Packed"])
    d = dash(env)
    assert (d["new_orders"], d["confirmed_orders"], d["packed_orders"], d["with_courier_orders"]) == (3, 1, 1, 0)
    assert (d["delivered_orders"], d["cancelled_orders"], d["returned_orders"], d["total_orders"]) == (0, 0, 0, 5)
    assert d["pending_orders"] == 5 and d["status_counts"]["unknown"] == {}
    # same numbers as the Orders list filtered by each status
    for status, key in (("New", "new_orders"), ("Confirmed", "confirmed_orders"), ("Packed", "packed_orders")):
        rows = client().get("/api/admin/orders", params={"status": status}, headers=admin_h(env)).json()
        assert len(rows) == d[key], status


def test_counts_follow_a_status_change(env):
    _orders(env, ["New", "New", "New", "Confirmed", "Packed"])
    # (the full order-update route is covered elsewhere; here only the counter's freshness matters)
    run(env["db"].orders.update_one({"order_number": "AYN-T0"}, {"$set": {"order_status": "Confirmed"}}))
    d = dash(env)
    assert (d["new_orders"], d["confirmed_orders"], d["packed_orders"]) == (2, 2, 1)


def test_unknown_or_messy_statuses_are_reported_not_swallowed():
    c = dashboard_metrics.count_statuses(["New", " New ", "Sent to Courier", "Unfamiliar", None])
    assert c["new"] == 2 and c["with_courier"] == 1 and c["unknown"] == {"Unfamiliar": 1, "(blank)": 1} and c["total"] == 5


def test_today_uses_dhaka_midnight():
    # 20 Oct 18:30 UTC = 21 Oct 00:30 in Dhaka -> today starts 20 Oct 18:00 UTC
    assert dashboard_metrics.dhaka_day_start_utc(datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)) == "2026-10-20T18:00:00+00:00"
    # 20 Oct 17:59 UTC = 20 Oct 23:59 in Dhaka -> today started 19 Oct 18:00 UTC
    assert dashboard_metrics.dhaka_day_start_utc(datetime(2026, 10, 20, 17, 59, tzinfo=timezone.utc)) == "2026-10-19T18:00:00+00:00"


def test_todays_orders_counts_only_the_dhaka_day(env):
    start = dashboard_metrics.dhaka_day_start_utc()
    _orders(env, ["New"], created_at=start)                      # exactly at Dhaka midnight -> today
    run(env["db"].orders.insert_one({"order_number": "AYN-OLD", "order_status": "New", "total_amount": 1, "payment_status": "Pending",
                                     "customer_name": "Old", "created_at": "2000-01-01T00:00:00+00:00"}))
    d = dash(env)
    assert d["todays_orders"] == 1 and d["new_orders"] == 2

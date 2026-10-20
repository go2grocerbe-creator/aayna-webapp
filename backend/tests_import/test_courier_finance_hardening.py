"""Courier-ledger hardening (20 Oct 2026 audit): concurrent writes, audit atomicity, money math.

Simulator only - no real Steadfast call, no live payout import. The Decimal oracle in
ledger_reference.py (from the founder's handoff) is an independent check of compute()."""
import asyncio
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_customer_accounts import env, client, admin_h, run  # noqa: E402,F401
from test_steadfast import sf, packed_order, book, sync, set_mock  # noqa: E402,F401
from test_courier_finance import fin, act, booked_delivered  # noqa: E402

import courier_finance  # noqa: E402
from courier_finance import FinanceAction, apply_action, compute  # noqa: E402
from ledger_reference import Line, expected_settlement as oracle_expected, variance as oracle_variance  # noqa: E402


class _Gated:
    """Wraps a collection: the first `hold` find_one calls all return only after every one of
    them has read, so concurrent actions are guaranteed to start from the same old record."""

    def __init__(self, real, hold=2):
        self.real, self.hold, self.reads, self.ev = real, hold, 0, None

    def __getattr__(self, name):
        return getattr(self.real, name)

    async def find_one(self, *a, **k):
        doc = await self.real.find_one(*a, **k)
        if self.reads < self.hold:
            self.ev = self.ev or asyncio.Event()
            self.reads += 1
            if self.reads == self.hold:
                self.ev.set()
            await self.ev.wait()
        return doc


class _FailingEvents:
    """Event collection whose first write fails, like a crash/network drop after the order update."""

    def __init__(self, real):
        self.real, self.failed = real, False

    def __getattr__(self, name):
        attr = getattr(self.real, name)
        if name in ("insert_one", "update_one", "replace_one") and not self.failed:
            async def boom(*a, **k):
                self.failed = True
                raise RuntimeError("simulated failure after the order was updated")
            return boom
        return attr


class _DbProxy:
    def __init__(self, real, **over):
        self.real, self.over = real, over

    def __getattr__(self, name):
        return self.over.get(name) or getattr(self.real, name)

    def __getitem__(self, name):
        return self.over.get(name) or self.real[name]


def _events(env, n):
    return run(env["db"].courier_finance_events.find({"order_number": n}, {"_id": 0}).to_list(100))


def test_two_different_concurrent_actions_both_survive(sf, monkeypatch):
    n = booked_delivered(sf)
    monkeypatch.setattr(courier_finance, "db", _DbProxy(sf["db"], orders=_Gated(sf["db"].orders)))

    async def both():
        return await asyncio.gather(
            apply_action(n, FinanceAction(action="add_deduction", key="k-deduct-0001", amount=20, label="Weight surcharge"), "a@x.test"),
            apply_action(n, FinanceAction(action="add_deduction", key="k-deduct-0002", amount=15, label="Packaging"), "b@x.test"))

    res = run(both())
    assert [r["duplicate"] for r in res] == [False, False]
    order = run(sf["db"].orders.find_one({"order_number": n}))
    deds = order["courier_finance"]["deductions"]
    assert sorted(d["amount"] for d in deds) == [15, 20], "a concurrent action was lost"
    assert {"k-deduct-0001", "k-deduct-0002"} <= set(order["courier_finance"]["applied_keys"])
    assert len(_events(sf, n)) == 2


def test_same_key_submitted_twice_concurrently_applies_once(sf, monkeypatch):
    n = booked_delivered(sf)
    monkeypatch.setattr(courier_finance, "db", _DbProxy(sf["db"], orders=_Gated(sf["db"].orders)))
    body = FinanceAction(action="add_deduction", key="k-same-00001", amount=20, label="Weight surcharge")

    async def both():
        return await asyncio.gather(apply_action(n, body, "a@x.test"), apply_action(n, body, "a@x.test"))

    res = run(both())
    assert sorted(r["duplicate"] for r in res) == [False, True]
    order = run(sf["db"].orders.find_one({"order_number": n}))
    assert len(order["courier_finance"]["deductions"]) == 1
    assert len(_events(sf, n)) == 1


def test_failure_after_order_update_leaves_a_replayable_audit_event(sf, monkeypatch):
    n = booked_delivered(sf)
    monkeypatch.setattr(courier_finance, "db", _DbProxy(sf["db"], courier_finance_events=_FailingEvents(sf["db"].courier_finance_events)))
    body = FinanceAction(action="add_deduction", key="k-crash-0001", amount=20, label="Weight surcharge")
    with pytest.raises(RuntimeError):
        run(apply_action(n, body, "a@x.test"))
    monkeypatch.setattr(courier_finance, "db", sf["db"])
    order = run(sf["db"].orders.find_one({"order_number": n}))
    assert len(order["courier_finance"]["deductions"]) == 1          # the change itself was saved
    # the next read of the ledger publishes the pending audit event, exactly once
    events = fin(sf, n).json()["events"]
    assert [(e["action"], e["key"]) for e in events] == [("add_deduction", "k-crash-0001")]
    assert fin(sf, n).json()["events"] == events
    # a retry of the same submission is a duplicate and adds nothing
    assert run(apply_action(n, body, "a@x.test"))["duplicate"] is True
    assert len(_events(sf, n)) == 1
    order = run(sf["db"].orders.find_one({"order_number": n}))
    assert not order["courier_finance"].get("outbox")


def test_event_log_has_unique_order_key_index(sf):
    run(courier_finance.ensure_finance_indexes())
    info = run(sf["db"].courier_finance_events.index_information())
    unique = [v["key"] for v in info.values() if v.get("unique")]
    assert [("order_number", 1), ("key", 1)] in unique


def test_existing_records_without_revision_still_work_and_get_one(sf):
    n = booked_delivered(sf)
    # a ledger written before this change: no revision field
    run(sf["db"].orders.update_one({"order_number": n}, {"$set": {"courier_finance": {"applied_keys": ["old-key-0001"], "deductions": []}}}))
    r = act(sf, n, action="add_deduction", amount=5, label="Old style")
    assert r.status_code == 200, r.text
    f = run(sf["db"].orders.find_one({"order_number": n}))["courier_finance"]
    assert f["revision"] == 1 and len(f["deductions"]) == 1
    act(sf, n, action="add_deduction", amount=6, label="Second")
    assert run(sf["db"].orders.find_one({"order_number": n}))["courier_finance"]["revision"] == 2


def _order(cod, delivery, cod_fee, ret, deductions=(), adjustments=(), payout=None, raw="delivered"):
    stamp = {"basis": "statement", "source": "steadfast_statement"}
    f = {"cod_collected": {"amount": cod, **stamp}, "delivery_fee": {"amount": delivery, **stamp},
         "cod_fee": {"amount": cod_fee, **stamp},
         "deductions": [{"id": str(i), "amount": a} for i, a in enumerate(deductions)],
         "adjustments": [{"id": str(i), "amount": a} for i, a in enumerate(adjustments)]}
    if ret is not None:
        f["return_fee"] = {"amount": ret, **stamp}
    if payout is not None:
        f["payout"] = {"amount": payout, "reference": "PAY-1"}
    return {"order_number": "AYN-T", "payment_method": "cod", "items": [], "courier_finance": f,
            "courier": {"state": "booked", "status_raw": raw, "cod_amount": cod, "consignment_id": "1"}}


@pytest.mark.parametrize("cod,delivery,cod_fee,ret,deds,adjs,payout", [
    (1390, 110, 14, 0, (), (), 1266),
    (1390.10, 110.20, 13.90, 0, ("0.1", "0.2"), (), 1265.71),
    (600, 110, 6, 55, ("20",), ("-6",), 400),
    (0, 110, 0, 55, (), (), -165),
    (2875.55, 130.35, 28.76, 0, ("12.35",), ("0.05", "-0.10"), 2704.03),
    (999999.99, 0.01, 0.01, 0, (), (), 999999.97),
])
def test_compute_matches_decimal_oracle(cod, delivery, cod_fee, ret, deds, adjs, payout):
    raw = "delivered" if ret == 0 else "cancelled_return_received"
    f = compute(_order(cod, delivery, cod_fee, ret, [float(d) for d in deds], [float(a) for a in adjs], payout, raw=raw))
    ret_line = Line.of(ret, "not_applicable" if ret == 0 and raw == "delivered" else "statement")
    exp, basis = oracle_expected(Line.of(cod, "statement"), Line.of(delivery, "statement"), Line.of(cod_fee, "statement"), ret_line,
                                 deductions=deds, adjustments=adjs)
    assert Decimal(str(f["expected_settlement"]["amount"])).quantize(Decimal("0.01")) == exp
    assert f["expected_settlement"]["basis"] == basis == "confirmed"
    assert Decimal(str(f["difference"])).quantize(Decimal("0.01")) == oracle_variance(payout, exp)


def test_unknown_fee_is_never_zero_like_the_oracle():
    o = _order(1390, None, 14, 0)
    o["courier_finance"]["delivery_fee"] = {}
    f = compute(o)
    exp, basis = oracle_expected(Line.of(1390, "statement"), Line.of(None, "not_available"), Line.of(14, "statement"), Line.of(0, "not_applicable"))
    assert f["expected_settlement"]["amount"] is None and exp is None and basis == "not_available"
    assert f["status"] != "SETTLED"


def test_three_concurrent_actions_all_survive_within_the_retry_bound(sf, monkeypatch):
    n = booked_delivered(sf)
    monkeypatch.setattr(courier_finance, "db", _DbProxy(sf["db"], orders=_Gated(sf["db"].orders, hold=3)))

    async def three():
        return await asyncio.gather(
            apply_action(n, FinanceAction(action="add_deduction", key="k-three-0001", amount=1, label="a"), "a@x.test"),
            apply_action(n, FinanceAction(action="add_adjustment", key="k-three-0002", amount=-2, label="b"), "b@x.test"),
            apply_action(n, FinanceAction(action="record_amounts", key="k-three-0003", delivery_fee=110, cod_fee=14,
                                          cod_collected=1390), "c@x.test"))

    run(three())
    f = run(sf["db"].orders.find_one({"order_number": n}))["courier_finance"]
    assert len(f["deductions"]) == 1 and len(f["adjustments"]) == 1 and f["delivery_fee"]["amount"] == 110
    assert f["revision"] == 3 and not f.get("outbox")
    assert sorted(e["key"] for e in _events(sf, n)) == ["k-three-0001", "k-three-0002", "k-three-0003"]
    assert fin(sf, n).json()["finance"]["expected_settlement"]["amount"] == 1390 - 110 - 14 - 1 - 2

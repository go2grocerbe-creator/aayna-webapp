"""
Order-level Steadfast financials (admin-only): what the customer owes, what the courier
charges AAYNA, what AAYNA should receive, and what Steadfast actually paid.

One record per order, stored on the order as `courier_finance` (the single source of truth),
plus an append-only `courier_finance_events` log (who, when, what changed, before/after,
source, reason). Nothing here changes the order's own totals.

    A. customer payable   = merchandise subtotal - approved discount + customer delivery charge
                            - verified prepayment            (from the SAVED order, never live prices)
    B. courier charges    = delivery fee, COD fee, return fee, other deductions (each with a basis)
    C. expected settlement= COD collected (confirmed, else expected) - delivery fee - COD fee
                            - return fee - other deductions + adjustments
    D. actual settlement  = the payout Steadfast reports / the founder records, with its reference
    E. profit             = NOT computed here (needs product and packaging costs; out of scope)

Every amount carries a basis: provider_confirmed / statement (entered by an admin from a
Steadfast statement) / estimated (from the founder's optional estimate settings) /
not_available. Unknown is never shown as 0 and an estimate is never called a payout.

Record status (one of):
    NOT_AVAILABLE      no booking yet, or not enough is known to estimate anything
    ESTIMATED          expected settlement computed with at least one estimate
    PROVIDER_CONFIRMED COD collected and all fees confirmed (provider or statement), no payout yet
    SETTLED            a payout has been recorded (amount + reference)
    RECONCILED         payout checked against the expected amount and accepted by an admin
    DISPUTED           an admin flagged a problem with the payout or the charges

Provider payouts (GET /payments, /payments/{id}): the founder's guide confirms the endpoints
but not their response fields. The importer below accepts ONE explicit schema and anything
else is reported, never guessed. In live mode it stays off until STEADFAST_PAYMENTS_SCHEMA_VERIFIED
is set after checking a real response; the simulator uses that schema for testing.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require, has_permission
from db import db, now_iso
import steadfast

CALC_VERSION = 1
BASES = ("provider_confirmed", "statement", "estimated", "not_available")
CONFIRMED = ("provider_confirmed", "statement")
FEE_FIELDS = ("delivery_fee", "cod_fee", "return_fee")
EST_DELIVERY_KEY = "steadfast_estimated_delivery_fee_bdt"   # optional founder setting, blank by default
EST_COD_PCT_KEY = "steadfast_estimated_cod_fee_pct"         # optional founder setting, blank by default
STATUSES = ("NOT_AVAILABLE", "ESTIMATED", "PROVIDER_CONFIRMED", "SETTLED", "RECONCILED", "DISPUTED")

finance_router = APIRouter(prefix="/api/admin")


def _num(v) -> Optional[float]:
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n else None


def _money(v):
    if v is None:
        return None
    v = round(float(v), 2)
    return int(v) if v.is_integer() else v


def _amount(entry) -> Optional[float]:
    return _num((entry or {}).get("amount")) if isinstance(entry, dict) else None


def compute(order: dict, settings: Optional[dict] = None) -> dict:
    """Pure calculation from the saved order + its finance record. No I/O."""
    settings = settings or {}
    fin = order.get("courier_finance") or {}
    courier = order.get("courier") or {}
    raw = courier.get("status_raw")
    info = steadfast.status_info(raw)
    kind = info[1] if info else None

    payable = steadfast.cod_amount(order)
    cod_requested = _num(courier.get("cod_amount")) if courier.get("state") == "booked" else None

    # COD collected: confirmed amount, else what is expected from the delivery outcome.
    cod_entry = fin.get("cod_collected") or {}
    if _amount(cod_entry) is not None and cod_entry.get("basis") in CONFIRMED:
        cod = {"amount": _amount(cod_entry), "basis": cod_entry["basis"]}
    elif cod_requested is None:
        cod = {"amount": None, "basis": "not_available"}
    elif raw == "delivered":
        cod = {"amount": cod_requested, "basis": "estimated", "note": "delivered: full COD expected, not yet confirmed"}
    elif raw in ("cancelled", "cancelled_return_proccessing", "cancelled_return_rider_assigned", "cancelled_return_received"):
        cod = {"amount": 0.0, "basis": "estimated", "note": "cancelled: no COD expected"}
    elif kind in ("attention", "return", "return_received") or (raw or "").startswith("partial"):
        cod = {"amount": None, "basis": "not_available", "note": "partial / exception: wait for Steadfast's figures"}
    else:
        cod = {"amount": cod_requested, "basis": "estimated", "note": "not delivered yet"}

    est_fee = _num(settings.get(EST_DELIVERY_KEY))
    est_pct = _num(settings.get(EST_COD_PCT_KEY))

    def fee(field):
        e = fin.get(field) or {}
        if _amount(e) is not None and e.get("basis") in CONFIRMED + ("estimated",):
            return {"amount": _amount(e), "basis": e["basis"]}
        if cod_requested is None:
            return {"amount": None, "basis": "not_available"}
        if field == "delivery_fee" and est_fee is not None:
            return {"amount": est_fee, "basis": "estimated", "note": "founder's estimate setting"}
        if field == "cod_fee" and est_pct is not None and cod["amount"] is not None:
            return {"amount": round(cod["amount"] * est_pct / 100.0, 2), "basis": "estimated", "note": f"{est_pct:g}% estimate setting"}
        if field == "return_fee" and raw == "delivered":
            return {"amount": 0.0, "basis": "not_applicable", "note": "delivered: no return"}
        if field == "return_fee" and not (raw or "").startswith(("cancelled", "partial")):
            return {"amount": 0.0, "basis": "estimated", "note": "no return so far"}
        return {"amount": None, "basis": "not_available"}

    fees = {f: fee(f) for f in FEE_FIELDS}
    deductions = [d for d in fin.get("deductions") or [] if not d.get("voided")]
    adjustments = [a for a in fin.get("adjustments") or [] if not a.get("voided")]
    ded_total = sum(_num(d.get("amount")) or 0 for d in deductions)
    adj_total = sum(_num(a.get("amount")) or 0 for a in adjustments)

    parts = [cod] + list(fees.values())
    if any(p["amount"] is None for p in parts):
        expected = None
        expected_basis = "not_available"
    else:
        expected = cod["amount"] - sum(p["amount"] for p in fees.values()) - ded_total + adj_total
        expected_basis = "confirmed" if all(p["basis"] in CONFIRMED + ("not_applicable",) for p in parts) else "estimate"

    payout = fin.get("payout") or None
    actual = _num((payout or {}).get("amount"))
    difference = None if (actual is None or expected is None) else round(actual - expected, 2)

    if fin.get("flag") == "disputed":
        status = "DISPUTED"
    elif fin.get("flag") == "reconciled":
        status = "RECONCILED"
    elif actual is not None:
        status = "SETTLED"
    elif expected is not None and expected_basis == "confirmed":
        status = "PROVIDER_CONFIRMED"
    elif expected is not None:
        status = "ESTIMATED"
    else:
        status = "NOT_AVAILABLE"

    return {
        "order_number": order.get("order_number"), "calc_version": CALC_VERSION,
        "consignment_id": courier.get("consignment_id"), "tracking_code": courier.get("tracking_code"),
        "payment_method": order.get("payment_method"), "courier_status": raw,
        "customer_payable": {"amount": _money(payable.get("amount")) if payable.get("ok") else None,
                             "breakdown": payable.get("breakdown"), "problem": None if payable.get("ok") else payable.get("reason")},
        "cod_requested": _money(cod_requested),
        "cod_collected": {**cod, "amount": _money(cod["amount"])},
        "fees": {f: {**v, "amount": _money(v["amount"])} for f, v in fees.items()},
        "deductions": deductions, "deductions_total": _money(ded_total),
        "adjustments": adjustments, "adjustments_total": _money(adj_total),
        "expected_settlement": {"amount": _money(expected), "basis": expected_basis},
        "actual_settlement": ({**payout, "amount": _money(actual)} if payout else None),
        "difference": _money(difference),
        "status": status, "flag_note": fin.get("flag_note"),
        "last_verified_source": fin.get("last_verified_source"), "last_sync_at": courier.get("last_sync_at"),
        "updated_at": fin.get("updated_at"),
    }


def view_bucket(order: dict, f: dict) -> List[str]:
    """Which finance filters an order belongs to."""
    raw = f.get("courier_status") or ""
    info = steadfast.status_info(raw)
    out = []
    if f["status"] in ("ESTIMATED", "PROVIDER_CONFIRMED") and raw in ("delivered", "partial_delivered"):
        out.append("awaiting")
    if f["status"] in ("SETTLED", "RECONCILED"):
        out.append("settled")
    if f["status"] == "DISPUTED" or (f["status"] == "SETTLED" and f["difference"] not in (None, 0)):
        out.append("mismatch")
    if (order.get("courier") or {}).get("attention") or (info and info[1] == "attention"):
        out.append("exception")
    if raw.startswith(("cancelled", "partial")) and raw not in ("cancelled_return_received", "partial_delivered_return_received"):
        out.append("return_pending")
    return out


async def _settings() -> dict:
    docs = await db.website_settings.find({"setting_key": {"$in": [EST_DELIVERY_KEY, EST_COD_PCT_KEY]}}, {"_id": 0}).to_list(10)
    return {d["setting_key"]: d["setting_value"] for d in docs}


# --- writes ---------------------------------------------------------------------
class FinanceAction(BaseModel):
    action: str                      # record_amounts | add_deduction | add_adjustment | record_payout | reconcile | dispute | void_entry
    key: str = Field(..., min_length=8, max_length=80)   # idempotency key (one per submission / provider event)
    source: str = Field("steadfast_statement", max_length=40)
    reference: Optional[str] = Field(None, max_length=80)
    note: Optional[str] = Field(None, max_length=500)
    cod_collected: Optional[float] = None
    delivery_fee: Optional[float] = None
    cod_fee: Optional[float] = None
    return_fee: Optional[float] = None
    amount: Optional[float] = None
    label: Optional[str] = Field(None, max_length=80)
    paid_on: Optional[str] = Field(None, max_length=40)
    entry_id: Optional[str] = Field(None, max_length=40)


SOURCES = {"steadfast_statement", "steadfast_portal", "steadfast_api", "bank_statement", "other"}


def _check_amount(name, v, allow_negative=False):
    if v is None:
        return None
    if v != v or abs(v) > 10_000_000 or (v < 0 and not allow_negative):
        raise HTTPException(status_code=400, detail=f"{name}: enter a valid amount in taka")
    return round(float(v), 2)


async def apply_action(order_number: str, body: FinanceAction, actor: str, provider: bool = False) -> dict:
    order = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if (order.get("courier") or {}).get("state") != "booked":
        raise HTTPException(status_code=409, detail="This order has no Steadfast consignment yet.")
    if body.source not in SOURCES:
        raise HTTPException(status_code=400, detail="Unknown source")
    fin = dict(order.get("courier_finance") or {})
    if body.key in (fin.get("applied_keys") or []):
        return {"duplicate": True, "finance": compute(order, await _settings())}
    basis = "provider_confirmed" if provider else "statement"
    at = now_iso()
    before = {}
    after = {}
    stamp = {"basis": basis, "source": body.source, "reference": body.reference, "at": at, "by": actor}

    if body.action == "record_amounts":
        vals = {"cod_collected": _check_amount("COD collected", body.cod_collected),
                **{f: _check_amount(f.replace("_", " "), getattr(body, f)) for f in FEE_FIELDS}}
        vals = {k: v for k, v in vals.items() if v is not None}
        if not vals:
            raise HTTPException(status_code=400, detail="Enter at least one amount")
        for k, v in vals.items():
            old = fin.get(k) or {}
            if _amount(old) is not None and old.get("basis") in CONFIRMED and _amount(old) != v and not (body.note or "").strip():
                raise HTTPException(status_code=400, detail=f"{k.replace('_', ' ')} was already recorded as {_money(_amount(old))}. Give a reason to change it.")
            before[k] = old or None
            fin[k] = {"amount": v, **stamp, "previous": old or None}
            after[k] = fin[k]
    elif body.action in ("add_deduction", "add_adjustment"):
        amt = _check_amount("Amount", body.amount, allow_negative=body.action == "add_adjustment")
        if amt is None or not (body.label or body.note):
            raise HTTPException(status_code=400, detail="Enter an amount and a label or reason")
        field = "deductions" if body.action == "add_deduction" else "adjustments"
        entry = {"id": str(uuid.uuid4())[:12], "amount": amt, "label": body.label or body.note, **stamp, "note": body.note}
        fin[field] = list(fin.get(field) or []) + [entry]
        after[field] = entry
    elif body.action == "void_entry":
        if not body.entry_id or not (body.note or "").strip():
            raise HTTPException(status_code=400, detail="Choose the entry and give a reason")
        found = False
        for field in ("deductions", "adjustments"):
            items = [dict(x) for x in fin.get(field) or []]
            for x in items:
                if x.get("id") == body.entry_id and not x.get("voided"):
                    before[field] = dict(x)
                    x.update(voided=True, voided_at=at, voided_by=actor, void_reason=body.note)
                    after[field] = x
                    found = True
            fin[field] = items
        if not found:
            raise HTTPException(status_code=404, detail="Entry not found")
    elif body.action == "record_payout":
        amt = _check_amount("Payout", body.amount, allow_negative=True)
        if amt is None or not (body.reference or "").strip():
            raise HTTPException(status_code=400, detail="Enter the payout amount and Steadfast's payment reference")
        old = fin.get("payout")
        if old:
            if old.get("reference") == body.reference and _num(old.get("amount")) == amt:
                return {"duplicate": True, "finance": compute(order, await _settings())}
            if not (body.note or "").strip():
                raise HTTPException(status_code=409, detail="A payout is already recorded for this order. Give a reason to replace it.")
        before["payout"] = old
        fin["payout"] = {"amount": amt, "reference": body.reference.strip(), "paid_on": body.paid_on, **stamp, "previous": old}
        after["payout"] = fin["payout"]
        fin.pop("flag", None)
    elif body.action in ("reconcile", "dispute"):
        current = compute({**order, "courier_finance": fin}, await _settings())
        if body.action == "reconcile":
            if current["actual_settlement"] is None:
                raise HTTPException(status_code=409, detail="Record the payout before reconciling.")
            if current["difference"] not in (0, None) and not (body.note or "").strip():
                raise HTTPException(status_code=400, detail=f"The payout differs from the expected amount by {current['difference']}. Explain the difference to reconcile.")
            if current["difference"] is None and not (body.note or "").strip():
                raise HTTPException(status_code=400, detail="The expected amount is not fully known. Add a note to reconcile anyway.")
        elif not (body.note or "").strip():
            raise HTTPException(status_code=400, detail="Describe the problem")
        before["flag"] = fin.get("flag")
        fin.update(flag="reconciled" if body.action == "reconcile" else "disputed", flag_note=(body.note or "").strip(), flag_at=at, flag_by=actor)
        after["flag"] = fin["flag"]
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    fin.update(calc_version=CALC_VERSION, updated_at=at, last_verified_source=body.source,
               applied_keys=(list(fin.get("applied_keys") or []) + [body.key])[-200:])
    res = await db.orders.update_one({"order_number": order_number, "courier_finance.applied_keys": {"$ne": body.key}},
                                     {"$set": {"courier_finance": fin}})
    if res.modified_count != 1:
        fresh = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
        return {"duplicate": True, "finance": compute(fresh, await _settings())}
    await db.courier_finance_events.insert_one({"id": str(uuid.uuid4()), "order_number": order_number, "action": body.action,
                                                "key": body.key, "basis": basis, "source": body.source, "reference": body.reference,
                                                "note": body.note, "before": before, "after": after, "actor": actor, "created_at": at})
    fresh = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    return {"duplicate": False, "finance": compute(fresh, await _settings())}


# --- provider payouts -------------------------------------------------------------
def parse_payment_detail(body: dict) -> Optional[dict]:
    """Strict: {"payment": {"id", "amount", ...}, "consignments": [{"consignment_id", "cod_amount",
    "delivery_charge", "cod_charge", "return_charge"?}]} - anything else -> None (manual reconciliation)."""
    pay = body.get("payment") if isinstance(body, dict) else None
    rows = body.get("consignments") if isinstance(body, dict) else None
    if not isinstance(pay, dict) or not isinstance(rows, list) or pay.get("id") in (None, ""):
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict) or r.get("consignment_id") in (None, ""):
            return None
        vals = {k: _num(r.get(k)) for k in ("cod_amount", "delivery_charge", "cod_charge", "return_charge")}
        if vals["cod_amount"] is None or vals["delivery_charge"] is None or vals["cod_charge"] is None:
            return None
        out.append({"consignment_id": str(r["consignment_id"]), **vals})
    return {"payment_id": str(pay["id"]), "amount": _num(pay.get("amount")), "paid_on": pay.get("paid_at") or pay.get("created_at"),
            "rows": out}


def payments_import_enabled() -> Optional[str]:
    mode = steadfast.config()["mode"]
    if mode == "mock":
        return None
    if mode != "live":
        return "Steadfast is not configured"
    if steadfast._env("STEADFAST_PAYMENTS_SCHEMA_VERIFIED").lower() not in ("1", "true", "yes"):
        return "Automatic payout import is off until a real /payments response has been checked against the expected fields."
    return None


async def import_payouts(actor: str, max_payments: int = 10) -> dict:
    why = payments_import_enabled()
    if why:
        raise HTTPException(status_code=409, detail=why)
    lst = await steadfast.call("GET", "/payments")
    if lst.outcome != "answered" or lst.status != 200:
        raise HTTPException(status_code=502, detail=f"Steadfast payments list unavailable ({steadfast._message(lst)})")
    items = lst.body.get("data") if isinstance(lst.body.get("data"), list) else None
    if items is None:
        raise HTTPException(status_code=502, detail="Unexpected payments list format - nothing imported; reconcile by hand.")
    applied, unmatched, skipped, unreadable = [], [], 0, []
    for item in items[:max_payments]:
        pid = str((item or {}).get("id") or "")
        if not pid or await db.courier_payment_imports.find_one({"payment_id": pid, "complete": True}):
            skipped += 1
            continue
        det = await steadfast.call("GET", f"/payments/{pid}")
        parsed = parse_payment_detail(det.body) if det.outcome == "answered" and det.status == 200 else None
        if not parsed:
            unreadable.append(pid)
            await db.courier_payment_imports.update_one({"payment_id": pid}, {"$set": {"payment_id": pid, "complete": False,
                                                        "problem": "unreadable detail", "at": now_iso()}}, upsert=True)
            continue
        per_order = []
        for row in parsed["rows"]:
            order = await db.orders.find_one({"courier.consignment_id": row["consignment_id"]}, {"_id": 0, "order_number": 1})
            if not order:
                unmatched.append({"payment_id": pid, "consignment_id": row["consignment_id"]})
                continue
            n = order["order_number"]
            base = dict(source="steadfast_api", reference=pid)
            await apply_action(n, FinanceAction(action="record_amounts", key=f"pay:{pid}:{row['consignment_id']}:amounts",
                                                cod_collected=row["cod_amount"], delivery_fee=row["delivery_charge"],
                                                cod_fee=row["cod_charge"], return_fee=row["return_charge"],
                                                note="from Steadfast payment detail", **base), actor, provider=True)
            settled = row["cod_amount"] - row["delivery_charge"] - row["cod_charge"] - (row["return_charge"] or 0)
            await apply_action(n, FinanceAction(action="record_payout", key=f"pay:{pid}:{row['consignment_id']}:payout",
                                                amount=settled, paid_on=parsed["paid_on"],
                                                note="per-consignment share of Steadfast payment " + pid, **base), actor, provider=True)
            per_order.append(n)
            applied.append({"payment_id": pid, "order_number": n})
        await db.courier_payment_imports.update_one({"payment_id": pid}, {"$set": {"payment_id": pid, "complete": True, "orders": per_order,
                                                                                   "amount": parsed["amount"], "at": now_iso(), "by": actor}}, upsert=True)
    return {"applied": applied, "unmatched": unmatched, "unreadable": unreadable, "already_imported": skipped}


# --- routes -------------------------------------------------------------------------
@finance_router.get("/orders/{order_number}/courier/finance")
async def finance_view(order_number: str, current=Depends(require("courier.finance"))):
    order = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    events = await db.courier_finance_events.find({"order_number": order_number}, {"_id": 0}).sort("created_at", -1).to_list(100)
    settings = await _settings()
    return {"finance": compute(order, settings), "events": events,
            "estimates": {"delivery_fee": _num(settings.get(EST_DELIVERY_KEY)), "cod_fee_pct": _num(settings.get(EST_COD_PCT_KEY))}}


@finance_router.post("/orders/{order_number}/courier/finance")
async def finance_action(order_number: str, body: FinanceAction, current=Depends(require("courier.finance"))):
    if body.action not in ("record_amounts", "add_deduction", "add_adjustment", "record_payout", "reconcile", "dispute", "void_entry"):
        raise HTTPException(status_code=400, detail="Unknown action")
    return await apply_action(order_number, body, current["email"])


@finance_router.get("/courier/finance")
async def finance_list(view: Optional[str] = None, current=Depends(require("courier.finance"))):
    settings = await _settings()
    orders = await db.orders.find({"courier.state": "booked"}, {"_id": 0}).sort("created_at", -1).to_list(500)
    rows = []
    for o in orders:
        f = compute(o, settings)
        buckets = view_bucket(o, f)
        if view and view not in buckets:
            continue
        rows.append({"order_number": o["order_number"], "customer_name": o.get("customer_name"), "created_at": o.get("created_at"),
                     "courier_status": f["courier_status"], "status": f["status"], "customer_payable": f["customer_payable"]["amount"],
                     "cod_requested": f["cod_requested"], "expected": f["expected_settlement"], "actual": (f["actual_settlement"] or {}).get("amount"),
                     "difference": f["difference"], "buckets": buckets})
    return rows


@finance_router.post("/courier/finance/import-payouts")
async def finance_import(current=Depends(require("courier.finance"))):
    return await import_payouts(current["email"])


def strip_finance(order: dict, user: dict) -> dict:
    """Courier financials are for super admins and admins only."""
    if order and not has_permission(user, "courier.finance"):
        order.pop("courier_finance", None)
    return order


async def ensure_finance_indexes():
    try:
        await db.courier_finance_events.create_index([("order_number", 1), ("created_at", -1)], name="finance_events_order")
        await db.courier_payment_imports.create_index("payment_id", unique=True, name="payment_import_unique")
    except Exception:  # noqa: BLE001
        pass

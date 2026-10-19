"""
Steadfast courier integration (merchant API v1, https://portal.packzy.com/api/v1).

Source of truth for the provider behaviour: the founder-supplied merchant API guide
(docs/STEADFAST_COURIER.md, summarised from "AAYNA Steadfast API Reference",
19 Oct 2026). That guide does NOT include response schemas, webhook
authentication or the exact "not found" / duplicate-invoice answers, so this
module parses provider answers defensively and anything it cannot confirm ends
in a state a person resolves ("needs_reconciliation"), never in a guess.

Modes (STEADFAST_MODE, server-side only):
    off   (default)  nothing is sent anywhere; the admin panel says "not configured"
    mock             deterministic in-process simulator (no network). Refused on aayna_prod.
    live             real API with STEADFAST_API_KEY / STEADFAST_SECRET_KEY. Creating a
                     real consignment ALSO needs STEADFAST_REAL_BOOKINGS=true and
                     DB_NAME=aayna_prod (founder approval). Status look-ups are read-only.

Workflow (explicit admin actions only - nothing is booked at checkout):
    order Packed -> [Book with Steadfast] -> courier.state "booked" (order stays Packed)
    -> admin sets "Sent to Courier" at hand-over (existing email) -> status checks
    -> confirmed "delivered" moves the order to Delivered (existing email).
Courier statuses never move an order backwards, never cancel/return an order and
never add stock back: cancelled / partial / hold / exceptional only raise an
admin "attention" flag (returned stock stays a manual, inspected step).

Duplicate-shipment protection:
    * invoice = the immutable AAYNA order number;
    * an atomic claim on the order document (state "booking" + claim id) so two
      clicks or two admins cannot both send a booking;
    * a unique index on courier.consignment_id;
    * an ambiguous outcome (timeout after sending, 5xx, 200 without an id) is
      never retried automatically: it becomes "needs_reconciliation" and is
      checked against Steadfast by invoice before anything else happens.

Credentials are read only from the environment, are sent only in request headers
to STEADFAST_BASE_URL, and never appear in responses, logs, errors or the database.
"""
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from auth import require
from db import db, now_iso

logger = logging.getLogger("aayna")

PROVIDER = "steadfast"
COURIER_NAME = "Steadfast"
DEFAULT_BASE_URL = "https://portal.packzy.com/api/v1"
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
STATE_DOC = "steadfast"
STATUS_CACHE_SECONDS = 60          # provider caches status answers for 60 s
STALE_CLAIM_SECONDS = 120          # a "booking" older than this can be reconciled
AUTH_BLOCK_SECONDS = 15 * 60       # after a 401/403: stop calling (10 failures/5 min -> 60 min lockout)
RATE_BLOCK_SECONDS = 60

# Provider field limits (guide: silently truncated by Steadfast - we refuse instead).
LIMITS = {"invoice": 100, "recipient_name": 100, "recipient_phone": 40, "recipient_address": 490, "note": 480}
PROVIDER_STRIPPED = re.compile(r"[{};<>$]")

# --- statuses ---------------------------------------------------------------
# rank: higher = later in the parcel's life. A lower-ranked answer than the one
# already accepted is stale and is recorded but never applied.
STATUS_INFO = {
    "in_review": (1, "booked", "Booked - awaiting Steadfast review"),
    "pending": (2, "booked", "Booked - not yet attempted"),
    "hold": (2, "attention", "On hold at Steadfast - contact Steadfast support"),
    "delivered_approval_pending": (3, "confirming", "Rider reports delivered - awaiting Steadfast confirmation"),
    "partial_delivered_approval_pending": (3, "confirming", "Rider reports PARTIAL delivery - awaiting confirmation"),
    "cancelled_approval_pending": (3, "confirming", "Rider reports cancelled - awaiting confirmation"),
    "unknown_approval_pending": (3, "confirming", "Rider status awaiting Steadfast confirmation"),
    "delivered": (4, "delivered", "Delivered (confirmed by Steadfast)"),
    "partial_delivered": (4, "attention", "Partly delivered (confirmed) - check what is coming back"),
    "cancelled": (4, "attention", "Cancelled (confirmed) - parcel returns to AAYNA"),
    "exceptional": (4, "attention", "Exceptional (lost/damaged) - contact Steadfast support"),
    "partial_delivered_return_proccessing": (5, "return", "Return being processed"),
    "cancelled_return_proccessing": (5, "return", "Return being processed"),
    "partial_delivered_return_rider_assigned": (6, "return", "Return rider assigned"),
    "cancelled_return_rider_assigned": (6, "return", "Return rider assigned"),
    "partial_delivered_return_received": (7, "return_received", "Returned parcel received by AAYNA - inspect before restocking"),
    "cancelled_return_received": (7, "return_received", "Returned parcel received by AAYNA - inspect before restocking"),
}
FINAL_KINDS = {"delivered", "return_received"}
# What a customer may see (no courier internals, no blame, no promises).
CUSTOMER_LABELS = {"booked": "Booked with Steadfast courier", "confirming": "With Steadfast courier",
                   "delivered": "Delivered by Steadfast courier"}
CUSTOMER_FALLBACK = "Delivery update in progress - our team will contact you"


def status_info(raw: Optional[str]):
    return STATUS_INFO.get((raw or "").strip().lower())


def customer_courier_status(order: dict) -> Optional[str]:
    c = order.get("courier") or {}
    if c.get("state") != "booked":
        return None
    info = status_info(c.get("status_raw"))
    if not info:
        return CUSTOMER_LABELS["booked"]
    return CUSTOMER_LABELS.get(info[1], CUSTOMER_FALLBACK)


# --- configuration ----------------------------------------------------------
def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def config() -> dict:
    mode = _env("STEADFAST_MODE").lower() or "off"
    db_name = _env("DB_NAME")
    keys = bool(_env("STEADFAST_API_KEY") and _env("STEADFAST_SECRET_KEY"))
    out = {"mode": mode, "keys_present": keys, "real_bookings": False, "reason": None,
           "polling": "manual (admin) + optional protected sync endpoint", "webhooks": "not enabled (no documented authentication)"}
    if mode not in ("off", "mock", "live"):
        out.update(mode="off", reason="STEADFAST_MODE is not one of off / mock / live")
    elif mode == "mock" and db_name == "aayna_prod":
        out.update(mode="off", reason="The simulator is never used with the production database")
    elif mode == "live" and not keys:
        out.update(mode="off", reason="Steadfast API keys are not configured on the server")
    elif mode == "live":
        out["real_bookings"] = _env("STEADFAST_REAL_BOOKINGS").lower() in ("1", "true", "yes") and db_name == "aayna_prod"
        if not out["real_bookings"]:
            out["reason"] = "Real bookings are switched off (needs STEADFAST_REAL_BOOKINGS=true on production, founder approval)"
    elif mode == "off":
        out["reason"] = "Steadfast is not configured"
    return out


# --- provider transport -----------------------------------------------------
class ProviderAnswer:
    """status: HTTP code (None if no answer). outcome: answered | not_sent | ambiguous."""

    def __init__(self, status=None, body=None, outcome="answered", note=""):
        self.status, self.body, self.outcome, self.note = status, (body if isinstance(body, dict) else {}), outcome, note


async def _live_call(method: str, path: str, payload: Optional[dict] = None) -> ProviderAnswer:
    base = (_env("STEADFAST_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith("https://"):
        return ProviderAnswer(outcome="not_sent", note="STEADFAST_BASE_URL must be https")
    headers = {"Api-Key": _env("STEADFAST_API_KEY"), "Secret-Key": _env("STEADFAST_SECRET_KEY"),
               "Content-Type": "application/json", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
            r = await client.request(method, base + path, headers=headers, json=payload)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
        return ProviderAnswer(outcome="not_sent", note="could not connect to Steadfast")
    except (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError):
        return ProviderAnswer(outcome="ambiguous", note="no answer from Steadfast (timeout or dropped connection)")
    try:
        body = r.json()
    except ValueError:
        body = {"message": (r.text or "")[:200]}
    return ProviderAnswer(status=r.status_code, body=body)


async def call(method: str, path: str, payload: Optional[dict] = None) -> ProviderAnswer:
    cfg = config()
    if cfg["mode"] == "mock":
        return await MockSteadfast.handle(method, path, payload)
    if cfg["mode"] == "live":
        return await _live_call(method, path, payload)
    return ProviderAnswer(outcome="not_sent", note=cfg["reason"] or "Steadfast is not configured")


async def _blocked_until() -> Optional[str]:
    st = await db.courier_state.find_one({"_id": STATE_DOC}) or {}
    until = st.get("blocked_until")
    if until and until > now_iso():
        return until
    return None


async def _block(seconds: int, why: str):
    until = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
    await db.courier_state.update_one({"_id": STATE_DOC}, {"$set": {"blocked_until": until, "blocked_reason": why}}, upsert=True)


def _message(ans: ProviderAnswer) -> str:
    b = ans.body
    parts = []
    if isinstance(b.get("errors"), dict):
        for k, v in b["errors"].items():
            parts.append(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
    if b.get("message"):
        parts.append(str(b["message"]))
    return ("; ".join(parts) or ans.note or f"HTTP {ans.status}")[:300]


def _consignment(body: dict) -> dict:
    """Pull ids out of a create/lookup answer without assuming one exact schema."""
    c = body.get("consignment") if isinstance(body.get("consignment"), dict) else body
    cid = c.get("consignment_id") if isinstance(c, dict) else None
    code = c.get("tracking_code") if isinstance(c, dict) else None
    st = (c.get("status") if isinstance(c, dict) else None) or body.get("delivery_status")
    return {"consignment_id": str(cid) if cid not in (None, "") else None,
            "tracking_code": str(code) if code not in (None, "") else None,
            "status": st if isinstance(st, str) else None}


def _delivery_status(body: dict) -> Optional[str]:
    for k in ("delivery_status", "return_status"):
        if isinstance(body.get(k), str) and body[k]:
            return body[k].strip().lower()
    return None


def _duplicate_invoice(ans: ProviderAnswer) -> bool:
    errs = ans.body.get("errors") if isinstance(ans.body.get("errors"), dict) else {}
    text = " ".join(map(str, errs.get("invoice") or [])) + " " + str(ans.body.get("message", ""))
    return ans.status in (400, 409, 422) and bool(re.search(r"(already|taken|duplicate|exist)", text, re.I)) and "invoice" in text.lower() + " ".join(errs).lower()


def _not_found(ans: ProviderAnswer) -> bool:
    if ans.outcome != "answered":
        return False
    return ans.status == 404 or str(ans.body.get("status")) == "404" or "not found" in str(ans.body.get("message", "")).lower()


# --- building the booking ---------------------------------------------------
def local_phone(phone: str) -> Optional[str]:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("880"):
        digits = digits[3:]
    if not digits.startswith("0"):
        digits = "0" + digits
    return digits if re.fullmatch(r"01[3-9]\d{8}", digits) else None


def cod_amount(order: dict) -> dict:
    """Amount the rider collects = what the customer still owes, from the server's
    own order totals: merchandise subtotal - discount + customer delivery charge,
    minus a verified prepayment. Courier fees are NOT in here (merchant cost)."""
    sub = float(order.get("subtotal") or 0)
    disc = float(order.get("discount_amount") or 0)
    deliv = float(order.get("delivery_charge") or 0)
    total = float(order.get("total_amount") or 0)
    if abs((sub - disc + deliv) - total) > 0.01:
        return {"ok": False, "reason": "Order totals do not add up (subtotal - discount + delivery != total); check the order first."}
    pay = str(order.get("payment_status") or "").lower()
    method = str(order.get("payment_method") or "").lower()
    if pay in ("paid", "payment_verified", "verified"):
        amount = 0.0
    elif "cash on delivery" in method or pay == "cod_pending":
        amount = total
    else:
        return {"ok": False, "reason": "This is a prepaid (bKash/Nagad) order whose payment is not verified yet. "
                                       "Verify the payment (payment status 'paid') before booking; partial prepayments are not supported yet."}
    amount = int(round(amount)) if float(amount).is_integer() else round(amount, 2)
    return {"ok": True, "amount": amount, "breakdown": {"subtotal": sub, "discount": disc, "delivery": deliv, "total": total,
                                                       "prepaid": total - amount}}


def build_booking(order: dict) -> dict:
    """The exact create_order payload, or the list of problems blocking it."""
    problems = []
    if order.get("order_status") != "Packed":
        problems.append(f"Order status is '{order.get('order_status')}'. Mark it Packed (confirmed and prepared) before booking.")
    invoice = str(order.get("order_number") or "")
    if not re.fullmatch(r"[A-Za-z0-9\-_]{1,100}", invoice):
        problems.append("Order number cannot be used as a Steadfast invoice.")
    name = PROVIDER_STRIPPED.sub(" ", str(order.get("customer_name") or "")).strip()
    phone = local_phone(order.get("customer_phone"))
    addr_parts = [str(order.get("delivery_address") or "").strip(), str(order.get("district") or "").strip()]
    address = PROVIDER_STRIPPED.sub(" ", ", ".join(p for p in addr_parts if p)).strip()
    note = PROVIDER_STRIPPED.sub(" ", str(order.get("delivery_note") or "")).strip()
    if not name:
        problems.append("Customer name is missing.")
    if not phone:
        problems.append("Customer phone is not a valid Bangladesh mobile number.")
    if len(str(order.get("delivery_address") or "").strip()) < 10:
        problems.append("Delivery address is missing or too short.")
    for field, value in (("recipient_name", name), ("recipient_address", address), ("note", note), ("invoice", invoice)):
        if len(value) > LIMITS[field]:
            problems.append(f"{field.replace('_', ' ')} is longer than Steadfast's {LIMITS[field]} characters; shorten it first.")
    cod = cod_amount(order)
    if not cod["ok"]:
        problems.append(cod["reason"])
    payload = {"invoice": invoice, "recipient_name": name, "recipient_phone": phone or "", "recipient_address": address,
               "cod_amount": cod.get("amount", 0)}
    if note:
        payload["note"] = note
    return {"ok": not problems, "problems": problems, "payload": payload, "cod": cod}


# --- persistence helpers ----------------------------------------------------
def _hist(event: str, **kw) -> dict:
    return {"at": now_iso(), "event": event, **{k: v for k, v in kw.items() if v is not None}}


async def _set_courier(order_number: str, claim_id: str, fields: dict, history: dict, extra_order_fields: Optional[dict] = None):
    upd = {"$set": {**{f"courier.{k}": v for k, v in fields.items()}, **(extra_order_fields or {}), "updated_at": now_iso()},
           "$push": {"courier.history": history}}
    return await db.orders.update_one({"order_number": order_number, "courier.claim_id": claim_id}, upd)


async def ensure_courier_indexes():
    try:
        await db.orders.create_index("courier.consignment_id", unique=True, sparse=True, name="courier_consignment_unique")
        await db.steadfast_mock_parcels.create_index("invoice", unique=True, name="mock_invoice_unique")
    except Exception as exc:  # noqa: BLE001 - never block startup for an index
        logger.warning("courier index skipped: %s", type(exc).__name__)


async def _get_order(order_number: str) -> dict:
    order = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def public_courier(order: dict) -> dict:
    """Admin view of the courier block (no secrets are ever stored in it)."""
    c = dict(order.get("courier") or {})
    info = status_info(c.get("status_raw"))
    c["status_label"] = info[2] if info else (f"Unrecognised Steadfast status '{c['status_raw']}' - check the Steadfast portal"
                                             if c.get("status_raw") else None)
    c["status_kind"] = info[1] if info else ("attention" if c.get("status_raw") else None)
    c.pop("claim_id", None)
    return c


# --- actions ------------------------------------------------------------------
async def book(order_number: str, actor: str) -> dict:
    cfg = config()
    if cfg["mode"] == "off":
        raise HTTPException(status_code=503, detail=cfg["reason"] or "Steadfast is not configured")
    if cfg["mode"] == "live" and not cfg["real_bookings"]:
        raise HTTPException(status_code=403, detail=cfg["reason"])
    until = await _blocked_until()
    if until:
        raise HTTPException(status_code=429, detail=f"Steadfast calls are paused until {until[11:16]} UTC after an authentication or rate-limit answer. Check the keys / wait.")
    order = await _get_order(order_number)
    existing = order.get("courier") or {}
    if existing.get("state") == "booked":
        raise HTTPException(status_code=409, detail="Already booked with Steadfast.")
    if existing.get("state") == "booking":
        raise HTTPException(status_code=409, detail="A booking for this order is already in progress.")
    if existing.get("state") == "needs_reconciliation":
        raise HTTPException(status_code=409, detail="A previous booking may exist at Steadfast. Reconcile it first - never book twice.")
    plan = build_booking(order)
    if not plan["ok"]:
        raise HTTPException(status_code=400, detail=" ".join(plan["problems"]))
    claim = str(uuid.uuid4())
    cond = {"order_number": order_number, "order_status": "Packed"}
    if existing:
        cond.update({"courier.state": "failed", "courier.claim_id": existing.get("claim_id")})
    else:
        cond["courier"] = {"$exists": False}
    attempt = int(existing.get("attempts") or 0) + 1
    courier = {**existing, "provider": PROVIDER, "state": "booking", "claim_id": claim, "claimed_at": now_iso(),
               "claimed_by": actor, "invoice": plan["payload"]["invoice"], "cod_amount": plan["payload"]["cod_amount"],
               "attempts": attempt, "last_error": None, "attention": None,
               "history": list(existing.get("history") or []) + [_hist("booking_started", by=actor, attempt=attempt,
                                                                       cod_amount=plan["payload"]["cod_amount"])]}
    res = await db.orders.update_one(cond, {"$set": {"courier": courier, "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Someone else is booking this order right now, or it changed. Reload the order.")

    ans = await call("POST", "/create_order", plan["payload"])
    if ans.outcome == "not_sent":
        await _set_courier(order_number, claim, {"state": "failed", "last_error": f"Not sent: {ans.note}"},
                           _hist("booking_not_sent", note=ans.note))
    elif ans.outcome == "ambiguous" or (ans.status or 0) >= 500:
        await _set_courier(order_number, claim, {"state": "needs_reconciliation",
                                                 "last_error": "Steadfast did not give a clear answer. The parcel MAY have been created - reconcile before doing anything else."},
                           _hist("booking_ambiguous", http=ans.status, note=ans.note or _message(ans)))
    elif ans.status in (401, 403):
        await _block(AUTH_BLOCK_SECONDS, f"HTTP {ans.status}")
        await _set_courier(order_number, claim, {"state": "failed", "last_error": f"Steadfast refused the credentials or account (HTTP {ans.status}). Calls paused; check the API keys / account."},
                           _hist("booking_refused", http=ans.status))
    elif ans.status == 429:
        await _block(RATE_BLOCK_SECONDS, "HTTP 429")
        await _set_courier(order_number, claim, {"state": "failed", "last_error": "Steadfast rate limit; wait a minute and retry."},
                           _hist("booking_rate_limited", http=429))
    elif ans.status == 200 and str(ans.body.get("status", 200)) in ("200", "201"):
        ids = _consignment(ans.body)
        if ids["consignment_id"] and ids["tracking_code"]:
            try:
                await _set_courier(order_number, claim,
                                   {"state": "booked", "consignment_id": ids["consignment_id"], "tracking_code": ids["tracking_code"],
                                    "booked_at": now_iso(), "booked_by": actor, "status_raw": (ids["status"] or "in_review").lower(),
                                    "status_at": now_iso(), "last_sync_at": now_iso(), "last_sync_result": "booked"},
                                   _hist("booked", consignment_id=ids["consignment_id"], tracking_code=ids["tracking_code"], by=actor),
                                   {"courier_name": COURIER_NAME, "courier_tracking_code": ids["tracking_code"]})
            except DuplicateKeyError:
                await _set_courier(order_number, claim, {"state": "needs_reconciliation",
                                                         "last_error": f"Consignment {ids['consignment_id']} is already linked to another order. Check in the Steadfast portal."},
                                   _hist("booking_duplicate_consignment", consignment_id=ids["consignment_id"]))
        else:
            await _set_courier(order_number, claim, {"state": "needs_reconciliation",
                                                     "last_error": "Steadfast answered OK but without a consignment ID/tracking code. Reconcile."},
                               _hist("booking_unclear_answer", http=200))
    elif _duplicate_invoice(ans):
        # Steadfast already has a parcel with this invoice: it must be linked, never booked again.
        await _set_courier(order_number, claim, {"state": "needs_reconciliation",
                                                 "last_error": "Steadfast says this invoice already exists. Reconcile and link the existing parcel - do not book again."},
                           _hist("booking_duplicate_invoice", http=ans.status, message=_message(ans)))
    else:  # 400 / 422 / other answered refusals: nothing was created
        await _set_courier(order_number, claim, {"state": "failed", "last_error": f"Steadfast rejected the booking: {_message(ans)}"},
                           _hist("booking_rejected", http=ans.status, message=_message(ans)))
    return await _get_order(order_number)


async def reconcile(order_number: str, actor: str) -> dict:
    """Find out, by invoice, whether a booking whose outcome is unknown exists at Steadfast."""
    order = await _get_order(order_number)
    c = order.get("courier") or {}
    stale = c.get("state") == "booking" and (c.get("claimed_at") or "") < (datetime.now(timezone.utc) - timedelta(seconds=STALE_CLAIM_SECONDS)).isoformat()
    if c.get("state") != "needs_reconciliation" and not stale:
        raise HTTPException(status_code=409, detail="Nothing to reconcile for this order.")
    if config()["mode"] == "off":
        raise HTTPException(status_code=503, detail=config()["reason"])
    claim = c.get("claim_id")
    if stale:  # a crashed/timed-out request: treat exactly like an ambiguous answer
        await _set_courier(order_number, claim, {"state": "needs_reconciliation"}, _hist("booking_stale", by=actor))
    ans = await call("GET", f"/status_by_invoice/{c['invoice']}")
    if _not_found(ans):
        await _set_courier(order_number, claim, {"state": "failed", "last_error": "Reconciled: Steadfast has no parcel for this invoice. It is safe to book again."},
                           _hist("reconciled_not_found", by=actor))
    elif ans.outcome == "answered" and ans.status == 200 and _delivery_status(ans.body):
        ids = _consignment(ans.body)
        if ids["consignment_id"] and ids["tracking_code"]:
            await _set_courier(order_number, claim, {"state": "booked", "consignment_id": ids["consignment_id"], "tracking_code": ids["tracking_code"],
                                                     "booked_at": now_iso(), "status_raw": _delivery_status(ans.body), "status_at": now_iso(),
                                                     "last_error": None, "found_at_provider": True},
                               _hist("reconciled_found", by=actor, consignment_id=ids["consignment_id"]),
                               {"courier_name": COURIER_NAME, "courier_tracking_code": ids["tracking_code"]})
        else:
            await _set_courier(order_number, claim, {"found_at_provider": True, "provider_status_seen": _delivery_status(ans.body),
                                                     "last_error": "Steadfast HAS a parcel for this invoice. Do not book again: copy its consignment ID and tracking code from the Steadfast portal and record them here."},
                               _hist("reconciled_exists_ids_missing", by=actor, status=_delivery_status(ans.body)))
    else:
        await _set_courier(order_number, claim, {"last_error": f"Could not confirm with Steadfast ({_message(ans)}). Still unresolved - do not book again; try later or check the portal."},
                           _hist("reconcile_unclear", by=actor, http=ans.status, note=ans.note))
    return await _get_order(order_number)


async def link_manual(order_number: str, consignment_id: str, tracking_code: str, actor: str) -> dict:
    """Record ids copied from the Steadfast portal for a parcel that exists there."""
    order = await _get_order(order_number)
    c = order.get("courier") or {}
    if c.get("state") != "needs_reconciliation":
        raise HTTPException(status_code=409, detail="Only an unresolved booking can be linked by hand.")
    cid, code = consignment_id.strip(), tracking_code.strip().upper()
    if not re.fullmatch(r"\d{3,20}", cid) or not re.fullmatch(r"[A-Z0-9]{4,40}", code):
        raise HTTPException(status_code=400, detail="Enter the numeric consignment ID and the tracking code exactly as shown in the Steadfast portal.")
    ans = await call("GET", f"/status_by_cid/{cid}")
    if _not_found(ans):
        raise HTTPException(status_code=400, detail="Steadfast does not know this consignment ID.")
    raw = _delivery_status(ans.body) if ans.outcome == "answered" and ans.status == 200 else None
    try:
        await _set_courier(order_number, c.get("claim_id"),
                           {"state": "booked", "consignment_id": cid, "tracking_code": code, "booked_at": c.get("booked_at") or now_iso(),
                            "status_raw": raw or "in_review", "status_at": now_iso(), "linked_by_hand": True, "last_error": None,
                            "last_sync_at": now_iso(), "last_sync_result": "linked" if raw else f"linked; status check failed ({_message(ans)})"},
                           _hist("linked_by_hand", by=actor, consignment_id=cid, verified=bool(raw)),
                           {"courier_name": COURIER_NAME, "courier_tracking_code": code})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="That consignment ID is already linked to another order.")
    return await _get_order(order_number)


async def sync_one(order_number: str, actor: str = "system", force: bool = False) -> dict:
    """Ask Steadfast for the current status (read-only at Steadfast) and apply it safely."""
    from admin_routes import order_status_side_effects  # shared counters / history / emails
    order = await _get_order(order_number)
    c = order.get("courier") or {}
    if c.get("state") != "booked" or not c.get("consignment_id"):
        raise HTTPException(status_code=409, detail="This order has no Steadfast consignment to check.")
    if config()["mode"] == "off":
        raise HTTPException(status_code=503, detail=config()["reason"])
    last = c.get("last_sync_at") or ""
    # Live answers are cached by Steadfast for 60 s, so checking sooner is pointless (the simulator is not cached).
    if not force and config()["mode"] == "live" and last > (datetime.now(timezone.utc) - timedelta(seconds=STATUS_CACHE_SECONDS)).isoformat():
        return {**order, "sync_note": "Checked less than a minute ago (Steadfast caches status for 60 seconds)."}
    if await _blocked_until():
        raise HTTPException(status_code=429, detail="Steadfast calls are paused after an authentication or rate-limit answer.")
    cur = status_info(c.get("status_raw"))
    path = f"/status_by_cid/{c['consignment_id']}"
    if cur and cur[0] >= 4 and cur[1] != "delivered":  # cancelled / partial: returns are only reported here
        path = f"/status_with_return_status_by_cid/{c['consignment_id']}"
    ans = await call("GET", path)
    claim = c.get("claim_id")
    if ans.outcome != "answered" or ans.status != 200:
        if ans.status in (401, 403):
            await _block(AUTH_BLOCK_SECONDS, f"HTTP {ans.status}")
        elif ans.status == 429:
            await _block(RATE_BLOCK_SECONDS, "HTTP 429")
        await _set_courier(order_number, claim, {"last_sync_at": now_iso(), "last_sync_result": f"failed: {_message(ans)}"},
                           _hist("sync_failed", http=ans.status, note=ans.note))
        return await _get_order(order_number)
    raw = _delivery_status(ans.body)
    info = status_info(raw)
    fields = {"last_sync_at": now_iso(), "observed_raw": raw, "provider_updated_at": ans.body.get("updated_at")}
    history = None
    if raw != c.get("observed_raw") and raw != c.get("status_raw"):
        history = _hist("status_seen", status=raw)
    if not info:
        fields.update(last_sync_result=f"unrecognised status '{raw}' (not applied)",
                      attention=f"Steadfast reported an unrecognised status '{raw}'. Check the Steadfast portal.")
    elif cur and info[0] < cur[0]:
        fields["last_sync_result"] = f"older status '{raw}' ignored (already '{c.get('status_raw')}')"
    elif cur and cur[0] == 4 and info[0] == 4 and raw != c.get("status_raw"):
        fields.update(last_sync_result=f"conflicting confirmed status '{raw}' not applied",
                      attention=f"Steadfast changed a confirmed status from '{c.get('status_raw')}' to '{raw}'. Check before acting.")
    else:
        fields.update(status_raw=raw, status_at=now_iso(), last_sync_result="updated" if raw != c.get("status_raw") else "unchanged")
        if info[1] in ("attention",):
            fields["attention"] = info[2]
        elif info[1] in ("return", "return_received"):
            fields["attention"] = "Parcel is coming back. Inspect it on arrival; restock by hand in Inventory (type 'return')."
        else:
            fields["attention"] = None
        if raw != c.get("status_raw"):
            history = _hist("status_applied", status=raw, previous=c.get("status_raw"))
    upd = {"$set": {**{f"courier.{k}": v for k, v in fields.items()}, "updated_at": now_iso()}}
    if history:
        upd["$push"] = {"courier.history": history}
    await db.orders.update_one({"order_number": order_number, "courier.claim_id": claim}, upd)

    # Order status follows only CONFIRMED forward progress; never backwards, never cancel/return.
    applied = fields.get("status_raw")
    if applied and info:
        target = None
        if applied == "delivered" and order["order_status"] in ("Packed", "Sent to Courier"):
            target = "Delivered"
        elif info[1] in ("confirming",) and applied.startswith(("delivered", "partial")) and order["order_status"] == "Packed":
            target = "Sent to Courier"  # a rider holding the parcel proves the hand-over
        elif applied == "partial_delivered" and order["order_status"] == "Packed":
            target = "Sent to Courier"
        if target:
            res = await db.orders.update_one({"order_number": order_number, "order_status": order["order_status"]},
                                             {"$set": {"order_status": target, "updated_at": now_iso()}})
            if res.modified_count:
                await order_status_side_effects(order, target, source="steadfast", actor=f"Steadfast sync ({actor})")
    return await _get_order(order_number)


async def sync_active(actor: str, limit: int = 20) -> dict:
    """Check booked, unfinished parcels not checked in the last 10 minutes (oldest first)."""
    if config()["mode"] == "off":
        raise HTTPException(status_code=503, detail=config()["reason"])
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    finals = [s for s, i in STATUS_INFO.items() if i[1] in FINAL_KINDS]
    q = {"courier.state": "booked", "courier.status_raw": {"$nin": finals},
         "$or": [{"courier.last_sync_at": {"$lt": cutoff}}, {"courier.last_sync_at": None}]}
    orders = await db.orders.find(q, {"_id": 0, "order_number": 1}).sort("courier.last_sync_at", 1).to_list(limit)
    done, failed = [], []
    for o in orders:
        try:
            after = await sync_one(o["order_number"], actor=actor, force=True)
            done.append({"order_number": o["order_number"], "status": (after.get("courier") or {}).get("status_raw")})
        except HTTPException as e:
            failed.append({"order_number": o["order_number"], "error": e.detail})
            if e.status_code == 429:
                break
    return {"checked": done, "failed": failed}


# --- deterministic simulator (STEADFAST_MODE=mock; never on aayna_prod) --------
class MockSteadfast:
    """Mimics the guide's endpoints in-process. Parcels live in steadfast_mock_parcels
    (preview/test database only). Faults are injected per call for tests (FAULTS) or
    through Admin -> order -> "Simulator" on the test preview."""
    FAULTS: dict = {}  # path-prefix -> fault, used once

    @classmethod
    async def _take_fault(cls, op: str) -> Optional[str]:
        if cls.FAULTS.get(op):
            return cls.FAULTS.pop(op)
        st = await db.courier_state.find_one_and_update({"_id": "mock", f"faults.{op}": {"$exists": True}},
                                                        {"$unset": {f"faults.{op}": ""}})
        return ((st or {}).get("faults") or {}).get(op)

    @classmethod
    async def handle(cls, method: str, path: str, payload: Optional[dict]) -> ProviderAnswer:
        op = path.strip("/").split("/")[0]
        fault = await cls._take_fault(op)
        if fault == "down":
            return ProviderAnswer(outcome="not_sent", note="simulated: Steadfast unreachable")
        if fault == "timeout_before_accept":
            return ProviderAnswer(outcome="ambiguous", note="simulated timeout (nothing created)")
        if fault == "validation" and op == "create_order":
            return ProviderAnswer(status=422, body={"status": 422, "errors": {"recipient_address": ["The recipient address is not serviceable (simulated)."]}})
        if fault in ("auth", "rate_limit", "server_error"):
            code = {"auth": 401, "rate_limit": 429, "server_error": 500}[fault]
            return ProviderAnswer(status=code, body={"status": code, "message": f"simulated {fault}"})
        if method == "POST" and op == "create_order":
            ans = await cls._create(payload or {})
            if fault == "timeout_after_accept" and ans.status == 200:
                return ProviderAnswer(outcome="ambiguous", note="simulated timeout after Steadfast accepted the parcel")
            if fault == "ok_without_ids" and ans.status == 200:
                return ProviderAnswer(status=200, body={"status": 200, "message": "Consignment has been created successfully."})
            return ans
        if method == "GET" and op == "status_by_invoice":
            p = await db.steadfast_mock_parcels.find_one({"invoice": path.split("/")[-1]})
            if not p:
                return ProviderAnswer(status=404, body={"status": 404, "message": "Consignment not found"})
            return ProviderAnswer(status=200, body={"status": 200, "delivery_status": p["delivery_status"]})
        if method == "GET" and op in ("status_by_cid", "status_with_return_status_by_cid"):
            p = await db.steadfast_mock_parcels.find_one({"consignment_id": path.split("/")[-1]})
            if not p:
                return ProviderAnswer(status=404, body={"status": 404, "message": "Consignment not found"})
            st = p["delivery_status"]
            if op == "status_with_return_status_by_cid" and p.get("return_status"):
                st = p["return_status"]
            return ProviderAnswer(status=200, body={"status": 200, "delivery_status": st, "updated_at": p.get("updated_at")})
        return ProviderAnswer(status=404, body={"status": 404, "message": "simulated: unknown endpoint"})

    @classmethod
    async def _create(cls, p: dict) -> ProviderAnswer:
        errors = {}
        if not re.fullmatch(r"[A-Za-z0-9\-_]{1,100}", str(p.get("invoice") or "")):
            errors["invoice"] = ["The invoice field is required."]
        if not str(p.get("recipient_name") or "").strip() or len(p.get("recipient_name", "")) > 100:
            errors["recipient_name"] = ["The recipient name field is invalid."]
        if not re.fullmatch(r"01[3-9]\d{8}", str(p.get("recipient_phone") or "")):
            errors["recipient_phone"] = ["The recipient phone must be 11 digits."]
        if not str(p.get("recipient_address") or "").strip() or len(p.get("recipient_address", "")) > 490:
            errors["recipient_address"] = ["The recipient address field is invalid."]
        try:
            if float(p.get("cod_amount")) < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors["cod_amount"] = ["The cod amount must be a number."]
        if errors:
            return ProviderAnswer(status=422, body={"status": 422, "errors": errors})
        seq = await db.courier_state.find_one_and_update({"_id": "mock_seq"}, {"$inc": {"n": 1}}, upsert=True, return_document=True)
        n = int((seq or {}).get("n") or 1)
        cid = str(9000000 + n)
        code = "SFM" + hashlib.sha256(p["invoice"].encode()).hexdigest()[:7].upper()
        doc = {"invoice": p["invoice"], "consignment_id": cid, "tracking_code": code, "cod_amount": p["cod_amount"],
               "delivery_status": "in_review", "return_status": None, "created_at": now_iso(), "updated_at": now_iso()}
        try:
            await db.steadfast_mock_parcels.insert_one(dict(doc))
        except DuplicateKeyError:
            return ProviderAnswer(status=422, body={"status": 422, "errors": {"invoice": ["The invoice has already been taken."]}})
        return ProviderAnswer(status=200, body={"status": 200, "message": "Consignment has been created successfully.",
                                                "consignment": {**doc, "status": "in_review", "consignment_id": int(cid)}})


# --- routes -------------------------------------------------------------------
courier_admin_router = APIRouter(prefix="/api/admin")
courier_internal_router = APIRouter(prefix="/api/internal")


class BookBody(BaseModel):
    confirm: bool = False


class LinkBody(BaseModel):
    consignment_id: str = Field(..., max_length=40)
    tracking_code: str = Field(..., max_length=60)


class MockBody(BaseModel):
    action: str  # set_status | fail_next
    status: Optional[str] = None
    return_status: Optional[str] = None
    fault: Optional[str] = None
    op: Optional[str] = "create_order"


@courier_admin_router.get("/courier/config")
async def courier_config(current=Depends(require("orders.view"))):
    cfg = config()
    until = await _blocked_until()
    return {**cfg, "paused_until": until}


@courier_admin_router.get("/orders/{order_number}/courier")
async def courier_view(order_number: str, current=Depends(require("orders.view"))):
    order = await _get_order(order_number)
    plan = build_booking(order)
    sim = None
    c = order.get("courier") or {}
    if config()["mode"] == "mock" and c.get("found_at_provider") and c.get("state") == "needs_reconciliation":
        p = await db.steadfast_mock_parcels.find_one({"invoice": c.get("invoice")}, {"_id": 0, "consignment_id": 1, "tracking_code": 1})
        sim = p  # what the Steadfast portal would show (simulator only)
    return {"config": config(), "courier": public_courier(order), "simulated_portal": sim,
            "booking_preview": {"ok": plan["ok"], "problems": plan["problems"], "cod": plan["cod"],
                                "recipient_name": plan["payload"]["recipient_name"], "recipient_phone": plan["payload"]["recipient_phone"],
                                "recipient_address": plan["payload"]["recipient_address"], "invoice": plan["payload"]["invoice"],
                                "note": plan["payload"].get("note", "")}}


@courier_admin_router.post("/orders/{order_number}/courier/book")
async def courier_book(order_number: str, body: BookBody, current=Depends(require("courier.book"))):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Confirm the booking details first.")
    order = await book(order_number, current["email"])
    return {"courier": public_courier(order), "order_status": order["order_status"]}


@courier_admin_router.post("/orders/{order_number}/courier/reconcile")
async def courier_reconcile(order_number: str, current=Depends(require("courier.book"))):
    order = await reconcile(order_number, current["email"])
    return {"courier": public_courier(order), "order_status": order["order_status"]}


@courier_admin_router.post("/orders/{order_number}/courier/link")
async def courier_link(order_number: str, body: LinkBody, current=Depends(require("courier.book"))):
    order = await link_manual(order_number, body.consignment_id, body.tracking_code, current["email"])
    return {"courier": public_courier(order), "order_status": order["order_status"]}


@courier_admin_router.post("/orders/{order_number}/courier/sync")
async def courier_sync(order_number: str, current=Depends(require("orders.edit"))):
    order = await sync_one(order_number, actor=current["email"])
    return {"courier": public_courier(order), "order_status": order["order_status"], "note": order.get("sync_note")}


@courier_admin_router.post("/courier/sync-active")
async def courier_sync_active(current=Depends(require("orders.edit"))):
    return await sync_active(current["email"])


@courier_admin_router.post("/orders/{order_number}/courier/mock")
async def courier_mock(order_number: str, body: MockBody, current=Depends(require("courier.book"))):
    """Simulator controls - only when STEADFAST_MODE=mock (never production)."""
    if config()["mode"] != "mock":
        raise HTTPException(status_code=404, detail="Not available")
    if body.action == "fail_next":
        allowed = {"timeout_after_accept", "timeout_before_accept", "server_error", "auth", "rate_limit", "down", "ok_without_ids", "validation"}
        if body.fault not in allowed or body.op not in ("create_order", "status_by_invoice", "status_by_cid"):
            raise HTTPException(status_code=400, detail="Unknown simulated fault")
        await db.courier_state.update_one({"_id": "mock"}, {"$set": {f"faults.{body.op}": body.fault}}, upsert=True)
        return {"ok": True}
    if body.action == "set_status":
        order = await _get_order(order_number)
        if body.status and body.status not in STATUS_INFO and body.status != "unknown":
            raise HTTPException(status_code=400, detail="Unknown Steadfast status")
        sets = {"updated_at": now_iso()}
        if body.status:
            sets["delivery_status"] = body.status
        if body.return_status is not None:
            sets["return_status"] = body.return_status or None
        res = await db.steadfast_mock_parcels.update_one({"invoice": order_number}, {"$set": sets})
        if not res.matched_count:
            raise HTTPException(status_code=404, detail="No simulated parcel for this order")
        return {"ok": True}
    raise HTTPException(status_code=400, detail="Unknown action")


@courier_internal_router.api_route("/courier/sync", methods=["GET", "POST"])
async def courier_cron(request: Request):
    """Optional scheduled sync (e.g. a Vercel Cron Job). Disabled unless CRON_SECRET is set;
    the scheduler must send `Authorization: Bearer <CRON_SECRET>`."""
    secret = _env("CRON_SECRET")
    import hmac
    got = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(got.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(status_code=404, detail="Not found")
    result = await sync_active("scheduled sync")
    return {"checked": len(result["checked"]), "failed": len(result["failed"])}

"""
AAYNA promotions: server-authoritative coupon codes and the welcome campaign.

Product-level `discount_price` (catalogue sale price) is unrelated and untouched.
A coupon never changes catalogue prices or costs; it produces an order-level
`discount_amount` on eligible merchandise only (never on delivery), computed
here from database prices - a browser-supplied amount is never trusted.

Usage consistency
  * total cap: `remaining_uses` is decremented with a conditional update
    (remaining_uses > 0), so concurrent checkouts cannot exceed the cap;
  * per-customer cap: one counter document per (promotion, customer) incremented
    conditionally (count < limit);
  * both reservations are released if the order is not created (stock failure,
    error, invalid data), so a failed checkout never consumes a code;
  * an idempotent checkout retry returns the existing order and never reserves twice.

Cancellation policy (documented in docs/CUSTOMER_ACCOUNTS.md): a redemption is NOT
restored automatically when an order is cancelled or returned. An admin with
promotions.manage can restore it explicitly for a Cancelled/Returned order; the
action is audited.

Welcome campaign: configuration lives in promotion_campaigns/_id="welcome" and is
disabled by default. The founder approved the limits on 2026-10-19 (10% off the
first eligible order, merchandise minimum 1,000 BDT, maximum discount 150 BDT,
valid 30 days from issue, one redemption per eligible customer, delivery
excluded). They are the defaults and are recorded in `approved_limits`. The
campaign stays disabled until a super admin enables it with an explicit
confirmation; enabling with values that differ from the approved limits needs a
second, explicit confirmation.
"""
import math
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from auth import require
from db import db, now_iso

promotions_router = APIRouter(prefix="/api")
promotions_admin_router = APIRouter(prefix="/api/admin/promotions")

CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,31}$")
WELCOME_ID = "welcome"
# Founder decision, 2026-10-19 (approved limits; the campaign itself stays disabled until launch).
APPROVED_WELCOME_LIMITS = {"value": 10, "validity_days": 30, "min_subtotal": 1000, "max_discount_bdt": 150,
                           "first_order_only": True, "decided_on": "2026-10-19"}
WELCOME_DEFAULTS = {
    "_id": WELCOME_ID, "enabled": False, "type": "percent", "value": 10, "validity_days": 30,
    "first_order_only": True, "single_use": True, "non_transferable": True,
    "min_subtotal": 1000, "max_discount_bdt": 150,
    "approved_limits": APPROVED_WELCOME_LIMITS,
    "approved_by": None, "approved_at": None,
}
_LIMIT_KEYS = ("value", "validity_days", "min_subtotal", "max_discount_bdt", "first_order_only")


def differs_from_approved(cfg: dict) -> List[str]:
    """Names of the welcome settings that differ from the founder-approved limits."""
    out = []
    for k in _LIMIT_KEYS:
        a, b = cfg.get(k), APPROVED_WELCOME_LIMITS[k]
        same = (a == b) if (isinstance(b, bool) or a is None) else float(a) == float(b)
        if not same:
            out.append(k)
    return out


class CouponError(Exception):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="Dates must be valid date-times.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=6)))  # Bangladesh time when no zone given
    return dt.astimezone(timezone.utc).isoformat()


def normalize_code(code: str) -> str:
    return re.sub(r"\s+", "", (code or "")).upper()[:40]


def effective_state(p: dict, now: Optional[str] = None) -> str:
    now = now or now_iso()
    status = p.get("status")
    if status != "active":
        return status or "draft"
    if p.get("starts_at") and now < p["starts_at"]:
        return "scheduled"
    if p.get("ends_at") and now >= p["ends_at"]:
        return "expired"
    if p.get("remaining_uses") is not None and p["remaining_uses"] <= 0:
        return "exhausted"
    return "active"


def compute_discount(p: dict, lines: List[dict]) -> dict:
    """lines: [{product_id, category_slug, line_total}] priced from the database."""
    prod = set(p.get("eligible_product_ids") or [])
    cats = set(p.get("eligible_category_slugs") or [])
    if prod or cats:
        eligible = sum(float(l["line_total"]) for l in lines if l["product_id"] in prod or l.get("category_slug") in cats)
    else:
        eligible = sum(float(l["line_total"]) for l in lines)
    value = float(p.get("value") or 0)
    raw = eligible * value / 100.0 if p.get("type") == "percent" else value
    caps = [raw, eligible]
    if p.get("max_discount_bdt") not in (None, ""):
        caps.append(float(p["max_discount_bdt"]))
    if p.get("max_percent_of_subtotal") not in (None, ""):
        caps.append(eligible * float(p["max_percent_of_subtotal"]) / 100.0)
    discount = max(0, math.floor(min(caps) + 1e-9))  # whole taka, never above any cap
    return {"discount": discount, "eligible_subtotal": eligible}


async def _prior_orders(account_id: Optional[str], phone: Optional[str]) -> int:
    ors = []
    if account_id:
        ors.append({"account_id": account_id})
    if phone:
        ors.append({"customer_phone": phone})
    if not ors:
        return 0
    return await db.orders.count_documents({"$or": ors, "order_status": {"$nin": ["Cancelled"]}})


def _who(account: Optional[dict], phone: Optional[str]) -> Optional[str]:
    if account:
        return "acct:" + account["id"]
    if phone:
        return "phone:" + phone
    return None


def _who_keys(account: Optional[dict], phone: Optional[str]) -> List[str]:
    """Every identity a per-customer limit is counted against: the account (when
    signed in) AND the order phone, so signing in or out does not reset a limit."""
    keys = []
    if account:
        keys.append("acct:" + account["id"])
    if phone:
        keys.append("phone:" + phone)
    return keys


async def evaluate(code: str, account: Optional[dict], phone: Optional[str], lines: List[dict]) -> dict:
    """Validate a code for this cart. Raises CouponError with a customer-safe message."""
    norm = normalize_code(code)
    if not CODE_RE.match(norm):
        raise CouponError("This code isn't valid.")
    p = await db.promotions.find_one({"code": norm}, {"_id": 0, "audit": 0})
    if not p or p.get("status") in (None, "draft", "archived"):
        raise CouponError("This code isn't valid.")
    state = effective_state(p)
    messages = {"paused": "This code isn't available right now.", "scheduled": "This code isn't active yet.",
                "expired": "This code has expired.", "exhausted": "This code has reached its usage limit."}
    if state in messages:
        raise CouponError(messages[state], state)
    restricted = p.get("customer_account_ids") or []
    if restricted:
        if not account:
            raise CouponError("Please sign in to use this code.", "signin")
        if account["id"] not in restricted or not account.get("email_verified"):
            raise CouponError("This code isn't valid.")
    who = _who(account, phone)
    who_keys = _who_keys(account, phone)
    limit = p.get("usage_limit_per_customer")
    if who_keys and limit:
        for key in who_keys:
            used = await db.promotion_usage.find_one({"_id": f"{p['id']}|{key}"})
            if used and int(used.get("count", 0)) >= int(limit):
                raise CouponError("You've already used this code.", "used")
    if p.get("first_order_only") and await _prior_orders(account["id"] if account else None, phone):
        raise CouponError("This code is for your first order only.", "first_order")
    result = compute_discount(p, lines)
    if result["eligible_subtotal"] <= 0:
        raise CouponError("This code doesn't apply to the items in your cart.", "not_applicable")
    minimum = float(p.get("min_subtotal") or 0)
    if result["eligible_subtotal"] < minimum:
        raise CouponError(f"Add eligible items worth at least ৳{minimum:,.0f} to use this code.", "minimum")
    if result["discount"] <= 0:
        raise CouponError("This code doesn't apply to the items in your cart.", "not_applicable")
    return {"promotion": p, "code": norm, "who": who, "who_keys": who_keys, **result}


async def reserve(ev: dict) -> dict:
    """Atomically take one use (total + per customer). Raises CouponError if a
    concurrent checkout took the last one."""
    p = ev["promotion"]
    q = {"id": p["id"], "status": "active"}
    if p.get("remaining_uses") is not None:
        q["remaining_uses"] = {"$gt": 0}
    inc = {"redeemed_count": 1}
    if p.get("remaining_uses") is not None:
        inc["remaining_uses"] = -1
    took = await db.promotions.find_one_and_update(q, {"$inc": inc}, return_document=ReturnDocument.AFTER)
    if not took:
        raise CouponError("This code has just reached its usage limit.", "exhausted")
    handle = {"promotion_id": p["id"], "limited": p.get("remaining_uses") is not None, "usage_key": None, "usage_keys": []}
    limit = p.get("usage_limit_per_customer")
    keys = ev.get("who_keys") or ([ev["who"]] if ev.get("who") else [])
    if keys and limit:
        for who in keys:
            key = f"{p['id']}|{who}"
            ok = False
            try:
                await db.promotion_usage.insert_one({"_id": key, "count": 1, "created_at": now_iso()})
                ok = True
            except DuplicateKeyError:
                ok = bool(await db.promotion_usage.find_one_and_update(
                    {"_id": key, "count": {"$lt": int(limit)}}, {"$inc": {"count": 1}}))
            if not ok:
                await release(handle)
                raise CouponError("You've already used this code.", "used")
            handle["usage_keys"].append(key)
        handle["usage_key"] = handle["usage_keys"][0]
    return handle


async def release(handle: Optional[dict]):
    if not handle:
        return
    inc = {"redeemed_count": -1}
    if handle.get("limited"):
        inc["remaining_uses"] = 1
    await db.promotions.update_one({"id": handle["promotion_id"]}, {"$inc": inc})
    for key in handle.get("usage_keys") or ([handle["usage_key"]] if handle.get("usage_key") else []):
        await db.promotion_usage.update_one({"_id": key, "count": {"$gt": 0}}, {"$inc": {"count": -1}})


async def record_redemption(ev: dict, handle: dict, order: dict):
    await db.promotion_redemptions.insert_one({
        "id": str(uuid.uuid4()), "promotion_id": ev["promotion"]["id"], "code": ev["code"],
        "order_id": order["id"], "order_number": order["order_number"], "account_id": order.get("account_id"),
        "usage_key": handle.get("usage_key"), "usage_keys": handle.get("usage_keys") or [], "limited": handle.get("limited"),
        "discount_amount": order["discount_amount"], "eligible_subtotal": ev["eligible_subtotal"],
        "status": "redeemed", "created_at": now_iso(),
    })


# ---------------------------------------------------------------------------
# Welcome campaign
# ---------------------------------------------------------------------------
async def welcome_config() -> dict:
    doc = await db.promotion_campaigns.find_one({"_id": WELCOME_ID})
    return {**WELCOME_DEFAULTS, **(doc or {})}


async def issue_welcome(account: dict) -> Optional[dict]:
    """Issue the personal welcome coupon once per verified account, only while the
    campaign is enabled. Returns the coupon or None."""
    cfg = await welcome_config()
    if not cfg.get("enabled") or not account.get("email_verified") or account.get("status") != "active":
        return None
    try:
        await db.welcome_issuance.insert_one({"_id": account["id"], "created_at": now_iso()})
    except DuplicateKeyError:
        return None
    for _ in range(5):
        code = "WELCOME-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        now = _now()
        promo = {
            "id": str(uuid.uuid4()), "code": code, "name": "Welcome offer", "kind": "welcome_issued",
            "type": cfg["type"], "value": cfg["value"], "max_discount_bdt": cfg.get("max_discount_bdt"),
            "max_percent_of_subtotal": None, "min_subtotal": cfg.get("min_subtotal") or 0,
            "starts_at": now.isoformat(), "ends_at": (now + timedelta(days=int(cfg["validity_days"]))).isoformat(),
            "usage_limit_total": 1, "remaining_uses": 1, "usage_limit_per_customer": 1, "redeemed_count": 0,
            "first_order_only": bool(cfg.get("first_order_only")), "eligible_product_ids": [], "eligible_category_slugs": [],
            "customer_account_ids": [account["id"]], "status": "active", "created_by": "system:welcome",
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        try:
            await db.promotions.insert_one({**promo})
        except DuplicateKeyError:
            continue
        await db.welcome_issuance.update_one({"_id": account["id"]}, {"$set": {"promotion_id": promo["id"]}})
        await _audit(promo["id"], "issued_welcome", "system", {"account_id": account["id"]})
        return promo
    await db.welcome_issuance.delete_one({"_id": account["id"]})
    return None


async def rewards_for(account: dict) -> dict:
    coupons = await db.promotions.find({"customer_account_ids": account["id"]},
                                       {"_id": 0, "audit": 0, "customer_account_ids": 0}).sort("created_at", -1).to_list(50)
    cfg = await welcome_config()
    return {
        "welcome_enabled": bool(cfg.get("enabled")),
        "coupons": [{"code": c["code"], "name": c.get("name"), "type": c["type"], "value": c["value"],
                     "max_discount_bdt": c.get("max_discount_bdt"), "min_subtotal": c.get("min_subtotal") or 0,
                     "first_order_only": c.get("first_order_only"), "ends_at": c.get("ends_at"),
                     "state": "used" if (c.get("remaining_uses") == 0 and c.get("redeemed_count", 0) > 0) else effective_state(c)}
                    for c in coupons],
    }


@promotions_router.get("/promotions/welcome")
async def public_welcome():
    """What the storefront may say about the welcome offer. Nothing while disabled."""
    cfg = await welcome_config()
    if not cfg.get("enabled"):
        return {"enabled": False}
    return {"enabled": True, "type": cfg["type"], "value": cfg["value"], "validity_days": cfg["validity_days"],
            "min_subtotal": cfg.get("min_subtotal") or 0, "max_discount_bdt": cfg.get("max_discount_bdt"),
            "first_order_only": bool(cfg.get("first_order_only"))}


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
class PromotionBody(BaseModel):
    code: str
    name: str
    description: Optional[str] = ""
    type: str
    value: float
    max_discount_bdt: Optional[float] = None
    max_percent_of_subtotal: Optional[float] = None
    min_subtotal: Optional[float] = 0
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    usage_limit_total: Optional[int] = None
    usage_limit_per_customer: Optional[int] = 1
    first_order_only: bool = False
    eligible_product_ids: List[str] = []
    eligible_category_slugs: List[str] = []
    customer_emails: List[str] = []


class PreviewBody(BaseModel):
    type: str
    value: float
    max_discount_bdt: Optional[float] = None
    max_percent_of_subtotal: Optional[float] = None
    min_subtotal: Optional[float] = 0
    subtotal: float
    delivery_charge: Optional[float] = 0


class ConfirmBody(BaseModel):
    confirm: bool = False
    note: Optional[str] = ""


class WelcomeBody(BaseModel):
    enabled: Optional[bool] = None
    value: Optional[float] = None
    validity_days: Optional[int] = None
    min_subtotal: Optional[float] = None
    max_discount_bdt: Optional[float] = None
    first_order_only: Optional[bool] = None
    confirm: bool = False
    confirm_unapproved_limits: bool = False


async def _audit(promotion_id: str, action: str, actor: str, changes: dict):
    await db.promotion_audit.insert_one({"id": str(uuid.uuid4()), "promotion_id": promotion_id, "action": action,
                                         "actor": actor, "changes": changes, "created_at": now_iso()})


def _num(v, name, lo=None, hi=None, allow_none=True):
    if v is None:
        if allow_none:
            return None
        raise HTTPException(status_code=422, detail=f"{name} is required.")
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{name} must be a number.")
    if math.isnan(f) or math.isinf(f) or (lo is not None and f < lo) or (hi is not None and f > hi):
        raise HTTPException(status_code=422, detail=f"{name} is out of range.")
    return f


async def _validated(body: PromotionBody) -> dict:
    code = normalize_code(body.code)
    if not CODE_RE.match(code) or code.startswith("WELCOME-"):
        raise HTTPException(status_code=422, detail="Code must be 3-32 letters, numbers or dashes (WELCOME- is reserved).")
    if body.type not in ("percent", "fixed"):
        raise HTTPException(status_code=422, detail="Type must be percent or fixed.")
    value = _num(body.value, "Value", 0.01, 100 if body.type == "percent" else 100000, allow_none=False)
    starts, ends = _parse_dt(body.starts_at), _parse_dt(body.ends_at)
    if starts and ends and ends <= starts:
        raise HTTPException(status_code=422, detail="The end date must be after the start date.")
    total = body.usage_limit_total
    per = body.usage_limit_per_customer
    for lim, label in ((total, "Total usage limit"), (per, "Per-customer limit")):
        if lim is not None and (lim < 1 or lim > 1000000):
            raise HTTPException(status_code=422, detail=f"{label} must be at least 1 (leave empty for no limit).")
    prods = sorted(set(body.eligible_product_ids))
    if prods and await db.products.count_documents({"id": {"$in": prods}}) != len(prods):
        raise HTTPException(status_code=422, detail="One of the selected products does not exist.")
    cats = sorted(set(body.eligible_category_slugs))
    if cats and await db.categories.count_documents({"slug": {"$in": cats}}) != len(cats):
        raise HTTPException(status_code=422, detail="One of the selected categories does not exist.")
    account_ids = []
    for e in body.customer_emails:
        e = (e or "").strip().lower()
        if not e:
            continue
        a = await db.customer_accounts.find_one({"email": e, "status": "active"}, {"id": 1})
        if not a:
            raise HTTPException(status_code=422, detail=f"No active customer account uses {e}.")
        account_ids.append(a["id"])
    return {
        "code": code, "name": (body.name or "").strip()[:80] or code, "description": (body.description or "").strip()[:300],
        "type": body.type, "value": value,
        "max_discount_bdt": _num(body.max_discount_bdt, "Maximum discount", 0),
        "max_percent_of_subtotal": _num(body.max_percent_of_subtotal, "Maximum percent", 0.01, 100),
        "min_subtotal": _num(body.min_subtotal or 0, "Minimum subtotal", 0) or 0,
        "starts_at": starts, "ends_at": ends, "usage_limit_total": total, "usage_limit_per_customer": per,
        "first_order_only": bool(body.first_order_only), "eligible_product_ids": prods,
        "eligible_category_slugs": cats, "customer_account_ids": sorted(set(account_ids)),
    }


async def _summary(p: dict) -> dict:
    redemptions = await db.promotion_redemptions.find({"promotion_id": p["id"], "status": "redeemed"},
                                                      {"_id": 0, "discount_amount": 1}).to_list(100000)
    return {**{k: v for k, v in p.items() if k not in ("audit", "customer_account_ids")},
            "customer_count": len(p.get("customer_account_ids") or []),
            "state": effective_state(p), "redemptions": len(redemptions),
            "discount_given": sum(float(r["discount_amount"]) for r in redemptions)}


@promotions_admin_router.get("")
async def list_promotions(kind: str = "codes", current=Depends(require("promotions.view"))):
    q = {"kind": {"$ne": "welcome_issued"}} if kind == "codes" else {"kind": "welcome_issued"}
    promos = await db.promotions.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [await _summary(p) for p in promos]


@promotions_admin_router.get("/campaigns/welcome")
async def get_welcome(current=Depends(require("promotions.view"))):
    cfg = await welcome_config()
    issued = await db.welcome_issuance.count_documents({})
    welcome_ids = [p["id"] for p in await db.promotions.find({"kind": "welcome_issued"}, {"id": 1}).to_list(100000)]
    redeemed = await db.promotion_redemptions.count_documents({"promotion_id": {"$in": welcome_ids}, "status": "redeemed"}) if welcome_ids else 0
    return {**{k: v for k, v in cfg.items() if k != "_id"}, "issued": issued, "redeemed": redeemed,
            "differs_from_approved": differs_from_approved(cfg)}


@promotions_admin_router.put("/campaigns/welcome")
async def update_welcome(body: WelcomeBody, current=Depends(require("promotions.activate"))):
    cfg = await welcome_config()
    changes = {}
    for field, lo, hi in (("value", 1, 100), ("validity_days", 1, 365), ("min_subtotal", 0, 1000000), ("max_discount_bdt", 0, 1000000)):
        v = getattr(body, field)
        if v is not None:
            changes[field] = _num(v, field, lo, hi)
            if field == "validity_days":
                changes[field] = int(changes[field])
    if body.first_order_only is not None:
        changes["first_order_only"] = body.first_order_only
    if body.enabled is not None:
        changes["enabled"] = body.enabled
    merged = {**cfg, **changes}
    if merged.get("enabled"):
        if merged.get("min_subtotal") is None or merged.get("max_discount_bdt") is None:
            raise HTTPException(status_code=400, detail="Set the minimum order subtotal and the maximum discount (0 is allowed) before enabling the welcome offer.")
        if not body.confirm:
            raise HTTPException(status_code=400, detail="Confirm to enable: new verified customers will start receiving real, usable coupons.")
        changed = differs_from_approved(merged)
        if changed and not body.confirm_unapproved_limits:
            raise HTTPException(status_code=400, detail="These settings differ from the founder-approved welcome limits ("
                                + ", ".join(changed) + "). Restore the approved values, or confirm the change explicitly.")
        if not cfg.get("enabled"):
            changes.update(approved_by=current["email"], approved_at=now_iso())
    changes["updated_at"] = now_iso()
    changes["updated_by"] = current["email"]
    await db.promotion_campaigns.update_one({"_id": WELCOME_ID}, {"$set": changes, "$setOnInsert": {
        k: v for k, v in WELCOME_DEFAULTS.items() if k not in changes and k != "_id"}}, upsert=True)
    await _audit(WELCOME_ID, "welcome_updated", current["email"], {k: v for k, v in changes.items() if k not in ("updated_at",)})
    return await get_welcome(current)


@promotions_admin_router.get("/{promotion_id}")
async def get_promotion(promotion_id: str, current=Depends(require("promotions.view"))):
    p = await db.promotions.find_one({"id": promotion_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Promotion not found")
    emails = [a["email"] for a in await db.customer_accounts.find({"id": {"$in": p.get("customer_account_ids") or []}}, {"email": 1}).to_list(500)]
    redemptions = await db.promotion_redemptions.find({"promotion_id": promotion_id}, {"_id": 0, "usage_key": 0, "usage_keys": 0}).sort("created_at", -1).to_list(500)
    audit = await db.promotion_audit.find({"promotion_id": promotion_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {**await _summary(p), "customer_emails": emails, "redemption_list": redemptions, "audit": audit}


@promotions_admin_router.post("")
async def create_promotion(body: PromotionBody, current=Depends(require("promotions.manage"))):
    fields = await _validated(body)
    promo = {"id": str(uuid.uuid4()), "kind": "code", **fields, "status": "draft",
             "remaining_uses": fields["usage_limit_total"], "redeemed_count": 0,
             "created_by": current["email"], "created_at": now_iso(), "updated_by": current["email"], "updated_at": now_iso()}
    try:
        await db.promotions.insert_one({**promo})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A promotion with this code already exists.")
    await _audit(promo["id"], "created", current["email"], {"code": promo["code"], "type": promo["type"], "value": promo["value"]})
    return await get_promotion(promo["id"], current)


@promotions_admin_router.put("/{promotion_id}")
async def update_promotion(promotion_id: str, body: PromotionBody, current=Depends(require("promotions.manage"))):
    p = await db.promotions.find_one({"id": promotion_id}, {"_id": 0})
    if not p or p.get("kind") == "welcome_issued":
        raise HTTPException(status_code=404, detail="Promotion not found")
    if p.get("status") == "active":
        raise HTTPException(status_code=400, detail="Pause this promotion before editing it.")
    fields = await _validated(body)
    if fields["code"] != p["code"] and p.get("redeemed_count"):
        raise HTTPException(status_code=400, detail="The code of a promotion that has been used cannot be changed.")
    used = int(p.get("redeemed_count") or 0)
    if fields["usage_limit_total"] is not None and fields["usage_limit_total"] < used:
        raise HTTPException(status_code=400, detail=f"The total limit cannot be below the {used} uses already made.")
    fields["remaining_uses"] = None if fields["usage_limit_total"] is None else fields["usage_limit_total"] - used
    changes = {k: v for k, v in fields.items() if p.get(k) != v}
    try:
        await db.promotions.update_one({"id": promotion_id}, {"$set": {**fields, "updated_by": current["email"], "updated_at": now_iso()}})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A promotion with this code already exists.")
    await _audit(promotion_id, "updated", current["email"], {k: v for k, v in changes.items() if k != "customer_account_ids"})
    return await get_promotion(promotion_id, current)


@promotions_admin_router.post("/{promotion_id}/activate")
async def activate_promotion(promotion_id: str, body: ConfirmBody, current=Depends(require("promotions.activate"))):
    p = await db.promotions.find_one({"id": promotion_id}, {"_id": 0})
    if not p or p.get("kind") == "welcome_issued":
        raise HTTPException(status_code=404, detail="Promotion not found")
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Confirm activation: customers will be able to use this code at checkout.")
    if p.get("ends_at") and p["ends_at"] <= now_iso():
        raise HTTPException(status_code=400, detail="This promotion's end date has passed.")
    await db.promotions.update_one({"id": promotion_id}, {"$set": {"status": "active", "activated_by": current["email"],
                                                                    "activated_at": now_iso(), "updated_at": now_iso()}})
    await _audit(promotion_id, "activated", current["email"], {"note": (body.note or "")[:200]})
    return await get_promotion(promotion_id, current)


@promotions_admin_router.post("/{promotion_id}/pause")
async def pause_promotion(promotion_id: str, current=Depends(require("promotions.manage"))):
    res = await db.promotions.update_one({"id": promotion_id, "status": "active"},
                                         {"$set": {"status": "paused", "updated_by": current["email"], "updated_at": now_iso()}})
    if not res.modified_count:
        raise HTTPException(status_code=400, detail="Only an active promotion can be paused.")
    await _audit(promotion_id, "paused", current["email"], {})
    return await get_promotion(promotion_id, current)


@promotions_admin_router.post("/{promotion_id}/archive")
async def archive_promotion(promotion_id: str, current=Depends(require("promotions.manage"))):
    res = await db.promotions.update_one({"id": promotion_id, "status": {"$in": ["draft", "paused"]}, "kind": {"$ne": "welcome_issued"}},
                                         {"$set": {"status": "archived", "updated_by": current["email"], "updated_at": now_iso()}})
    if not res.modified_count:
        raise HTTPException(status_code=400, detail="Pause the promotion first. Only draft or paused promotions can be archived.")
    await _audit(promotion_id, "archived", current["email"], {})
    return {"ok": True}


@promotions_admin_router.post("/preview")
async def preview(body: PreviewBody, current=Depends(require("promotions.view"))):
    if body.type not in ("percent", "fixed"):
        raise HTTPException(status_code=422, detail="Type must be percent or fixed.")
    subtotal = _num(body.subtotal, "Subtotal", 0, 10000000, allow_none=False)
    rules = {"type": body.type, "value": _num(body.value, "Value", 0, 100000, allow_none=False),
             "max_discount_bdt": _num(body.max_discount_bdt, "Maximum discount", 0),
             "max_percent_of_subtotal": _num(body.max_percent_of_subtotal, "Maximum percent", 0, 100)}
    meets = subtotal >= float(body.min_subtotal or 0)
    res = compute_discount(rules, [{"product_id": "-", "category_slug": "-", "line_total": subtotal}])
    discount = res["discount"] if meets else 0
    delivery = float(body.delivery_charge or 0)
    return {"meets_minimum": meets, "discount": discount, "merchandise_after": subtotal - discount,
            "total_with_delivery": subtotal - discount + delivery,
            "effective_percent": round(discount / subtotal * 100, 2) if subtotal else 0}


@promotions_admin_router.post("/redemptions/{redemption_id}/restore")
async def restore_redemption(redemption_id: str, body: ConfirmBody, current=Depends(require("promotions.manage"))):
    r = await db.promotion_redemptions.find_one({"id": redemption_id, "status": "redeemed"}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Redemption not found or already restored")
    order = await db.orders.find_one({"id": r["order_id"]}, {"order_status": 1})
    if not order or order.get("order_status") not in ("Cancelled", "Returned"):
        raise HTTPException(status_code=400, detail="A code can only be restored for a cancelled or returned order.")
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Confirm to give this customer the use of the code back.")
    res = await db.promotion_redemptions.update_one({"id": redemption_id, "status": "redeemed"},
                                                    {"$set": {"status": "restored", "restored_by": current["email"], "restored_at": now_iso()}})
    if res.modified_count:
        await release({"promotion_id": r["promotion_id"], "limited": r.get("limited"), "usage_key": r.get("usage_key"),
                       "usage_keys": r.get("usage_keys") or []})
        await _audit(r["promotion_id"], "redemption_restored", current["email"], {"order_number": r["order_number"], "note": (body.note or "")[:200]})
    return {"ok": True}


PROMOTION_INDEXES = [
    ("promotions", [("id", 1)], {"unique": True, "name": "id_unique"}),
    ("promotions", [("code", 1)], {"unique": True, "name": "code_unique"}),
    ("promotions", [("customer_account_ids", 1)], {"name": "customer_account_ids"}),
    ("promotion_redemptions", [("promotion_id", 1), ("order_id", 1)], {"unique": True, "name": "promotion_order_unique"}),
    ("promotion_audit", [("promotion_id", 1), ("created_at", -1)], {"name": "promotion_created"}),
]


async def ensure_promotion_indexes():
    for coll, keys, opts in PROMOTION_INDEXES:
        try:
            existing = await db[coll].index_information()
            if any(list(i.get("key", [])) == keys for i in existing.values()):
                continue
            await db[coll].create_index(keys, **opts)
        except Exception:  # noqa: BLE001
            pass

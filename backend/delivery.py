"""
AAYNA delivery charge policy (founder decision, 2026-10-19 - final).

    merchandise subtotal  < ৳1,500  ->  ৳100 delivery, anywhere in Bangladesh
    merchandise subtotal >= ৳1,500  ->  FREE delivery, anywhere in Bangladesh

"Merchandise subtotal" is the sum of the order lines at the server's current
selling prices, BEFORE any promotional (coupon / welcome) discount. A discount
therefore never pushes an order back below the free-delivery threshold, and a
coupon never reduces the delivery charge.

This module is the single server-side source of truth: /api/cart/validate,
/api/checkout and the public /api/settings all call it. Admin -> Settings may
override the two amounts with `delivery_charge_bdt` and
`free_delivery_min_subtotal_bdt`; when they are not set (production has no
settings yet) the founder's values below apply. The old per-district keys
(`delivery_charge_inside_dhaka` / `_outside_dhaka`) and the old
`free_delivery_threshold` key are no longer read.
"""
from typing import Optional

DEFAULT_DELIVERY_CHARGE_BDT = 100
DEFAULT_FREE_DELIVERY_MIN_SUBTOTAL_BDT = 1500
DECIDED_ON = "2026-10-19"

CHARGE_KEY = "delivery_charge_bdt"
THRESHOLD_KEY = "free_delivery_min_subtotal_bdt"
LEGACY_KEYS = ("delivery_charge_inside_dhaka", "delivery_charge_outside_dhaka", "free_delivery_threshold")

# Admin -> Settings validation bounds (whole taka).
MAX_CHARGE_BDT = 2000
MAX_THRESHOLD_BDT = 1_000_000


def _whole_taka(value, default: int) -> int:
    if value is None or value == "" or isinstance(value, bool):
        return default
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    if n != n or n < 0:  # NaN or negative: ignore a broken stored value
        return default
    return int(round(n))


def policy(settings: Optional[dict] = None) -> dict:
    s = settings or {}
    return {
        "charge": _whole_taka(s.get(CHARGE_KEY), DEFAULT_DELIVERY_CHARGE_BDT),
        "free_threshold": _whole_taka(s.get(THRESHOLD_KEY), DEFAULT_FREE_DELIVERY_MIN_SUBTOTAL_BDT),
    }


def quote(merchandise_subtotal: float, settings: Optional[dict] = None) -> dict:
    """Delivery for a merchandise subtotal taken BEFORE promotional discounts.

    An empty selection (subtotal 0) has nothing to deliver and is charged 0.
    A threshold of 0 means "no free delivery".
    """
    p = policy(settings)
    sub = max(0.0, float(merchandise_subtotal or 0))
    if sub <= 0:
        return {"delivery_charge": 0, "free_delivery": False, "amount_to_free_delivery": p["free_threshold"], **p}
    free = p["free_threshold"] > 0 and sub >= p["free_threshold"]
    remaining = 0 if free or p["free_threshold"] <= 0 else p["free_threshold"] - sub
    remaining = int(remaining) if float(remaining).is_integer() else round(remaining, 2)
    return {"delivery_charge": 0 if free else p["charge"], "free_delivery": free,
            "amount_to_free_delivery": remaining, **p}


def validate_setting(key: str, value) -> Optional[str]:
    """Error message for a bad Admin -> Settings value, or None when acceptable."""
    if key not in (CHARGE_KEY, THRESHOLD_KEY):
        return None
    if isinstance(value, bool):
        return f"{key} must be a whole number of taka"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return f"{key} must be a whole number of taka"
    hi = MAX_CHARGE_BDT if key == CHARGE_KEY else MAX_THRESHOLD_BDT
    if n != n or n < 0 or n > hi or not n.is_integer():
        return f"{key} must be a whole number between 0 and {hi}"
    return None

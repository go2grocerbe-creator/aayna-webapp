"""
AAYNA cost-based selling-price rule.

    adjusted_cost  = cost_price + EXTRA            (fixed amount per sold unit; per pair for earrings)
    selling_price  = adjusted_cost * MULTIPLIER, rounded UP to the next ৳10
                     (founder decision 2026-10-18; already-whole tens stay unchanged)
    gross_profit   = selling_price - adjusted_cost
    gross_margin   = gross_profit / selling_price  (on the rounded price)

The extra amount is added once per sellable unit; for earrings sold as a pair,
once per pair (founder-confirmed 2026-10-18).

The two founder-set values are BUSINESS-CONFIDENTIAL and are NOT in this
(public) repository: together with a public selling price they would reveal the
purchase cost and margin. They are read from the environment of the machine
that runs the import/repricing (backend/.env, git-ignored):

    AAYNA_PRICE_EXTRA_BDT=<fixed BDT added to each unit's cost>
    AAYNA_PRICE_MULTIPLIER=<multiplier applied to the adjusted cost>

All values are BDT. `cost_price` is the per-unit purchase cost exactly as
recorded (spreadsheet "Unit cost (BDT)" -> admin-only `cost_price`); it is never
modified here and the rule is never applied to an existing selling price, so
re-running it cannot stack the extra amount or the markup.

Nothing in this module is public: the storefront API serves products through
the PUBLIC_PRODUCT_FIELDS whitelist in server.py, which excludes cost_price and
every pricing/history field written by the importer and scripts/reprice_from_cost.py.
"""
import math
import os
from decimal import Decimal, ROUND_CEILING

RULE_ID = "cost_plus_fixed_x_multiplier"
ENV_EXTRA = "AAYNA_PRICE_EXTRA_BDT"
ENV_MULTIPLIER = "AAYNA_PRICE_MULTIPLIER"
ROUND_UP_TO_BDT = 10


class PricingError(ValueError):
    """Cost or rule parameter is missing, non-numeric, non-finite or out of range."""


def _number(value, what, allow_zero=False):
    if isinstance(value, bool) or value is None or value == "":
        raise PricingError(f"{what} is missing")
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise PricingError(f"{what} is not a number")
    if not math.isfinite(x) or x < 0 or (x == 0 and not allow_zero):
        raise PricingError(f"{what} must be a positive amount")
    return x


def _money(x):
    # BDT with at most 2 decimals; whole taka stay ints for display/storage.
    x = round(x + 0.0, 2)
    return int(x) if x == int(x) else x


def round_up(amount, step=ROUND_UP_TO_BDT):
    """Round a BDT amount up to the next multiple of `step` (exact multiples unchanged).

    Decimal on the 2-dp value, so float noise (e.g. 1349.9999999) never bumps a
    whole price to the next ten."""
    d = Decimal(str(round(amount, 2)))
    return _money(float((d / step).to_integral_value(rounding=ROUND_CEILING) * step))


def rule_from_env(env=None):
    """Return (extra, multiplier) from the environment, or raise PricingError."""
    env = os.environ if env is None else env
    extra = _number(env.get(ENV_EXTRA), ENV_EXTRA, allow_zero=True)
    mult = _number(env.get(ENV_MULTIPLIER), ENV_MULTIPLIER)
    if mult <= 1:
        raise PricingError(f"{ENV_MULTIPLIER} must be greater than 1 (selling price above adjusted cost)")
    return _money(extra), _money(mult)


def price_from_cost(cost, extra, multiplier):
    """Return the full per-unit breakdown. Raises PricingError on a bad cost or rule."""
    c = _number(cost, "cost")
    e = _number(extra, "extra", allow_zero=True)
    m = _number(multiplier, "multiplier")
    adjusted = c + e
    unrounded = adjusted * m
    selling = round_up(unrounded)
    profit = selling - adjusted
    return {
        "rule": RULE_ID,
        "cost": _money(c),
        "extra": _money(e),
        "multiplier": _money(m),
        "adjusted_cost": _money(adjusted),
        "unrounded_price": _money(unrounded),
        "round_up_to": ROUND_UP_TO_BDT,
        "selling_price": _money(selling),
        "gross_profit": _money(profit),
        "gross_margin_pct": round(profit / selling * 100, 2),
    }

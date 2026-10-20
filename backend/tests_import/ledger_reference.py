# Copied unchanged (test aid only) from the 20 Oct 2026 founder handoff "AAYNA_Product_SEO_Steadfast".
"""Independent money-math ORACLE for AAYNA courier ledger tests.
No DB calls, no production writes. Does not replace backend/courier_finance.py.
All amounts are decimal strings in BDT, not floating point source-of-truth.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from dataclasses import dataclass
from typing import Optional

Q = Decimal("0.01")
def bdt(value):
    if value is None or isinstance(value, bool): return None
    try: n = Decimal(str(value))
    except (InvalidOperation, ValueError): raise ValueError("invalid money amount")
    if not n.is_finite(): raise ValueError("invalid money amount")
    return n.quantize(Q, rounding=ROUND_HALF_UP)

@dataclass(frozen=True)
class Line:
    amount: Optional[Decimal]
    basis: str = "not_available"  # provider_confirmed / statement / estimated / not_applicable
    @classmethod
    def of(cls, value, basis): return cls(bdt(value), basis)

def expected_settlement(collected: Line, delivery: Line, cod_fee: Line,
                        return_fee: Line, deductions=(), adjustments=()):
    """No fake 0s. Return (amount, classification)."""
    fields = (collected, delivery, cod_fee, return_fee)
    if any(x.amount is None for x in fields): return None, "not_available"
    amount = collected.amount - delivery.amount - cod_fee.amount - return_fee.amount
    amount -= sum((bdt(x) for x in deductions), Decimal("0.00"))
    amount += sum((bdt(x) for x in adjustments), Decimal("0.00"))
    confirmed = {"provider_confirmed", "statement", "not_applicable"}
    return amount.quantize(Q), "confirmed" if all(x.basis in confirmed for x in fields) else "estimate"

def variance(actual_payout, expected):
    if actual_payout is None or expected is None: return None
    return bdt(actual_payout) - bdt(expected)

"""Admin dashboard order counters (21 Oct 2026, adapted from the founder's kit).

Counts are grouped by the SAME order_status values the Orders list and the order API use
(admin_routes.ORDER_STATUSES). Each status has its own counter - "Confirmed" is never folded
into "New" - and anything unexpected is reported under `unknown` instead of disappearing.
"Today" uses the Asia/Dhaka calendar day (orders store UTC ISO timestamps).
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

DHAKA = timedelta(hours=6)  # Asia/Dhaka has no daylight saving

# key used by the dashboard API -> stored order_status value
BUCKETS = {
    "new": "New",
    "confirmed": "Confirmed",
    "packed": "Packed",
    "with_courier": "Sent to Courier",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
    "returned": "Returned",
}
OPEN = ("New", "Confirmed", "Packed", "Sent to Courier")


def count_statuses(statuses) -> dict:
    """statuses: iterable of raw order_status values (one per order)."""
    counts = Counter((s or "").strip() for s in statuses)
    known = set(BUCKETS.values())
    out = {k: counts.get(v, 0) for k, v in BUCKETS.items()}
    out["open"] = sum(counts.get(s, 0) for s in OPEN)
    out["unknown"] = {k or "(blank)": v for k, v in counts.items() if k not in known}
    out["total"] = sum(counts.values())
    return out


def dhaka_day_start_utc(now: datetime | None = None) -> str:
    """UTC ISO timestamp of the most recent midnight in Asia/Dhaka."""
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(timezone.utc) + DHAKA
    return (local.replace(hour=0, minute=0, second=0, microsecond=0) - DHAKA).isoformat()

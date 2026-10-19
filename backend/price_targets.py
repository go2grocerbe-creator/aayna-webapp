"""
Founder-approved selling-price update of 2026-10-19: every one of the 10 launch
products goes up by exactly ৳100. These are PUBLIC selling prices (no cost data).

    SKU -> (price before the update, approved target price)

The "before" prices were read from aayna_prod (read-only) on 2026-10-19 21:20 and
again at 22:40 Dhaka; the targets are those prices + ৳100 and match the founder's
verification figures (৳970 Bold Chunky, ৳1,090 Crystal Stone Cuff, ৳1,510 Floral Bloom).

Idempotency: a product is changed only while it still has its "before" price; a
product already at its target is left alone, and any other price is reported and
never touched. Running the update twice can therefore never add ৳200.
"""
PRICE_UPDATE_ID = "plus-100-2026-10-19"
PRICE_INCREASE_BDT = 100

PRICE_TARGETS = {
    "AYN-NKL-LUN-GLD": (1350, 1450),  # Luna Statement Locket
    "AYN-NKL-AUR-GLD": (1350, 1450),  # Aura Statement Locket
    "AYN-CUF-CRS-GLD": (1050, 1150),  # Golden Crossline Cuff
    "AYN-CUF-STN-GLD": (990, 1090),   # Crystal Stone Cuff
    "AYN-EAR-CHK-GLD": (870, 970),    # Bold Chunky Earrings
    "AYN-EAR-FLR-GLD": (1410, 1510),  # Floral Bloom Earrings - Golden
    "AYN-EAR-FLR-SLV": (1410, 1510),  # Floral Bloom Earrings - Silver
    "AYN-BRC-FLR-GLD": (1310, 1410),  # Floral Charm Bracelet - Golden
    "AYN-BRC-FLR-SLV": (1310, 1410),  # Floral Charm Bracelet - Silver
    "AYN-RNG-CLS-GLD": (1290, 1390),  # Classic Statement Ring
}

assert all(new - old == PRICE_INCREASE_BDT for old, new in PRICE_TARGETS.values())


def plan(sku: str, current_price, discount_price=None) -> dict:
    """What the update does to one product. Pure function."""
    if sku not in PRICE_TARGETS:
        return {"sku": sku, "action": "skip", "reason": "not part of this price update"}
    old, new = PRICE_TARGETS[sku]
    row = {"sku": sku, "current": current_price, "before": old, "target": new}
    if discount_price not in (None, "", 0):
        return {**row, "action": "flag", "reason": "has a discount price; review by hand"}
    if current_price == new:
        return {**row, "action": "already"}
    if current_price == old:
        return {**row, "action": "update"}
    return {**row, "action": "flag", "reason": f"unexpected current price {current_price}; not changed"}

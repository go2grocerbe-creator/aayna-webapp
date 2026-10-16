# Deferred work (not part of the active application)

## `order-stock-returns-ui.patch` — admin "Stock from this order" panel

Status: **deferred** in Phase 4B. Saved so it is not lost; **not** applied.

What it is: an admin panel on Order detail for Cancelled/Returned orders where the
admin records, per item, whether goods go "Back to stock (sellable)" or "Damaged /
not sellable", with an audit history. It calls `POST /api/admin/orders/{n}/stock-returns`,
**which does not exist** — the matching backend endpoint was proposed but not
implemented, pending a separately reviewed workflow (design in
`docs/audits/PRODUCTION_DATA_INTEGRITY.md` §4).

Until then, inventory for cancelled and returned orders is adjusted **manually** in
Admin → Inventory → Adjust stock (reason: the order number). Nothing restocks automatically.

To restore the UI later (only together with the reviewed backend endpoint):

```bash
git apply docs/deferred/order-stock-returns-ui.patch
```

Applying the patch alone would show a panel whose submit fails (404).

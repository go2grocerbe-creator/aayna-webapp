# AAYNA Launch Settings Baseline (post-L3.1)

What is approved and applied, and what is still unresolved, as of L3.1. See
`LAUNCH_BUSINESS_SETTINGS_AUDIT.md` for the original findings this responds
to.

## Approved and applied

| Setting | Value | Where |
|---|---|---|
| Delivery, inside Dhaka | ৳80 | `aayna_dev.website_settings`, live via `PUT /api/admin/settings` |
| Delivery, outside Dhaka | ৳150 (was ৳130) | same |
| COD | Enabled (`cod_available: true`) | same, **and now actually enforced** — Checkout.jsx previously never read this flag; it does now |
| bKash | Disabled | unchanged — `bkash_number` stays a placeholder, `isPlaceholder()` gate untouched |
| Nagad | Disabled | unchanged — same as bKash |
| Return/Exchange policy | 7-day exchange window; item must be undamaged for a standard exchange; damaged/wrong item eligible for assessment (replacement or refund); refund eligibility determined after assessment, never promised automatically | `frontend/src/data/staticPages.js` |

## Explicitly NOT approved (presentation now correctly hides these)

| Item | State | What changed |
|---|---|---|
| WhatsApp / phone | Placeholder (`+8801XXXXXXXXX`), **value unchanged in the database** | Now hidden everywhere it was previously shown ungated: `WhatsAppFloat` (was rendering unconditionally — a real bug, no gate existed at all), `Footer.jsx`, `Contact.jsx`. `isPlaceholder()` already correctly gated the PDP inline WhatsApp inquiry link and the Checkout bKash/Nagad flow before this task — those were untouched. |
| Support email | `hello@aayna.xyz`, **value unchanged in the database** | Founder said "NA for now" — this is a launch-approval decision, not a placeholder-detection one (the stored value doesn't match `isPlaceholder()`'s patterns). No longer rendered as a customer-facing contact method in `Footer.jsx` or `Contact.jsx`. |
| TikTok | Stored, resolves, **unchanged** | Stays hidden — never surfaced in Footer/Contact, exactly as before. Nothing to fix; it was already not shown. |

## Support contact channel — launch blocker, unresolved

**SUPPORT CONTACT CHANNEL: MISSING.** No phone, WhatsApp, or email has been
approved for production. `Contact.jsx` now says so honestly ("We don't have
a direct support channel live yet. For an existing order, use Track
Order.") instead of showing broken/placeholder methods. The Return &
Exchange policy states real eligibility rules, but a customer with an
actual damaged-item or exchange request currently has no approved way to
reach AAYNA to act on them.

This remains a launch blocker **for actually fulfilling exchange/refund
requests** — it does not block moving on to SEO preparation. Resolve by
providing a real phone/WhatsApp number or a real, monitored support email
before accepting real customer orders.

## Database mutation record

Applied via `PUT /api/admin/settings` (existing endpoint, no schema
changes):

```
delivery_charge_inside_dhaka: 80 -> 80   (no change, now explicit)
delivery_charge_outside_dhaka: 130 -> 150
cod_available: true -> true               (no change, now explicit)
```

Not touched: `bkash_number`, `nagad_number`, `whatsapp_number`,
`support_email`, `tiktok_url`, or any other key. `aayna_dev` product/
category/order/customer counts are unaffected by this task (verified
unchanged: 18/10/51/2 products/categories/orders/customers).

## Code changed (presentation/gating only, no new settings keys)

`frontend/src/components/Footer.jsx`, `frontend/src/components/
WhatsAppFloat.jsx`, `frontend/src/pages/Contact.jsx`,
`frontend/src/pages/Checkout.jsx`, `frontend/src/data/staticPages.js`.

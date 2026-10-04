# AAYNA Launch Operations Runbook

Practical day-to-day order handling for whoever runs Admin after launch.
Every mechanism referenced here was verified live against `aayna_dev`
during L5 QA (order `ORD-1052` — see `L5_DEPLOYMENT_READINESS.md`), not
assumed from reading code. Where a founder decision is missing, marked
**TODO**.

## A. New order arrives

Customer completes Checkout (PDP → Cart → Checkout → COD). The order is
created with `order_status: "New"`, stock is decremented immediately (not
reserved-then-confirmed — decrement happens at order creation), and the
customer sees the confirmation page via a one-time token (never a raw
order-number lookup). Admin → Orders lists it, newest first.

If `ORDER_WEBHOOK_ENABLED=true` and `ORDER_WEBHOOK_URL` is set, a
notification also fires to your configured router (Make.com/n8n/etc.) —
verified this is fully disabled in dev by default and does not fire
unless explicitly turned on.

## B. Verify the order

Open Admin → Orders → the order. Confirm: item(s), quantity, delivery
district, address, phone, payment method. `payment_status` starts as
`COD_pending` for COD orders (no other payment methods are enabled at
launch — bKash/Nagad are off).

## C. Confirm

Set status to `Confirmed` once you've verified stock is genuinely
available and the order looks legitimate (not a test/spam submission).
No side effects beyond the status change itself.

## D. Pack

Set status to `Packed` when the item is physically packed and ready for
courier pickup. No side effects beyond the status change.

## E. Mark Sent to Courier

Set status to `Sent to Courier` once handed to the delivery courier.

## F. Enter courier/tracking details

`courier_name` and `courier_tracking_code` are optional, free-text,
admin-editable fields on the same order — set them whenever you have
them (courier name and their tracking code/waybill number). They appear
immediately on the customer's Track Order lookup. **No courier service is
integrated** — this is a manual field, not a live tracking feed. Do not
put a real courier account credential here; it's just a label + code
shown to the customer.

## G. Mark Delivered

Set status to `Delivered` once the courier confirms delivery. Verified
side effect: increments the customer's `successful_orders` counter only
— no inventory or payment change happens automatically.

**COD payment is not auto-marked as collected.** `payment_status` stays
`COD_pending` through Delivered — verified this live. If you need to
track "cash actually collected," that is currently a manual note
(`admin_note` field) or a **TODO**: no dedicated "payment collected"
toggle exists yet.

## H. Cancelled order

Setting `order_status: "Cancelled"` **does not automatically restore
stock** — verified by direct code inspection, no exceptions. If you
cancel an order, you must **separately** go to Admin → Inventory → the
product → Adjust Stock, and add back the quantity (`change_type: "return"`
or `"adjustment"`, positive `quantity_change`) yourself, or the product
will show fewer units available than actually exist. This is a real gap
in the current system — see `L5_DEPLOYMENT_READINESS.md` §28 — and is
flagged there as a post-launch automation candidate, not something
invented or silently patched here.

**Proposed rule for founder approval (not implemented — L5.1):**
`Cancelled` → restore the ordered quantity exactly once, only if stock was
previously decremented for this order (guard against double-restore on a
repeated/duplicate status write). `Returned` → do **not** auto-restore —
see §I, a returned item may be damaged/unsellable and needs inspection
first. Do not build either until approved.

There is also **no transition guard**: any order can be set to any
status from any other status (including `Delivered → Cancelled`) with no
warning. Use judgment; don't rely on the system to stop an accidental
transition.

## I. Returned order

Same as Cancelled: set `order_status: "Returned"`, then **manually**
restore stock via Admin → Inventory → Adjust Stock. Nothing automatic
happens on this transition either.

## J. Stock handling

- Stock decrements **once**, at order creation (checkout), for every
  item in the order — not on Confirmed/Packed/etc.
- Stock only goes back up through a manual Inventory adjustment (§H/§I),
  or by an admin directly editing a product's stock quantity.
- Every stock change (sale, manual adjustment) is recorded in
  `inventory_logs` with a before/after quantity and reason — useful for
  reconciling "why is this number what it is."
- A product's `status` auto-flips to `out_of_stock` when its quantity
  hits 0, and back to `active` when a manual adjustment brings it above 0.

## K. Customer exchange/refund handling

Per the approved Return & Exchange policy (`LAUNCH_SETTINGS_BASELINE.md`):
7-day exchange window, item must be undamaged for a standard exchange;
a damaged or wrong item is eligible for assessment → replacement or
refund (never an automatic refund promise).

**There is currently no system-supported exchange/refund workflow** — no
"initiate exchange" button, no refund-tracking field. Handling this today
means: cancel/return the order status manually (§H/§I), restore stock
manually if the item comes back sellable, and track the resolution
outside the system (a spreadsheet, or the `admin_note` field) until a
real workflow exists. **TODO** if volume justifies building one.

## L. What to do when payment is COD

This is the only enabled payment method at launch. There is no
payment-gateway integration, no automatic reconciliation. Cash
collection and any discrepancy handling is entirely an offline courier/
admin process outside this system today. **TODO**: decide whether
`payment_status` should ever be manually flipped to something like
`"paid"` once cash is collected and reconciled, or whether it's tracked
elsewhere entirely.

## M. Current unsupported systems

Explicitly **not** implemented — do not assume any of these exist:
- Email order confirmation (none)
- SMS notifications (none)
- Automated WhatsApp messages (none — the WhatsApp float button, when a
  real number is configured, only opens a manual chat)
- Courier API integration (courier fields are free-text labels only)
- Payment gateway / auto payment reconciliation (COD only, manual)
- Automatic stock restoration on Cancel/Return (§H/§I — manual only)
- Refund/exchange workflow tooling (§K — manual only)
- **A monitored customer support channel** — the single biggest launch
  blocker. See "Support channel" section below.

## Support channel

**SUPPORT CONTACT CHANNEL: MISSING.** No phone, WhatsApp, or monitored
email is approved for production as of this milestone
(`LAUNCH_SETTINGS_BASELINE.md`). This blocks actually fulfilling any
exchange/refund/complaint a real customer raises. To be configured
before public order acceptance begins — not invented here.

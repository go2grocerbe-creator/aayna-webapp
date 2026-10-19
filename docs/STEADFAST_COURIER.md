# Steadfast courier integration (preview feature, 2026-10-19)

Status: built and tested against a **simulator**. No real Steadfast call has been made, no real
consignment exists, and real bookings are switched off in code until the founder approves them.
The mocked tests prove AAYNA's own logic. They do **not** prove that real Steadfast bookings work.

Code: `backend/steadfast.py`, panel `frontend/src/admin/SteadfastPanel.jsx`, tests
`backend/tests_import/test_steadfast.py`, browser check `scripts/verify/delivery_courier_ui.js`.

## Source of the API details

The founder's "AAYNA Steadfast API Reference (redacted)", taken from the Steadfast merchant portal
guide on 19 Oct 2026. Base URL `https://portal.packzy.com/api/v1`, headers `Api-Key` and
`Secret-Key` on every authenticated call, JSON bodies. No community SDK was used.

That guide does **not** include response schemas, webhook setup or authentication, the exact
duplicate-invoice and "not found" answers, or sandbox keys. The code therefore reads answers
defensively. Anything it cannot confirm ends in `needs_reconciliation` for a person to resolve.

## Endpoints used

| Use | Endpoint | Notes |
|---|---|---|
| Book a parcel | `POST /create_order` | invoice = AAYNA order number; name, phone `01XXXXXXXXX`, address + district, `cod_amount`, optional note |
| Reconcile an unknown outcome | `GET /status_by_invoice/{invoice}` | used only after a timeout, 5xx or unclear answer |
| Check a manually linked id | `GET /status_by_cid/{id}` | |
| Delivery status | `GET /status_by_cid/{id}` | |
| Return status | `GET /status_with_return_status_by_cid/{id}` | only after a confirmed cancellation or partial delivery |

Not used: bulk booking, pickup, return requests, balance and payouts, and `fraud_check`. Returns
need the request schema confirmed first. `fraud_check` would need a separate privacy review.

## Order to courier workflow

1. New: review the order. Confirmed: phone the customer.
2. **Packed**: the Steadfast panel lets you book. Booking is refused for any other status, for
   cancelled or returned orders, for missing or invalid contact and address details, for fields
   longer than Steadfast allows, and for prepaid orders that are not verified.
3. **Book with Steadfast**: the panel shows the exact recipient, phone, address and the cash to
   collect, and needs a second "Confirm booking" click. The order stays **Packed**, because
   booking a parcel is not dispatching it.
4. Hand the parcel over, then set **Sent to Courier**. The existing "Handed to courier" email is
   sent once.
5. **Check delivery status**, either per order or with "Check Steadfast parcels" on the Orders list.
   - A confirmed `delivered` moves the order to **Delivered** and the existing email is sent once.
   - A rider-reported `delivered_approval_pending` is shown but not acted on.
6. Exceptions (`hold`, `partial_delivered`, `cancelled`, `exceptional`, unknown statuses and
   returns) only raise an amber "attention" note.
   - The order is never moved backwards and never cancelled or returned automatically.
   - Stock is never added back automatically. Inspect the returned parcel, then restock in
     Inventory with type "return".

Status mapping, in order of a parcel's life (an older answer never replaces a newer one):

| Order | Steadfast statuses | What AAYNA does |
|---|---|---|
| 1 | `in_review` | Booked |
| 2 | `pending`, `hold` | Booked; `hold` raises attention |
| 3 | `*_approval_pending` | Awaiting Steadfast confirmation; no order change, except Packed → Sent to Courier for a rider-reported delivery |
| 4 | `delivered` | Order → Delivered |
| 4 | `partial_delivered`, `cancelled`, `exceptional` | Attention only |
| 5–7 | return statuses (`*_proccessing`, `*_rider_assigned`, `*_received`) | Attention: inspect before restocking |

The `proccessing` spelling is Steadfast's own.

## Duplicate-shipment protection

- The invoice is the immutable order number.
- An **atomic claim** on the order document is required before anything is sent. A second click,
  a second admin or a second browser tab gets "already in progress / already booked".
- A unique index on `courier.consignment_id` stops one consignment being attached to two orders.
- An unclear outcome is never retried automatically: a timeout after sending, a 5xx, an OK without
  ids, a duplicate-invoice refusal, or a crash mid-request (a claim older than 2 minutes).
- **Reconcile** looks the invoice up at Steadfast:
  - "not found" makes it safe to book again;
  - "found" means you link the parcel by copying its consignment ID and tracking code from the
    portal. The ID is checked with Steadfast before it is saved.
  - Anything else leaves it unresolved.
- After a 401 or 403 answer, calls pause for 15 minutes, and for 60 seconds after a 429. This avoids
  Steadfast's 10-failures lockout.

## Cash on delivery (COD)

Cash to collect = merchandise subtotal − discount + the delivery charge the customer pays −
verified prepayment. It is computed from the order the server stored at checkout and refused if
those numbers do not add up.

| Order | COD |
|---|---|
| ৳970 earrings | ৳1,070 (৳970 + ৳100 delivery) |
| ৳1,090 cuff, 10% welcome | ৳1,081 (৳981 + ৳100) |
| ৳1,510 earrings, welcome capped at ৳150 | ৳1,360 (free delivery) |
| Verified prepaid (payment status `paid`) | ৳0 |
| Unverified bKash/Nagad | booking refused until verified |
| Partial prepayment | not supported yet; refused |

Steadfast's own charge to AAYNA is a merchant cost. It is never added to the COD amount.
No Steadfast fee rates are assumed anywhere.

## Status sync, notifications and customers

- **Polling only.** No public webhook exists, because the guide gives no way to authenticate one.
  An unauthenticated callback could mark orders delivered.
- Admin checks happen per order or with the Orders-list button (up to 20 unfinished parcels not
  checked in 10 minutes).
- Live answers are cached for 60 seconds, as Steadfast caches them.
- **Automatic tracking (20 Oct):** a Vercel Cron Job calls `GET /api/internal/courier/sync` once a
  day at 02:15 UTC (08:15 Dhaka). It is in `frontend/vercel.json` and has no extra cost.
  - Vercel runs cron jobs only for the **production** deployment.
  - A daily schedule works on every Vercel plan. On Hobby, cron jobs may run only once a day,
    ±59 min. Runs more often than daily need the paid Pro plan; nothing was bought.
  - The endpoint answers 404 unless `CRON_SECRET` is set and Vercel sends it as
    `Authorization: Bearer …`.
  - With Steadfast off, the run is a quiet no-op.
- **What each run checks:** only parcels that can still change. Confirmed `delivered` parcels and
  received returns are never polled again.
  - It skips anything checked in the last 10 minutes.
  - At most 20 parcels per run, inside a 22-second budget (functions here stop at 30 s).
  - It stops on a rate-limit answer.
  - A failed check backs off for that parcel: 10 min, 20, 40 … up to 24 h.
  - The last run's result shows in `GET /api/admin/courier/config`.
- **Manual checks stay** for urgent cases: "Check delivery status" on the order and "Check Steadfast
  parcels" on the Orders list.
- Each order keeps the raw status, the accepted status, the provider timestamp if any, when it
  was checked, the result, and an append-only history.
- Emails use the existing deduplicated status emails ("Handed to courier", "Delivered"). Polls
  never send email.
- Customers see the courier name, the tracking code and a short label: "Booked with Steadfast
  courier", "With Steadfast courier" or "Delivered by Steadfast courier". Any exception shows
  "Delivery update in progress - our team will contact you".
  - Never shown to customers: consignment IDs, COD figures, credentials, balances, admin notes, or
    another customer's data.
  - Ownership checks are unchanged.

## Steadfast financials (order level, admin only)

Code: `backend/courier_finance.py`, the "Steadfast financials" panel on the order, and Admin →
Courier money.

- **Where it is stored:** each order has one `courier_finance` record, the single source of
  truth, plus an append-only `courier_finance_events` log (who, when, before/after, source,
  reference, reason).
- **What it never touches:** the order total and anything the customer sees.

| Concept | How it is worked out |
|---|---|
| Customer payable | From the saved order: subtotal − approved discount + customer delivery charge − verified prepayment. It never uses current catalogue prices |
| COD requested | The amount sent at booking (the same customer payable) |
| COD collected | The amount confirmed by Steadfast or a statement. Otherwise an estimate from the delivery outcome (delivered → full, cancelled → 0, partial → unknown) |
| Courier charges | Delivery fee, COD fee, return fee, other deductions and adjustments. Each has a basis: from Steadfast / from statement / estimate / pending |
| Expected settlement | COD collected − delivery fee − COD fee − return fee − deductions + adjustments. Blank ("pending provider confirmation") while any part is unknown |
| Actual settlement | The payout amount, payment reference and date, as recorded or imported |
| Difference | Actual − expected |
| Profit | Not worked out here: purchase and packaging costs are separate |

- **Statuses:**
  - NOT_AVAILABLE: no booking, or not enough known.
  - ESTIMATED: worked out with at least one estimate.
  - PROVIDER_CONFIRMED: all charges confirmed, no payout yet.
  - SETTLED: payout recorded.
  - RECONCILED: an admin accepted the payout; a reason is needed if it differs.
  - DISPUTED.
  - A delivered parcel never counts as paid.
- **Estimates:** they exist only if the founder fills the two optional private settings: estimated
  delivery fee per parcel and estimated COD %. Both are blank by default, so nothing is assumed;
  the ৳60/৳115/৳135 screenshot rates are not used.
- **Safeguards:**
  - Each submission carries an idempotency key, so a double click or a repeated payment event
    changes nothing.
  - Changing a confirmed amount, replacing a payout or voiding an entry needs a reason. The
    previous value is kept.
  - Only the super admin and admins (`courier.finance`) can see or change any of this; order and
    product managers get 403.
  - Customer pages and the tracking API never include it.
- **Views:** Awaiting settlement · Settled · Mismatch · Delivery exception · Return pending.
- **Payout import (`GET /payments`, `/payments/{id}`):**
  - The importer accepts one explicit format, a payment plus per-consignment COD and charges, and
    matches rows by consignment ID. Anything else is reported "unreadable" for manual
    reconciliation.
  - The founder's guide does not define these response fields. So in live mode the import stays off
    until `STEADFAST_PAYMENTS_SCHEMA_VERIFIED=true` is set after checking a real answer.
  - The simulator uses that format so the matching logic is tested.
  - Until then: record charges and payouts by hand from the Steadfast statement (the panel's
    "Record charges / COD" and "Record payout").

## Permissions

| Action | Who |
|---|---|
| Book, reconcile, link and simulator controls (`courier.book`) | super admin, admin, order manager |
| Check status | anyone with `orders.edit` |
| View the panel | anyone with `orders.view` |
| Courier money: view, record, reconcile, import (`courier.finance`) | super admin, admin |
| Any courier action | product managers: none |

## Credentials and switches (server environment only; never in React, the repo, logs or responses)

| Variable | Meaning |
|---|---|
| `STEADFAST_MODE` | `off` (default) / `mock` (simulator; refused with `aayna_prod`) / `live` |
| `STEADFAST_API_KEY`, `STEADFAST_SECRET_KEY` | Sensitive. Use **new** keys. Keys pasted into any chat must be revoked first |
| `STEADFAST_BASE_URL` | optional; must be https; defaults to the guide's URL |
| `STEADFAST_REAL_BOOKINGS` | `true` allows real consignments, and only on `aayna_prod`. Founder approval |
| `CRON_SECRET` | Sensitive, Production: any long random string; enables the daily tracking run |
| `STEADFAST_PAYMENTS_SCHEMA_VERIFIED` | `true` only after a real `/payments/{id}` answer has been checked against the importer's fields |

The preview uses `STEADFAST_MODE=mock`. Production has none of these until approved.

## Before the first real parcel (founder)

1. Revoke any Steadfast key that was ever pasted into a chat. Create a named key for AAYNA and add
   it to Vercel **Production** as Sensitive variables.
2. Ask Steadfast for:
   - the `create_order` and status response JSON;
   - the answers for "not found" and for a duplicate invoice;
   - the allowed invoice characters;
   - whether a test or sandbox account exists;
   - COD, partial-delivery and settlement rules;
   - your contracted fees.
3. With `STEADFAST_MODE=live` and real bookings still off, check the status of one existing
   parcel. This is read-only and confirms the keys and parsing.
4. Approve `STEADFAST_REAL_BOOKINGS=true`, then book one real low-value order. Check it in the
   portal and reconcile.

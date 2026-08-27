# AAYNA Production Data Migration Plan

`aayna_dev` must not be cloned wholesale into production — it's a working
development database with real dev history mixed into it. This document
defines the allowlist for what moves and what doesn't. **Not executed in
this milestone** — plan only, per L5 instructions.

## Current `aayna_dev` composition (verified this milestone, Gate 0)

| Collection | Count | Composition |
|---|---|---|
| products | 18 | 6 active (launch) + 4 out_of_stock (real, held-back non-launch-category catalogue) + 8 inactive (confirmed test data) |
| categories | 10 | 6 active (3 launch + 3 real non-launch-category) + 4 inactive (confirmed test data) |
| orders | 51 | Historical dev/QA orders, including `ORD-1052` (this milestone's controlled QA order) |
| customers | 2 (now 3, after `ORD-1052`'s synthetic QA customer) | Dev/QA-only customer records |
| settings | 20 | Founder-approved launch settings (delivery, COD, payment gating — `LAUNCH_SETTINGS_BASELINE.md`) |

## What SHOULD move to production

- **Legitimate categories** — the 6 active, non-test categories (Earrings,
  Necklaces, Rings, Bracelets, Hair Accessories, Gift Sets). Launch
  discovery scope (which 3 are promoted) is a frontend/sitemap
  presentation decision (`LAUNCH_CATALOGUE_BASELINE.md`, L2.2/L4), not a
  reason to exclude the other 3 from the database — they're real
  catalogue, just not launch-promoted yet.
- **Legitimate products** — the 10 non-test products (6 in-stock launch +
  4 real out-of-stock/non-launch-category held catalogue). Same
  reasoning: real catalogue, presentation-gated, not data-gated.
- **Approved settings** — the 20 `website_settings` records as they stand
  after L3.1 (delivery charges, COD enabled, bKash/Nagad disabled,
  Return/Exchange policy text). Placeholder values (WhatsApp number,
  support email) should be reviewed once more at actual migration time in
  case they've since been resolved — do not migrate them silently
  assuming they're still placeholders.
- **Safe business content** — static policy page content
  (`frontend/src/data/staticPages.js` — this is frontend code, not DB
  data, so it ships with the frontend build regardless; no migration
  action needed for it specifically, listed here for completeness).

## What must NOT move to production

- **All 51 dev orders**, including `ORD-1052` — none are real customer
  transactions. Real production starts at order `#1` (or whatever the
  order-numbering sequence naturally continues to — confirm
  `next_order_number()`'s counter document does not carry over from dev).
- **All dev/QA customer records** — none are real people.
- **The 8 confirmed test products** (`TEST-HIST-*`/`TEST-IMP-*` SKUs) —
  already deactivated, stay deactivated, do not migrate at all (not even
  inactive).
- **The 4 test categories** (`TEST_Cat_*`) — do not migrate at all.
- **`inventory_logs` / `notification_logs`** tied to dev/test order
  activity — dev-only audit trail, not meaningful in a fresh production
  database.
- **Internal-only product fields** — `cost_price` and any other field on
  the repo's own internal-field blocklist (`CLAUDE.md`) may legitimately
  exist in the production database (Admin needs them for margin
  tracking), but must never be exported into anything customer-facing or
  public. This plan is about what enters the production **database**, not
  what's public — the existing public-field allowlist
  (`backend/server.py`'s product-serialization logic) already handles the
  public/private split at the API layer and needs no change for this
  migration.

## Method (when actually executed, not now)

1. Export categories/products via a targeted, allowlisted query against
   `aayna_dev` — filter to `status != "inactive"` AND SKU/slug not
   matching the known test patterns (`TEST-HIST-`, `TEST-IMP-`,
   `TEST_Cat_`) as a double-check even though status already excludes
   them.
2. Export the 20 settings records as-is (re-verify placeholder fields
   first, per above).
3. Import both into the fresh production database via the existing admin
   API (`POST /api/admin/products`, `POST /api/admin/categories`,
   `PUT /api/admin/settings`) rather than a raw Mongo import, so the same
   validation/business logic that would apply to a founder using Admin
   normally also applies here — no bypassing app-level rules.
4. Do not touch `orders`, `customers`, `inventory_logs`, or
   `notification_logs` in production at all — production starts these
   collections empty.
5. Verify with a read-only count check afterward (same pattern as this
   milestone's Gate 0) that production has exactly the expected
   legitimate category/product counts and zero orders/customers.

## Old `aayna_test` backup

Untouched, not part of this plan. Remains the pre-L1 migration backup
until launch has proven stable, per explicit standing instruction — no
cleanup action here or anywhere in L5.

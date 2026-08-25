# AAYNA Launch Catalogue Baseline (post-L2.1)

Result of the founder-approved controlled cleanup. `aayna_dev` is now the
clean baseline going forward. See `LAUNCH_CATALOGUE_AUDIT.md` for the
original findings and `LAUNCH_CATALOGUE_AUDIT.csv` for current per-product
status.

## Public launch assortment (6 products)

| Product | SKU | Category | Stock | Price |
|---|---|---|---|---|
| Gold Pearl Hoop Earrings | EAR-GD-0001 | Earrings | 5 | ৳399 |
| Rose Quartz Drop Earrings | EAR-RS-0002 | Earrings | 4 | ৳469 |
| Minimal Silver Stud Earrings | EAR-SV-0003 | Earrings | 8 | ৳280 |
| Layered Gold Chain Necklace | NEC-GD-0001 | Necklaces | 4 | ৳599 |
| Heart Pendant Necklace | NEC-GD-0002 | Necklaces | 5 | ৳429 |
| Adjustable Rose Stone Ring | RNG-RS-0001 | Rings | 6 | ৳319 |

Category `product_count` (the figure Home/Header/nav actually use), verified
live post-cleanup: **Earrings 3, Necklaces 2, Rings 1 — total 6.** Matches
the founder-approved baseline exactly.

## Preserved, not launch-facing (unchanged, real)

| Product | SKU | Category | Stock | Note |
|---|---|---|---|---|
| Gold Stack Ring Set | RNG-GD-0002 | Rings | 0 | Real, out of stock. Still shown in `/category/rings`'s full listing with the existing "Out of Stock" badge (pre-existing D2 behavior, not changed here) — does not count toward the 6-product `product_count` baseline. |
| Pearl Charm Bracelet | BRC-PL-0001 | Bracelets | 0 | Preserved, outside D1/D2 launch scope, untouched. |
| Blush Satin Scrunchie Set | HAR-PN-0001 | Hair Accessories | 0 | Preserved, outside D1/D2 launch scope, untouched. |
| Gold Butterfly Hair Clip | HAR-GD-0002 | Hair Accessories | 0 | Preserved, outside D1/D2 launch scope, untouched. |

Categories Bracelets, Hair Accessories, and Gift Sets remain `active` and
untouched — not deleted, not recategorized, not restocked.

## Test pollution — resolved

All 8 confirmed test products (§15 of `LAUNCH_CATALOGUE_AUDIT.md`) were
processed through the existing, unmodified `DELETE /api/admin/products/{id}`
endpoint. Every one came back `deactivated: true, deleted: false` — the
endpoint's own order-history check found all 8 referenced by historical
orders and correctly refused to hard-delete them.

| Product | SKU | Outcome |
|---|---|---|
| TEST_HistProduct | TEST-HIST-4003DF | Deactivated |
| TEST Imported | TEST-IMP-B3ED7 | Deactivated |
| TEST_HistProduct | TEST-HIST-D80B93 | Deactivated |
| TEST Imported | TEST-IMP-83F3C | Deactivated |
| TEST_HistProduct | TEST-HIST-644744 | Deactivated |
| TEST Imported | TEST-IMP-865C3 | Deactivated |
| TEST_HistProduct | TEST-HIST-DF45F0 | Deactivated |
| **TEST Imported** | **TEST-IMP-CC4C5** | **Deactivated** (this is the originally-flagged record, id `f29c3c31-f66f-44fd-b3d5-019abd2f569a`) |

**Deleted: 0. Deactivated: 8.** (Deletion would have required zero order
references; all 8 had some.)

The 4 test categories (`TEST_Cat_87151_upd`, `TEST_Cat_7dd8e_upd`,
`TEST_Cat_bc73d_upd`, `TEST_Cat_35aae_upd`) are unchanged — no admin
`DELETE /categories/{id}` endpoint exists in this codebase, so there is no
existing, safe business-logic path to remove them further than they already
are. All 4 are already `status: inactive`, already zero products, already
excluded from `GET /api/categories` (which filters `status: "active"`).

## Bug found and fixed during verification

`GET /api/products/{slug}` had no `status` filter on its primary
`find_one` lookup — every other public product query in the codebase
(`list_products`, this same endpoint's own related-products query, category
counts) filters to `{"active", "out_of_stock"}`. This meant a deactivated
product's direct PDP route stayed reachable by slug regardless of status.
Confirmed live before the fix: `GET /api/products/test-imported-e4c6`
returned 200 even after deactivation. Fixed in `backend/server.py` to use
the same filter already applied everywhere else; confirmed after the fix
that all 8 deactivated products now 404 on their direct PDP route, and a
real product (`gold-pearl-hoop-earrings`) still returns 200 unaffected.

This is a backend query-filter fix, not a storefront design change — no
frontend file was touched.

## Public exposure — verified zero across every surface

| Surface | Before cleanup | After cleanup |
|---|---|---|
| `GET /api/products` | 11 items (1 test) | 10 items (0 test) |
| `GET /api/products?category=earrings` | 4 items (1 test) | 3 items (0 test) |
| Direct PDP (`GET /api/products/{slug}`) for all 8 test slugs | 200 for the exposed one | **404 for all 8** |
| `GET /api/sitemap.xml` | `test-imported-e4c6` present | **0 test matches** |
| `/shop`, `/category/earrings`, homepage/The Edit discovery | inherits from `/api/products` | clean, same data source |

## Order history integrity

- Order count: **51 before, 51 after.**
- Integrity check: SHA-256 hash of every order's `order_number` + full
  `items` array + `total_amount`, all 51 orders, computed before and after
  cleanup — **identical.** No order, no line item, no total was altered.
- The 20 orders that reference test-product IDs (including `ORD-1001`)
  still reference those same product IDs — deactivation preserves the
  product record and its id, so historical order line items remain valid
  and unchanged.

## Database counts

| Collection | Before | After |
|---|---|---|
| products | 18 | 18 (unchanged count — deactivation, not deletion) |
| categories | 10 | 10 (unchanged — no delete path exists) |
| orders | 51 | 51 |
| website_settings | 20 | 20 |
| customers | 2 | 2 |

## What did not change

Product prices, descriptions, images, material/claim text, stock quantities
(other than the 8 test products' `status` field), payment settings,
delivery settings, contact settings, and every D1–D6 storefront file are
untouched. The only code change is the one-endpoint query-filter fix above.

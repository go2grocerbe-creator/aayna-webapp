# AAYNA — Cost-based selling prices

Date: 2026-10-18 · Branch `chore/production-consolidation-20261015`

**Rule (founder):** `selling_price = (cost + extra) × multiplier`, **rounded up to the next ৳10** (2026-10-18; prices already on a ৳10 step are unchanged). Everything is in BDT. The rounding step is not confidential and lives in code (`ROUND_UP_TO_BDT = 10`).

**This repository is public**, so the two rule values are **confidential**. With a public price, they would reveal every purchase cost and the margin.
- They live only in `backend/.env` on the machine that runs the import or repricing (git-ignored), as `AAYNA_PRICE_EXTRA_BDT` and `AAYNA_PRICE_MULTIPLIER`.
- The code has no default for either. Tests use fake values.
- This document lists only public selling prices. Costs, profit and margin per SKU are kept out of the repository.

## 1. Audit

**Where the cost comes from.**
- No database contains the 10 real products. The databases that do exist are synthetic or demo only:
  - `aayna_release_test`
  - the local test database
  - the demo seed products
- So the authoritative cost is the "Unit cost (BDT)" column in `AAYNA_Product_Inventory.xlsx`.
- The importer stores that column as the admin-only `cost_price`.

**Currency.** BDT is entered directly. The RMB column is derived from it, so no conversion is applied.

**Landed cost.**
- The sheet records purchase cost only, with no shipping, customs or fee column.
- The figures cannot already contain the fixed extra amount.
- Treated as purchase cost **excluding** the extra amount. Founder to confirm.

**Unit.** The extra amount is added **once per sellable unit; for earrings, once per pair** (founder-confirmed 2026-10-18).

**Product records.**

| Records | Treatment |
|---|---|
| 10 real SKUs (spreadsheet) | Eligible. |
| Rejected row `REJ-EAR-SHL-001` | Skipped (not imported). |
| Demo seed products (test databases only) | Skipped. They do not come from the inventory spreadsheet. |

## 2. Resulting selling prices (public)

| SKU | Product | Selling price |
|---|---|---|
| AYN-NKL-LUN-GLD | Aayna Luna Statement Locket | ৳1,350 |
| AYN-NKL-AUR-GLD | Aayna Aura Statement Locket | ৳1,350 |
| AYN-CUF-CRS-GLD | Aayna Golden Crossline Cuff | ৳1,050 |
| AYN-CUF-STN-SLV | Aayna Crystal Stone Cuff | ৳990 |
| AYN-EAR-CHK-GLD | Aayna Bold Chunky Earrings (pair) | ৳870 |
| AYN-EAR-FLR-GLD | Aayna Floral Bloom Earrings - Golden (pair) | ৳1,410 |
| AYN-EAR-FLR-SLV | Aayna Floral Bloom Earrings - Silver (pair) | ৳1,410 |
| AYN-BRC-FLR-GLD | Aayna Floral Charm Bracelet - Golden | ৳1,310 (rounded up from ৳1,302) |
| AYN-BRC-FLR-SLV | Aayna Floral Charm Bracelet - Silver | ৳1,310 (rounded up from ৳1,302) |
| AYN-RNG-CLS-GLD | Aayna Classic Statement Ring | ৳1,290 |

**Status:**
- Verified in the local **test** environment only.
- **Not applied to any real database**, because none exists yet (`LAUNCH_CATALOGUE_READINESS.md` §2).
- Only the two Floral Charm Bracelets needed rounding; the other eight already fall on a ৳10 step.

## 3. What was built

| File | Change |
|---|---|
| `backend/pricing.py` (new) | Implements the rule as a pure function, with parameters read from the environment by `rule_from_env()`. Missing, invalid or non-positive costs are rejected and never guessed. A multiplier of 1 or less is refused. The result is rounded up to the next ৳10 (decimal arithmetic, so float noise never bumps a whole price). The unrounded price is kept in the admin-only breakdown. |
| `scripts/import_inventory.py` | New `manifest --cost-price-rule`. It prices rows from "Unit cost (BDT)". It is never applied on top of a selling price already in the sheet (that row is blocked), and it cannot be combined with `--temp-price`. The breakdown is stored in the admin-only `pricing`. |
| `scripts/reprice_from_cost.py` (new) | Re-derives the price of existing real-inventory products from `cost_price`. Behaviour is listed below the table. |
| `frontend/src/context/CartContext.jsx`, `pages/Cart.jsx`, `pages/Checkout.jsx` | Fixes a bug: the cart is saved in the browser, so after a price change a returning customer saw the old price while the server charged the new one. Cart and checkout now take the server's current price from `/cart/validate`. |
| `backend/tests_import/test_pricing.py` (new) | Offline tests, all with fake costs and fake rule values. |
| `scripts/verify/pricing_storefront.js` (new) | Storefront, cart, checkout and admin consistency check (production build, test backend). |
| `frontend/src/components/TheEdit.jsx`, `pages/Shop.jsx` | `/shop` "All" now lists every active, in-stock product in every category (cuffs and bracelets were hidden before). The Earrings / Necklaces / Rings chips are unchanged. |

**How `scripts/reprice_from_cost.py` behaves:**
- **Dry run by default.** `--apply` requires `--target-db` to equal `DB_NAME`, and it refuses test databases.
- **Which products it touches.** Only products created by the importer (`source.type = inventory_xlsx`) with status draft, active or out_of_stock.
- **What it keeps.** `cost_price` is never written. The old price is kept in `previous_selling_price` and in an append-only `price_history`.
- **Idempotent.** A second run with the same rule reports "unchanged". A changed rule (including the new rounding) is applied once and recorded.
- **What it flags without changing:**
  - a manual Admin price set after the last rule run (`--override-manual` resets it)
  - an existing discount at or above the new price
- **Concurrency.** Each write only succeeds if price and cost are unchanged since it was planned.

**Unchanged by design:**
- Orders are priced on the server from the database (`effective_price`). Each order line stores its `unit_price` snapshot, so historical orders never change.
- The public API keeps its field whitelist (`PUBLIC_PRODUCT_FIELDS`). It does not include `cost_price`, `pricing`, `price_history` or `previous_selling_price`.
- No prices are hard-coded in React.

## 4. Verification (local test environment, FerretDB `aayna_pytest`, production build)

**Setup.** The 10 SKUs were imported as existing products at an old price of ৳999 and set active. A historical order was placed first (ORD-1001, total ৳3,077). Then the rule was applied, with the founder's values set only in the test process environment.

| Check | Result |
|---|---|
| Formula, independently computed for all 10 | match |
| Apply: 10 updated, 10 demo skipped | ✓, `cost_price` unchanged, `previous_selling_price` = 999, 1 history entry each |
| Re-run | 10 "unchanged", 0 writes |
| Importer `--cost-price-rule` gives the same 10 prices | ✓ |
| Historical order ORD-1001 | ৳3,077 before and after, line prices ৳999 kept |
| Storefront (desktop 1280 and mobile 390): product page price = database price for all 10 | 20/20 |
| Listing cards (shop and category pages) show the new price, never the old | ✓ both viewports |
| `/shop` "All" lists all 10, cuffs and bracelets included; chips unchanged, Earrings chip shows only earrings | ✓ both viewports |
| Cart and checkout with all 10 products (saved at the old price) | every line, subtotal ৳12,340 and Dhaka total ৳12,420 = server, both viewports |
| Cart saved at the old price: shows the new price, subtotal and saved cart updated | ✓ both viewports |
| Checkout total = server total; order placed; confirmation and stored total match | ✓ |
| BDT formatting `৳1,350` (same `formatBDT` everywhere) | ✓ |
| Public API responses contain no cost, pricing or history fields | ✓ (intercepted on every page) |
| Admin product list shows the new price for all 10 | ✓ |
| `pricing_storefront.js` | **48/48** (after rounding and the shop fix) |
| Offline tests (`backend/tests_import`) | **160 passed** |
| Regression on the new build | storefront routes 60/60, home/footer 47/47, admin UI 11/11, backend/admin 61/61, inventory rules 28/28 |
| Backend pytest on the FerretDB stand-in | 120 passed. The same 3 known FerretDB-only failures as every earlier run (aggregations unsupported); these passed on Atlas. |
| Release checks on FerretDB | 8 passed, 9 not verified, 1 concurrency failure. The concurrency checks are non-deterministic on FerretDB, which lacks a unique index; earlier FerretDB runs ranged from 0 to 3 failures and Atlas passed. Order code is untouched by this change. |

## 5. Production readiness

**Not applied to production.** There is no real catalogue database yet.

**When one exists:**
1. Put `AAYNA_PRICE_EXTRA_BDT` and `AAYNA_PRICE_MULTIPLIER` in `backend/.env` on the machine that runs the import.
2. Run `import_inventory.py manifest --cost-price-rule`.
3. Run `import_inventory.py import --target-db <DB_NAME> --static-images` (draft).
4. Review in Admin, then publish.
5. Later cost or rule changes: `reprice_from_cost.py` (dry run, then `--apply --target-db <DB_NAME>`).

**Open founder point:**
- Do the sheet costs exclude shipping and fees (purchase cost only, not landed cost)? Prices assume they do.

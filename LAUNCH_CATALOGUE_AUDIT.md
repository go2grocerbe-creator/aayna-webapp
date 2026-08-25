# AAYNA Launch Catalogue Audit (L2)

Read-only audit of `aayna_dev`. No data was deleted, deactivated, published,
unpublished, renamed, reprioritized, or restocked in this pass. See
`LAUNCH_CATALOGUE_AUDIT.csv` for the same findings in one-row-per-product form.

## 1. Executive Summary

`aayna_dev` holds 18 product records. **10 are real** (founder catalogue,
verified via consistent professional photography, complete pricing/
description data, and coherent SKU numbering). **8 are confirmed synthetic
test pollution** — 4× `TEST_HistProduct`, 4× `TEST Imported` — all created by
`backend/tests/test_aayna_admin.py`'s history/CSV-import tests before L1's
database isolation fix landed.

Of the 10 real products, **6 are in-stock and inside the current storefront's
Earrings/Necklaces/Rings scope** — these are the proposed launch assortment.
4 more real products (1 ring, 1 bracelet, 2 hair accessories) are genuine
founder catalogue but currently out of stock.

**One launch blocker was found and is the single most important finding of
this audit**: one of the 8 test records — `TEST Imported` / SKU
`TEST-IMP-CC4C5` / slug `test-imported-e4c6` — has `status: "out_of_stock"`
instead of `"inactive"` like its 7 siblings, and the public API includes
`out_of_stock` products (only `"inactive"` is excluded). This was verified
live: it appears today in `/api/products`, in the `?category=earrings`
listing, its PDP resolves with HTTP 200, and **it is present in
`sitemap.xml`** — meaning it is indexable. The other 7 test records are
correctly excluded from every public surface. Full evidence in §20.

No claim-audit issues, price issues, stock anomalies, duplicate SKUs/slugs,
or broken image URLs were found in the real catalogue. No Higgsfield asset
matched an existing product with usable confidence — see §7.

## 2. Product Inventory

Full field-by-field data is in `LAUNCH_CATALOGUE_AUDIT.csv`. Supplier/cost
fields (`cost_price`, `low_stock_alert`) exist on every record internally but
are never returned by the public API (confirmed in §19/§13 of L1) and are
omitted here except where needed for integrity checks below.

**Real products (10):**

| Product | SKU | Category | Stock | Price | Discount | Images | Material | Short/Full desc |
|---|---|---|---|---|---|---|---|---|
| Gold Pearl Hoop Earrings | EAR-GD-0001 | Earrings | 5 | ৳450 | ৳399 | 1 | Alloy w/ artificial pearl | Y/Y |
| Rose Quartz Drop Earrings | EAR-RS-0002 | Earrings | 4 | ৳520 | ৳469 | 1 | Alloy w/ rose quartz-style stone | Y/Y |
| Minimal Silver Stud Earrings | EAR-SV-0003 | Earrings | 8 | ৳280 | — | 1 | Stainless-style alloy | Y/Y |
| Layered Gold Chain Necklace | NEC-GD-0001 | Necklaces | 4 | ৳650 | ৳599 | 1 | Alloy chain | Y/Y |
| Heart Pendant Necklace | NEC-GD-0002 | Necklaces | 5 | ৳480 | ৳429 | 1 | Alloy pendant and chain | Y/Y |
| Adjustable Rose Stone Ring | RNG-RS-0001 | Rings | 6 | ৳350 | ৳319 | 1 | Alloy w/ rose stone | Y/Y |
| Gold Stack Ring Set | RNG-GD-0002 | Rings | **0** | ৳420 | ৳379 | 1 | Alloy ring set | Y/Y |
| Pearl Charm Bracelet | BRC-PL-0001 | Bracelets | **0** | ৳390 | ৳349 | 1 | Alloy chain w/ pearl charm | Y/Y |
| Blush Satin Scrunchie Set | HAR-PN-0001 | Hair Accessories | **0** | ৳250 | — | 1 | Satin-style fabric | Y/Y |
| Gold Butterfly Hair Clip | HAR-GD-0002 | Hair Accessories | **0** | ৳320 | ৳299 | 1 | Metal alloy | Y/Y |

All 10 have: `weight` empty (optional field, not required), `color`/`size`
populated, `is_featured`/`is_best_seller`/`is_new_arrival` flags set
meaningfully (not all-false placeholders), `created_at` = 2026-08-21 (single
seed batch).

**Test records (8)** — see §10/§20, full detail in the CSV.

## 3. Category Inventory

| Category | Slug | Status | Products (real) | In stock | Out of stock | Suspected test-only | Current D1/D2 scope |
|---|---|---|---|---|---|---|---|
| Earrings | earrings | active | 3 | 3 | 0 | No (but hosts all 8 test products as their category_slug) | Yes |
| Necklaces | necklaces | active | 2 | 2 | 0 | No | Yes |
| Rings | rings | active | 2 | 1 | 1 | No | Yes |
| Bracelets | bracelets | active | 1 | 0 | 1 | No | No (legitimate future catalogue) |
| Hair Accessories | hair-accessories | active | 2 | 0 | 2 | No | No (legitimate future catalogue) |
| Gift Sets | gift-sets | active | 0 | 0 | 0 | No (empty, not test-created) | No |
| TEST_Cat_87151_upd | test-cat-87151 | **inactive** | 0 | 0 | 0 | **Yes** | N/A |
| TEST_Cat_7dd8e_upd | test-cat-7dd8e | **inactive** | 0 | 0 | 0 | **Yes** | N/A |
| TEST_Cat_bc73d_upd | test-cat-bc73d | **inactive** | 0 | 0 | 0 | **Yes** | N/A |
| TEST_Cat_35aae_upd | test-cat-35aae | **inactive** | 0 | 0 | 0 | **Yes** | N/A |

All 4 test categories are `status: "inactive"` and `GET /api/categories`
filters to `status: "active"` only (verified in server.py) — they do not
appear publicly today. Bracelets, Hair Accessories, and Gift Sets are real,
active categories; none should be deleted. Whether they stay hidden from
launch navigation (they already are, since Home/TheEdit only render
Earrings/Necklaces/Rings by design) or get product_count-based hiding is a
presentation decision already made in D1/D2 — no category-level change is
needed for launch; this is a founder catalogue-planning question, not a bug.

## 4. Proposed Launch Assortment

Do not treat this as a decision — it is what the data supports today.

**Earrings (3, all in stock):** Gold Pearl Hoop Earrings, Rose Quartz Drop
Earrings, Minimal Silver Stud Earrings.
**Necklaces (2, all in stock):** Layered Gold Chain Necklace, Heart Pendant
Necklace.
**Rings (1 in stock + 1 out of stock):** Adjustable Rose Stone Ring
(launchable now); Gold Stack Ring Set (real, complete data, currently 0
stock — restock or exclude).
**Other (out of scope for D1/D2, real but 0 stock):** Pearl Charm Bracelet,
Blush Satin Scrunchie Set, Gold Butterfly Hair Clip.

| Product | Category | Stock | Price | Image Quality | Data Complete | Launch Ready? | Blocker |
|---|---|---|---|---|---|---|---|
| Gold Pearl Hoop Earrings | Earrings | 5 | ৳399 | READY | Yes | **YES** | — |
| Rose Quartz Drop Earrings | Earrings | 4 | ৳469 | READY | Yes | **YES** | — |
| Minimal Silver Stud Earrings | Earrings | 8 | ৳280 | READY | Yes | **YES** | — |
| Layered Gold Chain Necklace | Necklaces | 4 | ৳599 | READY | Yes | **YES** | — |
| Heart Pendant Necklace | Necklaces | 5 | ৳429 | READY | Yes | **YES** | — |
| Adjustable Rose Stone Ring | Rings | 6 | ৳319 | READY | Yes | **YES** | — |
| Gold Stack Ring Set | Rings | 0 | ৳379 | READY | Yes | NO | stock = 0 |
| Pearl Charm Bracelet | Bracelets | 0 | ৳349 | READY | Yes | NO | stock = 0, outside current scope |
| Blush Satin Scrunchie Set | Hair Accessories | 0 | ৳250 | READY | Yes | NO | stock = 0, outside current scope |
| Gold Butterfly Hair Clip | Hair Accessories | 0 | ৳299 | READY | Yes | NO | stock = 0, outside current scope |

Six products are launchable today with zero data or image issues. No
speculative blockers used (no "needs certification" language applied to
anything — no product makes a claim that would require one).

## 5. Blocked Products

Only stock=0 blocks the 4 real-but-unavailable products above. Separately,
**all 8 test products are launch blockers by definition** (§10) — one of
them is live-exposed today (§7, §11).

## 6. Image Audit

All 10 real products: **READY**. Every image URL returns HTTP 200
(`static.prod-images.emergentagent.com`), matches its product (verified
visually across this session's repeated storefront QA — Gold Pearl Hoop
Earrings, Heart Pendant Necklace, Adjustable Rose Stone Ring, Gold Stack
Ring Set, and Gold Butterfly Hair Clip were all directly seen rendered on
real pages during D1–D6 QA), studio-quality with clean neutral backgrounds,
no supplier pricing/watermarks/screenshots visible, no cluttered demo
photography. Every real product has exactly 1 image, so every PDP uses D3's
detail-crop fallback for the "second" image — already verified acceptable
in D3 QA and consistent across the whole catalogue, not a special case for
any one product.

Test products: 7 of 8 have `images: []` (BROKEN/no image at all); the
publicly-exposed one (`test-imported-e4c6`) also has `images: []` — so if a
customer reached its PDP today they'd see the shared `ProductImage`
placeholder gem icon, not a broken-image icon, but also nothing resembling
a real product photo.

## 7. Higgsfield Asset Inventory & Mapping

**23 files inspected** in `AAYNA - Product Sourcing Photos/AAYNA - Higgsfield
Assets`, all named generically (`AAYNA Product (1).png` … `(23).png`, no
descriptive filenames). 20 are 896×1200 (RGB/RGBA), 3 are 1744×2336
(higher-res lifestyle portraits). Every file was viewed directly.

**Distinct pieces identified** (several files are repeat angles/crops of the
same physical piece):
1. Gold sculptural fan-shaped stud earrings (#1, #2)
2. White pearl + crystal starburst drop earring (#3)
3. Gold crystal-flower cluster bracelet (#4)
4. Silver crystal-flower cluster bracelet (#5, #20)
5. Gold crystal-starburst + grey pearl drop earring (#6)
6. Silver crystal-starburst + grey pearl drop earring (#7)
7. Gold oval-solitaire ring (#8, #12)
8. Chunky gold curb-chain bracelet, worn (#9)
9. Gold circular crystal-lattice pendant necklace, hexagon pattern (#10, #11)
10. Chunky gold curb-link hinged bangle (#13)
11. Gold + silver pavé bangle pair (#14, #15)
12. Gold fan/shell-shaped pendant necklace (#16)
13. Gold hexagon-lattice pavé pendant, wide bezel (#17)
14. Gold ribbed circular pendant/wreath necklace, worn (#18)
15. Gold + crystal teardrop stud earring, lifestyle (#19)
16. Textured/hammered gold "pebble" stud earring, lifestyle (#21, #22, #23 — same physical piece)

**Mapping confidence against the 10 real products: NONE for all 23 files.**
Every Higgsfield piece is a visually distinct design from every current
catalogue product — different silhouettes (starburst/pavé/solitaire/curb-
chain vs. the catalogue's plain hoops, simple pendants, thin adjustable
bands) and a noticeably more elaborate/premium styling tier than the current
minimal catalogue. None share the same stone, metal texture, or shape as any
of the 10 real products closely enough to justify even a MEDIUM-confidence
flag, per the instruction not to map on category alone (e.g. "both are
earrings"). This library reads as a separate, aspirational or future-
collection photo set, not exact-SKU photography for what's live today.

## 8. High-Confidence Image Mapping Table

| Higgsfield File | → Product/SKU | Confidence | Reason |
|---|---|---|---|
| — | — | — | No file reached HIGH or MEDIUM confidence against any current SKU; no mappings recommended. |

## 9. D1/D2/D3 Image Coverage Check

**D1 Homepage:** Reflection category-hover previews and Your Reflection both
resolve to real, in-stock products in Earrings/Necklaces/Rings — all have
READY images (already the in-stock-first fix from D4.1 QA). No weak product.
**D2 The Edit:** grid renders only real images, all resolving; the one
publicly-exposed test record (§7 above) would render with the gem-icon
placeholder if it appears in a listing — not broken, but visually
inconsistent with real product photography and priced at an oddly round
৳750 with no discount, which reads as out of place next to real inventory.
**D3 The Object:** PDP hero images all usable; single-image detail-crop
approach is uniform across all 10 real products (every one has exactly 1
image), already verified acceptable.

No real product visually weakens the storefront. The one thing that does is
the exposed test record, covered in full below.

## 10. Data Completeness

All 10 real products have every required commerce field (`product_name`,
`slug`, `sku`, `category`, `selling_price`, `stock_quantity`, ≥1 image,
`status`) and every useful PDP field except `weight` (optional, blank on
all 10 — not a gap). Nothing was fabricated or filled in during this audit.

The 8 test products are missing `short_description`, `full_description`,
`material`, `color`, `size`, and (for the 7 `inactive` ones) `images` —
consistent with being throwaway test fixtures, not incomplete real listings.

## 11. SKU / Slug Integrity

No duplicate SKUs, no duplicate slugs, no blank SKUs, no blank slugs across
all 18 records (real + test). No malformed slugs. No product/category
mismatch on any real product. All 8 test SKUs are self-identifying
(`TEST-HIST-*`, `TEST-IMP-*`) — easy to positively identify, matching the
existing confirmed-pollution pattern exactly.

## 12. Price Integrity

All 10 real products: `selling_price > 0`, and where `discount_price` is
set, it is always less than `selling_price` (confirmed against the actual
schema semantics in `backend/server.py`'s `effective_price()` — discount_price
is the current/effective price when present, selling_price is the
compare-at). No violations found. Test products all have `discount_price:
null`, no compare-at inconsistency there either.

## 13. Stock Integrity

No negative stock anywhere. In stock: 6 real products (Earrings ×3,
Necklaces ×2, Adjustable Rose Stone Ring). Zero stock: 4 real products (Gold
Stack Ring Set, Pearl Charm Bracelet, Blush Satin Scrunchie Set, Gold
Butterfly Hair Clip) + 5 of 8 test products (the rest hold placeholder stock
values of 4, which is a test artifact, not a real inventory signal).

## 14. Claim Audit

Searched every real product's `short_description`, `full_description`,
`material`, and `tags` for: `316L`, `PVD`, `18K`, `waterproof`,
`hypoallergenic`, `nickel free`, `tarnish`, `sweat resistant`, `warranty`,
`long lasting`. **Zero matches.** The current real catalogue makes no
material-purity, durability, or care claims at all — material fields
describe items plainly ("Alloy with artificial pearl", "Stainless
steel-style alloy", etc.), which is itself already the safe, defensible
phrasing. Nothing to classify as VERIFIED/NEEDS EVIDENCE/UNKNOWN because
nothing claims anything.

## 15. Test Pollution

**8 confirmed synthetic records**, all traced to specific test files:

| Product | SKU | Slug | Status | Publicly exposed |
|---|---|---|---|---|
| TEST_HistProduct | TEST-HIST-4003DF | test-histproduct | inactive | No |
| TEST Imported | TEST-IMP-B3ED7 | test-imported | inactive | No |
| TEST_HistProduct | TEST-HIST-D80B93 | test-histproduct-7da4 | inactive | No |
| TEST Imported | TEST-IMP-83F3C | test-imported-86ce | inactive | No |
| TEST_HistProduct | TEST-HIST-644744 | test-histproduct-40e0 | inactive | No |
| TEST Imported | TEST-IMP-865C3 | test-imported-44ba | inactive | No |
| TEST_HistProduct | TEST-HIST-DF45F0 | test-histproduct-65f5 | inactive | No |
| **TEST Imported** | **TEST-IMP-CC4C5** | **test-imported-e4c6** | **out_of_stock** | **YES — see §7** |

**This is the originally-flagged record** (`id:
f29c3c31-f66f-44fd-b3d5-019abd2f569a`), confirmed still present, not
deleted, per instructions.

**Live public exposure, verified directly against the running dev
backend:**
- `GET /api/products` → **included** (11 items returned instead of 10; the
  test record is the 11th)
- `GET /api/products?category=earrings` → **included**
- `GET /api/products/test-imported-e4c6` → **HTTP 200**, PDP resolves
- `GET /api/sitemap.xml` → **`<loc>.../product/test-imported-e4c6</loc>`
  present** — indexable by search engines if this reached production as-is
- Search: not separately tested, but since it's returned by the base
  products query, it would also surface in any search that matches its
  `product_name` field

**Why:** the public `/api/products` query filters
`status: {"$in": ["active", "out_of_stock"]}` — it excludes `"inactive"` but
not `"out_of_stock"`. This one test record's status differs from its 7
otherwise-identical siblings (all `"inactive"`), which is why it alone
leaks while the other 7 correctly do not. This is a data-state difference
on one record, not an application filtering bug — the other 7 prove the
filtering logic itself works correctly. **This is the launch blocker.**

**Historical-order references:** 20 of the 51 orders in `aayna_dev`
reference one or more of the 8 test product IDs (including `ORD-1001`).
Any future deletion of these products must use the existing
`DELETE /api/admin/products/{id}` behavior, which already checks for order
history and deactivates instead of hard-deleting when references exist
(confirmed in `admin_routes.py`, unmodified) — hard-deleting would break
those 20 orders' item references.

## 16. Recommended Cleanup Actions (not performed)

1. Deactivate (not delete) all 8 test products via the existing admin
   `DELETE /api/admin/products/{id}` endpoint, once the founder approves —
   it will automatically deactivate rather than hard-delete given the order
   history found above.
2. Delete the 4 `TEST_Cat_*` categories (all `inactive`, zero products
   attached, no order references possible since categories aren't
   order-referenced) — lower risk than the products.
3. Separately consider: the 20 orders that reference only test products are
   themselves test artifacts in the order history, not real customer
   orders. Not in scope for this catalogue audit; flagging for a future,
   separate order-data review.

## 17. Founder Decisions Required

Grouped, minimal:

1. **Test cleanup approval** — approve deactivating the 8 confirmed test
   products (§15) and deleting the 4 test categories (§3), now that L1 has
   proven tests can no longer reach this database. This directly closes the
   live public-exposure issue in §7/§15.
2. **Rings restock decision** — Gold Stack Ring Set is real, complete, and
   currently 0 stock. Restock for launch, or leave excluded?
3. **Bracelets / Hair Accessories launch inclusion** — Pearl Charm
   Bracelet, Blush Satin Scrunchie Set, and Gold Butterfly Hair Clip are
   real, complete, but 0 stock and outside D1/D2's current category scope.
   Restock and bring into scope, or hold for a later catalogue expansion?
4. **Higgsfield assets** — none matched an existing product with usable
   confidence (§7/§8). Are these intended as photography for a *future*
   product line, or was a different asset batch expected? No action needed
   from this audit either way, but worth confirming intent before assuming
   they'll ever map to current SKUs.

## Production data changed: NO
## Storefront design changed: NO

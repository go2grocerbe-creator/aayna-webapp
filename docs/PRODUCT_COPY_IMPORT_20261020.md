# Product copy import — 20 Oct 2026 (PREVIEW ONLY)

Source: founder handoff `AAYNA_Product_SEO_Steadfast_Claude_Handoff.zip` → `docs/content/product_copy_10_skus.json`
(status `DRAFT_NOT_PUBLISHED`, every SKU `draft_requires_founder_review`).

## Where it was applied
- **aayna_preview only**, 20 Oct 2026 ~18:15 Dhaka, through the normal admin route
  `PUT /api/admin/products/{id}` from the founder's signed-in preview admin session, so every
  change is in `product_content_history` (one entry per SKU, actor = the admin account).
- **aayna_prod: not touched.** All 10 products remain drafts with no description (verified read-only).

## SKU → fields written
| SKU | short | full | highlights | seo_title | seo_description | history |
|---|---|---|---|---|---|---|
| AYN-NKL-LUN-GLD | 72 c | 51 w | 3 | 37 c | 126 c | 1 |
| AYN-NKL-AUR-GLD | 69 c | 56 w | 3 | 37 c | 121 c | 1 |
| AYN-CUF-CRS-GLD | 60 c | 56 w | 3 | 47 c | 99 c | 1 |
| AYN-CUF-STN-GLD | 62 c | 54 w | 3 | 35 c | 99 c | 1 |
| AYN-EAR-CHK-GLD | 62 c | 51 w | 3 | 37 c | 97 c | 1 |
| AYN-EAR-FLR-GLD | 61 c | 54 w | 3 | 38 c | 90 c | 1 |
| AYN-EAR-FLR-SLV | 61 c | 47 w | 3 | 45 c | 97 c | 1 |
| AYN-BRC-FLR-GLD | 53 c | 53 w | 3 | 38 c | 98 c | 1 |
| AYN-BRC-FLR-SLV | 53 c | 49 w | 3 | 45 c | 98 c | 1 |
| AYN-RNG-CLS-GLD | 62 c | 52 w | 3 | 39 c | 90 c | 1 |

All passed `backend/product_content.py` (plain text, length caps). 10 distinct SEO titles.
**Not written:** `material`, `care_note`, `size` (left as recorded: 1" / 2.5" / 1" per earring /
0.7" diameter), `status`, price, stock, images, slug, name. Read-back confirmed none changed.

## Mapping check (catalogue = source of truth)
- SKU, colour and approximate dimension in every highlight match the catalogue `size`/`color`.
- "Sold as a pair" (earrings) matches the inventory note "2 individual earrings per pair".

## Unresolved facts / founder decisions (grouped)
1. **Product names differ.** The copy's names ("Luna Locket Necklace", "Golden Crossline Cuff Bracelet"…)
   are not the catalogue names ("Aayna Luna Statement Locket", "Aayna Golden Crossline Cuff"…). The
   page heading uses the catalogue name; the SEO title uses the copy's name. Choose one naming before
   production (rename in admin, or edit the SEO titles). Not changed here.
2. **Third highlight** "Bangladesh-inspired editorial story; not product origin" is shown to customers
   as a product detail on every SKU. Accurate, but reads like an internal note — keep, reword or drop.
3. **Material / plating / stone composition** — unknown for all 10; `material` left blank and omitted
   from structured data. "Crystal-look" is used for the Crystal Stone Cuff.
4. **Care instructions, closure, ring size/fit** — unknown; not asserted.
5. **Exact dimensions** — copy says "approximately"; confirm against the physical items.
6. **Photos** — silhouettes described ("round locket", "intersecting lines", "flower-shaped") should be
   checked against the approved product photos.
7. Copy is **English only**; no Bangla version supplied.

## Production import (later, needs separate explicit founder approval)
Same admin route on production after the founder approves the text, or the founder edits each
product in Admin → Products → Description & details.

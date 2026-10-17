# AAYNA — Phase 5C: Launch Catalogue Readiness

Date: 2026-10-17 · Branch `chore/production-consolidation-20261015` · Base commit `5089307`

**Scope.** This phase prepares the 10-product inventory for safe import. It did not import or publish anything, and it did not modify real product data in any database.

**Sources.**
- `AAYNA_Product_Inventory.xlsx`, sheet "Inventory", read through the importer's own parser (`read_inventory` / `map_row`).
- The reviewed photo map.

**Cost and supplier columns.** The sheet has cost, stock-value and notes columns. They are deliberately left out of this report. On import they map only to admin-only fields (`cost_price`, `internal_notes`), which the public API never returns. An offline test asserts this.

## 1. Catalogue audit (safe fields only)

| SKU | Product name (sheet) | Sheet category → site | Colour | Size | Unit | Qty |
|---|---|---|---|---|---|---|
| AYN-NKL-LUN-GLD | Aayna Luna Statement Locket | Necklace / Locket → Necklaces | Golden | 1" diameter | Piece | 1 |
| AYN-NKL-AUR-GLD | Aayna Aura Statement Locket | Necklace / Locket → Necklaces | Golden | 1" diameter | Piece | 1 |
| AYN-CUF-CRS-GLD | Aayna Golden Crossline Cuff | Cuff → Bracelets | Golden | 2.5" diameter | Piece | 2 |
| AYN-CUF-STN-SLV | Aayna Crystal Stone Cuff | Cuff → Bracelets | Golden | 2.5" diameter | Piece | 12 |
| AYN-EAR-CHK-GLD | Aayna Bold Chunky Earrings | Earrings → Earrings | Golden | 1" per earring | Pair | 6 |
| AYN-EAR-FLR-GLD | Aayna Floral Bloom Earrings | Earrings → Earrings | Golden | 1" per earring | Pair | 5 |
| AYN-EAR-FLR-SLV | Aayna Floral Bloom Earrings | Earrings → Earrings | Silver | 1" per earring | Pair | 5 |
| AYN-BRC-FLR-GLD | Aayna Floral Charm Bracelet | Bracelet → Bracelets | Golden | 2.5" diameter | Piece | 5 |
| AYN-BRC-FLR-SLV | Aayna Floral Charm Bracelet | Bracelet → Bracelets | Silver | 2.5" diameter | Piece | 4 |
| AYN-RNG-CLS-GLD | Aayna Classic Statement Ring | Ring → Rings | Golden | 0.7" diameter | Piece | 5 |

Totals: 10 SKUs and 46 saleable units. Earrings are counted in pairs, and the stock quantity is taken from the sheet's Qty column as written.

One row, `REJ-EAR-SHL-001` Seashell Earrings, sits in the "rejected" block. The importer excludes it.

### Findings

| Check | Result |
|---|---|
| SKUs | 10 unique. Each one has a reviewed static photo gallery; the 2–4 photos per SKU are listed in `PRODUCT_PHOTOGRAPHY_INTEGRATION.md`. |
| Names | Present on all rows. The gold and silver versions of Floral Bloom and of Floral Charm share a name, so the importer appends the sheet's colour, e.g. "Aayna Floral Bloom Earrings - Golden". |
| **Selling price** | **Missing on all 10 rows.** The importer blocks every row ("Missing selling price"), so nothing is ready to import. |
| Compare-at / discount price | Not in the sheet. This is optional. |
| Stock | Present and valid (whole numbers ≥ 0) on all rows. No numbers were invented. |
| Description | No column. Products would be created with empty short and full descriptions. Descriptions are optional for publishing but needed for a quality launch and for SEO. |
| Material | No column. It stays empty unless provided. |
| Care note, weight | Not in the sheet. |
| SEO title / description | Not in the sheet. The pages fall back to the product name. |
| Category | All 10 map to existing site categories. The two cuffs go to Bracelets (founder-confirmed). |
| **SKU/colour mismatch** | `AYN-CUF-STN-SLV` has the suffix SLV but its Colour column and photos are golden. The founder confirmed the product is golden. The SKU is unchanged until the impact audit below is approved. |
| Rejected row | Excluded by the importer. |

### `AYN-CUF-STN-SLV` rename impact

- **Database.** No references exist, because no reachable database contains the 10 SKUs.
- **Repository references:**
  - `scripts/assets/product_image_map.json`
  - `frontend/src/data/productGallery.json`, generated from the map
  - the docs
- **Photo URLs** are keyed by photo group (`crystal-stone-cuff-golden`), not by SKU, so they do not change.
- **Importer.** It is idempotent by SKU. A rename after import would create a second product unless the existing record is migrated.
- **Orders** store `sku_snapshot`, so a later rename does not alter order history but leaves the old SKU in it.

**Conclusion.** Renaming before the first import costs almost nothing: change the sheet, update one map entry and regenerate the gallery JSON. After the first import it becomes a database migration. If the founder wants a golden SKU (for example `AYN-CUF-STN-GLD`), decide before the import.

### Draft and publish requirements (code as it stands)

- **Import.** The importer creates products as `draft`, which the public API hides because it serves only `active` and `out_of_stock`.
- **Validation for import and editing.** Admin requires:
  - selling price > 0
  - a valid discount below the price, if one is set
  - stock ≥ 0
  - a valid status
- **Publishing.** The founder sets the status to `active` in Admin > Products. Photos then appear automatically from the static gallery by exact SKU.
- **Category.** The category must already exist in the database. On a fresh production database it will not, because demo seeding is disabled when `APP_ENV=production`. Create Necklaces, Earrings, Bracelets and Rings in Admin > Categories first.

## 2. Import prerequisites

### Target database: not yet decided (technical blocker)

| Candidate | Status |
|---|---|
| `aayna_release_test` (Atlas test cluster) | **Excluded.** It holds synthetic release-test data only, and the importer now refuses it. |
| `aayna_pytest`, `aayna_import_test` | Excluded: offline and local test databases. |
| Emergent `test_database` | Excluded: never modified. |
| Local `aayna_dev` | Not found on the founder PC (Phase 5A). It is not assumed to exist. |
| Production (planned name `aayna_prod`) | Not provisioned. |

**There is no authorised real catalogue database today.** Before anyone imports, the founder must choose:
- the cluster
- the database name
- who holds the credentials

### Importer changes in this phase (`scripts/import_inventory.py`)

- **Target-DB guard.**
  - `import` now requires `--target-db`, which must repeat `DB_NAME` exactly.
  - It refuses `aayna_release_test`, `aayna_pytest`, `aayna_import_test`, `test_database` and any name containing "test".
  - The guard runs before the confirmation prompt and before any write.
- **`--static-images` mode.**
  - Creates draft products with no database images and uploads nothing.
  - The storefront then shows the reviewed static gallery for the exact SKU.
  - It is needed because object storage is disabled; the old path would fail on upload.
  - A SKU without a static gallery is skipped, never created without a photo.
  - In this mode the photo-folder match is not required, but every other blocker (price, stock, category) still applies.
- **Tests.** 13 offline tests were added (mongomock, no network). They cover:
  - each refused name
  - a target mismatch
  - a missing target
  - the CLI refusing before any import call
  - gallery coverage of all 10 SKUs
  - static mode uploading nothing and leaving `images == []`
  - the photo blocker being lifted while the price blocker stays

  Import suite: **124 passed**.

## 3. Launch catalogue report

### Ready for import
- **SKU, name, category, colour, size, unit and stock** for all 10 products are clean and valid.
- **Photos** for all 10 SKUs are in the approved order (product-only first) and verified 87/87 on a production build.
- **Importer** is safe by construction:
  - drafts only
  - idempotent by SKU
  - cost and notes kept admin-only
  - test databases refused
  - static photo mode available

Overall, **0 of 10 can be imported today**: every row is blocked only by the missing selling price.

### Missing founder decisions
1. **Selling price (BDT) for each of the 10 SKUs.** Add a "Selling price (BDT)" column to the sheet. The alternative is a founder-approved `--temp-price`, which applies one price to all 10 and flags them as temporary.
2. **Compare-at prices**, if any (optional).
3. **Crystal Stone Cuff SKU.** Keep `AYN-CUF-STN-SLV`, or rename it (e.g. `AYN-CUF-STN-GLD`) **before** the first import.
4. **Product copy.** For each product: short and full description, material and care note. These are optional for publishing but recommended for launch and SEO. Nothing will be invented.
5. **Which database becomes the real catalogue,** plus approval to provision it. Provisioning may be paid and is not done here.
6. **Publish order.** Publish all 10 at once, or publish a first test SKU, check it, then the rest.

### Technical blockers
1. There is no real catalogue database (see §2). Nothing can be imported until one is provisioned and its `DB_NAME` is set.
2. Categories must exist in that database. A production database starts empty, because demo seeding is disabled; create the four categories in Admin first.
3. Object storage is disabled. Use `--static-images`; database uploads come later, with a storage provider.
4. Selling prices: see founder decision 1. The importer will not guess them.

### Safe next actions
1. Founder adds prices (and, optionally, copy and material) to the spreadsheet, and settles the cuff SKU.
2. Founder chooses and provisions the catalogue database and sets `MONGO_URL` / `DB_NAME` in `backend/.env` on the machine that runs the import.
3. Run a dry run, which touches nothing:

   ```
   python scripts/import_inventory.py manifest --xlsx "<sheet>" --photos "<photo folder>" --out import_manifest.json
   ```

   The summary must show `ready: 10`.
4. Create the four categories in Admin, then import a single SKU:

   ```
   python scripts/import_inventory.py import --manifest import_manifest.json --target-db <DB_NAME> --static-images --only AYN-RNG-CLS-GLD
   ```

   Then type `IMPORT`.
5. In Admin, check the draft (price, stock, category); it must not appear on the public site. Set it to `active` and confirm the product page shows its photos in the approved order.
6. Import the remaining 9 (the same command without `--only`), review them, and publish.

## 4. Verification in this phase

| Check | Result |
|---|---|
| Gallery after reorder (`static_product_images.js`, production build, desktop + mobile) | 87/87 |
| WebP files | 62, byte-identical to before (sha256) |
| Gallery JSON vs fresh generator output | identical |
| Offline import tests | 124 passed |
| Responsive audit (production build, 17 pages × 14 viewports) | 0 overflow, clipped headings, JS errors, small targets, unnamed controls, missing focus, broken or distorted images |
| Real or production database contacted | **No** |

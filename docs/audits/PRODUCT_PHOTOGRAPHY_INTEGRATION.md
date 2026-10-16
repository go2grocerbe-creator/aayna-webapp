# AAYNA — Phase 5B: Product Photography Integration

Date: 2026-10-17. Branch `chore/production-consolidation-20261015`.

Source (READ-ONLY, unchanged): `E:\deMarkt\AAYNA - Product Sourcing Photos\Product_Photos_Higgsfield`
Excluded: `Naira_Bold Chunky Earring.png` (per instruction).

## 1. Result

| Item | Status |
|---|---|
| Inventory | **33 files** found; **32 included**, 1 excluded (Naira). All 33 are valid PNGs: full chunk-CRC check plus complete image-data decompression. **No unreadable files, no duplicate content.** One numbering gap: Aura Locket has no variation 3. |
| Asset library | **32 copied byte-for-byte** to `E:\deMarkt\aayna-webapp\aayna-website-assets\product-photos\<group>\<group>-NN.png` (86 MB). This is inside the project folder but **outside git**, so originals aren't committed. `MANIFEST.csv` and `MANIFEST.json` sit beside them, and a copy of the CSV is in `docs/audits/evidence/phase5b/`. **32/32 copy checksums match**, and **all 33 source files were re-hashed afterwards: unchanged.** |
| Product groups | **10**, each a single physical piece across its numbered photos (visually reviewed). |
| Mapping to products | **10/10 groups map 1:1** to the 10 products in `AAYNA_Product_Inventory.xlsx`. The importer's deterministic matcher was run as a dry run: **0 partial, 0 ambiguous, 0 orphan.** None of the 10 current catalogue/seed products (earlier `LAUNCH_CATALOGUE_AUDIT.md`) matches a photo. |
| Frontend | **Done and verified** (cards, gallery, aspect ratio, loading, alt text, fallbacks); **110/110 browser checks** on desktop and mobile. |
| Photos on the live catalogue | **Awaiting decision.** Products and image URLs live in the database, and the importer needs object storage. See §6. |

## 2. Inventory (all files)

| Original filename | Product group | Var. | Format / dimensions | Size | SHA-256 | Status |
|---|---|---|---|---|---|---|
| Aura Locket Necklace Golden 1.png | Aura Locket Necklace Golden | 1 | PNG 928×1152 RGB | 1.97 MB | `2a772eed74d6bf7d11cbd8032951f42907f0f4ba1115e3500084345442e3e3d0` | copied |
| Aura Locket Necklace Golden 2.png | Aura Locket Necklace Golden | 2 | PNG 928×1152 RGB | 1.60 MB | `25a9fce052d7bffad283bb460bc8c7eb79653bfc30930d2d3eef715d758b2b34` | copied |
| Aura Locket Necklace Golden 4.png | Aura Locket Necklace Golden | 4 | PNG 896×1200 RGB | 1.81 MB | `3ce04a9a4b15766190b94b5bcdeb5dd01e2ba1a40620be967e8c1022da711667` | copied |
| Bold Chunky Earring Golden 1.png | Bold Chunky Earring Golden | 1 | PNG 928×1152 RGB | 1.94 MB | `5826bc1a8c2f9e1254a667b800575ed732bcb4f2187b02f405d36179f0ee6496` | copied |
| Bold Chunky Earring Golden 2.png | Bold Chunky Earring Golden | 2 | PNG 928×1152 RGB | 1.18 MB | `bee070f40b42180f19d637ad2ed20bdb815bc681c51a95c6e541806d16996d6d` | copied |
| Classic Statement Ring Golden 1.png | Classic Statement Ring Golden | 1 | PNG 928×1152 RGB | 2.04 MB | `463783f02857957e80cb19303de48f460d458549878ed56c412e34319516f0c0` | copied |
| Classic Statement Ring Golden 2.png | Classic Statement Ring Golden | 2 | PNG 928×1152 RGB | 1.38 MB | `b8e59aa4ff4fd761ae8bc029231e62aeab3d183bbd5106dcc053ea91f499b1d1` | copied |
| Classic Statement Ring Golden 3.png | Classic Statement Ring Golden | 3 | PNG 896×1200 RGBA | 1.21 MB | `9c40f2174a740aa21ac9c81b198449321de17fe4fe62df8b1e956da515c1f8b0` | copied |
| Classic Statement Ring Golden 4.png | Classic Statement Ring Golden | 4 | PNG 896×1200 RGB | 0.88 MB | `d58703119cd5cc225be9428f64b4a3eba49a0f370325077425ce63aebc4d8861` | copied |
| Crystal Stone Cuff Golden 1.png | Crystal Stone Cuff Golden | 1 | PNG 928×1152 RGB | 1.38 MB | `39fa0595a53a2eee043c603abb9dd2f693549528f7e65c9c8b4dae14fc57bdfd` | copied |
| Crystal Stone Cuff Golden 2.png | Crystal Stone Cuff Golden | 2 | PNG 928×1152 RGB | 1.78 MB | `311b95bb23c48c86ca1bb7bb7f9630050f2efa8d808a2c12e0a028dc3c20e937` | copied |
| Crystal Stone Cuff Golden 3.png | Crystal Stone Cuff Golden | 3 | PNG 896×1200 RGB | 1.77 MB | `684911392d7953e534bed6764baacaeaa3c2f3ff3844d6ac0e224305c2e8888e` | copied |
| Crystal Stone Cuff Golden 4.png | Crystal Stone Cuff Golden | 4 | PNG 896×1200 RGB | 1.38 MB | `08a72a82c42e757a258fb8dc3d7e2ffa14d5c9621c5d7f7061dda564bd1bd2b4` | copied |
| Floral Bloom Earring Golden 1.png | Floral Bloom Earring Golden | 1 | PNG 1744×2336 RGB | 5.08 MB | `dda3d503480a26d8b6d322100ea0253bd3369aa15b7f54c2656df21d78aff040` | copied |
| Floral Bloom Earring Golden 2.png | Floral Bloom Earring Golden | 2 | PNG 1744×2336 RGB | 5.38 MB | `12639c0dc056f4d3979a8608065f0fce624597e52b6b3b08bde745b0adf08a7d` | copied |
| Floral Bloom Earring Silver 1.png | Floral Bloom Earring Silver | 1 | PNG 1792×2400 RGB | 7.11 MB | `b6790342832018fd9f7e578fece3d48593998649a700c58297fdd2c6332446d6` | copied |
| Floral Bloom Earring Silver 2.png | Floral Bloom Earring Silver | 2 | PNG 1792×2400 RGB | 5.36 MB | `ea2e0d525e17caa96b28fcc5291ce2882020f15551c5912ab40d7c9cddef550a` | copied |
| Floral Bloom Earring Silver 3.png | Floral Bloom Earring Silver | 3 | PNG 896×1200 RGB | 1.40 MB | `b0f1318dd8f733b2af81fdc84f13b3e2c7d93f12d6daab8e74027c9098e1724b` | copied |
| Floral Charm Golden Bracelet 1.png | Floral Charm Golden Bracelet | 1 | PNG 1792×2400 RGB | 7.17 MB | `117d09d7f0f95f2bbbdc3532c63e77e850f8923e26feb67f2e5bd4511185fe0f` | copied |
| Floral Charm Golden Bracelet 2.png | Floral Charm Golden Bracelet | 2 | PNG 1792×2400 RGB | 7.43 MB | `c11b7872cf32358cc2b28ce09a45e92406e656f9cf7d1885bd725dd391aa531d` | copied |
| Floral Charm Golden Bracelet 3.png | Floral Charm Golden Bracelet | 3 | PNG 896×1200 RGBA | 1.36 MB | `db3081947f94eb8fd30d82067d7462c56d3e2917ae6fc751494286cdd2e4ae2e` | copied |
| Floral Charm Silver Bracelet 1.png | Floral Charm Silver Bracelet | 1 | PNG 928×1152 RGB | 2.35 MB | `858dd2560ac6d7bff266ead36cb1ee5a0b31cb42e52f814e46292ab0cae4f4f0` | copied |
| Floral Charm Silver Bracelet 2.png | Floral Charm Silver Bracelet | 2 | PNG 928×1152 RGB | 1.01 MB | `e819a690fda83bfe81c0133874436cef3f50aa192ea427659ff572c92033ce96` | copied |
| Floral Charm Silver Bracelet 3.png | Floral Charm Silver Bracelet | 3 | PNG 896×1200 RGB | 2.05 MB | `dd3b519e29913821ee1a1ae3f74b020c3a0411623348fa51c37b7b2c80a26ce7` | copied |
| Floral Charm Silver Bracelet 4.png | Floral Charm Silver Bracelet | 4 | PNG 896×1200 RGB | 1.67 MB | `5471337762735ce78cfa56524e4f3bfc59d23123caf36378bfa1813740c42268` | copied |
| Golden Crossline Cuff Bracelet 1.png | Golden Crossline Cuff Bracelet | 1 | PNG 1792×2400 RGBA | 5.90 MB | `2515bce5e4892eaacbdb41e3eb35ab8c7b76c16b6e6d0ff3766de5e339c8de08` | copied |
| Golden Crossline Cuff Bracelet 2.png | Golden Crossline Cuff Bracelet | 2 | PNG 1792×2400 RGB | 3.67 MB | `57f8e7568ff3644dfaae3dc65e839cc8f36897beaa311cccedd75c9322adcff0` | copied |
| Golden Crossline Cuff Bracelet 3.png | Golden Crossline Cuff Bracelet | 3 | PNG 896×1200 RGB | 1.53 MB | `620e472fc466f92dee7eb25a2477e9ac44ef8789fc155662c1eb8de53d3c347a` | copied |
| Golden Crossline Cuff Bracelet 4.png | Golden Crossline Cuff Bracelet | 4 | PNG 896×1200 RGB | 1.26 MB | `bb7cc2346276ebfc1edde36f86915ea9dd28d030656393df56664d528c2e5227` | copied |
| Luna Locket Necklace Golden 1.png | Luna Locket Necklace Golden | 1 | PNG 928×1152 RGB | 1.97 MB | `9a6598078cc33ad99a840d0db896f6e1e4a78d397a17ddf3317a7a47a40a4453` | copied |
| Luna Locket Necklace Golden 2.png | Luna Locket Necklace Golden | 2 | PNG 928×1152 RGB | 1.76 MB | `790c6a870e8c2ab670ed434ccb9c9f4b0a73a0db865a47a835acdbf5d39aef0e` | copied |
| Luna Locket Necklace Golden 3.png | Luna Locket Necklace Golden | 3 | PNG 896×1200 RGB | 1.44 MB | `d186633195ecb58d5a40ff016d9fbe3b67bebf7c2c66467d392baabd95925f7a` | copied |
| Naira_Bold Chunky Earring.png | — | — | PNG 1744×2336 RGB | 5.04 MB | `5c5446f093d1a8d748a4189b551ccd7981e6c53e077406d4982bcfbd9102399a` | **EXCLUDED** |

Aspect ratios:
- **3:4** for 896×1200, 1744×2336 and 1792×2400 (20 files).
- **≈4:5** for 928×1152 (12 files).

## 3. Product groups → products (exact mapping)

How the mapping was made:
- The SKU and product names come **only** from `E:\deMarkt\AAYNA Brand Details\AAYNA_Product_Inventory.xlsx`.
- It was read through `scripts/import_inventory.py`'s dry-run `build_manifest`, which writes nothing.
- Matching uses the importer's deterministic filename-token rule: every name and colour token of the product must appear in the filename, ignoring word order. Nothing was inferred from filenames alone.
- No costs or notes were read into this report, and the staged spreadsheet copy was deleted afterwards.

| Photo group | Spreadsheet product | SKU | Colour | Category | Photos (variation numbers) |
|---|---|---|---|---|---|
| Luna Locket Necklace Golden | Aayna Luna Statement Locket | `AYN-NKL-LUN-GLD` | Golden | necklaces | 1, 2, 3 |
| Aura Locket Necklace Golden | Aayna Aura Statement Locket | `AYN-NKL-AUR-GLD` | Golden | necklaces | 1, 2, 4 |
| Golden Crossline Cuff Bracelet | Aayna Golden Crossline Cuff | `AYN-CUF-CRS-GLD` | Golden | bracelets ⚠ | 1, 2, 3, 4 |
| Crystal Stone Cuff Golden | Aayna Crystal Stone Cuff | `AYN-CUF-STN-SLV` ⚠ | Golden | bracelets ⚠ | 1, 2, 3, 4 ⚠ |
| Bold Chunky Earring Golden | Aayna Bold Chunky Earrings | `AYN-EAR-CHK-GLD` | Golden | earrings | 1, 2 |
| Floral Bloom Earring Golden | Aayna Floral Bloom Earrings | `AYN-EAR-FLR-GLD` | Golden | earrings | 1, 2 |
| Floral Bloom Earring Silver | Aayna Floral Bloom Earrings | `AYN-EAR-FLR-SLV` | Silver | earrings | 1, 2, 3 |
| Floral Charm Golden Bracelet | Aayna Floral Charm Bracelet | `AYN-BRC-FLR-GLD` | Golden | bracelets | 1, 2, 3 |
| Floral Charm Silver Bracelet | Aayna Floral Charm Bracelet | `AYN-BRC-FLR-SLV` | Silver | bracelets | 1, 2, 3, 4 |
| Classic Statement Ring Golden | Aayna Classic Statement Ring | `AYN-RNG-CLS-GLD` | Golden | rings | 1, 2, 3, 4 |

Numbered photos are **gallery views of one product**, never inventory variants. Colour variants are separate SKUs in the spreadsheet, such as the golden and silver Floral Bloom earrings.

### Ambiguities and items for founder decision
1. **`AYN-CUF-STN-SLV` (Crystal Stone Cuff):**
   - The SKU suffix says **silver**, but the spreadsheet colour and all four photos are **golden**.
   - **Photo 4 also shows a second, silver cuff**, which suggests a silver version exists.
   - Confirm the SKU and colour. Until then, keep photo 4 out of this product's gallery (it shows another item).
2. **Cuff → `bracelets`** category for both cuffs: the importer maps "Cuff" to bracelets and asks for confirmation.
3. **All 10 products lack a selling price** in the spreadsheet, so the importer marks them *not ready* and will not create them without a founder-approved price.
4. **Aura Locket: variation 3 is missing** from the source folder (1, 2, 4 exist). This may be intentional, so no action unless a photo was lost.
5. **The current catalogue** (10 older products: Gold Pearl Hoop Earrings, etc.) has **no photographs here**, and none of these photos belongs to them.

## 4. Proposed primary (catalogue) image per product

The proposal favours a clean product-only shot as the primary for consistent grids. Model shots go into the gallery. The importer's own default is "variation 1 is the hero", so **this needs founder approval** (set `is_main` / order in Admin).

| SKU | Proposed primary | Gallery order after primary | Note |
|---|---|---|---|
| AYN-NKL-LUN-GLD | 2 (pendant on fabric) | 1, 3 | |
| AYN-NKL-AUR-GLD | 2 (pendant on fabric) | 1, 4 | |
| AYN-CUF-CRS-GLD | 2 (cuff on white block) | 1, 3, 4 | |
| AYN-CUF-STN-SLV | 1 (cuff on stone) | 2, 3 | **exclude 4** until §3.1 is decided |
| AYN-EAR-CHK-GLD | 2 (pair on white) | 1 | |
| AYN-EAR-FLR-GLD | 1 (pair on fabric) | 2 | |
| AYN-EAR-FLR-SLV | 2 (pair on burgundy) | 1, 3 | |
| AYN-BRC-FLR-GLD | 2 (bracelet flat) | 1, 3 | |
| AYN-BRC-FLR-SLV | 2 (bracelet flat) | 1, 3, 4 | |
| AYN-RNG-CLS-GLD | 2 (ring on fabric) | 1, 3, 4 | |

## 5. Storefront integration (done, application code only, no database or storage changes)

| Requirement | Implementation |
|---|---|
| One ordering rule | New `frontend/src/lib/productImages.js`: the `is_main` image first, then `sort_order`, then stored order. Used by product cards, the cart, the home preview, the product page and its SEO image list. (Cards previously ignored `is_main`.) |
| Product detail gallery | The product page shows **every** photo: a main frame plus a thumbnail row (4/5 per row), each a `<button>` with `aria-label="Show image n of m"`, `aria-pressed`, ≥44 px and a visible focus ring. It resets to the primary photo when another product is opened. The old 16:9 second image (which cropped portrait photos heavily) is gone; the single-photo CSS detail crop is kept. |
| Aspect ratio, no unwanted cropping | The main product-page frame uses `object-contain` (whole photo on the mist background). Cards keep the existing 4:5 `cover` grid: at most ~7% top and bottom trimmed from a 3:4 photo, 0% for 4:5. |
| Loading | `loading="lazy"` except above-the-fold (`eager`) images; `decoding="async"` added. |
| Accessible descriptions | Alt text that looks like a filename (`*.png`, which admin uploads currently store) is replaced by "<product name> — image n of m". Thumbnails use empty alt because the button label describes them. |
| Missing-image fallback | Unchanged `ProductImage`: mist frame with a gem mark, never a broken-image icon. |
| No Windows paths | Images are referenced only by URL (`image_url`); nothing local is hardcoded. |

**Verification**: `scripts/verify/product_gallery.js` scored **110/110**. It ran against a local **test** database holding 10 throwaway QA products, using test-only WebP renditions served from the gitignored build folder. Not committed, not real data. It checks:
- desktop 1280 and mobile 390
- the main photo loads, is from the product's own group, is the primary, is `contain` and has good alt text
- the right number of thumbnails, all from the product's own group, each switching the main photo
- tap targets ≥44 px, no horizontal scroll
- category cards show each product's own primary photo
- the gallery resets when another product is opened

**No product displayed another item's photo.**

Regression on the new build:
- storefront routes 60/60
- home/footer layout 47/47
- admin UI 11/11
- inventory rules 28/28
- offline 111/111
- responsive audit: 0 in every category

Web weight: WebP renditions (max 1600 px, quality 82) are **18–133 KB** against 0.9–7.4 MB for the PNG originals. Production should never serve the PNG originals.

## 6. Getting the photos onto real products: decision required (stopped here)

Products and their `images[].image_url` live in MongoDB, so any route needs **database writes**. The real database is not yet located (see `DATABASE_DISCOVERY_AND_TEST_VERIFICATION.md` §11). Per the brief, I stopped before any database or storage change. Options:

| Option | How | Pros | Cons / needs |
|---|---|---|---|
| **A. Existing importer** (`scripts/import_inventory.py import`) | Creates the 10 products as **draft**, uploads WebP via `storage.put_object`, records `db.files`; photos served at `/api/files/...` | Already built and tested; idempotent; keeps originals untouched | Needs a working object storage (the Emergent key is empty and a migration is planned); needs founder-approved prices; needs the real database |
| **B. Static assets with the frontend** | Commit WebP renditions (~2.3 MB) under `frontend/public/product-images/<group>/`; set `image_url` to `/product-images/...` (a small importer flag) | No storage service, free, CDN-cached by the static host | Photo changes need a redeploy; the database records still need updating; ties images to the frontend host |
| **C. New object storage/CDN** (R2, S3, Cloudinary…) | Swap `storage.py` behind the same API, then option A | Durable; independent of Emergent | Provider choice, possibly paid; founder approval |

Recommendation:
- **A, on top of C**, once a storage provider is chosen.
- **B** is the fastest free path if you want photos live before choosing storage.

Every option also needs §3 decisions 1–3.

## 7. Tests

| Suite | Result |
|---|---|
| Inventory integrity (CRC and decompress, all 33) | 33/33 readable, 0 duplicates |
| Copy verification | 32/32 SHA-256 match; all 33 source files unchanged (re-checked again at the end of the phase: names and checksums identical) |
| Frontend build (`CI=true`, warnings are errors) | PASS |
| `product_gallery.js` desktop + mobile | **110/110** |
| storefront routes / home+footer / admin UI / inventory rules / offline pytest | 60/60 / 47/47 / 11/11 / 28/28 / 111/111 |
| Responsive audit (17 pages × 14 viewports) | **0 in every category**: overflow, clipped headings, targets <24/<44 px, unnamed, tiny text, missing focus, broken or distorted images |

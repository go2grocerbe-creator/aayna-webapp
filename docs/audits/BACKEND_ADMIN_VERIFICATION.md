# AAYNA — Phase 4: Backend, Admin & Database Verification

Date: 2026-10-16 · Branch: `chore/production-consolidation-20261015` · Start: `265e66a` · Commits: §8
Legend: **VERIFIED** (executed, evidence below) · **NOT VERIFIED** (could not be executed — reason given) · **OPEN** (known, not fixed here) · **DECISION** (founder input needed)

---

## 1. Summary

- **Real MongoDB was not reachable**, so the three MongoDB-only admin tests and concurrent-checkout oversell protection are **NOT VERIFIED** (§2). FerretDB results are not presented as equivalent.
- The audit confirmed **15 backend defects (B-01 to B-15) and 3 admin UI defects** by running checks against the unmodified code first: **19/40** backend checks passed before the fixes (21 failing) and **3/11** admin UI checks. All are fixed. The final run is **61/61** backend checks (the concurrent case is reported separately) and **11/11** admin UI checks, with no regressions in earlier suites (§7).
- The most serious defects found and fixed:
  1. **Overselling.** Concurrent orders all succeeded (10 orders for 3 units). Duplicate cart lines bypassed the stock check (2 + 2 of 3).
  2. **Draft and inactive products became public** when their stock reached 0.
  3. **The login lockout could be bypassed** with a spoofed `X-Forwarded-For`, giving unlimited password guesses.
  4. **Production accepted a 3-character JWT secret** and an admin password of `123`.
  5. **Admin accepted bad data:** zero or negative prices, negative stock, unknown statuses and duplicate slugs. **CSV re-import republished drafts.**
- **Launch blockers that remain** (§9): real-MongoDB verification, image storage (all images depend on Emergent), and the founder decisions listed in §9.

## 2. MongoDB-only tests: NOT VERIFIED

| What | Result |
|---|---|
| `fastdl.mongodb.org`, `repo.mongodb.org`, `downloads.mongodb.com`, Docker Hub, conda-forge from the cloud workspace | Blocked by the network allowlist (proxy `connect_rejected` / no route) |
| The same hosts from the Linux VM on the founder's linked computer | Blocked |
| Unofficial MongoDB binaries from GitHub or package mirrors | Not used (unverified supply chain) |
| FerretDB 1.24 (test stand-in) | Not equivalent: it lacks `$first` in `$group` and `$lte` inside `$expr`, and its conditional `findOneAndUpdate` is **not atomic under concurrency**. A raw probe with no app code let 10 concurrent conditional decrements of `n=3` succeed 7 times (MongoDB guarantees 3). |

**Still NOT VERIFIED:**
- `TestDashboard::test_dashboard_keys` — dashboard aggregation.
- `TestInventory::test_low_stock_only` — low-stock `$expr` filter.
- `TestCustomers::test_list_and_detail` — `$first` aggregation.
- Concurrent checkout oversell protection.

The code paths are reviewed in §3. Their queries are standard MongoDB, and the oversell fix relies on MongoDB's documented single-document atomicity.

**How to close this.** Either allow `fastdl.mongodb.org` in claude.ai → Settings → Capabilities so the official server can run as a throwaway instance here, or run the following on the founder machine against the isolated `aayna_pytest` database. It never touches `aayna_dev`, and `conftest.py` refuses any database name without "test".

```bash
cd backend
# .env.test: MONGO_URL=mongodb://localhost:27017  DB_NAME=aayna_pytest  APP_ENV=test
#            JWT_SECRET=<random 64 hex>  ADMIN_EMAIL=qa@example.test  ADMIN_PASSWORD=<random>
#            CORS_ORIGINS=http://localhost:3000  TRUSTED_PROXY_HOPS=1
set -a; source .env.test; set +a
./venv/Scripts/uvicorn.exe server:app --host 127.0.0.1 --port 8001        # shell 1
# shell 2 (same .env.test sourced):
REACT_APP_BACKEND_URL=http://localhost:8001 ./venv/Scripts/python.exe -m pytest tests/ -q
# restart uvicorn (pytest drops the test DB, incl. the admin), then:
cd .. && API=http://localhost:8001/api ./backend/venv/Scripts/python.exe scripts/verify/backend_admin_checks.py
```

`backend_admin_checks.py` detects real MongoDB and then also asserts the **concurrent** case (10 parallel orders for 3 units → exactly 3).

## 3. Admin and backend audit — findings

| # | Area | Finding (evidence) | Status |
|---|---|---|---|
| B-01 | Products / stock | Adjusting or editing a **draft or inactive** product's stock to 0 set status `out_of_stock`, a public status, so unreleased products appeared on the storefront (public detail HTTP 200) | Fixed `c99e949` |
| B-02 | Products | No validation. Selling price 0 or negative, discount ≥ price, negative stock or alert, unknown status (`published`) and blanking required fields were all accepted. Editing a slug to another product's slug was accepted. | Fixed `c99e949` (400; slug clash 409) |
| B-03 | CSV import | Every row wrote `status` and defaulted it to `active`, so re-importing a draft **published it**. Unknown statuses and non-positive prices were imported. | Fixed `c99e949` |
| B-04 | Orders | Saving "Delivered" twice counted 2 successful orders, and moving out of Delivered/Cancelled never corrected the counters | Fixed `c99e949` |
| B-05 | Dashboard | "Today" started at UTC midnight (06:00 in Dhaka) | Fixed `c99e949` |
| B-06 | Inventory | "Low stock only" included drafts while the dashboard count excluded them, so the two numbers disagreed | Fixed `c99e949` |
| B-07 | Checkout | Read, check, then overwrite with a computed value: **10 concurrent orders for 3 units all succeeded** (stock ended at 2) | Fixed `9a96ca4` (atomic conditional decrement, with rollback) — sequential VERIFIED; concurrent NOT VERIFIED (§2) |
| B-08 | Checkout | Duplicate lines of one product were checked separately: 2 + 2 of 3 sold, stock went to 1 | Fixed `9a96ca4` — VERIFIED |
| B-09 | Checkout | A failed order could still create or increment the customer record | Fixed `9a96ca4` (stock reserved before the customer write) — VERIFIED |
| B-10 | Auth | Lockout keyed on the client-controlled left-most `X-Forwarded-For`: rotating it gave **unlimited attempts** | Fixed `0b20351` (`TRUSTED_PROXY_HOPS`, default 0) — VERIFIED |
| B-11 | Production config | `JWT_SECRET='abc'` and `ADMIN_PASSWORD='123'` were accepted | Fixed `8347452` (minimum 32 / 12 characters) — VERIFIED |
| B-12 | API | `/docs`, `/redoc` and `/openapi.json` were public in production (full admin API map) | Fixed `af4ca80` |
| B-13 | API | Public `/settings` returned **every** stored key | Fixed `af8839c` (storefront allowlist) — VERIFIED |
| B-14 | API | Unhandled exceptions bypassed CORS, so browsers saw a network failure instead of a 500 | Fixed `ca355a9` (JSON 500 with CORS, no exception text) — VERIFIED |
| B-15 | Storage | Blocking `requests` calls inside async handlers: each `/api/files` image stalled the whole API (up to 60 s) | Fixed `0b36fcd` (`asyncio.to_thread`) |
| B-16 | Auth | Admin roles (`order_manager`, `product_manager`, …) are not enforced, so any admin role can do everything, including settings and customer exports. There are no user-management endpoints, so only the seeded `super_admin` exists today. | **OPEN** — latent; becomes a blocker before adding staff accounts |
| B-17 | Auth | JWT lives 7 days, logout does not revoke it (stateless), and the token is stored in `localStorage` (readable by any XSS) | **OPEN** — acceptable for a single founder admin; review before adding staff |
| B-18 | Database | Only `users.email` has a unique index. Product `slug`/`sku`, `orders.order_number` and `orders.client_request_id` are not unique. `ensure_indexes` swallows errors, so converting an existing index silently fails on duplicates. | **OPEN** — recommend: run a duplicate check on real data, then create unique indexes in a one-off migration (not at startup) |
| B-19 | Orders | Cancelling or returning an order does **not** restock | **DECISION** — automatic restock vs. manual adjustment after physical return |
| B-20 | Customers | `total_orders` is incremented before the order insert (if the insert then fails, the count is one too high) | OPEN — low risk |
| B-21 | Existing data | Validation is not retroactive. The real database may already hold drafts flipped to `out_of_stock` by B-01, negative stock, or odd statuses. | **OPEN** — check with the read-only queries in §6 before launch |

Reviewed and found correct:
- **Passwords:** bcrypt; `password_hash` is never returned.
- **Sessions:** JWT signature, expiry and the user's active status and role are checked on every admin request.
- **Lockout:** 5 failures → 15 minutes, keyed by IP + email.
- **Admin routes:** every admin endpoint refuses anonymous access, including uploads and exports.
- **Order lookups:** confirmation requires a random token (only its hash is stored); public tracking requires order number + phone and returns no address.
- **Order numbers:** atomic counter; checkout is idempotent on `client_request_id`.
- **Uploads:** extension allowlist, 8 MB limit; `/api/files` serves only recorded uploads and rejects traversal.
- **Admin data:** `cost_price` is excluded from the inventory listing, and admin edits write inventory logs.

## 4. Admin UI fixes (documented Phase 3 issues)

| Issue | Before | After | Commit |
|---|---|---|---|
| Automatic retries before an error | Server error ~7,993 ms; 401 ~7,932 ms; unreachable ~7,720 ms | 1,853 / 502 / 1,817 ms (4xx not retried, others retried once) | `a4efdc9` |
| Misleading messages | 500s appeared as "server could not be reached" (CORS, B-14); 401 offered "Try again" | Distinct messages for server error / expired session (with **Sign in again**) / no permission / not found / unreachable, plus HTTP status | `ca355a9`, `0e31374` |
| Broken-image thumbnails | 10 of 10 product rows and the image editor showed the browser's broken-image icon | Neutral "No image" / "Image could not be loaded" icon, 0 broken | `d1c00cd` |
| `undefined/api` when `REACT_APP_BACKEND_URL` unset (admin client and uploaded image URLs) | — | Same-origin fallback as the storefront | `0e31374` |

All rows above are VERIFIED with `scripts/verify/admin_ui_checks.js` against the Phase 3 build (`265e66a`, **3/11**) and the final build (**11/11**). Screenshots are in `evidence/phase4/`.

## 5. Exposure, purchase restrictions and production protections — VERIFIED

**Public exposure** (`backend_admin_checks.py`). A product was seeded with `internal_notes`, `supplier_url`, `supplier_price`, `landed_cost`, `margin`, `price_is_temporary` and sourcing notes, and an order with an `admin_note`. None of these values, nor `password_hash` or the confirmation `token_hash`, appear in any of these 12 public endpoints:
- product list and search, product detail
- categories and category detail
- settings, health/ready, sitemap
- `/cart/validate`
- checkout response, token-gated order confirmation, `/track`

Order confirmation contains no phone or address. `/api/files` rejects `..` paths and other apps' keys.

**Purchase restrictions** (`backend_admin_checks.py` + `inventory_rules.py` 28/28):
- Draft, inactive and out-of-stock products are refused by `/cart/validate` and `/checkout`, even by direct ID, and also when mixed with a valid item.
- An unknown ID, quantity 0, a negative quantity, more than is in stock, and duplicate lines that together exceed stock are all refused.
- Refused attempts leave stock untouched, and client-sent prices are ignored.
- The last unit flips the product to `out_of_stock`.

**Production protections.** The backend was actually started with `APP_ENV=production` and one unsafe setting at a time. All **12/12 were refused at startup**:
- JWT secret: missing, dev fallback, or shorter than 32 characters
- Admin password: missing, the default, or shorter than 12 characters
- `CORS_ORIGINS=*`
- localhost `PUBLIC_SITE_URL`
- `DB_NAME` of `aayna_dev` or `aayna_pytest`
- localhost `MONGO_URL`
- webhook enabled without a URL

A safe configuration passes validation, and the API docs are off in production. Demo seeding is blocked in production unless `ALLOW_PRODUCTION_SEED=true`.

**Credentials in git.** `git ls-files` and a pattern scan of all branches' history found no `.env` file (only `.env.example`), no connection strings with credentials and no API keys or private keys. The only credential string is the documented dev-only fallback `admin@aayna.xyz` / `ChangeMe123!` (README, tests, old Emergent test reports), which production refuses. `.env*` is gitignored.

**Deployment settings introduced or used here:**
- `TRUSTED_PROXY_HOPS`: set it to the number of reverse proxies in front of the API (e.g. 1 behind one load balancer), otherwise leave it at 0.
- `JWT_SECRET`: at least 32 characters.
- `ADMIN_PASSWORD`: at least 12 characters.

## 6. Image storage: Emergent dependency audit and provider-neutral migration plan

### 6.1 Current dependencies

| Dependency | Where | Effect if Emergent is unavailable |
|---|---|---|
| Emergent object storage API `integrations.emergentagent.com/objstore` with `EMERGENT_LLM_KEY` | `backend/storage.py` (`put_object`, `get_object`); used by admin upload `/api/admin/upload`, public `/api/files/{path}` and `scripts/import_inventory.py` | Admin uploads fail (HTTP 502). **Every uploaded product image 404s**, because `/api/files` proxies each request to Emergent. |
| Uploaded image URLs stored **absolute, with the backend host baked in** | `ImageUpload.jsx` (`fullImageUrl` → `${REACT_APP_BACKEND_URL}/api/files/...`) and `import_inventory.py --public-base` | **Changing the backend domain breaks all uploaded images even if storage stays the same** |
| Emergent CDN `static.prod-images.emergentagent.com` | `seed_data.py` demo catalogue, category images, `hero_image_url` | Demo images disappear. Production seeding is blocked, but any of these URLs copied into real data break. |
| `@emergentbase/visual-edits` | `craco.config.js` (optional, dev-only; package removed in Phase 2) | None |
| `.emergent/emergent.yml`, `.gitconfig` (Emergent agent identity) | repo root | Metadata only |

The real database could not be inspected here. **First step:** run `scripts/storage/audit_image_refs.py` (read-only, added in `9ca179a`) against `aayna_dev` and later production. It counts every product, category, settings and order-snapshot image reference by host and kind, plus `db.files` records. Tested on the test database.

### 6.2 Migration plan (provider-neutral; nothing is purchased or integrated)

1. **Measure.** Run the audit script on the real data. Record the counts of `app_files` (Emergent object storage), `emergent_cdn`, `other`, and products without images.
2. **Export.** For each `db.files` record (`is_deleted=false`), fetch the bytes through the existing backend (`/api/files/<path>`, or `storage.get_object` in a script). Save them to an archive keyed by `storage_path`, with a SHA-256 manifest. For `emergent_cdn` URLs still referenced, download them the same way. Do this **while Emergent is still reachable**; this export is the time-critical step.
3. **Choose a provider** (founder decision). Any S3-compatible bucket or a CDN-backed file store works, because the app only needs `put_object` / `get_object` and keeps the bucket private behind `/api/files`. Branch `feat/aayna-real-inventory-v1` (`1340203`) contains an unmerged S3-compatible implementation that can be reviewed once a provider is chosen.
4. **Switch `storage.py` behind the same two functions.** No call-site changes: the routes and the importer already go through `put_object` / `get_object`.
5. **Make image URLs host-independent.** Store `/api/files/<path>` (relative) and resolve to the API base when rendering, or front `/api/files` from the storefront domain. This removes the baked-in-host problem for good.
6. **Rewrite stored URLs** with a dry-run-first script. It maps old absolute URLs to the new form, writes a before/after CSV for review, and applies only with an explicit `--apply` flag after a database backup. Order item snapshots (`orders.items[].image`) are historical and can be rewritten the same way or left as they are.
7. **Verify.** Re-run the audit (expect 0 `emergent_cdn` and no Emergent hosts), then `storefront_routes.js` and `responsive_audit.js` with real images reachable. This also closes the Phase 3 "product photography NOT VERIFIED" item.

Neither the upload path nor the database was changed for storage in this phase, apart from the non-blocking fix B-15.

**Read-only data-quality queries to run with step 1 (B-21):**
- `db.products.find({stock_quantity: {$lt: 0}})`
- `db.products.find({status: {$nin: ["active","draft","inactive","out_of_stock"]}})`
- `db.products.find({selling_price: {$lte: 0}})`
- Duplicate slugs and SKUs: `db.products.aggregate([{$group: {_id: "$slug", n: {$sum: 1}}}, {$match: {n: {$gt: 1}}}])` (same for `sku`)
- Drafts that may have been published by B-01: `out_of_stock` products created by the inventory importer (`price_is_temporary` present) — review in Admin.

## 7. Test results (final build, isolated test backend on FerretDB, DB reset per suite)

| Suite | Result |
|---|---|
| `CI=true yarn build` | PASS |
| `pytest backend/tests` | 120 passed, 1 skipped, 3 failed — the 3 FerretDB-only cases in §2 (**NOT VERIFIED**); unchanged from Phases 2–3 |
| `pytest backend/tests_import` (offline: importer, DB guard, client-IP, product rules, production secrets) | **40/40** (was 7) |
| `scripts/verify/backend_admin_checks.py` | **61/61**, plus concurrent oversell **NOT VERIFIED** (before fixes: 19/40 on the then-current 40 checks) |
| `scripts/verify/admin_ui_checks.js` | **11/11** (Phase 3 build: 3/11) |
| `scripts/verify/inventory_rules.py` | 28/28 |
| `scripts/verify/storefront_routes.js` | 60/60 |
| `scripts/verify/home_footer_layout.js` | 47/47 |
| `scripts/verify/responsive_audit.js` (238 combinations) | see §7.1 |
| Production start-up refusals | 12/12 |

### 7.1 Responsive regression
`responsive_audit.js` on the final build (17 pages × 14 viewports):
- overflow, clipped headings, targets under 24 or 44 px, unnamed controls, sub-12 px text, missing focus and distorted images: **all 0**, unchanged from Phase 3.

Two readings that changed must not be over-read:
- **"JS errors: none"** — the admin dashboard's FerretDB 500 now arrives as a proper HTTP error instead of a CORS failure (B-14), so it is no longer counted. The dashboard still cannot load on FerretDB; it shows the error card.
- **"Broken images: 0"** — no page renders a broken-image icon any more (`ProductImage` on the storefront, `AdminThumb` in admin). Product photos are **still unreachable** in this environment, so photography remains **NOT VERIFIED**.

Summary: `evidence/phase4/responsive_audit_summary_final.txt`.

## 8. Commits (Phase 4)

| Commit | Change |
|---|---|
| `c99e949` | Product status/validation, CSV import, order counters, dashboard day, low-stock definition |
| `9a96ca4` | Atomic stock reservation; duplicate lines |
| `af8839c` | Public settings allowlist |
| `ca355a9` | JSON 500 with CORS |
| `0b20351` | Lockout not bypassable via `X-Forwarded-For` (`TRUSTED_PROXY_HOPS`) |
| `0b36fcd` | Non-blocking object-storage calls |
| `83955a8`, `0df7dcb` | `backend_admin_checks.py` |
| `a4efdc9` | Retry policy |
| `0e31374` | Admin error messages; API base fallback |
| `d1c00cd` | Admin thumbnails |
| `6916947` | `admin_ui_checks.js` |
| `8347452` | Production secret minimums |
| `af4ca80` | No API docs in production |
| `9ca179a` | Read-only image-reference audit |
| *(this document)* | Phase 4 record, checklist, evidence |

Files modified:
- **Backend:** `backend/admin_routes.py`, `backend/server.py`, `backend/auth.py`, `backend/storage.py`, plus new offline tests `backend/tests_import/test_{product_rules,client_ip,production_secrets}.py`
- **Frontend:** `frontend/src/index.js`, `frontend/src/admin/{AdminLoadError,AdminThumb,adminApi,ImageUpload}.jsx|js`, `frontend/src/admin/pages/{Products,Categories}.jsx`
- **Scripts:** `scripts/verify/{backend_admin_checks.py,admin_ui_checks.js}`, `scripts/storage/audit_image_refs.py`

## 9. Remaining risks and launch blockers

**Blockers:**
1. **Real-MongoDB verification** of the 3 admin aggregations and concurrent oversell protection (§2).
2. **Image storage.** All uploaded and seeded images depend on Emergent, and uploaded URLs embed the backend host. Export must happen while Emergent is reachable (§6). Product photography remains visually unverified.
3. **Data-quality check of the real database** (B-21) before launch.
4. **Founder decisions:**
   - restock on cancel/return (B-19)
   - storage provider (§6.2 step 3)
   - payment approach — unchanged and out of scope

**Risks (not blockers for a single-admin launch):**
- unenforced admin roles (B-16)
- 7-day non-revocable JWT in `localStorage` (B-17)
- missing unique indexes (B-18)
- customer counter on a failed insert (B-20)
- native iOS/Android not tested (Phase 3)

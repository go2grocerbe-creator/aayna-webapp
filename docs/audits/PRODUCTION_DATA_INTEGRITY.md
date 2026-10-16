# AAYNA — Phase 4B: Production Data Integrity, Checkout Safety & Media Inventory

Date: 2026-10-16 · Branch: `chore/production-consolidation-20261015` · Start: `40d81c7` · Commits: §9
Legend: **VERIFIED** (executed here, evidence linked) · **NOT VERIFIED** (could not be executed — reason given) · **OPEN** · **DECISION**

---

## 1. Summary

- **Real MongoDB is still inaccessible**, so five checks remain **NOT VERIFIED** (§2). No production concurrency-safety claim is made, whether from FerretDB or from sequential tests.
- Two further checkout defects were found and fixed. Both are independent of the database engine.
  - **Duplicate orders from one submission.** 8 concurrent submissions with one `client_request_id` created **8 orders**.
  - **Incomplete rollback.** A failed order insert left a stray customer record or an incremented `total_orders`.
- Read-only tools are ready for the real database. Neither has been run against live data (§5).
  - an integrity report
  - an index-migration plan (dry run)
- **Image migration manifest:** produced from **test data only**. Real images and the real database were not accessible (§6).
- **Returns and cancellations stay manual** for launch. The admin panel is parked as a recoverable patch (§4).

## 2. Real MongoDB: still NOT VERIFIED

**Blocker** (checked once at the start of this phase; not retried afterwards):
- **Cloud workspace:** `curl: (56) CONNECT tunnel failed, response 403`. The agent proxy logged `connect_rejected` for `fastdl.mongodb.org`, `repo.mongodb.org`, `downloads.mongodb.com`, `registry-1.docker.io` and `conda.anaconda.org`.
- **Linux VM on the founder's computer:** `X-Proxy-Error: blocked-by-allowlist`; no `mongod` and no Docker installed.

| # | Check | Status | What FerretDB showed (not evidence of production behaviour) |
|---|---|---|---|
| 1 | Dashboard aggregation | **NOT VERIFIED** | HTTP 500 — `$lte` inside `$expr` not implemented |
| 2 | Low-stock filtering | **NOT VERIFIED** | HTTP 500 — same operator |
| 3 | Customer list/detail aggregation | **NOT VERIFIED** | HTTP 500 — `$first` in `$group` not implemented |
| 4 | 10 concurrent single-item orders for 3 units → exactly 3 | **NOT VERIFIED** | 4–9 orders succeeded across runs. FerretDB's conditional updates are not atomic; a raw probe without app code let 7 of 10 conditional decrements of `n=3` succeed. |
| 5 | Simultaneous multi-item order atomicity | **NOT VERIFIED** | 6–10 orders succeeded across runs |

`scripts/verify/mongo_release_checks.py` runs all five on real MongoDB with explicit expected values, plus the checks in §3. Its exit code is 0 only when nothing is FAIL or NOT VERIFIED. The run procedure is in §5.3.

## 3. Checkout: idempotency, reservation and rollback

### 3.1 Fixed and VERIFIED in the test environment

| Check (`mongo_release_checks.py`) | Before (`40d81c7`) | After |
|---|---|---|
| 8 concurrent submissions, one `client_request_id` → exactly 1 order, all responses name it | **FAIL** (8 orders, 8 different numbers) | PASS (1 order) |
| No duplicate `client_request_id` stored | **FAIL** | PASS |
| Order insert fails after reservation → 500 JSON, stock restored, no customer left behind, key released | **FAIL** (stray customer record) | PASS |
| Same request succeeds on retry after that failure | PASS | PASS |
| Failing multi-item order (second line short) → every product unchanged, no order, no customer | PASS | PASS |
| No negative stock afterwards | PASS | PASS |

Evidence: `evidence/phase4b/release_checks_before_40d81c7.txt` and `evidence/phase4b/release_checks_after_ferretdb.txt`.

**How it works (`8ac43dc`, `6493a1f`):**
- The idempotency key is claimed by inserting it as the `_id` of a `checkout_requests` document. `_id` is unique in every MongoDB deployment with no index or migration, and FerretDB enforces it too (which is why this check could be verified).
- Concurrent duplicates wait up to about 10 s for the first attempt, then return its order number.
- Any failure releases the claim.
- Stock is reserved per product with one conditional `findOneAndUpdate` (still public **and** stock ≥ quantity, then `$inc -qty`) *before* the customer or order is written.
- Everything after the reservation (customer write, order number, order insert) is wrapped. On failure, reservations are released and this request's customer write is undone.

### 3.2 Crash and multi-worker review (design analysis; NOT VERIFIED where marked)

**Multiple backend workers or instances.** Every safety property above is enforced *inside the database* (conditional update, unique `_id`, atomic counter `$inc`), not in process memory. So it holds across any number of workers on real MongoDB. **NOT VERIFIED** for lack of MongoDB. One exception: the **login lockout counter is in process memory**, so with N workers an attacker gets up to N×5 attempts per window, and a restart resets it. Acceptable for a single-instance launch; move it to the database before scaling out.

**Process crash** (kill, out-of-memory, deploy restart). There are no multi-document transactions, so a hard crash can leave partial state. Normal exceptions are rolled back (§3.1); crashes cannot be.

| Crash point | Effect | Detection | Recovery |
|---|---|---|---|
| After the key claim, before reservation | Claim stuck in `processing`. The same page's retry gets HTTP 409 "already being processed" after ~10 s; a page reload creates a new key and works. | `data_integrity.py`: "checkout_requests stuck > 15 min" | Delete the claim after confirming no order exists |
| After some or all reservations, before the order insert | **Stock decremented with no order** (units appear sold) | `data_integrity.py`: "stock differs from the latest inventory-log entry" (sale logs are written after the insert) | Manual stock adjustment with reason |
| After the customer write, before the order insert | Customer `total_orders` one too high | not detected | cosmetic |
| After the order insert, before the sale logs | Order and stock correct, inventory log missing | "stock differs from the latest inventory-log entry" | add a manual log note |
| After the order insert, before the claim is marked done | None: retries find the order first | — | — |

To remove the crash windows, put reservation, customer and order in **one MongoDB multi-document transaction**. That needs a replica set, which managed MongoDB provides; a standalone local `mongod` does not. Recommended for Phase 5 once the production database is chosen. Not implemented here.

**Duplicate response has no confirmation token.** A retry that finds the existing order returns the order number without the one-time confirmation token, which only the first response carries. The customer lands on the generic confirmation page and must use Track Order (order number + phone). This is a UX limitation, not a duplicate order. **OPEN** (low).

**Callers that send no key** (non-storefront API clients) get no idempotency protection, by design. The storefront always sends one, generated per checkout page load.

## 4. Order stock lifecycle (cancellations and returns)

**Launch policy:** restocking stays under explicit administrator control. **Nothing changes stock when an order is cancelled or returned** (`update_order` only changes the status and customer counters). The admin records the outcome in Admin → Inventory → Adjust stock:
- `return` to put sellable goods back
- `damage` to record write-offs

with the order number as the reason. Every adjustment writes an inventory log. **Returned goods never become sellable automatically.**

**Reviewed design for the dedicated workflow (deferred; not implemented):**
- **Where:** an admin action only on Cancelled or Returned orders.
- **Per item:** quantity plus a required choice of `restock` (sellable) or `damaged` (written off). There is no default.
- **Double-restock prevention:** `items[].returned_qty` is incremented with one conditional update. It succeeds only while `returned_qty + qty ≤ quantity ordered`, so double clicks and concurrent admins cannot restock twice.
- **Audit:** an inventory log with `reference_order_id` and the admin's email, plus `order.stock_events[]`.
- **Guard:** an order with returned stock cannot be moved back to an active status, which would re-sell goods without deducting stock.

The UI half is parked at `docs/deferred/order-stock-returns-ui.patch` (verified to re-apply cleanly; see `docs/deferred/README.md`). The backend endpoint was **not** implemented. The active app does not reference it, and the frontend bundle is byte-identical to Phase 4 (`main.8c0c97c5.js`).

**DECISION:** approve the workflow before it is built and reviewed in a later phase.

## 5. Database integrity: read-only diagnostics and index plan

### 5.1 Tools (VERIFIED on test data only)

**`scripts/diagnostics/data_integrity.py`** — read-only. Exit code 2 = BLOCKER, 1 = REVIEW, 0 = clean.

**BLOCKER checks:**
- duplicate product `id` / `sku` / `slug`
- duplicate order `id` / `order_number` / `client_request_id`
- order-number counter behind the highest existing number (the next checkout would reuse a number)
- negative or non-integer stock
- invalid status
- public products with an invalid price

**REVIEW checks:**
- drafts possibly published by the pre-Phase-4 stock bug: imported drafts now public, or never-sold products an admin zeroed. Status changes were never logged, so this cannot prove *how*; each must be confirmed in Admin.
- duplicate customer phone
- orders referencing missing products
- totals that do not add up
- stock vs. inventory history
- stuck checkout claims

It also prints all indexes. Offline test `backend/tests_import/test_data_integrity.py` plants every problem type and checks:
- each one is reported
- a clean database reports nothing
- a **full database snapshot is identical before and after** (it never writes)

**`scripts/diagnostics/index_migration.py`** — dry run by default. For each recommended index it reports OK, CREATE (with the exact operations) or BLOCKED by duplicates (with examples). `--apply` is refused unless the database name contains "test"; it was refused for `aayna_dev`. If a create fails, the previous index is restored. **Rehearsed on the test DB:** 12 of 13 indexes applied. The partial unique index on `orders.client_request_id` is **NOT VERIFIED** because FerretDB lacks `partialFilterExpression`. With the indexes in place, rules 28/28, backend checks 61/61 and release checks (7 pass, 0 fail, 5 NOT VERIFIED) still pass (`evidence/phase4b/index_migration_rehearsal_test_db.txt`).

### 5.2 Recommended indexes and migration

| Collection | Index | Purpose |
|---|---|---|
| products | `id` unique, `sku` unique, `slug` unique (replaces non-unique `slug_1`) | lookups, import matching, public URLs |
| orders | `id` unique, `order_number` unique (replaces non-unique), `client_request_id` unique **partial** (string keys only), `{customer_id, created_at}`, `{created_at}` | identity, tracking, idempotency backstop, admin lists |
| customers | `id` unique, `phone` unique (replaces non-unique) | checkout matches by phone (code already tolerates the unique index: `6493a1f`) |
| categories | `slug` unique | public URLs |
| files | `storage_path` unique | `/api/files` lookup |
| inventory_logs | `{product_id, created_at}` | history |
| users | `email` unique | already exists |

**Migration procedure** (founder-approved, maintenance window; **not run**):
1. Back up the database.
2. Run `data_integrity.py`. Resolve every BLOCKER by hand: duplicates, the counter, negative stock and so on.
3. Run `index_migration.py` (dry run) and review the printed operations.
4. Rehearse on a restored copy whose name contains "test", using `--apply`.
5. Run the printed operations on production.
6. Re-run both scripts and confirm everything is OK.

The application does not create these indexes at startup on purpose: `auth.ensure_indexes` swallows errors, so a unique index blocked by duplicates would fail silently there.

### 5.3 Procedure for the actual database — NOT executed (no authorization, no access)

```bash
# Read-only. Prefer a MongoDB user with the 'read' role only.
export MONGO_URL='<connection string>' DB_NAME=aayna_dev        # later: the production DB
python scripts/diagnostics/data_integrity.py --json integrity_$(date +%F).json
python scripts/diagnostics/index_migration.py                    # dry run only
python scripts/storage/audit_image_refs.py --manifest image_manifest_$(date +%F).csv --check-reachable
```

To verify the five MongoDB items, use a **separate disposable test database** on a real MongoDB 7 server (never `aayna_dev` or production):

```bash
# backend env: DB_NAME=aayna_pytest APP_ENV=test TRUSTED_PROXY_HOPS=1 (+ test-only JWT/admin values)
uvicorn server:app --port 8001          # from backend/
API=http://localhost:8001/api python scripts/verify/mongo_release_checks.py   # exit 0 = all verified
python -m pytest backend/tests -q        # the 3 aggregation tests
```

**Data-integrity audit status:** tools ready and tested; **the real database has not been examined.**

## 6. Product media inventory and migration manifest

`scripts/storage/audit_image_refs.py --manifest` (read-only) writes one row per image reference with these columns:
- collection, field, record id, SKU/slug, position
- URL, kind, host
- `storage_path`
- upload record: ok / missing / deleted
- `shared_by` (how many references use the same URL)
- `export_from`
- proposed host-independent URL (**not applied**)
- reachability (optional, read-only HTTP)

Unreferenced uploads (orphans) are listed too.

**What was inventoried: TEST data only** (`evidence/phase4b/image_manifest_TEST_DATA.csv`). That means the seeded demo catalogue plus one planted example of each upload case.

| Measure (test data) | Result |
|---|---|
| References | 21: products 14, categories 6, `hero_image_url` 1 |
| Emergent CDN (`static.prod-images.emergentagent.com`) | 17 distinct images to download |
| Uploaded via Emergent object storage, host baked in (`womens-aayna.preview.emergentagent.com/api/files/…`) | 4 references, 4 originals to retrieve |
| Upload record missing / deleted | 1 / 1 (originals possibly unrecoverable) |
| URL shared by several references | 1 |
| Unreferenced uploads (orphans) | 1 |
| Reachable from this environment | 0 of 20 (egress blocked; says nothing about real availability) |

**What could NOT be inventoried:**
- **The real database.** Real product, category and order image references and the real `db.files` records are unknown.
- **The real image bytes.** No original was downloaded, hashed or size-checked, so whether originals are actually retrievable from Emergent is unknown.
- **Image quality.** Product photography was not evaluated (since Phase 3).

**Migration path that does not disrupt product records** (no step executed):
1. Run the manifest on the real database while Emergent is reachable.
2. Export every `storage_path` with an `ok` upload record via `storage.get_object` (or `GET /api/files/<path>`), and download every distinct Emergent-CDN URL. Write an archive plus a SHA-256 manifest and verify every file opens. `missing`/`deleted` rows become a list for the founder: re-shoot or re-upload.
3. Copy the files to the chosen provider under the **same `storage_path` keys**, so the paths stay unchanged.
4. Switch `storage.py` behind its two functions. Product records still point at `/api/files/<storage_path>`, so nothing changes for the storefront.
5. Rewrite only the host part of URLs with a dry-run-first script (before/after CSV, then `--apply` after a backup). The proposed form is the relative `/api/files/<storage_path>`, plus a render-time base URL. Emergent-CDN references are re-hosted under new upload paths and then rewritten.
6. Re-run the manifest and expect 0 Emergent hosts. Then run the storefront and responsive suites with real images.

**Image migration status:** **not started** (no export, no provider change, no URL change). The manifest tooling is ready, and **the real inventory is unknown.**

## 7. Verification (final build, isolated test backend on FerretDB 1.24, DB reset per suite)

| Suite | Result |
|---|---|
| `CI=true yarn build` | PASS; bundle `main.8c0c97c5.js`, identical to Phase 4 (deferred panel absent) |
| `pytest backend/tests` | 120 passed, 1 skipped, 3 failed. The 3 failures are the MongoDB-only aggregation tests: **NOT VERIFIED** (§2). |
| `pytest backend/tests_import` (offline) | **42/42** (was 40; +2 data-integrity tests) |
| `inventory_rules.py` (draft/inactive purchase block, stock, exposure, admin safeguards) | **28/28** |
| `backend_admin_checks.py` (auth, validation, exposure sweep, direct purchase attempts, errors) | **61/61**; concurrent oversell NOT VERIFIED |
| `mongo_release_checks.py` (idempotency, rollback, partial reservation, invariants, + the five MongoDB items) | **7 passed, 0 failed, 5 NOT VERIFIED** |
| `admin_ui_checks.js` | **11/11** |
| `storefront_routes.js` (routes, cart, checkout → order, admin guard, API-down states) | **60/60** |
| `home_footer_layout.js` (11 widths) | **47/47** |
| `responsive_audit.js` (17 pages × 14 viewports) | all criteria 0 (overflow, clipped headings, targets < 24 or 44 px, unnamed controls, sub-12 px text, missing focus, distorted images); product photos still unreachable |

`data_integrity.py` was also run on the **test DB right after the concurrency runs**. It reported exactly the damage FerretDB's non-atomic writes cause: 5 duplicate order numbers (BLOCKER), a stock value that differs from the inventory log (lost update), and a duplicate customer phone. This shows the report detects these signatures. The duplicate customer is **not** FerretDB-specific; see §8. Evidence: `evidence/phase4b/integrity_report_TEST_DB_after_concurrency_runs.txt`.

## 8. Risks: duplicate orders, overselling, incomplete rollback

- **Duplicate orders:** fixed for the storefront path and VERIFIED in the test environment (8 → 1). Remaining risks:
  - callers without a key are unprotected (by design)
  - a crash can leave a stuck claim (detectable; recovered by page reload)
  - the partial unique index backstop is not yet created (§5)
- **Duplicate customers:** two *simultaneous first orders* from the same new phone can create two customer records on any MongoDB. The lookup is by phone, then insert, and there is no unique index yet. Order safety is unaffected; one person's history is split. The fix is the unique `customers.phone` index in §5.2, which checkout already tolerates (`6493a1f`). **OPEN** until the index migration runs.
- **Overselling:** a single request cannot oversell (sequential and duplicate-line checks VERIFIED). **Concurrent oversell protection is NOT VERIFIED.** It depends on MongoDB single-document atomicity, which FerretDB does not provide. Treat it as unproven until `mongo_release_checks.py` passes on real MongoDB.
- **Incomplete rollback:** exceptions are fully rolled back (VERIFIED). **Process crashes are not**: there is no transaction, so the windows in §3.2 can leave stock decremented without an order. This is detectable with `data_integrity.py`; the remedy is a transaction on a replica set (Phase 5).

## 9. Commits (Phase 4B)

| Commit | Change |
|---|---|
| `8ac43dc` | Idempotency via `_id` claim; full rollback including the customer write |
| `afa6991` | `mongo_release_checks.py` and before/after evidence |
| `6493a1f` | Checkout tolerates a unique `customers.phone` index |
| `4078f2e` | `data_integrity.py` and offline test |
| `c4ec513` | `index_migration.py` (dry run; `--apply` only on test DBs); rehearsal evidence |
| `54b2ee6` | Return panel parked as a recoverable patch; active app unchanged |
| `6d6a0cd` | Image manifest (`--manifest`, `--check-reachable`); test-data evidence |
| *(docs commit)* | This document and the checklist |

# AAYNA Production Recovery — Checklist

Branch: `chore/production-consolidation-20261015` · Details and evidence: `REPOSITORY_RECOVERY_AUDIT.md`
Legend: [x] done with evidence · [ ] open · [~] NOT VERIFIED (environment limit)

## Phase 1 — Forensic audit
- [x] Branch lineage and pre-Vercel reference (`3e04781`) identified
- [x] Displaced files identified (`App.js`, `api.js`, root `package.json`)
- [x] Keep / Restore / Refactor / Remove register
- [x] Founder local checkout inspected — no unpushed or uncommitted app work (2026-10-15)

## Phase 2 — Restore ecommerce application
- [x] Router restored from `3e04781` (`786e90a`)
- [x] Vercel wrapper removed (`7c53dc1`)
- [x] Frontend installs off-Emergent (`fc92698`)
- [x] API failure vs not-found states (`95d0e54`)
- [x] Storefront gate 60/60 (`scripts/verify/storefront_routes.js`)

## Inventory & design recovery (from `feat/aayna-real-inventory-v1`)
- [x] Founder visual edits rounds 1–3 (`443346f`, `a4186e9`, `0c5951c`)
- [x] Real-inventory importer + offline tests (`0a7c6be`, `21d871b`)
- [x] Draft/inactive products cannot be bought (`0a7c6be`) — proven against pre-recovery backend
- [x] Admin owns price/images/stock; temporary-price flag cleared on real price (`21d871b`)
- [x] Production refuses dev/test/localhost DB (`2c89acb`)
- [x] Backend installs off-Emergent (`ff41837`)
- [x] Inventory rules 28/28 (`scripts/verify/inventory_rules.py`)
- [x] Home/footer layout 46/46 across 11 widths (`scripts/verify/home_footer_layout.js`)
- [x] Hero headline: "Reflect Your Aura." default confirmed by founder brief (2026-10-16); optional override setting added in Phase 3
- [ ] Deferred until provider decisions: object storage (R2 or other), hosting (Railway/Pages), `.python-version`

## Not verified in sandbox
- [x] 3 admin aggregation tests on real MongoDB: PASS on MongoDB 8.0.34, Atlas test cluster, 2026-10-17 (DATABASE_DISCOVERY_AND_TEST_VERIFICATION.md §10)
- [x] Concurrent checkout oversell protection on real MongoDB: PASS (10 orders for 3 units → 3), 2026-10-17
- [~] Product images / Google Fonts loading
- [~] Real iOS Safari / Android Chrome devices

## Phase 3 — Responsive UI/UX (details: `RESPONSIVE_UI_AUDIT.md`)
- [x] Audit 17 pages × 14 viewports, before/after, screenshots inspected (`scripts/verify/responsive_audit.js`)
- [x] Mobile/tablet hero in first view; 44px "Enter the Edit" (`b814f33`)
- [x] Tablet menu + desktop nav (`b241b74`)
- [x] Footer duplication removed, 44px targets (`b3429b5`) — founder review of round-3 row change
- [x] Missing-photo frames no longer collapse to 0px (`9526579`)
- [x] Product, cart, checkout, track-order, contact spacing/targets (`66fb345`, `ddaf208`, `230bcea`, `c27e264`, `2b6d0d0`, `edfbff9`, `0717bf4`)
- [x] Admin labels, touch actions, 44px controls, error states (`99d992e`, `31c88dc`, `410e2ff`, `0717bf4`)
- [x] Focus visibility, reduced motion (`5e9c82e`, `13d112c`)
- [x] Stale failed-login toast (`99d992e`)
- [x] "Reflect Your Aura." default + safe override setting (`b814f33`, `909ea53`)
- [x] All automated responsive criteria 0 across 238 combinations; 60/60, 28/28, 47/47, 7/7
- [~] Product photography evaluation (images unreachable in sandbox)
- [~] Native iOS Safari / Android Chrome
- [ ] Expose `hero_headline_override` in Admin > Settings (optional, founder decision)
- [x] Admin thumbnails: graceful missing-image placeholder (`d1c00cd`, Phase 4)
- [ ] `CartContext` localStorage write hardening

## Phase 4 — Backend, admin & database (details: `BACKEND_ADMIN_VERIFICATION.md`)
- [x] Auth audit: 401/403 cases, all admin endpoints guarded, no password_hash leak
- [x] Login lockout not bypassable via X-Forwarded-For (`0b20351`, `TRUSTED_PROXY_HOPS`)
- [x] Draft/inactive never published by stock changes (`c99e949`)
- [x] Product validation, slug uniqueness, CSV import status/price rules (`c99e949`)
- [x] Order counters on real transitions; dashboard day in Dhaka time (`c99e949`)
- [x] Atomic stock reservation; duplicate cart lines (`9a96ca4`); concurrent case verified on MongoDB 8.0.34 (2026-10-17)
- [x] Public /settings allowlist (`af8839c`); JSON 500 with CORS (`ca355a9`); no API docs in production (`af4ca80`)
- [x] Production refuses weak JWT_SECRET / ADMIN_PASSWORD (`8347452`); 12/12 unsafe configs refused at startup
- [x] Non-blocking object storage calls (`0b36fcd`)
- [x] Admin retries, error messages, thumbnails (`a4efdc9`, `0e31374`, `d1c00cd`)
- [x] Public exposure sweep (12 endpoints) and direct purchase attempts — 61/61
- [x] No secrets in git (all branches)
- [x] Emergent storage dependency audit + migration plan; read-only `scripts/storage/audit_image_refs.py` (`9ca179a`)
- [ ] Run image-reference audit and data-quality queries on real data (B-21)
- [ ] Export images from Emergent object storage while reachable (migration step 2)
- [x] Restock on cancel/return: manual for launch (Inventory → Adjust stock); workflow designed, UI parked (`docs/deferred/`), backend not built — Phase 4B
- [ ] DECISION: approve the dedicated stock-return workflow before it is built
- [ ] DECISION: storage provider
- [ ] Before adding staff accounts: enforce admin roles (B-16), review JWT lifetime/storage (B-17)
- [x] Index plan + dry-run migration tool; rehearsed on test DB 12/13 (`c4ec513`) — Phase 4B
- [ ] Apply indexes on real data after backup + integrity check (founder-approved maintenance window)

## Phase 4B — Data integrity & checkout safety (details: `PRODUCTION_DATA_INTEGRITY.md`)
- [x] Duplicate orders from concurrent double-submits fixed (8 → 1) via `_id` key claim (`8ac43dc`)
- [x] Full rollback on failed order incl. customer write (`8ac43dc`); tolerate unique customers.phone (`6493a1f`)
- [x] Real-MongoDB release-check script (`afa6991`) — 7 pass / 0 fail / 5 NOT VERIFIED on FerretDB
- [x] Read-only `data_integrity.py` + offline tests proving it never writes (`4078f2e`)
- [x] Dry-run `index_migration.py`, `--apply` test-DB only (`c4ec513`)
- [x] Stock-return UI parked as patch; active app makes no call to a missing endpoint (`54b2ee6`)
- [x] Image export/migration manifest tooling; run on TEST data (`6d6a0cd`)
- [x] Crash / multi-worker review documented (no transactions; in-memory login limiter)
- [x] VERIFIED on MongoDB 8.0.34 (Atlas `aayna-dev`/`aayna_release_test`): dashboard aggregation, low-stock filter, customer list/detail, 10×3 concurrent orders, concurrent multi-item atomicity, duplicate-order idempotency, rollback
- [ ] Run data_integrity.py, index_migration.py (dry run) and the image manifest on the REAL database (needs authorization + access)
- [ ] Export originals from Emergent (storage paths + CDN URLs) while reachable; founder list for missing/deleted
- [ ] Apply unique indexes (incl. customers.phone, orders.client_request_id partial) after backup
- [ ] Consider MongoDB transactions (replica set) to close crash windows; persistent login limiter before multiple workers

## Database discovery & isolated verification (details: `DATABASE_DISCOVERY_AND_TEST_VERIFICATION.md`)
- [x] Database identified: production NOT provisioned (Atlas Flex planned only, no credentials); real data only in the founder PC's local MongoDB (`aayna_dev`, backup `aayna_test`); Emergent/Vercel/live domain UNKNOWN or not inspectable
- [x] Isolated official-MongoDB runner `scripts/verify/run_isolated_mongo_checks.py` (own mongod, fresh dir, non-default port, loopback, generated creds, webhook off, scrubbed logs)
- [x] Release checks refuse non-loopback hosts and any instance holding real AAYNA data
- [x] Runner plumbing + guards self-tested on a stand-in (verdict correctly NOT VERIFIED); suites unchanged
- [x] Five MongoDB checks + duplicate-order/rollback on official MongoDB: release 16/0/0, backend 62/62, pytest 123 passed + 1 skipped (storage), integrity 0 BLOCKER / 2 REVIEW
- [~] Runner throwaway-`mongod --auth` path (unused; the Atlas path was used instead)
- [x] Founder created dedicated Atlas test cluster `aayna-dev` (M0, Singapore), user `aayna_test_app` (readWrite on `aayna_release_test` only), /32 network access
- [x] Exact-allowlist guard for every write-capable test entry point; `test_database` and all real DB names refused (`2abf543`); 27 offline tests
- [x] Runner `--atlas-env` mode with live privilege/cluster checks, gitignored credentials file, scrubbed logs (`3544f27`, `d04d072`)
- [x] Approved Atlas host pinned exactly: `aayna-dev.gzn5qto.mongodb.net` (from authenticated Atlas UI); lookalike tests (`42ce6a2`)
- [x] Founder's `.env.release-test` host corrected (was missing); `--check-only` reached official MongoDB 8.0.34, identity + isolation verified
- [x] Guard requires database-wide readWrite on `aayna_release_test` and nothing else (positive evidence)
- [x] FOUNDER: `aayna_test_app` role corrected to database-wide readWrite on `aayna_release_test`
- [x] `--check-only` then the full Atlas run: verdict PASS (evidence `docs/audits/evidence/atlas/`)
- [ ] DEFECT (medium, confirmed on MongoDB): concurrent first orders from one phone create duplicate customers. Fix = unique `customers.phone` index after merging existing duplicates; then re-run the Atlas suite with the unique indexes applied to the test DB
- [x] REVIEW explained: inventory-log `new_stock` is a snapshot that can include other requests' in-flight reservations; stock itself correct (sum of logged changes = movement). Optional later: refine the log fields or the integrity heuristic
- [ ] FOUNDER: back up local `aayna_dev`/`aayna_test` before any migration; authorize read-only diagnostics on it

## Phase 5A — Local data protection & customer-phone migration (details: DATABASE_DISCOVERY_AND_TEST_VERIFICATION.md §11)
- [~] Back up local `aayna_dev`: BLOCKED. No MongoDB on the founder PC (all drives, services, registry checked); Docker Desktop stopped and not inspected
- [ ] FOUNDER: say where the real AAYNA data lives (other PC? Docker container? Emergent only?) or approve starting Docker Desktop for a read-only look
- [x] Backup tool with content-hash verification + RESTORE.txt (`scripts/backup/backup_local_db.py`), tested
- [x] Read-only diagnostics extended (normalized-phone dupes, SKU/image gaps, orphan orders), phone numbers never printed; `--aggregate-only`
- [x] Deterministic, logged, reversible customer merge (`merge_duplicate_customers.py`), 7 offline tests; test targets only
- [x] `index_migration.py`: preflight/rollback documented, duplicate values redacted; `ensure_indexes` keeps unique indexes
- [x] Atlas with unique indexes: merge rehearsal 10/10 (exact rollback), release 22/0/0, backend 62/62, pytest 123+1 skip; first-time same-phone x10 -> 1 customer
- [x] Emergent storage not contacted when the key is empty (startup, upload 503, files 404); offline tests
- [ ] On real data (after backup + founder approval, maintenance window): diagnostics -> merge plan -> review -> apply -> verify -> unique indexes

## Phase 5B — Product photography (details: PRODUCT_PHOTOGRAPHY_INTEGRATION.md)
- [x] 33 photos inventoried (32 + Naira excluded), all readable, no duplicates; checksums recorded
- [x] 32 copied byte-for-byte to `aayna-website-assets/product-photos` (outside git) with MANIFEST; source unchanged (verified twice)
- [x] 10 groups map 1:1 to the 10 spreadsheet SKUs via importer dry run (0 partial/ambiguous/orphan)
- [x] Storefront: shared image-order rule, PDP gallery (all photos, no crop), alt text, lazy/async; 110/110 desktop+mobile; audits clean
- [ ] DECISION: Crystal Stone Cuff SKU suffix SLV vs golden photos (photo 4 shows a silver cuff too)
- [ ] DECISION: Cuff -> bracelets category; primary-photo proposal; selling prices for the 10 SKUs
- [ ] DECISION: image delivery route (importer + object storage / static frontend assets / new CDN), then import as draft into the located real DB

## Phase 5 — Production readiness (not started)
- [x] Backend suite, backend_admin_checks and mongo_release_checks on real MongoDB (test cluster): exit 0, 2026-10-17
- [ ] Repeat against the provisioned production-shaped staging DB before launch (with unique indexes)
- [ ] Migrate product images off Emergent; host-independent image URLs
- [ ] Payment approach (founder decision — do not implement before confirmation)
- [ ] Legal entity (Vellora Mercantile International) disclosures — verified details only

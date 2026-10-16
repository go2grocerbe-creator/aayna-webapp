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
- [~] 3 admin aggregation tests on real MongoDB (dashboard keys, low-stock filter, customers) — still NOT VERIFIED after Phase 4 (MongoDB downloads blocked; see BACKEND_ADMIN_VERIFICATION.md §2)
- [~] Concurrent checkout oversell protection on real MongoDB (FerretDB is not atomic)
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
- [x] Atomic stock reservation; duplicate cart lines (`9a96ca4`) — concurrent case NOT VERIFIED (needs MongoDB)
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
- [~] NOT VERIFIED (real MongoDB blocked): dashboard aggregation, low-stock filter, customer list/detail, 10×3 concurrent orders, concurrent multi-item atomicity
- [ ] Run data_integrity.py, index_migration.py (dry run) and the image manifest on the REAL database (needs authorization + access)
- [ ] Export originals from Emergent (storage paths + CDN URLs) while reachable; founder list for missing/deleted
- [ ] Apply unique indexes (incl. customers.phone, orders.client_request_id partial) after backup
- [ ] Consider MongoDB transactions (replica set) to close crash windows; persistent login limiter before multiple workers

## Phase 5 — Production readiness (not started)
- [ ] Re-run backend suite, backend_admin_checks and mongo_release_checks on real MongoDB (exit 0 required)
- [ ] Migrate product images off Emergent; host-independent image URLs
- [ ] Payment approach (founder decision — do not implement before confirmation)
- [ ] Legal entity (Vellora Mercantile International) disclosures — verified details only

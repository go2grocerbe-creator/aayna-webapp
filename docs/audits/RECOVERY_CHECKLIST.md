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
- [ ] Founder confirms fixed hero headline (admin hero-headline setting now unused)
- [ ] Deferred until provider decisions: object storage (R2 or other), hosting (Railway/Pages), `.python-version`

## Not verified in sandbox
- [~] 3 admin aggregation tests on real MongoDB (dashboard keys, low-stock filter, customers)
- [~] Product images / Google Fonts loading
- [~] Real iOS Safari / Android Chrome devices

## Phase 3 — Responsive UI/UX (not started)
- [ ] Full matrix screenshots for every major page (320→1920, portrait/landscape)
- [ ] Mobile hero first-viewport empty space
- [ ] Hero CTA (25 px) and footer bottom-nav (~16 px) tap targets
- [ ] Sparse desktop header navigation
- [ ] Stale failed-login toast after successful admin login
- [ ] `CartContext` localStorage write hardening

## Phase 4/5 — Backend safety & production readiness (not started)
- [ ] Re-run backend suite on real MongoDB
- [ ] Migrate product images off Emergent CDN; choose storage provider
- [ ] Payment approach (founder decision — do not implement before confirmation)
- [ ] Legal entity (Vellora Mercantile International) disclosures — verified details only

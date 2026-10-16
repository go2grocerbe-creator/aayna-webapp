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
- [~] 3 admin aggregation tests on real MongoDB (dashboard keys, low-stock filter, customers)
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
- [ ] Admin thumbnails: graceful missing-image placeholder (minor)
- [ ] `CartContext` localStorage write hardening

## Phase 4/5 — Backend safety & production readiness (not started)
- [ ] Unhandled 500s should keep CORS headers (browser currently reports them as network errors)
- [ ] Re-run backend suite on real MongoDB
- [ ] Migrate product images off Emergent CDN; choose storage provider
- [ ] Payment approach (founder decision — do not implement before confirmation)
- [ ] Legal entity (Vellora Mercantile International) disclosures — verified details only

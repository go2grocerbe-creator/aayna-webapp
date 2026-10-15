# AAYNA — Repository Recovery Audit (Phase 1) and Restore Report (Phase 2)

Date: 2026-10-15 · Branch: `chore/production-consolidation-20261015` · Operator: Claude (AI engineer), for Vellora Mercantile International / AAYNA

Status legend: **VERIFIED** (executed, evidence below) · **NOT VERIFIED** (could not be executed — reason given) · **OPEN** (known, not addressed in this phase)

---

## 1. Starting state

| Item | Finding | Evidence |
|---|---|---|
| Branch audited | `chore/production-consolidation-20261015` @ `744db79`, fresh clone from GitHub, clean working tree | `git status -sb` |
| Founder's local checkout `E:\deMarkt\aayna-webapp` | **NOT VERIFIED** — folder access was requested from the session and not granted in time. Any unpushed local work there has not been inspected. | — |
| `E:\deMarkt\deMarkt` (connected folder) | Contains only the separate BuyOS repo (`aayna-product-scout-agent`, branch `chore/buyos-ai-memory`) and planning docs. Not modified. | `ls`, `.git/HEAD` |
| `main` | `5885d59` (2026-10-04) — the Vercel "meeting showcase". **Not touched.** | `git log origin/main` |

## 2. Lineage and the pre-Vercel reference

`3e047816` ("chore: remove Emergent runtime marker", tip of `feat/emergent-launch-integration-v1`, merged as PR #3) is the strongest recovery reference. The consolidation branch is exactly:

```
3e04781  (pre-Vercel reference, full ecommerce app)
 └ 1a7d85d  Merge PR #3
   ├ d29e2dc  fix(deploy): configure repository root     → adds root package.json (Vercel build wrapper)
   ├ 1a38256  fix(deploy): serve React build              → adds vercel.json
   ├ 0a662ef  fix(deploy): align Vercel output            → vercel.json
   ├ 589a3b0  fix(storefront): missing backend URL        → lib/api.js hardening
   ├ aefe8d3  hotfix(demo): stable meeting showcase       → REPLACES App.js with static showcase
   ├ 5885d59  hotfix(demo): showcase mobile-first         → App.js showcase restyle   (= main)
   ├ a0bac23  chore: remove Vercel config                 → deletes vercel.json
   └ 744db79  docs: PRODUCTION_STANDARD.md
```

`git diff --stat 3e04781 744db79` touches only 4 files: `frontend/src/App.js`, `frontend/src/lib/api.js`, root `package.json`, `docs/PRODUCTION_STANDARD.md`.

### Did the showcase bypass the ecommerce app?
**Yes.** At `744db79`, `frontend/src/index.js` renders `App`, and `App.js` was a self-contained static page (hero + three hard-coded category names, no router, no providers, no API). None of the 11 storefront pages, 11 admin screens, `Layout`, `CartProvider` or `Analytics` were imported — but every one of them was still present and unchanged in the tree.

### Other branches (compared with `3e04781`)

| Branch | Commits not in reference | Assessment |
|---|---|---|
| `implementation/digital-mirror-storefront-v1`, `redesign/brand-book-v1`, `redesign/digital-mirror-v1`, `design/digital-mirror-system`, `fix/webapp-seo-social-launch` | 0 | Fully contained in the reference (ancestors). Nothing to recover. |
| `launch/aayna-readiness-v1` | 1 (`c563a8a` PDP tablet overflow) | Same one-line fix already in reference via `bd4ceca` (`overflow-hidden` present at `ProductDetail.jsx:175`). Nothing to recover. |
| `chore/lean-deployment-readiness` | 2 (`c563a8a`, docs plan) | Hosting-cost planning doc only. Not merged (hosting not chosen). |
| `conflict_300926_2111` | 7 | Subset of `feat/aayna-real-inventory-v1`. |
| **`feat/aayna-real-inventory-v1`** | **11** (2026-09-29 → 10-02) | **Unmerged, potentially valuable — needs founder decision.** Contains: founder visual edits rounds 1–3 (`Home.jsx`, `Footer.jsx`, `index.css`); real-inventory importer `scripts/import_inventory.py` + tests; "draft products blocked from cart/checkout"; admin owns price/images/stock; Cloudflare R2 storage (`storage.py`); production DB guard; Cloudflare Pages robots/sitemap functions; Railway install fix (removes the Emergent-hosted `litellm`/`emergentintegrations` requirements). Mixes storefront work with hosting/paid-storage choices, so it was **not** merged in this phase (rule: do not merge every historical branch; do not choose hosting). |

## 3. Preservation and removal register

### KEEP (working, necessary — unchanged)
- `backend/server.py`, `admin_routes.py`, `auth.py`, `db.py`, `seed_data.py` — FastAPI + Motor/MongoDB. Production guards present: refuses to boot in production with missing/default `JWT_SECRET` / `ADMIN_*`, wildcard `CORS_ORIGINS`; demo seeding blocked in production unless `ALLOW_PRODUCTION_SEED=true`.
- `backend/tests/` (+ `conftest.py` test-DB safety gate: refuses any DB name without "test").
- Storefront: `frontend/src/pages/*` (Home, Shop, Category, ProductDetail, Cart, Checkout, OrderConfirmation, TrackOrder, Contact, StaticPage, NotFound), `components/{Layout,Header,Footer,AnnouncementBar,WhatsAppFloat,ProductCard,ProductGrid,ProductImage,TheEdit,Analytics}.jsx`, `components/ui/*` (46 shadcn primitives), `context/CartContext.jsx`, `hooks/useStore.js`, `lib/{seo,format}.js`.
- Admin: `frontend/src/admin/*` (AdminAuthContext, AdminLayout + `AdminProtected` guard, AdminLogin, ImageUpload, adminApi, 10 pages).
- Brand system: `tailwind.config.js` `aayna-*` tokens, `design_guidelines.json`, `DESIGN.md`, `AAYNA_FRONTEND_VISION.md`.
- `frontend/src/lib/api.js` hardening from `589a3b0` (same-origin `/api` fallback instead of `undefined/api`, 10 s timeout) — host-agnostic, kept.
- `docs/PRODUCTION_STANDARD.md` — release gates.

### RESTORE (done in Phase 2)
- `frontend/src/App.js` — restored byte-for-byte from `3e04781` (`git diff 3e04781 -- frontend/src/App.js` is empty).

### REFACTOR
| Item | Status |
|---|---|
| API failures were shown as "Product/Category not found" or "0 pieces" | **Fixed** in Phase 2 (see §4). |
| `frontend/package.json` devDependency `@emergentbase/visual-edits` fetched from `assets.emergent.sh` — blocks `yarn install --frozen-lockfile` on any host that cannot reach Emergent | **Fixed** — removed; `craco.config.js` already treats it as optional (dev-only overlay). Lockfile diff is exactly that 4-line entry. |
| `backend/requirements.txt` pins `emergentintegrations` and `litellm @ https://customer-assets.emergentagent.com/...` — unused by backend code (`grep` finds no import), blocks clean `pip install` off-Emergent | **OPEN** — a fix exists on `feat/aayna-real-inventory-v1` (`9ded808`); bring in with that branch decision. |
| `backend/storage.py` uploads via Emergent object storage (`integrations.emergentagent.com`) — fails off-Emergent (logged at startup in test) | **OPEN** — R2 replacement exists on `feat/aayna-real-inventory-v1`; storage provider is a founder/hosting decision. |
| Seed/demo product images hosted on `static.prod-images.emergentagent.com` | **OPEN** — real product images must be migrated before launch. |
| Admin dashboard: a failed-login toast remains visible after a subsequent successful login | **OPEN** (cosmetic). |
| Mobile homepage: first viewport is mostly empty decorative space with the headline at the bottom | **OPEN** — Phase 3 responsive audit. |
| `CartContext` writes `localStorage` without try/catch (throws in some private-browsing contexts) | **OPEN** — minor hardening. |

### REMOVE
| Item | Status |
|---|---|
| Static meeting showcase in `App.js` | **Removed** (replaced by restored router). History retained in Git. |
| Root `package.json` (Vercel build wrapper `aayna-webapp-deployment`) | **Removed** — no other consumer; frontend builds from `frontend/`. |
| `vercel.json` | Already removed in `a0bac23`. |
| Historical branches | **Not deleted** (per instructions). |

## 4. Phase 2 — changes made

| Commit scope | Files |
|---|---|
| Restore real ecommerce router | `frontend/src/App.js` |
| Remove Vercel root build wrapper | `package.json` (root, deleted) |
| Make frontend installable off-Emergent | `frontend/package.json`, `frontend/yarn.lock` |
| Distinguish API failure from not-found | new `frontend/src/components/LoadError.jsx`; `pages/ProductDetail.jsx`, `pages/Category.jsx`, `components/TheEdit.jsx` |
| Audit + repeatable verification | this file, `scripts/verify/storefront_routes.js`, `docs/audits/evidence/phase2/*.png` |

API-failure behaviour after the fix: a real `404` still renders "not found" with `noindex`; a network error, timeout or `5xx` renders a retryable "We couldn't load … right now" state (`data-testid="load-error"`, `role="alert"`, 44 px buttons) with `noindex`, and The Edit no longer shows "0 pieces" while loading or on error. No backend, API contract, data or styling-system changes.

## 5. Verification (Phase 2)

### Environment used
- Frontend: production build (`craco build`) served by a static SPA server on `localhost:3000`.
- Backend: `uvicorn server:app` on `localhost:8001` with `APP_ENV=test`, `DB_NAME=aayna_pytest`, throwaway generated `JWT_SECRET` / admin credentials (not stored in the repo).
- Database: MongoDB itself could not be downloaded in the sandbox (egress to `fastdl.mongodb.org` blocked), so **FerretDB 1.24 (MongoDB wire-compatible, SQLite backend)** was used as a disposable test database. No real, development or production data was read or written.
- Browser: Playwright 1.56 + Chromium (headless), 375×812, 390×844 (touch/mobile), 1280×800.

### Results

| Check | Result |
|---|---|
| `yarn install --frozen-lockfile` | **PASS** after removing the Emergent-hosted devDependency (failed before) |
| `CI=true yarn build` (lint warnings = errors) | **PASS** — "Compiled successfully", 194 kB JS / 13 kB CSS gzip |
| Frontend unit tests | **NOT VERIFIED** — none exist in the repo |
| Backend `pytest tests/` | **120 passed, 1 skipped, 3 failed.** The 3 failures (`TestDashboard::test_dashboard_keys`, `TestInventory::test_low_stock_only`, `TestCustomers::test_list_and_detail`) are FerretDB `NotImplemented` errors (`$first` in `$group`; `$lte` inside `$match/$expr`), which real MongoDB supports → **NOT VERIFIED here**, must be re-run on MongoDB. Backend code unchanged in this phase. |
| Browser checks (`scripts/verify/storefront_routes.js`) | **60/60 PASS** on a fresh test DB |

Browser checks covered:
- All 14 routes (`/`, `/shop`, `/category/:slug`, `/product/:slug`, `/cart`, `/checkout`, `/track-order`, `/contact`, 4 policy pages, 404, `/admin/login`) at 375 px and 1280 px: correct shell (storefront header/footer, or standalone admin login), correct `<h1>`/`<title>`, **no horizontal overflow**, no uncaught errors, no failed `/api` responses, showcase absent.
- Mobile journey (390 px, touch): menu → Shop → product card → PDP (price in ৳) → quantity +1 → Add to Cart → header badge 2 → reload → cart persisted (`localStorage.aayna_cart`) → Cart subtotal → Checkout blocks empty submit → fill form → **order created (`ORD-1001`)** → confirmation page → cart cleared. Stock decremented 5 → 3 on the test DB.
- Admin: `/admin`, `/admin/products`, `/admin/orders`, `/admin/customers` redirect to `/admin/login` when unauthenticated; login page is `noindex,nofollow`; wrong credentials rejected with message; valid test admin reaches dashboard; products/orders/inventory/categories/settings render; the test order is visible in admin orders.
- API unreachable (all `/api` requests aborted): no blank screen or crash; `/shop`, `/product/:slug`, `/category/:slug` show the retryable error state, not "not found".
- Unknown product/category slugs still show "not found" + `noindex`.
- Public `GET /api/products` payload keys checked: no `cost_price`, `supplier_*`, `internal_notes`, `margin`.

### NOT VERIFIED in this phase
- Image loading and Google Fonts: the sandbox cannot reach `static.prod-images.emergentagent.com` or `fonts.googleapis.com`; image tiles render as empty placeholders in screenshots.
- Real MongoDB behaviour of the 3 aggregation endpoints above.
- iOS Safari / Android Chrome real devices; full 11-width responsive matrix (Phase 3).
- The founder's local checkout for unpushed work.

Evidence screenshots: `docs/audits/evidence/phase2/`.

## 6. Risks and decisions needed

1. **`feat/aayna-real-inventory-v1`** — 11 unmerged commits including founder-approved Home/Footer edits and the real-inventory importer. Recommend cherry-picking the storefront/inventory commits (founder edits, importer, draft-product cart block) onto this branch, and deferring R2/Railway/Cloudflare-Pages commits until hosting and storage are chosen. Requires founder confirmation.
2. **Emergent platform dependencies** remain in backend requirements, image storage and image URLs — the app is not yet deployable off Emergent end-to-end.
3. Local checkout at `E:\deMarkt\aayna-webapp` not inspected.

## 7. Next recommended task
Founder decision on item 6.1, then Phase 3 responsive audit across the full viewport matrix using `scripts/verify/storefront_routes.js` as the regression gate, run against real MongoDB with real product images reachable.

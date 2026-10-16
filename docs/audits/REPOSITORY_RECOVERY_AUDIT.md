# AAYNA — Repository Recovery Audit (Phase 1) and Restore Report (Phase 2)

Date: 2026-10-15 · Branch: `chore/production-consolidation-20261015` · Operator: Claude (AI engineer), for Vellora Mercantile International / AAYNA

Status legend: **VERIFIED** (executed, evidence below) · **NOT VERIFIED** (could not be executed — reason given) · **OPEN** (known, not addressed in this phase)

---

## 1. Starting state

| Item | Finding | Evidence |
|---|---|---|
| Branch audited | `chore/production-consolidation-20261015` @ `744db79`, fresh clone from GitHub, clean working tree | `git status -sb` |
| Founder's local checkout `E:\deMarkt\aayna-webapp` | **VERIFIED 2026-10-15 (see §8)** — no unpushed commits, no stash; only an untracked `.claude/settings.local.json`. (At the time of the Phase 1 audit this was not yet accessible.) | §8 |
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
| `backend/requirements.txt` pins `emergentintegrations` and `litellm @ https://customer-assets.emergentagent.com/...` — unused by backend code (`grep` finds no import), blocks clean `pip install` off-Emergent | **Fixed** in `ff41837` (recovered from `9ded808`, see §8). |
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

1. ~~`feat/aayna-real-inventory-v1`~~ — **done**: storefront, inventory and safety work selectively recovered; provider-specific parts deferred (see §8).
2. **Emergent platform dependencies** remain in backend requirements, image storage and image URLs — the app is not yet deployable off Emergent end-to-end.
3. Local checkout at `E:\deMarkt\aayna-webapp` not inspected.

## 7. Next recommended task
Founder decision on item 6.1, then Phase 3 responsive audit across the full viewport matrix using `scripts/verify/storefront_routes.js` as the regression gate, run against real MongoDB with real product images reachable.


---

## 8. Inventory & design recovery (2026-10-15, follows Phase 2)

Base: `5a1821f`. Head after this step: see commit list below. Source branch `feat/aayna-real-inventory-v1` (`9ded808`) was **not** merged wholesale; each commit was reviewed and applied selectively.

### 8.1 Local checkout check — VERIFIED
Read-only inspection of `E:\deMarkt\aayna-webapp\Aayna-Webapp` (git run with `GIT_OPTIONAL_LOCKS=0`, nothing written, no lock files left):
- Checked-out branch `launch/aayna-readiness-v1` @ `13d6c0c`; local refs last fetched ~2026-09-30 (stale, not a problem).
- `git status`: only `?? .claude/settings.local.json` (local editor settings — not app code, left untouched).
- No stash. `git log <branch> --not --remotes` is empty for every local branch.
- Local-only branches `chore/aayna-webapp-ai-memory` (`9d000b8`), `fix/webapp-hardening-batch` (`070ca7e`), `fix/webapp-security-launch-blockers` (`9c81e06`) have no upstream, but all three commits are already contained in `origin/main` and in this consolidation branch.
- **Conclusion: no local work is at risk.** Recommend `git fetch` + switching the local checkout to `chore/production-consolidation-20261015` when convenient (not done — local repo not modified).

### 8.2 Commit-by-commit decisions for `feat/aayna-real-inventory-v1`

| Source | Content | Decision | Recovered as |
|---|---|---|---|
| `eaabfe3` | Visual round 1: hero fixed to "Reflect Your Aura.", remove "আয়না — mirror." subline, glassy mirror-disc sheen (reduced-motion aware), Bracelets in Digital Mirror, footer tagline | **Recovered** (frontend paths) | `443346f` |
| `b50dea5`, `fd98a89`, `9ac08b8`, `3b991d8` | `.emergent` marker toggles / agent log messages, no code | Skipped | — |
| `df65c6a` | Visual round 2: burgundy category accent, Add to Cart under mirror preview, footer brand copy | **Recovered** (frontend paths; marker file excluded) | `a4186e9` |
| `2b23813` | Visual round 3: charcoal→burgundy on hover/focus/active, footer bottom nav to all 8 pages | **Recovered** (frontend paths; marker excluded) | `0c5951c` |
| `509bd26` | `scripts/import_inventory.py` (xlsx + photos → **draft** products, dry-run manifest, idempotent by SKU), offline tests, **cart/validate + checkout reject non-public statuses**, manifest gitignored | **Recovered whole** | `0a7c6be` |
| `1e1c322` | `--temp-price` flagged `price_is_temporary`; re-imports never overwrite admin-owned price/status/images/live stock; admin price save clears the flag; Main image kept at `images[0]` | **Recovered whole** | `21d871b` |
| `1340203` | (a) production DB guard in `auth.py` + tests; (b) S3/R2 storage backend; (c) `image_storage` on `/api/health/ready`; (d) Cloudflare Pages functions; (e) R2 checklist rows | **(a) only** — b–e are provider decisions | `2c89acb` |
| `9ded808` | (a) drop unused Emergent-hosted `emergentintegrations` / `litellm` requirements; (b) `.python-version` 3.13→3.12 for Railway; (c) Railway baseline doc | **(a) only** | `ff41837` |

Recovered files match the source branch byte-for-byte for `Home.jsx`, `Footer.jsx`, `index.css`, `import_inventory.py`, `test_inventory_import.py`, `ImageUpload.jsx`, `admin_routes.py`. `server.py` differs from the source only by the excluded `image_storage` health field.

**Explicitly not present on this branch:** `frontend/functions/`, S3/R2 code in `storage.py`, `OBJECT_STORAGE_*` usage, Railway `.python-version` change. No product media migrated; no production or development database touched.

### 8.3 Validation

Environment as §5 (isolated `aayna_pytest` on FerretDB, generated throwaway credentials, Chromium via Playwright). DB reset before each suite.

| Check | Result |
|---|---|
| `pip install -r backend/requirements.txt` in a fresh venv, **unmodified file** | **PASS** (previously failed on the Emergent-hosted wheel) |
| `rm -rf node_modules && yarn install --frozen-lockfile` | **PASS** |
| `CI=true yarn build` | **PASS** — 194.9 kB JS / 13.3 kB CSS gzip |
| Backend `pytest backend/tests` | **120 passed, 1 skipped, 3 failed** — same 3 FerretDB `NotImplemented` cases as §5 (no regression); **NOT VERIFIED** on real MongoDB |
| Offline `pytest backend/tests_import` (importer + DB guard) | **7/7 PASS** |
| `scripts/verify/inventory_rules.py` (business rules over HTTP) | **28/28 PASS** (`evidence/inventory-recovery/inventory_rules_output.txt`) |
| Same rules against pre-recovery backend `5a1821f` | **20/27** — draft and inactive products **could be ordered by id** (HTTP 200, stock decremented). Proves the recovered block is effective. |
| `scripts/verify/storefront_routes.js` (Phase 2 gate) | **60/60 PASS** — routing, cart, checkout, admin guard, API-down states unchanged |
| `scripts/verify/home_footer_layout.js`, 11 widths 320→1920, before vs after | **46/46 PASS** |

Business rules verified (28): admin endpoints refuse unauthenticated requests; draft and inactive products are absent from public list/detail, flagged unavailable by `/cart/validate`, refused by `/checkout` even with a known id, stock untouched; active purchase decrements stock (3→1); oversell refused with stock unchanged; last unit flips status to `out_of_stock`; out-of-stock refused; public product list/detail, categories, checkout response and token-gated order confirmation contain none of `cost_price`, `internal_notes`, `supplier_*`, `landed_cost`, `margin`, `price_is_temporary`; order confirmation without token is 404; admin price change clears `price_is_temporary`; admin restock returns an out-of-stock product to `active` but keeps a draft as `draft`.

Layout (after build): no horizontal overflow and no clipped hero headline at 320/360/375/390/430/768/820/1024/1280/1440/1920; no uncaught errors; Bracelets present; mirror category buttons ≥ 44 px; sheen animates and is disabled under `prefers-reduced-motion`; footer bottom nav lists and navigates to all 8 pages; tablet touch (1024 px, no hover): tap Bracelets → preview → Add to Cart adds the product; phone (390 px): the preview panel is hidden by design (`hidden md:flex`), tapping a category selects it and shows that category's products. Screenshots: `evidence/inventory-recovery/`.

### 8.4 Findings and open items from this step
| Item | Status |
|---|---|
| Hero headline is now fixed text (approved round 1); the admin **"hero headline" setting no longer affects the homepage** | Known effect of founder decision — confirm intended |
| Hero "Enter the Edit" CTA is 25 px tall (same before and after) | **OPEN** — Phase 3 |
| Footer bottom-nav links are ~16 px tall tap targets and duplicate the column links | **OPEN** — Phase 3 |
| Mirror preview Add to Cart is tablet/desktop only by design; phones rely on the category edit below | Design note — Phase 3 review |
| Importer uploads through the backend's current `storage.py` (still Emergent object storage) | **OPEN** — blocked on storage-provider decision; importer itself is provider-neutral |
| 3 admin aggregation tests unverified on real MongoDB; image loading unverified in sandbox | **NOT VERIFIED** |


---

## 9. Phase 3 (2026-10-16)
Responsive UI/UX audit and repair recorded separately in `RESPONSIVE_UI_AUDIT.md`.

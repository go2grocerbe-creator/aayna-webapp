# AAYNA Infrastructure Baseline (L5.1)

The approved production architecture, and exactly what's been prepared
in the repository versus what still requires a founder to actually create
an account and click "deploy." No credentials in this file. Nothing
described here has been provisioned — see "Remaining blockers."

## Frontend — Cloudflare Pages

| Setting | Value | Source |
|---|---|---|
| Root directory | `frontend` | Repo layout (monorepo) |
| Build command | `yarn build` | `frontend/package.json` pins `"packageManager": "yarn@1.22.22..."` and ships `yarn.lock` (no `package-lock.json`) — Cloudflare Pages auto-detects yarn from these; using `npm run build` would work but drift from the pinned lockfile. `yarn build` runs the same underlying `"build": "craco build"` script either way. |
| Output directory | `build` | CRA/craco default, confirmed via a real local build this milestone |
| Node version | `20` | Pinned via `frontend/.nvmrc` (added this milestone — no `engines` field existed before; React 19 + craco 7 need a modern Node, 20 LTS is a safe, standard floor) |
| SPA routing | **No extra config needed** | Verified against current Cloudflare Pages docs: a project with no top-level `404.html` automatically routes every unmatched path to `index.html`. CRA never generates a `404.html`, and this app's own `NotFound.jsx` is a React Router route, not a static file — so the default behavior is already correct. A `_redirects` file was deliberately **not** added; it would be redundant. The one constraint: never add a top-level `404.html` to `frontend/public/`, or this silently breaks. |
| Production env | `REACT_APP_BACKEND_URL=https://api.shopaayna.com`, `REACT_APP_PUBLIC_SITE_URL=https://shopaayna.com` | Set in Cloudflare Pages project settings, Production environment only — not in this repo |
| Preview env | `REACT_APP_BACKEND_URL=` (Railway-generated URL, not production), `REACT_APP_PUBLIC_SITE_URL=` unset | Set separately in Cloudflare Pages project settings, Preview environment |
| Production branch | **Not yet set to `launch/aayna-readiness-v1` or `main`** | Per explicit instruction: deploy the launch branch as a **preview** first; do not attach `shopaayna.com` to an unverified preview |

Invalid product/category not-found states (L4) render entirely
client-side via React Router + `useSeo({ noindex: ... })` — they return
a normal `200` with a JS-rendered "not found" UI, not a server-level 404
status. Cloudflare's SPA fallback is fully compatible with this: it only
governs what's served for a path Cloudflare itself can't find a static
file for (i.e., every app route), not what the React app then renders —
so L4's behavior is unaffected either way.

## Backend — Railway

| Setting | Value | Source |
|---|---|---|
| Root directory | `backend` | Set via Railway dashboard/CLI (`railway environment edit --service-config <name> source.rootDirectory /backend`) — this is **not** a `railway.json` field, confirmed against current Railway docs; documented here rather than forced into config-as-code |
| Install | Auto-detected from `backend/requirements.txt` (Railway's default Python builder) | No custom build command needed |
| Start command | `uvicorn server:app --host 0.0.0.0 --port $PORT` | `backend/railway.json` (committed this milestone). Confirmed entrypoint is `server:app` — no `__main__` block exists, `app = FastAPI(...)` is the real object, matches exactly |
| Healthcheck | `GET /api/health/ready` | Same file — pings MongoDB and re-validates production config before Railway promotes a deploy; confirmed this leaks no secrets |
| Restart policy | `ON_FAILURE` | Same file |
| Region | `asia-southeast1-eqsg3a` (Singapore) | Same file, via `deploy.multiRegionConfig`, `numReplicas: 1` (Hobby-appropriate — not attempting horizontal scaling) |
| Python version | `3.13` | Pinned via `backend/.python-version` (added this milestone, matches the actual local dev venv — Railway's Python builder respects this file) |
| Custom domain | `api.shopaayna.com` — **not yet added** | Railway generates the required CNAME/verification record only once the domain is attached to an existing service; nothing is guessed here (§Domain below) |

## Database — MongoDB Atlas Flex (Singapore)

| Setting | Value |
|---|---|
| Tier | Flex — chosen over the free/shared tier specifically because a real ecommerce launch needs managed daily backups, which Flex includes and the free tier does not |
| Region | Singapore |
| Production DB name | `aayna_prod` |
| Staging DB name | `aayna_staging` |
| Credentials | Not created — requires an authenticated Atlas account/founder action |
| Database user isolation | Production and staging should each get their own scoped Atlas database user (read/write on their own DB only) rather than sharing one, and never the org/founder admin Atlas login in application env — a decision to apply at actual provisioning time, not implemented here |
| Network access | Railway Hobby has no fixed outbound IP for this setup — Atlas's IP allowlist can't be scoped to one address at this tier. Practical options: allow `0.0.0.0/0` and rely on strong per-environment DB credentials as the real access control, or move to a Railway tier with a static-IP feature if that becomes necessary. No private/VPC-peered connection exists between Railway Hobby and Atlas — not claimed here |
| Backups | Atlas Flex retains standard **daily snapshot** history (verify the exact retention window at actual provisioning — plan-dependent). **Not** point-in-time recovery — that's an M10+ feature, not being adopted for this MVP |

## DNS / Domain — Cloudflare DNS

| Route | Target | Status |
|---|---|---|
| `shopaayna.com` | Cloudflare Pages production | Not configured — zone/domain ownership unconfirmed in this repo (below) |
| `www.shopaayna.com` | 301 → `https://shopaayna.com` | Not configured |
| `api.shopaayna.com` | Railway backend | Not configured — Railway must generate its verification record first |
| HTTP | → HTTPS | Automatic once TLS is issued on both hosts |

**Domain ownership: `DOMAIN OWNERSHIP — FOUNDER ACTION REQUIRED`.** Nothing
in this repository or its docs proves `shopaayna.com` is currently
registered/owned. No replacement domain was searched for or suggested —
the approved canonical stays `shopaayna.com` regardless.

No DNS record was created, changed, or guessed at in this milestone.

## Staging strategy

Cloudflare Pages preview deployments (automatic per-branch/per-PR,
including this milestone's `launch/aayna-readiness-v1`) plus a Railway
service pointed at the separate `aayna_staging` Atlas database, using the
provider-generated URLs (Cloudflare preview URL, Railway
`*.up.railway.app` URL) — **not** `staging.shopaayna.com` /
`api-staging.shopaayna.com`. Those subdomains stay a later, optional
addition per explicit instruction; not configured now. Staging may
contain synthetic staging orders (mirroring this session's `ORD-1052`
pattern); production may not.

## Production data strategy

See `PRODUCTION_DATA_MIGRATION_PLAN.md` for the full allowlist. Summary:
`aayna_dev` is never cloned. Production/staging both start from the same
clean, allowlisted catalogue + settings export; production starts with
zero orders/customers, staging may accumulate synthetic ones. Not
executed until `aayna_prod`/`aayna_staging` actually exist.

## Object storage — deferred

All six current launch product images resolve from a stable external CDN
URL (`static.prod-images.emergentagent.com`, seeded via
`backend/seed_data.py`), independent of whichever host serves this app.
**Re-verified this milestone: all six still resolve** (spot-checked
during L5.1 build/QA — same URLs seen live in L4/L5). No object storage
integration (Cloudflare R2, S3, Cloudinary, or the existing Emergent
objstore mechanism) is configured or needed for initial launch.

**Future note:** when Admin image upload becomes operationally required
(replacing the current scaffold demo images with real product
photography, or adding new products with new photos), migrate
`backend/storage.py`'s upload path to a production-owned, persistent
object store. Cloudflare R2 was the researched recommendation in
`L5_DEPLOYMENT_READINESS.md` §40 (zero egress cost, fits Cloudflare's
existing DNS/Pages relationship) — not decided or built here.

## Confirmation-token access-log remediation (L5.1)

`L5_DEPLOYMENT_READINESS.md` §23-24/36 flagged that the order-confirmation
token, passed as a URL query parameter, could appear in plaintext in
routine access logs. Investigated across every logging layer this
milestone:

| Layer | Finding | Action |
|---|---|---|
| Frontend URL / browser history | The token sat in the visible address bar and browser history for the life of the tab, with no expiry | **Fixed** — `OrderConfirmation.jsx` now captures the token once on mount, then replaces the URL (`navigate(..., { replace: true })`) to drop the query string, with no extra history entry and no refetch. Verified live via CDP: URL becomes the clean path immediately, `history.length` unchanged. |
| Uvicorn access log | Confirmed live (L5): the full raw token appeared in the access-log line for its own verification request | **Fixed** — a `logging.Filter` on the `uvicorn.access` logger (`server.py`) redacts the `token=` value to `token=REDACTED` before it's written. Verified live: a real request with a token no longer leaves the raw value in the log; a request with no token param is unaffected; the log line's normal format/shape is preserved (this took two iterations to get right — uvicorn's access formatter unpacks `record.args` by fixed position rather than doing plain `%`-substitution, so the filter redacts matching string elements in place rather than replacing `record.msg`/`record.args` wholesale). |
| Application-level logging | Reviewed `send_order_notification` and all other `logger.*` calls touching an order — none log the raw token, only `order_number` | No action needed |
| Railway edge/HTTP request logs | **Unresolved, verify at deploy time.** Railway's own HTTP-log schema (confirmed via current docs) exposes fields named `method`, `path`, `httpStatus`, `srcIp`, etc. — no separate "query string" field is documented, which suggests `path` may be logged without the query string, but this isn't confirmed either way from available documentation. Hobby-plan HTTP logs retain for 48 hours regardless. | **Action required after the Railway service exists**: send one real request with a test token to a live deployment and inspect `railway logs --http` (or the dashboard) to see whether the query string appears in the `path` field. If it does and there's no Railway-side redaction option, treat this as a **pre-launch security consideration** — the token's own validation/hashing stays untouched either way (never weakened), but a data-retention decision (e.g., is the 48-hour Hobby-tier window acceptable) belongs to a founder, not silently accepted here. |

No confirmation-token validation logic was weakened. No order is
reachable by `order_number` alone (unchanged, still requires the correct
token hash match). No large redesign was performed — both fixes are
small, targeted, and additive.

## Estimated platform cost structure

Research-derived, not vendor-quoted (`L5_DEPLOYMENT_READINESS.md` §40 has
the full comparison and its own caveats — figures below are the ones
relevant to what was actually approved):

| Component | Estimated monthly cost | Notes |
|---|---|---|
| Cloudflare Pages | $0 | Free tier is production-suitable for a low-traffic static frontend |
| Railway (Hobby, Singapore) | ~$5 base + metered usage | No free tier on Railway as of this research; Hobby is the practical always-on floor |
| MongoDB Atlas Flex | Low, usage-based (below the M10 dedicated-tier cost) | Exact figure depends on actual read/write/storage volume — not quoted without a live account; chosen over the free M0 tier specifically for included daily backups |
| Cloudflare DNS | $0 | DNS itself is free; only a domain registration cost applies if the domain isn't already owned/renewed |
| Object storage | $0 (deferred) | Not provisioned |

**This is a directional estimate for founder budgeting, not a quote.**
Confirm real numbers against each provider's live pricing page and
actual usage once accounts exist.

## Remaining blockers

1. **No provider account/project exists yet** — Cloudflare Pages,
   Railway, and Atlas Flex all need to actually be created; nothing was
   provisioned this milestone per explicit instruction.
2. **Domain ownership of `shopaayna.com`** — unconfirmed in this repo;
   founder action required.
3. **All secrets** (`JWT_SECRET`, `ADMIN_PASSWORD`, `MONGO_URL` with real
   credentials) — must be generated by a founder/authorized system, not
   invented here.
4. **Railway edge HTTP-log query-string behavior** — unverified until a
   real deployment exists to test against (see table above).
5. **Support contact channel** — still `MISSING`, unchanged since L3.1;
   blocks accepting real customer orders, not blocking staging
   deployment itself.
6. **Order-status transition guards / automatic stock restoration on
   Cancel/Return** — proposed rule documented in
   `LAUNCH_OPERATIONS_RUNBOOK.md` §H, awaiting founder approval before
   any implementation.
7. **Real product photography** — current launch images are stable but
   are Emergent scaffold demo images, not real AAYNA product photos; a
   content decision, not an infrastructure one.

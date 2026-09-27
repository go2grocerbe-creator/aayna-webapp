# AAYNA — $5/month deployment readiness (pre-purchase)

Status: preparation only. No service provisioned, payment approved, production credentials generated, DNS changed, or production deployment completed.

## Target and architecture

- Spending ceiling: USD $5/month initially, not a guarantee of actual usage.
- Candidate: one Railway Hobby FastAPI service, MongoDB Atlas M0 (free), and a commercial-use-permitted free static host for the React build. Do not activate services until the gates below pass. Confirm current provider terms and Railway usage estimates at purchase time.
- Do not deploy a separate always-on frontend server or MongoDB on Railway. No paid analytics, messaging or background worker.
- `shopaayna.com` is a known project domain, but DNS control and final frontend/API subdomains must be verified before configuration. Use placeholders below, not guessed URLs.

## Verified code observations

- React CRA/CRACO build: `frontend/package.json` uses `yarn build`. API base is compile-time `REACT_APP_BACKEND_URL` in `frontend/src/lib/api.js`; set it before building, with no trailing `/api`.
- FastAPI entry point: `backend/server.py`, app `server:app`, API under `/api`. Readiness endpoint `GET /api/health/ready` checks database and production config. Liveness `/api/health` does not test DB.
- MongoDB: `backend/db.py` reads `MONGO_URL` and `DB_NAME`; production must use its own account/database and must never be the dev or test database.
- `APP_ENV=production` rejects missing/default JWT/admin credentials, placeholder site URL, wildcard/empty CORS, and enabled webhook without URL.
- `ALLOW_PRODUCTION_SEED=false` prevents automatic demo catalogue/settings seeding; a real catalogue and verified storefront settings must be entered separately.
- Public product projection is allowlisted in `backend/server.py`; verify cost/supplier/internal fields remain absent from public responses after deployment.
- **Blocking portability risk:** `backend/storage.py` uses Emergent object storage through `EMERGENT_LLM_KEY`, initializes on startup but catches failures, and serves product images through `/api/files/...` backed by MongoDB `files` records. Confirm off-Emergent access, ownership, retention and export/migration of existing images before taking orders or changing image URLs.
- **Build portability risk:** frontend dependency `@emergentbase/visual-edits` and backend `litellm` direct Emergent-hosted wheel in `requirements.txt`; verify clean install/build off Emergent. Do not remove dependencies blindly.
- `backend/tests/conftest.py` drops its test database; only run against a separately provisioned disposable database and backend, as described in `ENVIRONMENTS.md`. Never run pytest against preview/founder or production DB.

## Private environment template — placeholders only

Backend host secrets (never commit real values):

```dotenv
APP_ENV=production
MONGO_URL=<production Atlas URI stored as host secret>
DB_NAME=<new dedicated production database name>
JWT_SECRET=<unique strong random secret>
ADMIN_EMAIL=<founder-approved admin email>
ADMIN_PASSWORD=<unique strong password>
PUBLIC_SITE_URL=https://<verified storefront hostname>
CORS_ORIGINS=https://<verified storefront hostname>
ALLOW_PRODUCTION_SEED=false
ORDER_WEBHOOK_ENABLED=false
ORDER_WEBHOOK_URL=
EMERGENT_LLM_KEY=<only if independently verified portable; otherwise resolve storage first>
```

Frontend build-time configuration (public, not a secret):

```dotenv
REACT_APP_BACKEND_URL=https://<verified API hostname>
```

No real secrets, customer data or supplier costs in source control, screenshots, logs, or chat.

## Release gates before paying or connecting DNS

1. Confirm actual host architecture and commercial-use permission of free static host; check Railway estimate against $5 ceiling. Configure spend alerts; note hard caps can take the shop offline.
2. Clean off-Emergent frontend build and backend dependency install, with version pinning/lockfile verified.
3. Confirm storage works outside Emergent; upload, retrieve, restore and migrate images; ensure old catalogue images do not break. If not portable, plan a provider change before production deployment (cost to be approved).
4. Design encrypted daily database backup to independent storage and demonstrate restoration into an isolated DB. Atlas M0 has no managed cloud backups. No customer orders before this passes.
5. Provision isolated production Atlas database/user with least privilege, TLS, restricted network access appropriate to the host; no test/demo data migration.
6. Set host environment secrets privately, build frontend with correct API URL, restrict CORS to exact frontend origin, use HTTPS, verify health/ready and startup.
7. Validate SPA deep-link fallback and `/admin` noindex; test robots/sitemap/canonical/Open Graph URLs and Product structured data against actual domain.
8. Test admin login/permissions, uploads, inventory, COD/manual checkout only after founder-approved payment settings, order tracking privacy, real shipping/returns/contact settings, mobile checkout, and public API field allowlist.
9. Use a disposable isolated test DB for full automated suite; conduct non-destructive production smoke tests only.
10. Founder approves launch catalogue, operations and rollback plan. Record final spend and alert thresholds.

## Deployment commands (illustrative, not executed)

Backend service root: `backend`; install dependencies after clean-install validation; start: `uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}`. Readiness: `/api/health/ready`.

Frontend root: `frontend`; install with repository's Yarn lockfile; build: `yarn build`; output: `build`. Configure SPA fallback without swallowing real API, robots or sitemap endpoints. Verify whether `PUBLIC_SITE_URL`/SEO API routing requires same-origin proxying rather than assuming separate-host deployment is equivalent.

## Explicitly unresolved

Hosting account access, commercial static-host choice, domain DNS control, production Atlas credentials, admin identity/password, storage portability, backup destination, real catalogue/settings, payment activation, order notification destination and actual resource consumption. None is silently approved by this document.

# AAYNA Deployment Runbook

No real secrets in this file. No hosting provider is chosen yet (see
`L5_DEPLOYMENT_READINESS.md` for the decision packet) — this is the
sequence to follow once one is. Every stage references the actual
mechanisms already implemented in this repo; nothing here is invented
infrastructure.

## 1. Choose/confirm hosting

Pick a frontend static host, a backend process host, and a MongoDB
target. See `L5_DEPLOYMENT_READINESS.md` for the comparison packet — this
is a founder decision, not made here.

## 2. Provision production database

Create a **new, dedicated** MongoDB database — never reuse `aayna_dev`,
`aayna_pytest`, or `aayna_test`. Note the connection string and database
name; you'll need them for `MONGO_URL`/`DB_NAME` in step 4. Do not import
`aayna_dev` wholesale — see `PRODUCTION_DATA_MIGRATION_PLAN.md`.

## 3. Configure secrets

Generate a real `JWT_SECRET` (`python -c "import secrets;print(secrets.token_hex(32))"`),
choose a strong unique `ADMIN_PASSWORD`, and a real `ADMIN_EMAIL`. Set
these directly in your hosting provider's environment-variable UI/CLI —
never commit them, never put them in this repo.

## 4. Configure backend

Set, on the backend host: `APP_ENV=production`, `MONGO_URL`, `DB_NAME`,
`JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS` (the real
frontend origin), `PUBLIC_SITE_URL` (the real domain). See
`PRODUCTION_ENV_CHECKLIST.md` for the full variable list. The backend
**will refuse to start** (`validate_security_config()`) if any of the
critical ones are missing, default, or unsafe — this is intentional and
already implemented; do not work around it.

## 5. Deploy backend

Deploy via your chosen host's normal process for a FastAPI/uvicorn app.
On first successful boot, `seed_admin()` creates the admin account from
`ADMIN_EMAIL`/`ADMIN_PASSWORD` automatically — no separate bootstrap
script or manual DB write is needed. `seed_database()` will **not**
auto-seed demo catalogue data in production unless `ALLOW_PRODUCTION_SEED`
is explicitly set (existing safeguard, confirmed in code) — the real
launch catalogue is imported per `PRODUCTION_DATA_MIGRATION_PLAN.md`
instead of relying on the dev seed data.

## 6. Health check

- Liveness: `GET /api/health` (fast, no DB touch)
- Readiness: `GET /api/health/ready` (pings MongoDB + re-validates prod
  config; 503 if not ready — point your host's health-check/readiness
  probe here, not at `/api/health`)

Both are already implemented and verified this milestone to leak no
secrets, DB URI, or credentials.

## 7. Configure frontend backend URL

Set `REACT_APP_BACKEND_URL` (frontend env, build-time) to the real
deployed backend URL from step 5. Never `localhost`/`:8000`/`:8001`.

## 8. Build frontend

`REACT_APP_PUBLIC_SITE_URL` = real domain (optional — self-corrects at
runtime if unset, but set it for consistency). Then `npx craco build`
from `frontend/`. Verify the output has no `localhost`, no unreplaced
`%…%` tokens, and no test-catalogue references (same checks performed in
L4, re-run them against the real production env values).

## 9. Deploy frontend

Deploy the `frontend/build` output to your chosen static host.

## 10. Configure domain

Point the real domain at both hosts (frontend host for the apex/www,
backend host for the API — either as a subdomain like `api.shopaayna.com`
or via the frontend host's own rewrite/proxy rule, depending on what's
chosen in step 1). See §43 of `L5_DEPLOYMENT_READINESS.md` for the DNS
checklist shape — no records are guessed here.

## 11. HTTPS

Use your chosen hosts' built-in TLS (all mainstream static/PaaS hosts
issue free certificates automatically for a connected custom domain) —
do not hand-roll certificate management for a lean MVP.

## 12. CORS verification

After deploy, confirm `CORS_ORIGINS` on the backend exactly matches the
real frontend origin (and `https://www.` variant only if www is actually
served/redirected). Test with a real browser request from the live
frontend, not just `curl` (browsers enforce CORS; `curl` doesn't).

## 13. SEO verification

Re-run the L4 CDP `<head>` snapshot approach against the live production
URLs: confirm canonical/OG/robots/sitemap all resolve to the real domain
with zero `localhost` leakage. Submit the sitemap per step 17.

## 14. Admin bootstrap

Log in at `/admin/login` with the `ADMIN_EMAIL`/`ADMIN_PASSWORD` set in
step 3. Change nothing else here — this already happened automatically
in step 5.

## 15. Seed/import real catalogue safely

Follow `PRODUCTION_DATA_MIGRATION_PLAN.md` — legitimate categories and
products only, no dev/test data, no order/customer history.

## 16. End-to-end production smoke

Run `BASE_URL=https://your-real-domain ./scripts/smoke_test.sh` (already
exists, read-only, no orders placed). Then perform **one** real,
low-value manual order yourself (a founder/team member, real payment
method available — COD) to prove the live path end-to-end exactly once,
the same way `ORD-1052` proved it in dev this milestone. Do not automate
or repeat this against production.

## 17. Search Console

Once the domain is live and DNS-resolving: verify ownership in Google
Search Console (real verification method chosen at that time — DNS TXT
or HTML file, whichever the provider supports), submit
`{PUBLIC_SITE_URL}/sitemap.xml`, request indexing for the homepage.

## 18. Rollback

See `L5_DEPLOYMENT_READINESS.md` §34 for what rollback readiness
currently means (repo-level: previous commit is always checkable via
git; infra-level: depends entirely on the host chosen in step 1, most
mainstream PaaS/static hosts keep previous deploys one click away — this
is not yet configured and is a step-1-dependent detail, not invented
here).

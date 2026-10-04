# AAYNA Deployment Runbook

No real secrets in this file. **Infrastructure is now decided**
(`INFRASTRUCTURE_BASELINE.md`): Cloudflare Pages (frontend), Railway /
Singapore (backend), MongoDB Atlas Flex / Singapore (database),
Cloudflare DNS. **Nothing has been provisioned yet** — no project has
been created in any of these three, per this milestone's explicit
no-provisioning constraint. This is the sequence to follow once a
founder authorizes provisioning.

## 1. Choose/confirm hosting

**Done.** Cloudflare Pages + Railway (Singapore,
`asia-southeast1-eqsg3a`) + MongoDB Atlas Flex (Singapore). See
`INFRASTRUCTURE_BASELINE.md` for the full rationale.

## 2. Provision production database

Create a MongoDB **Atlas Flex** cluster, Singapore region. Create a
**new, dedicated** database — never reuse `aayna_dev`, `aayna_pytest`, or
`aayna_test`. Use naming: `aayna_prod` (production), `aayna_staging`
(staging, step-17-of-L5.1 concept — see §17 of `L5_DEPLOYMENT_READINESS.md`).
Create a scoped Atlas database user per environment (production user →
`aayna_prod` only; staging user → `aayna_staging` only) — never the
founder/org admin Atlas credentials in application env. Note the
connection string; you'll need it for `MONGO_URL` in step 4. **Do not
import `aayna_dev` wholesale** — see `PRODUCTION_DATA_MIGRATION_PLAN.md`.

Network access: Railway's Hobby plan does not provide a fixed outbound
IP for this setup (confirmed — no static-IP add-on at this tier), so
Atlas's IP-allowlist cannot be scoped to a single known Railway IP. The
practical, honest options are: (a) allow access from anywhere (`0.0.0.0/0`)
and rely on the database username/password + a strong, unique,
per-environment credential as the actual access control, or (b) upgrade
Railway if a static-IP feature becomes available/needed later. Do not
pretend a private-network/VPC-peered connection exists between Railway
Hobby and Atlas — it doesn't at this tier. Document whichever is chosen
at provisioning time; this is a founder call given the actual constraint,
not invented here.

## 3. Configure secrets

Generate a real `JWT_SECRET` (`python -c "import secrets;print(secrets.token_hex(32))"`),
choose a strong unique `ADMIN_PASSWORD`, and a real `ADMIN_EMAIL`. Set
these directly in **Railway's** environment-variable UI for the backend
service — never commit them, never put them in this repo.

## 4. Configure backend

In Railway, create the service with **root directory `backend`**
(monorepo — Railway must not build from the repo root). Set:
`APP_ENV=production`, `MONGO_URL` (step 2), `DB_NAME=aayna_prod`,
`JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS=https://shopaayna.com`,
`PUBLIC_SITE_URL=https://shopaayna.com`. See `PRODUCTION_ENV_CHECKLIST.md`
for the full variable list. The backend **will refuse to start**
(`validate_security_config()`) if any of the critical ones are missing,
default, or unsafe — intentional, already implemented, do not work
around it. `backend/railway.json` (committed this milestone) already
declares the start command, healthcheck path, restart policy, and
Singapore region — Railway picks it up automatically once the service is
linked to this repo.

## 5. Deploy backend

Deploy via Railway (root directory `backend`, install auto-detected from
`requirements.txt` by Railway's default Python builder — no custom build
command needed). On first successful boot, `seed_admin()` creates the
admin account from `ADMIN_EMAIL`/`ADMIN_PASSWORD` automatically — no
separate bootstrap script or manual DB write is needed. `seed_database()`
will **not** auto-seed demo catalogue data in production unless
`ALLOW_PRODUCTION_SEED` is explicitly set (existing safeguard, confirmed
in code) — the real launch catalogue is imported per
`PRODUCTION_DATA_MIGRATION_PLAN.md` instead.

## 6. Health check

Railway is configured (`backend/railway.json`) to use
`GET /api/health/ready` as its deploy healthcheck — it pings MongoDB and
re-validates production config; Railway only promotes a deployment after
this returns 200. `GET /api/health` (liveness, no DB touch) is also
available if a separate liveness check is ever needed. Both are already
implemented and verified this milestone to leak no secrets, DB URI, or
credentials.

## 7. Configure frontend backend URL

In **Cloudflare Pages** project settings, set `REACT_APP_BACKEND_URL` for
the **Production** environment to `https://api.shopaayna.com` (only once
step 10's custom domain is live on Railway — until then, use the
Railway-generated `*.up.railway.app` URL as a placeholder so the build
isn't pointed at nothing). Set the **Preview** environment's
`REACT_APP_BACKEND_URL` to the Railway-generated service URL directly —
preview builds must never point at the production API. Never
`localhost`/`:8000`/`:8001` in either.

## 8. Build frontend

Cloudflare Pages builds this automatically per its own project settings
(root directory `frontend`, build command `yarn build`, output directory
`build`, Node version pinned via `frontend/.nvmrc` — see
`INFRASTRUCTURE_BASELINE.md` for exactly why these values, not the
generic `npm run build` guess). Set
`REACT_APP_PUBLIC_SITE_URL=https://shopaayna.com` for Production only
(Preview: leave unset — self-corrects to the preview URL at runtime).
After any build, spot-check the output has no `localhost`, no unreplaced
`%…%` tokens, and no test-catalogue references (same checks performed in
L4/L5.1, re-run against real production env values).

## 9. Deploy frontend

Connect the Cloudflare Pages project to this repo. **Deploy
`launch/aayna-readiness-v1` as a preview first** (per this milestone's
explicit instruction) — do not set it as the production branch and do
not attach `shopaayna.com` to it yet. Cloudflare Pages' default SPA
fallback (verified via current Cloudflare docs this milestone: any
project without a top-level `404.html` automatically routes all
unmatched paths to `index.html`) already handles React Router correctly
— no `_redirects` file was added because none is needed; adding one
would be dead configuration. The one constraint: never introduce a
top-level `404.html` into `frontend/public/` or the build output, or
this default breaks silently.

## 10. Configure domain

**Railway first, then Cloudflare** — Railway will generate the exact
CNAME/TXT verification records once a custom domain (`api.shopaayna.com`)
is attached to the backend service; those values do not exist yet and
are never guessed here. Add them to Cloudflare DNS exactly as Railway
returns them. Cloudflare Pages similarly provides its own target for the
apex (`shopaayna.com`) once a Pages custom domain is added. Eventual
target state (§11 of `L5_DEPLOYMENT_READINESS.md`, §21-22 of the L5.1
instructions):
```
shopaayna.com       → Cloudflare Pages production
www.shopaayna.com    → 301 redirect to https://shopaayna.com
api.shopaayna.com   → Railway backend
```
Do not configure any of this until the Cloudflare zone and Railway
service actually exist and a founder authorizes the change.

## 11. HTTPS

Both Cloudflare Pages and Railway issue free TLS certificates
automatically for a connected custom domain — no manual certificate
management for this lean MVP.

## 12. CORS verification

After deploy, confirm `CORS_ORIGINS` on the backend exactly matches
`https://shopaayna.com` (add `https://www.shopaayna.com` only if www
ends up served rather than redirected — per §21, the plan is redirect,
so it should not be needed). Test with a real browser request from the
live frontend, not just `curl` (browsers enforce CORS; `curl` doesn't).

## 13. SEO verification

Re-run the L4 CDP `<head>` snapshot approach against the live production
URLs: confirm canonical/OG/robots/sitemap all resolve to
`https://shopaayna.com` with zero `localhost` leakage. The static
`index.html` OG fallback already hardcodes this exact domain (L4,
reconfirmed current in L5.1 — no change needed). Submit the sitemap per
step 17.

## 14. Admin bootstrap

Log in at `/admin/login` with the `ADMIN_EMAIL`/`ADMIN_PASSWORD` set in
step 3. Nothing else to do here — this already happened automatically in
step 5.

## 15. Seed/import real catalogue safely

Follow `PRODUCTION_DATA_MIGRATION_PLAN.md` — legitimate categories and
products only, no dev/test data, no order/customer history. The six
launch product images need no migration — they already resolve from a
stable external CDN, independent of which host serves the app
(`INFRASTRUCTURE_BASELINE.md`, object storage deferred).

## 16. End-to-end production smoke

Run `BASE_URL=https://api.shopaayna.com ./scripts/smoke_test.sh`
(already exists, read-only, no orders placed). Then perform **one** real,
low-value manual order yourself (a founder/team member, real payment
method available — COD) to prove the live path end-to-end exactly once,
the same way `ORD-1052` proved it in dev this milestone. Do not automate
or repeat this against production.

## 17. Search Console

Once the domain is live and DNS-resolving: verify ownership in Google
Search Console (real verification method chosen at that time — DNS TXT
via Cloudflare DNS, or an HTML file, whichever the provider supports),
submit `https://shopaayna.com/sitemap.xml`, request indexing for the
homepage.

## 18. Rollback

Repo-level: previous commit always checkable via git. Railway keeps
prior deployments available to instantly roll back to (standard platform
feature, one click/CLI command) — verify at actual provisioning time,
not claimed as configured here. Cloudflare Pages keeps every prior
deployment as its own permanent preview URL and supports promoting any
of them back to production instantly — same caveat, verify when the
project exists. Atlas Flex retains standard daily snapshot backups (see
`INFRASTRUCTURE_BASELINE.md` — not point-in-time recovery, that's an M10+
feature not being adopted here). For local `aayna_dev`, `aayna_test`
remains the pre-L1 migration backup — explicitly not a production backup
strategy, just historical continuity.

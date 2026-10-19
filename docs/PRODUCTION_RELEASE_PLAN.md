# AAYNA production release plan (prepared 2026-10-19, not executed)

Release candidate: branch `feat/customer-accounts-20261018`. It is a fast-forward of `main`
(0 commits behind, 101 ahead), so the merge cannot conflict. Nothing in this plan has been run
against production. Every step that writes to production, DNS or Vercel production settings
waits for the founder's explicit approval.

## 1. Current state

| Item | State |
| --- | --- |
| Vercel production | `main` @ 5885d59 (demo showcase), deployment `dpl_9YPEq1LJahBvkNfoxpt6ZHH8P636`, domain `aayna-webapp.vercel.app` only |
| Deployment protection | Vercel login on every deployment except custom domains (`all_except_custom_domains`) |
| Production environment variables | none exist yet (every variable is Preview-scoped) |
| `shopaayna.com`, `www` | Cloudflare nameservers; A records point at Cloudflare proxy IPs; not attached to Vercel |
| `aayna_prod` (read-only check, 2026-10-19 21:20) | 10 products, all draft, 46 units; 4 categories; 1 super admin; 0 orders, 0 customers; 10 stock-in logs (+46); unique index `sku_unique`; no `website_settings`. Matches the 2026-10-18 import exactly |

Attaching `shopaayna.com` makes the shop public, because custom domains are not behind the Vercel
login. That step is therefore the go-live moment, after everything else is checked.

## 2. Production environment variables (Production scope only; values never in the repo)

| Variable | Value / source | Notes |
| --- | --- | --- |
| `APP_ENV` | `production` | |
| `DB_NAME` | `aayna_prod` | |
| `MONGO_URL` | Sensitive; `aayna_prod_app` user | the same user the import used |
| `JWT_SECRET` | Sensitive; new random value | must differ from every preview secret |
| `PUBLIC_SITE_URL` | `https://shopaayna.com` | email links, Google redirect, sitemap |
| `CORS_ORIGINS` | `https://shopaayna.com` | |
| `TRUSTED_PROXY_HOPS` | `1` | |
| `ORDER_WEBHOOK_ENABLED` | `false` | |
| `RESEND_API_KEY` | Sensitive | domain already verified in Resend |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Sensitive; production OAuth client | see section 4 |
| `STEADFAST_MODE` | leave unset (= off) until approved; then `live` | `docs/STEADFAST_COURIER.md` |
| `STEADFAST_API_KEY`, `STEADFAST_SECRET_KEY` | Sensitive; NEW keys (revoke any pasted in chat) | only when Steadfast is approved |
| `STEADFAST_REAL_BOOKINGS` | `true` only after the founder approves real parcels | |
| `CRON_SECRET` | Sensitive; any long random string | turns on the daily Steadfast tracking run (`frontend/vercel.json` crons, production only) |

Must NOT exist in Production: `ALLOW_PRODUCTION_SEED`, `PREVIEW_ADMIN_BOOTSTRAP`,
`EMAIL_LINK_PREVIEW_ACCESS`, `PREVIEW_CATALOGUE`, `EMAIL_MODE`, `EMAIL_CAPTURE_FILE`, and `STEADFAST_MODE=mock` (the simulator refuses `aayna_prod` anyway). `ADMIN_EMAIL`/`ADMIN_PASSWORD`
are not needed: an admin exists, so the first-run bootstrap skips and never changes it.

## 3. Domain (Cloudflare DNS, DNS only)

1. Vercel → project → Domains: add `shopaayna.com` (production) and `www.shopaayna.com`
   with a 308 redirect to `shopaayna.com`. Canonical = `https://shopaayna.com`.
2. Cloudflare → DNS: replace only the apex `A` records with the address Vercel's Domains page
   shows (on 2026-10-19: `216.198.79.1`, also `64.29.17.1`) and set `www` to
   `CNAME d86db8b75585f868.vercel-dns-017.com`, both **DNS only** (grey cloud) so Vercel issues
   and renews the certificate.
3. Do not touch MX, SPF/DKIM/DMARC TXT records, or the Resend sending subdomain records.
4. Check: `https://shopaayna.com` serves the site with a valid certificate,
   `https://www.shopaayna.com` → 308 → apex, `/robots.txt` and `/sitemap.xml` answer from
   the backend with `https://shopaayna.com` URLs.

## 4. Google sign-in for production

Preview Google sign-in was tested by the founder; production is untested until it runs on
`https://shopaayna.com`. Recommended: a separate production OAuth client in the same Google
Cloud project (preview credentials are readable by anyone with preview access).

- Authorised JavaScript origin: `https://shopaayna.com`
- Authorised redirect URI: `https://shopaayna.com/api/auth/google/callback` (exact; the code
  never adds a query string)
- OAuth consent screen publishing status: **In production** (in "Testing" only listed test
  users can sign in). Scopes are openid, email, profile.
- Then add the two values as Production-scoped Sensitive variables.

## 5. Backup and data checks (founder runs, read-only)

1. Counts baseline: `aayna-prod-import\4-inspect.bat` (read-only).
2. Backup: `python scripts/backup/backup_local_db.py --env-file <.env.prod-import> --dbs aayna_prod
   --production --out-root <aayna-private-backups>`. It is read-only, verifies every collection by
   count and content hash, writes `manifest.json` and `RESTORE.txt`, and refuses any database but
   `aayna_prod`. M0 clusters have no Atlas snapshots, so this file is the only backup: keep the
   folder on an encrypted drive, never in the repository or a shared folder.
3. Restore drill (optional): restore into `aayna_prod_restored`, compare counts, delete it.

What the first production start writes (expected, non-destructive): indexes on new empty
customer/promotion collections and a non-unique `orders.account_id` index. It does not seed,
does not touch products, settings or the admin account.

## 6. Release sequence

1. Founder approvals (checklist in the release report).
2. Backup + counts baseline (section 5).
2b. +৳100 price update (founder-approved 2026-10-19; NOT yet applied to `aayna_prod`):
    `python scripts/prices/apply_price_update_20261019.py --env-file <.env.prod-import>` (dry run,
    read-only) -> `... --apply --confirm aayna_prod` -> `... --verify`. Writes only `selling_price`,
    `previous_selling_price`, one `price_history` entry and `updated_at`; idempotent; rollback with
    `--rollback --confirm aayna_prod`. Targets: backend/price_targets.py.
3. Create the Production variables (section 2).
4. Fast-forward `main` to the release commit and push. Vercel builds the production deployment
   on `aayna-webapp.vercel.app` (still behind the Vercel login).
5. Verify on that protected URL: `/api/health` → `aayna_prod`; `/api/health/version` → release
   commit; `/api/health/ready` → ready; admin login (founder); counts unchanged (4-inspect);
   no public products; `/api/promotions/welcome` → disabled.
6. Founder sets Admin → Settings for production (announcement, contact). Delivery needs nothing:
   the founder's policy is the code default (backend/delivery.py) - ৳100 nationwide below a ৳1,500
   merchandise subtotal, free from ৳1,500, measured before discounts.
7. Go-live (separate approval): publish the approved products, attach the domain (section 3),
   verify HTTPS, redirects, robots, sitemap, Google sign-in, one order end to end.
8. Welcome offer: the founder-approved limits (10%, ৳1,000 minimum, ৳150 cap, 30 days, one
   redemption per customer, delivery excluded) are the recorded configuration; enable only when
   separately authorised.

## 7. Rollback

- Code: Vercel → Deployments → Instant Rollback to `dpl_9YPEq1LJahBvkNfoxpt6ZHH8P636`
  (`main` @ 5885d59), or revert the merge on `main`.
- Public access: remove the domain from the project or restore the previous Cloudflare A records.
- Data: the release only adds collections and indexes; they can stay. Restore from the
  section-5 backup only if production data was damaged, per `RESTORE.txt`.

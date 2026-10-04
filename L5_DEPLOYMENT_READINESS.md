# AAYNA L5 — Staging + Production Deployment Readiness

Operational QA and infrastructure-readiness assessment. No deployment
occurred. No infrastructure was provisioned. No credentials were invented.

> **L5.1 update:** the hosting decision this document's §40-42 left open
> is now made — Cloudflare Pages, Railway (Singapore), MongoDB Atlas Flex
> (Singapore), object storage deferred. See `INFRASTRUCTURE_BASELINE.md`
> for the approved architecture and `DEPLOYMENT_RUNBOOK.md` for the
> updated step-by-step. The findings below (§0-39, §43-53) are left as
> originally written — they're still accurate QA results, not
> infrastructure recommendations, and nothing here has been provisioned.

## Gate 0 — database reconciliation

Raw, direct, read-only counts against `aayna_dev` (not the public API):

| Collection | Raw total | Breakdown |
|---|---|---|
| products | 18 | 6 active + 4 out_of_stock (real, held-back) + 8 inactive (confirmed test) |
| categories | 10 | 6 active (3 launch + 3 real non-launch) + 4 inactive (confirmed test) |
| orders | 52 | 51 pre-existing dev/QA + 1 new (`ORD-1052`, this milestone's controlled QA order) |
| settings | 20 | Unchanged |
| customers | 3 | 2 pre-existing + 1 new synthetic QA customer (this milestone) |

**Matches the expected historical baseline exactly (18/10/51/20/2 before
this milestone's QA order added 1 order + 1 customer).** L4's reported
"10 products / 6 categories" was the **public API view** (`/api/products`
returns `status != inactive` = active + out_of_stock = 10;
`/api/categories` returns `status == active` = 6) — not a different raw
count, just a different, correctly-filtered lens on the same 18/10.

**Integrity issue: none found. CONTINUE.**

## 1. Git

```
Starting HEAD: ae432e0
Branch: launch/aayna-readiness-v1
```
Working tree was clean at start; no merge performed.

## 2-3. Infrastructure discovery

Searched repo root/subdirectories for `vercel.json`, `netlify.toml`,
`render.yaml`, `railway.json`, `fly.toml`, `Dockerfile`, docker-compose,
`Procfile`, nginx/Caddy config, Cloudflare config, `CNAME`, and
`.github/workflows/*` — **none exist**. The only infra-adjacent file is
`.emergent/emergent.yml` (an image name + job ID — build-scaffold
metadata from the original app generator, not a deployment target).
`README.md` documents a **generic assumed** "Kubernetes ingress" routing
model (`/api/*` → backend, else → frontend) as guidance for whichever
host is eventually chosen — this is written instruction, not evidence of
an actual live cluster. Git history confirms **no deployment has ever
occurred** for this app (only a documentation commit, "Milestone 4C:
deployment runbook, prod env template, final launch QA docs" — the README
sections this report builds on).

| Target | Status |
|---|---|
| Frontend deployment target | NOT CONFIGURED |
| Backend deployment target | NOT CONFIGURED |
| Database target | NOT CONFIGURED |
| Object storage target | PARTIALLY CONFIGURED — see §Object storage below |
| Existing deployment | NONE |

## 4. Production architecture requirements (actual stack)

React/CRACO static frontend + FastAPI/uvicorn backend (long-running
process — holds an async Motor client and in-memory login rate-limit
state, so not a fit for pure stateless serverless) + MongoDB + optional
object storage for admin image uploads. Minimum needed: a static host for
the frontend build, a process host for uvicorn, a MongoDB instance
reachable from that host, TLS on the public domain, and the env vars in
`PRODUCTION_ENV_CHECKLIST.md`. This is intentionally the full requirement
list — no message queue, no cache layer, no CDN beyond what the static
host provides natively; over-engineering was avoided.

## 5. Production database must be separate

Confirmed: nothing in this repo defaults production at any point to
`aayna_dev`/`aayna_pytest`/`aayna_test` — `DB_NAME` is a required env var
with no hardcoded fallback in production mode. `validate_security_config()`
does not currently check that `DB_NAME` is *different* from the known
dev names (it validates presence/format of `PUBLIC_SITE_URL`/`CORS_ORIGINS`/
secrets, not `DB_NAME` content) — this is a manual discipline point for
whoever sets `DB_NAME` at deploy time, not an automated guard. Noted, not
changed (adding that check would be a real, small, safe hardening — left
as a §51 observation rather than implemented, since no order/business
logic depends on it and this report's scope is audit-first).

## 6. Old `aayna_test` backup

Untouched. No cleanup performed or recommended in L5.

## 7. Production environment matrix

See `PRODUCTION_ENV_CHECKLIST.md` — full variable-by-variable inventory,
no secret values, every "value supplied" column correctly reads NO.

## 8-9. Domain

Canonical stays `https://shopaayna.com` (non-www) — this task's stated
fallback, unopposed by any existing config. DNS: not configured (no
provider chosen). HTTPS: not yet applicable (no hosting). www: undecided,
defer to whichever host is chosen (§10 below) — most static hosts handle
this with a one-click redirect rule once the domain is connected.

L4 hardcoded `https://shopaayna.com` into `frontend/public/index.html`'s
three static OG/Twitter tags as the working fallback (CRA has no native
token for a build-time-injected absolute URL beyond `%PUBLIC_URL%`, which
only resolves relative to the site root, not to an absolute domain).
**This should remain the permanent implementation** — it's not fragile
abstraction avoidance, it's the smallest reliable mechanism given CRA's
actual capabilities, and it self-documents where to look if the domain
changes. **Every location that must change if the canonical domain
changes:**
1. `frontend/public/index.html` — 3 lines (`og:url`, `og:image`, `twitter:image`)
2. `frontend/.env` (production) — `REACT_APP_PUBLIC_SITE_URL`
3. `backend/.env` (production) — `PUBLIC_SITE_URL`

Runtime SEO (the `useSeo()` hook, all per-page canonical/OG/JSON-LD) does
**not** need a code change — it already self-corrects to
`window.location.origin` when `REACT_APP_PUBLIC_SITE_URL` is unset, and
picks up the real value automatically once #2 is set.

## 10. Frontend → backend URL

`REACT_APP_BACKEND_URL` (frontend, build-time). **Confirmed empirically
this milestone**: today's `npx craco build` output bakes in
`http://localhost:8000` — the current `frontend/.env` dev value — because
no production value has been set yet. This is the expected, correct
current state (not a new bug); `DEPLOYMENT_RUNBOOK.md` step 7 exists
specifically to prevent shipping this. No backend production hostname is
invented here — infrastructure decision, §Hosting below.

## 11. CORS

`server.py`'s `CORSMiddleware` reads `CORS_ORIGINS` directly (defaults to
`*` only when unset — dev-only path). `validate_security_config()`
already refuses to boot in production with `CORS_ORIGINS` empty or `*`
(confirmed by direct code reading, `backend/auth.py:110-112`). No
wildcard+credentials risk survives into production. Once the real domain
exists, set `CORS_ORIGINS=https://shopaayna.com` (add
`https://www.shopaayna.com` only if www is actually served/redirected,
per §8-9).

## 12. Production security startup

Re-confirmed by direct code reading (not re-executed with fabricated
prod env, to avoid needing throwaway secrets): production boot refuses to
start on a missing/default `JWT_SECRET`, missing/default admin
credentials, empty/localhost `PUBLIC_SITE_URL`, empty/`*` `CORS_ORIGINS`,
or `ORDER_WEBHOOK_ENABLED=true` without `ORDER_WEBHOOK_URL`. No safeguard
was weakened. One earlier-session's own test file
(`backend/tests/test_aayna_health_config.py`) already exercises exactly
these cases against monkeypatched env — part of the 123 passing this
milestone.

## 13-14. Admin production readiness

Authentication: bcrypt password hashing, JWT (7-day TTL), in-memory
login rate-limiting (5 failed attempts → 15-minute lockout, single
process — note: won't share state across multiple backend instances if
ever horizontally scaled; a lean single-instance MVP is unaffected).
Admin API routes require the JWT dependency; storefront-facing routes
never expose admin data. Admin pages are `noindex` (confirmed, L4).

**Bootstrap mechanism — real, already implemented, verified by reading
`auth.py:seed_admin()`:** on every backend boot, if `ADMIN_EMAIL`/
`ADMIN_PASSWORD` are set, the account is created if missing or its
password hash is refreshed if the env value changed. No manual DB write,
no separate CLI, no seed script to run by hand.

```
ADMIN BOOTSTRAP: READY (mechanism) / NEEDS FOUNDER INPUT (real credentials)
```

## 15-16. Object storage & product image survival

`storage.py` integrates with **Emergent's own proprietary object-store
API** (`integrations.emergentagent.com/objstore`), gated by
`EMERGENT_LLM_KEY` — not a generic S3-compatible service. Currently
unset in dev; `init_storage_safe()` fails safely (logs an error, does not
crash the app — confirmed live in this session's dev backend log every
boot). The admin `/api/admin/upload` endpoint would fail with a clean 502
if used today without that key.

**Separately, and more importantly for launch:** all 6 current launch
product images are **not** served through this app's storage at all —
they're direct URLs to `static.prod-images.emergentagent.com`, seeded by
`backend/seed_data.py`. These are stable, absolute, third-party-hosted
URLs (confirmed live via the L4 CDP snapshot and this milestone's QA
order's stored `image` field) — not `localhost`, not ephemeral dev
storage. **They will survive a deployment unchanged.**

```
Can production Admin upload/change product images persistently? Only if EMERGENT_LLM_KEY is supplied and remains valid outside Emergent's own environment — unverified, real open question, flagged as a founder/infra decision, not resolved here.
Product image survival: READY (URLs are stable and third-party-hosted)
```

Separately — not new, already flagged in `README.md`'s own launch
checklist — the current images are Emergent scaffold demo photography,
not real AAYNA product photos. That's a content gap, not a technical
one; restated here only because §16 asked the survival question directly.

## 17. Staging strategy

Lightest safe model for this stack: a second backend process (or a
second deploy on the same PaaS) pointed at a **separate** staging
MongoDB database (logical name suggestion only: `aayna_staging` — not
created here), plus a preview/staging deploy of the frontend build
pointed at that backend. Do not point staging at `aayna_dev` (real
founder catalogue/settings, mixed with dev QA noise) or at the future
production database. Provisioning is deferred to §Hosting below — no
staging infrastructure was created in this milestone.

## 18-30. Controlled QA order — `ORD-1052`

Placed against `aayna_dev` (confirmed safe per the explicit local-QA
allowance: webhook disabled, no email/SMS gateway exists in this codebase
at all, synthetic customer identity used throughout).

```
Product: Minimal Silver Stud Earrings (EAR-SV-0003)
Stock before: 8
Qty ordered: 1
Stock after: 7  (verified: decremented by exactly the ordered quantity, inventory_logs entry recorded — sale, -1, prev 8, new 7)
Subtotal: ৳280.00
Delivery (Dhaka): ৳80.00  (matches LAUNCH_SETTINGS_BASELINE.md exactly)
Total: ৳360.00
client_request_id: exact repeat of the same request returned {"duplicate": true} with the SAME order_number, stock unchanged on retry — idempotency confirmed working
```

Delivery cross-check (structural, not a second order): `delivery_charge_for()`
returns `outside_dhaka` (৳150) for any district other than `"Dhaka"` —
confirmed by direct code reading, matches `LAUNCH_SETTINGS_BASELINE.md`.

**Customer identity used:** "AAYNA QA Test Customer",
`01700000000` (obviously synthetic — all-zero suffix), delivery address
explicitly labeled "DEVELOPMENT QA ONLY — synthetic address", email
`qa-order-test@example.invalid` (RFC 2606 reserved non-deliverable TLD).
No real person's data was used or exposed.

## 23-24. Confirmation token

Valid token: verified the confirmation endpoint returns the correct
order number, status, subtotal/delivery/total, and item — matches the
checkout response exactly. Missing token → generic 404. Invalid token →
generic 404 (same message/status as missing). Raw token was used exactly
once immediately after checkout, then discarded — never printed again in
this report, never committed, never persisted beyond that one
verification call.

**Verified the order document stores only `order_confirmation_token_hash`
(64-char SHA-256 hex) — no raw token field exists anywhere in the DB
record.**

**Finding (disclosed at the time, remediated in L5.1 — see
"Confirmation-token access-log remediation" in `INFRASTRUCTURE_BASELINE.md`;
left as originally written below):** the token travels as a URL query
parameter (`GET /api/orders/{order_number}?token=...`), which means it
appears in plaintext in standard HTTP access logs — confirmed live: the
uvicorn access-log line for this exact request contains the full raw
token. This is inherent to a `GET`+query-string design, not a new app
bug, and changing it (to a header or a `POST`) is an API contract change
outside this milestone's "no redesign" scope. Flagged as a real,
low-severity hardening candidate: token is single-purpose (read-only
order display, no payment/financial action gated behind it) and
short-lived in practical terms (relevant mainly for the one
confirmation-page view right after checkout), but production log
retention/access should account for this.

## 25. Track Order

```
Correct order + correct phone: 200, correct order data returned
Correct order + wrong phone: 404, generic "No matching order found..." message
Wrong order + correct phone: 404, IDENTICAL generic message
```
No information leakage — confirmed empirically, not just by reading code.

## 26-27. Admin order flow

Found `ORD-1052` via `GET /api/admin/orders/ORD-1052` immediately after
creation. Progressed the full lifecycle via the real admin API:
`New → Confirmed → Packed → Sent to Courier → Delivered`, all
successful. Set synthetic courier fields (`courier_name: "QA-TEST-COURIER"`,
`courier_tracking_code: "QA-TRACK-0001"`) — confirmed both fields are
optional, free-text, admin-editable, and immediately reflected on the
customer-facing Track Order response. **Delivered was inspected first**
(per instruction): the only side effect is `customers.successful_orders += 1`
(confirmed live: the QA customer's counter went from 0 to 1) — no
inventory or payment change. `payment_status` stayed `COD_pending`
through and after Delivered — COD payment collection is not
auto-tracked (see runbook §L).

## 28. Cancel/Return inventory semantics

**Inspected via direct code reading (not executed destructively against
the QA order, per instruction).** `PUT /api/admin/orders/{order_number}`
(`admin_routes.py:295-312`) only ever does two things beyond the raw
field update: increments `customer.successful_orders` on `Delivered`,
increments `customer.cancelled_orders` on `Cancelled`. **There is no
stock-restoration logic anywhere in the codebase for `Cancelled` or
`Returned`** — confirmed by exhaustive grep across `server.py` and
`admin_routes.py` for any stock-increment tied to either status; none
exists. **There are also no transition guards at all** — any order can
move from any status to any other status, including `Delivered →
Cancelled`, with no warning or block, and repeated identical transitions
are not specially handled (not destructive, just a no-op re-write).

A real, already-existing workaround exists: `POST
/api/admin/inventory/{product_id}/adjust` (supports
`change_type: "return"`) lets an admin manually restore stock after a
cancel/return. This is now documented as a required manual step in
`LAUNCH_OPERATIONS_RUNBOOK.md` §H/§I. **Not silently fixed in code** —
automatically linking order cancellation to stock restoration requires a
business-rule decision (should a `Delivered → Cancelled` restore stock
the same as `New → Cancelled`? should repeated re-saves double-restore?)
that wasn't specified, so it's flagged as a real, disclosed, operationally
important gap rather than guessed at.

## 31. Communication side effects

Confirmed before placing the QA order: `ORDER_WEBHOOK_ENABLED=false` in
`backend/.env` (dev). No email-sending code exists anywhere in this
codebase. No SMS gateway integration exists. No automated WhatsApp
messaging exists (the WhatsApp float button is a manual `wa.me` chat
link, gated behind `isPlaceholder()`, not an automated send). **Verified
live after placing `ORD-1052`: zero `notification_logs` entries were
created** — the webhook path never fired, exactly as expected.

## 32. Operations manual

`LAUNCH_OPERATIONS_RUNBOOK.md` created — sections A through M, plus the
support-channel blocker restated. Every mechanism in it was verified
live or by direct code reading this milestone, not assumed.

## 33. Support channel

**BLOCKER BEFORE PUBLIC ORDER ACCEPTANCE, unchanged.** No workaround
invented.

## 34. Backup / rollback

Repo-level rollback is always available (any commit on
`launch/aayna-readiness-v1` is checkable via git). Infra-level rollback
(previous frontend/backend deploy, database backup/point-in-time
restore) depends entirely on whichever host and MongoDB provider are
chosen — **not configured, because no host is chosen yet.** No automated
backup exists or is claimed. For local `aayna_dev`, `aayna_test` remains
the pre-L1 migration backup (unchanged, untouched) — explicitly not a
production backup strategy, just historical continuity.

## 35. Health checks

`GET /api/health` (liveness, no DB touch) and `GET /api/health/ready`
(readiness, pings MongoDB + re-validates production config, 503 when not
ready) both already exist (`server.py:183-218`, documented in
`README.md`). Confirmed by direct reading: neither returns the Mongo URI,
credentials, admin email, or webhook URL/secret — `/api/health`'s
`database` field is only the configured `DB_NAME` string (used
deliberately by the test-isolation safety in `conftest.py`, not a leak).
No change needed; these already satisfy production exposure
requirements.

## 36. Logging

Lightweight review of the dev backend log produced during this
milestone's QA: no password, JWT, or secret values found anywhere in it.
**One real finding**: the confirmation token appears in the access-log
line for its own verification request, because it travels as a URL query
parameter — see §23-24 above for the full disclosure; not a new app bug,
not fixed here, flagged as a hardening candidate.

## 37. Production catalogue baseline

Reconfirmed against `LAUNCH_CATALOGUE_BASELINE.md`: 6 launch products
(Earrings ×3, Necklaces ×2, Rings ×1) unchanged, zero test data in the
live discovery surface, zero held product leaking into launch discovery
— all re-verified live in L4's CDP pass and structurally unchanged since
(no catalogue edits occurred in L5 beyond the one QA order's stock
decrement, which is expected evidence, not a regression).

## 38. SEO production env

Already verified in L4: canonical/OG/sitemap all derive from
`PUBLIC_SITE_URL`/`REACT_APP_PUBLIC_SITE_URL`, self-correct via
`window.location.origin` at runtime when unset, and the one static
fallback (`index.html`) now resolves to `https://shopaayna.com` rather
than a broken token. No localhost fallback would survive into an actual
production build once those two env vars are set per
`DEPLOYMENT_RUNBOOK.md` steps 4/7-8. Ready, waiting on domain
infrastructure only.

## 39. Staging build

No hosting provider exists, so no deployment was attempted. A
production-like local build was produced instead (`npx craco build`,
frontend; production-safety code path re-verified by reading, backend
was not booted with `APP_ENV=production` since that requires real
secrets this milestone was told not to invent). Build output confirmed
clean of test-data and unreplaced tokens; confirmed (expected, disclosed)
to still contain today's dev `REACT_APP_BACKEND_URL` — see §10.

## 40. Hosting decision packet

External research (2026, via web search — directionally current, not
verified against live provider pricing pages; distinct from this
project's own facts above). Capped at 3 options per category as
instructed.

**Backend hosting (FastAPI — needs a real, non-sleeping process; the
in-memory login rate-limiter and the Motor client both assume one
long-lived process, so a pure serverless-per-request model is a poor
fit):**

| Option | Notes |
|---|---|
| **Render** | Free tier exists (750 hrs/mo) but sleeps on idle → cold start hurts a live storefront's first request. Starter tier ~$7/mo removes sleep. Simplest setup of the three. |
| **Railway** | No free tier as of this search; one-time $5 trial credit, then Hobby $5/mo base + metered usage. Fast deploy workflow. |
| **Fly.io** | No free tier, pure pay-per-second. Best multi-region/edge story, but Bangladesh-specific edge presence wasn't confirmed in this search — check at signup if latency matters more than budget. |

For a lean single-country MVP that shouldn't cold-start on a customer's
first request, **Render Starter (~$7/mo) or Railway Hobby (~$5/mo)** are
the realistic always-on choices — not a final decision, a founder one.

**MongoDB hosting:**

| Option | Notes |
|---|---|
| **MongoDB Atlas Free/Shared tier (M0)** | Still offered as of this search — one per project, no included backups, no data-egress charge. Comfortably fits current scale (10 real products, ~50 orders). |
| *(No compelling alternative found)* | A MongoDB-native app like this one is well-served by Atlas's own free tier; self-hosting Mongo adds ops burden with no clear MVP benefit. |

**Object storage** (only relevant if real product-photo uploads via
Admin become a real workflow — not required for launch itself, per §15-16):

| Option | Notes |
|---|---|
| **Cloudflare R2** | ~$0.015/GB-month storage, **$0 egress**, free tier ~10GB + generous ops. Best fit for low-volume admin uploads. |
| **Backblaze B2** | Cheaper raw storage (~$0.007/GB-month) but $0.01/GB egress unless routed through Cloudflare's Bandwidth Alliance. |
| **AWS S3** | Most expensive on egress (~$0.09/GB); only sensible if other AWS infra already exists, which it doesn't here. |

**Frontend:** any of Vercel/Netlify/Cloudflare Pages have production-
suitable free tiers for a low-traffic static React build — not a
meaningfully contentious choice, not compared further.

**No sign-up, provisioning, or purchase occurred.** These are
recommendations for a founder decision, not commitments.

```
HOSTING DECISION REQUIRED: YES
```

## 41. Database host decision

```
DATABASE HOST DECISION REQUIRED: YES
Recommendation (not a decision made here): MongoDB Atlas free/shared tier — realistic fit for current scale, zero setup cost to start.
```

## 42. Object storage decision packet

```
OBJECT STORAGE DECISION REQUIRED: NOT BLOCKING FOR LAUNCH
```
Current launch product images already load from a stable, third-party
URL and don't depend on this app's own storage mechanism at all (§15-16).
A real decision (Cloudflare R2 recommended, per §40) is only needed once
the founder wants to upload real product photography through Admin
rather than relying on the current scaffold demo images — deferred, not
blocking L5.1.

## 43. Domain DNS checklist (shape only, no values)

Once a provider is chosen: apex domain (`shopaayna.com`) → frontend host;
`www` → redirect or alias to apex, per §8-9; HTTPS certificate → issued
automatically by most static/PaaS hosts on a connected custom domain; API
hostname → either a subdomain (e.g. `api.shopaayna.com` → backend host)
or a same-origin rewrite, depending on what the chosen frontend host
supports; domain-ownership verification → whatever method the DNS
registrar/Search Console pairing requires at that time. No record values
invented — provider supplies them.

## 44. Search Console

Not configured. Post-domain steps only (§17 of `DEPLOYMENT_RUNBOOK.md`):
verify ownership, submit sitemap, request homepage indexing, spot-check
product/category pages once live. No token fabricated.

## 45-46. Files created

`PRODUCTION_ENV_CHECKLIST.md`, `DEPLOYMENT_RUNBOOK.md` — both described
above.

## 47-48. Production data strategy

`PRODUCTION_DATA_MIGRATION_PLAN.md` created — full allowlist (what moves:
6 real categories + 10 real products + 20 approved settings; what
doesn't: all 52 dev orders including `ORD-1052`, all 3 dev/QA customers,
8 test products, 4 test categories, dev-only inventory/notification
logs). Not executed.

## 49. Tests

`APP_ENV=test`, `DB_NAME=aayna_pytest`, second backend instance on port
8001: **123 passed, 0 failed, 1 skipped** (re-run this milestone,
identical to L4's result). The one QA order ran only against `aayna_dev`,
never against `aayna_pytest`.

## 50. Frontend build

`npx craco build` succeeds. Verified zero unreplaced `%…%` tokens, zero
test-catalogue references, zero `TEST_Cat`/`TEST-HIST`/`TEST-IMP`
patterns in the build output. One expected, disclosed finding:
`REACT_APP_BACKEND_URL` still bakes in today's dev value
(`http://localhost:8000`) because no production value has been set yet
(§10) — this is the correct current state, not a defect, and
`DEPLOYMENT_RUNBOOK.md` step 7 exists specifically to close it before a
real production build.

## 51. Security final check

| Check | Status |
|---|---|
| Public product field whitelist | Unchanged, re-confirmed no internal/supplier fields exposed |
| Admin route protection | JWT-gated, confirmed |
| Rate limiting | Exists (5 attempts / 15-min lockout, single-instance in-memory) |
| Confirmation token hashing | Confirmed — only SHA-256 hash persisted, verified live this milestone |
| Track Order order+phone requirement | Confirmed live, generic failure both ways |
| `client_request_id` idempotency | Confirmed live, no duplicate order/stock-decrement on retry |
| Storage path handling | Traversal-guarded prefix check confirmed in `storage.py` |
| CORS production validation | Confirmed via `validate_security_config()`, unmodified |
| Secrets env-only | Confirmed — only `.env.example` (placeholders) is tracked in git |
| Admin noindex | Confirmed, L4 |
| Checkout/confirmation noindex | Confirmed, L4 |
| Confirmation-token-in-query-string logging | **Disclosed finding**, remediated in L5.1 (uvicorn + frontend URL, see `INFRASTRUCTURE_BASELINE.md`); Railway edge logging unverified until deploy — see §23-24/36 |
| Order-status transition guards | **Disclosed finding**, none exist — see §28 |
| Stock auto-restore on Cancel/Return | **Disclosed finding**, none exists — manual workaround documented in runbook |

No security safeguard was weakened. No redesign performed.

## 52-53. This document, commits

This file is the summary. **No backend/frontend code was changed in
L5** — every finding this milestone required either a business-rule
decision not yet made (stock auto-restore, transition guards, COD
payment-collected tracking) or genuinely-missing infrastructure
(hosting/DB/domain), neither of which is safe to invent or silently
patch. Only new documentation was added.

## Founder decisions required

1. Choose hosting: backend process host + frontend static host (§40).
2. Choose production MongoDB target (§41, Atlas recommended).
3. Register/confirm DNS for `shopaayna.com`, decide www handling (§8-9, §43).
4. Set real `ADMIN_EMAIL` / `ADMIN_PASSWORD` for production (§13-14).
5. Resolve the support contact channel (§33 — the one outstanding
   business blocker carried since L3.1).
6. Decide whether/how to track COD "payment collected" state.
7. Decide whether to build automatic stock-restoration on Cancel/Return
   and order-status transition guards, or keep the current manual
   workaround (§28).
8. Decide object storage strategy (§42) — only once real product
   photography/admin uploads become a real need, not launch-blocking.
9. Real product photography, to eventually replace the current Emergent
   scaffold demo images (§15-16 — content decision, not infra).

**READY FOR L5.1 INFRASTRUCTURE SELECTION / DEPLOYMENT: YES**

(The application itself is technically and operationally sound —
end-to-end order flow, admin lifecycle, security posture, and SEO layer
are all verified. What remains is exclusively founder infrastructure
selection and business-process decisions, none of which this milestone
is authorized to make. Do not deploy until those decisions are made and
the resulting real configuration is verified.)

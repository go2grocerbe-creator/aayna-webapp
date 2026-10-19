# AAYNA customer accounts, order tracking, email and promotions

Branch: `feat/customer-accounts-20261018` (based on `chore/production-consolidation-20261015` @ `75f3b67`).
Not merged to `main`. Nothing here has been deployed against `aayna_prod`.

## 1. What customers get

| Route | Purpose |
|---|---|
| `/register` | Name, email, Bangladesh mobile, password (12+ chars, passphrases welcome), Terms/Privacy acceptance (not pre-ticked). No marketing opt-in. |
| `/login` | Email + password, "Continue with Google" when configured, link-Google mode (`?link=google`). |
| `/verify-email#token=…` | Confirms the email, activates the account and signs in. Expired/used/invalid states with resend. |
| `/forgot-password`, `/reset-password#token=…` | 15-minute single-use reset. Identical public answer for every email. |
| `/confirm-email#token=…` | Confirms an email-address change. |
| `/account` | Overview: orders in progress, rewards (only when real), profile, default address. |
| `/account/orders`, `/account/orders/:orderNumber` | Own orders only; active vs completed; recorded timeline, courier, discount. Guest-order claiming panel. |
| `/account/orders/claim#token=…` | Confirms a guest order emailed-link claim. |
| `/account/addresses` | Up to 10 addresses, default, validation. |
| `/account/profile` | Name, phone, email change (password + link to new address). |
| `/account/security` | Change/set password, sign-in methods (link/unlink Google), devices (sign out one / others / everywhere), recent activity, deletion request. |
| `/account/rewards` | Personal coupons with their real conditions and state. |
| `/checkout` | Guest checkout unchanged. Signed-in: prefill + saved-address picker; orders link to the account. Coupon field (server-validated). |
| `/order-confirmation/:n` | Discount line; "Save this order to my account" (uses the confirmation token). |
| `/track-order` | Same Order-ID + phone check, now rate limited, with the recorded timeline. |

Admin: **Accounts** (list/filter/detail, suspend/reactivate), **Promotions** (codes, preview, activation, pause, archive, redemptions, restore, audit; Welcome offer; issued welcome codes). Order detail shows coupon, customer emails and status history.

## 2. Architecture and security

* **Separate identity system.** Collections `customer_accounts`, `customer_identities` (provider + subject, unique), `customer_sessions`, `customer_tokens`, `customer_addresses`, `security_events`. Admin users stay in `users`. Account ids are UUIDs; email is unique but never the identity key for Google (Google `sub` is).
* **Sessions.** Opaque 256-bit id in an HttpOnly, SameSite=Lax cookie (`__Host-aayna_sid` on HTTPS; Secure, host-only). Only its SHA-256 is stored. 30-day absolute / 14-day idle expiry. Logout revokes; "everywhere", password reset and email change revoke all; password change revokes the others. Nothing in localStorage.
* **Admin/customer separation.** Admin endpoints accept only the admin Bearer JWT (users collection); customer endpoints accept only the cookie session. Tested both ways. No role field exists on customer accounts; unknown body fields are ignored.
* **CSRF.** Every state-changing customer endpoint requires `X-AAYNA-CSRF: 1` and, when present, an allowed `Origin`; cookies are SameSite=Lax.
* **Passwords.** bcrypt (cost 12) over SHA-256 pre-hash so passphrases longer than 72 bytes stay fully significant; 12–256 chars; common-password and "contains your email" checks. Never logged, emailed or returned.
* **Email tokens** (verify 24 h, reset 15 min, email change 24 h, order claim 24 h, Google link 15 min): random 256-bit, stored hashed, purpose-bound, consumed atomically (concurrent reuse → exactly one succeeds), older ones superseded. Links put the token in the URL **fragment**, which never reaches servers, logs, analytics or Referer headers; pages strip it from the address bar immediately.
* **No enumeration.** Registration, resend, forgot-password and email-change answer identically whether or not the address exists. An existing owner receives an "account exists" notice instead of a second account. Unverified/suspended states are revealed only after the correct password.
* **Rate limits** are stored in MongoDB (`rate_limits`) so they hold across serverless instances: register 10/h/IP, login 40/15 min/IP plus 5 failures per IP+email (15 min) and 20 per account (1 h), forgot 10/h/IP and 3/15 min/account (silent), resend cooldown 60 s and 5/day/account, track 20/10 min/IP, coupon checks 30/10 min/IP, Google start/callback 30/10 min/IP.
* **Google sign-in.** Server-side Authorization Code flow with PKCE (S256), `state` (single use, deleted on read) bound to an HttpOnly browser cookie (login-CSRF protection), `nonce`, ID-token signature verified against Google JWKS (RS256), `iss`, `aud`, `azp`, `exp`, `iat`; `email_verified` required. Redirect targets are relative and allow-listed. Matching email never merges accounts: the owner must sign in with the existing password, then the pending Google identity (held in a 15-minute HttpOnly cookie) is attached. Google-only accounts never get a password from "forgot password"; adding one requires a fresh Google sign-in (15 min). Cancel/denied/unverified/unconfigured all end on `/login` with a clear message.
* **Orders.** Checkout derives the account from the session only, and links only verified accounts. Guest orders are never exposed by phone/email match: they are added with the high-entropy confirmation token, or via a link emailed to the order's recorded address when it equals the verified account email. Order detail/list endpoints filter by `account_id` (IDOR-tested).
* **Tracking timeline.** Append-only `order_events` written at checkout and on every admin status change. Only recorded transitions show times; older orders show their current status with no invented dates. Customer view never includes phone, admin notes or token hashes.

## 3. Transactional email (Resend)

`backend/emailer.py` renders and sends every message (HTML + plain text, AAYNA layout, escaped content, one action, expiry, unsolicited-request explanation, support contact = Reply-To). Senders: `accounts@shopaayna.com` (verification, reset, password changed, email change, order claim) and `orders@shopaayna.com` (order confirmation, status updates for Confirmed, Handed to courier, Delivered, Cancelled). Reply-To `shopaayna.bd@gmail.com`. `support@shopaayna.com` is **not** used as a receiving inbox.

* Up to 3 attempts on 429/5xx/network, Resend `Idempotency-Key`, 8 s timeout.
* `email_logs` keeps event, template, masked recipient, status, provider id, attempts, error class — never bodies, links, tokens or the key.
* De-duplication keys for order confirmation and each status email; a failed send releases its key so a later retry can send.
* No key configured → status `not_configured` (never reported as sent); order placement and account creation are never blocked by email.
* `EMAIL_MODE=capture` (tests/local only; refused when `APP_ENV=production`) keeps messages in memory and optionally `EMAIL_CAPTURE_FILE`.

## 4. Promotions

Server-authoritative, separate from catalogue `discount_price`. Percentage or fixed BDT; caps by maximum BDT and maximum % of eligible subtotal; minimum eligible subtotal; start/end; total and per-customer limits; first-order-only (no prior non-cancelled order by account **or** phone); product/category eligibility; customer-specific codes. One code per order, merchandise only (never delivery), whole taka, never negative.

* Total cap: conditional decrement of `remaining_uses`; per customer: conditional counter document. Concurrent test: 5 parallel reservations of the last use → exactly 1.
* Reservation happens after stock reservation inside the order transaction-equivalent; any failure releases both. Idempotent checkout retries reuse the existing order and never reserve twice.
* **Cancellation policy:** a redemption is not restored automatically. An admin with `promotions.manage` may restore it for a Cancelled/Returned order; the action is audited.
* Permissions: `promotions.view`/`promotions.manage` = super_admin, admin. **`promotions.activate` (making a code usable, and any welcome-campaign change) = super_admin only.** Product and order managers have no promotion access. New codes are always drafts.
* Admin preview endpoint shows the exact discount the engine would apply.

### Welcome campaign — limits approved 2026-10-19, campaign DISABLED until launch authorisation

10% off the first eligible order, personal single-use code (`WELCOME-XXXXXXXX`) per verified account, valid 30 days from issue, non-transferable, non-stackable. Issued only after email verification (or a Google sign-up with a Google-verified email), at most once per account (`welcome_issuance`). Founder-approved limits (2026-10-19): minimum merchandise order ৳1,000, maximum discount ৳150, valid 30 days, one redemption per eligible customer, delivery charges excluded. They are the recorded configuration (`approved_limits`). The campaign remains disabled until a super admin enables it with an explicit confirmation; enabling with values that differ from the approved limits needs a second explicit confirmation. While disabled the storefront popup only invites account creation and promises no discount.

Known limit: one person can create several accounts with different email addresses; first-order-only (account **and** phone) limits repeat use.

## 5. Configuration

| Variable | Where | Notes |
|---|---|---|
| `RESEND_API_KEY` | backend secret | Sending-only key. |
| `EMAIL_FROM_ACCOUNTS`, `EMAIL_FROM_ORDERS`, `EMAIL_REPLY_TO`, `SUPPORT_CONTACT` | optional | Defaults as above. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | backend secret | Both required to show the Google button. |
| `PUBLIC_SITE_URL` | backend | Base for every email link and the Google redirect URI (`<PUBLIC_SITE_URL>/api/auth/google/callback`). |
| `CORS_ORIGINS` | backend | Also used for the Origin check. |
| `COOKIE_SECURE` | optional | Forces Secure cookies outside production. |

Frontend needs no new variables (same-origin `/api`). No secret reaches the browser bundle.

### Google OAuth client (founder action when ready)

Google Cloud Console → APIs & Services → OAuth consent screen (External, app name AAYNA, support email, authorised domain `shopaayna.com` and `vercel.app` for the preview) → Credentials → Create OAuth client ID → Web application:

* Authorised JavaScript origins: `https://aayna-webapp-git-feat-customer-accounts-20261018-go2-grocer.vercel.app` (test preview) and later `https://shopaayna.com` (and `https://www.shopaayna.com` if used).
* Authorised redirect URIs: `https://aayna-webapp-git-feat-customer-accounts-20261018-go2-grocer.vercel.app/api/auth/google/callback`, later `https://shopaayna.com/api/auth/google/callback`. The backend always sends exactly `<PUBLIC_SITE_URL>/api/auth/google/callback` (never with the preview share code), so these must match character for character.
* While the consent screen is in "Testing", add the Google accounts allowed to sign in under Test users.
* Put the Client ID and Client Secret into Vercel as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (Sensitive), scoped like the other secrets.

## 6. Database changes (non-destructive)

At startup the API creates, only if missing: unique indexes on `customer_accounts.id`, `customer_accounts.email`, `customer_identities(provider, subject)`, `customer_sessions.token_hash`, `customer_tokens.token_hash`, `promotions.id`, `promotions.code`, `promotion_redemptions(promotion_id, order_id)`, and non-unique indexes on account/audit fields plus `orders.account_id`. Existing documents are never modified; existing orders simply have no `account_id`/`coupon_code` and keep working. No migration script, no reseed.

Rollback: deploy the previous commit. The new collections can stay (unused) or be dropped; the `orders.account_id` index is harmless and can be dropped with `db.orders.dropIndex("account_id")`. Coupon fields on orders created meanwhile remain valid history.

Before this reaches `aayna_prod`: back up, record collection counts, deploy, confirm counts unchanged and `/api/health/ready` = ready.

## 7. Tests

* `backend/tests_import/test_customer_accounts.py` — 48 offline tests (mongomock): registration/policy, hashing, verification, enumeration, CSRF/Origin, lockout, sessions, admin/customer separation, reset (expiry, replay, concurrency, throttling), Google OIDC (new/repeat, wrong aud/iss/azp/nonce/key/kid, expired, replay, missing state, login-CSRF binding, cancel, unverified email, open redirect, no email-only merge, set-password rules), addresses isolation, email change, guest/authenticated checkout, IDOR, claiming, timeline, track rate limit, promotions (permissions, server-side maths, rules, limits, concurrency, failed checkout, idempotency, restore policy, customer-specific, preview), welcome campaign, admin accounts, email engine.
* `scripts/verify/customer_accounts_ui.js` — real-browser suite (Playwright/Chromium) against an isolated backend in capture mode: 70 checks across 390/768/1280.
* `scripts/verify/finalization_ui.js` — release-candidate suite (86 checks): guest-order claiming (valid, wrong/missing token, replay by another account, email-link claim, link opened in the wrong account, replayed and expired links, email mismatch), saved addresses (validation, default switching, edit, delete-promotes-default, IDOR, checkout prefill), profile and email change, password change, deletion request, admin Accounts (search, method filter, suspend → session ends and sign-in refused, reactivate), promotion rules (fixed/minimum, percent caps, scheduled, expired, paused, draft, total limit, first order, category, customer-specific, role authority, restore after cancellation), order status → tracking timeline and one status email, checkout validation, stock limit, idempotent retry, double-click, logout and customer/admin token isolation.
* `scripts/verify/route_audit.js` — every storefront, auth, account and admin route at 320/390/430/768/1280/1440: overflow, uncaught errors, title, broken images, one `<h1>`, robots (private pages noindex, launch-category public pages indexable); screenshots at 390 and 1280.
* How to run all suites locally (no founder involvement): start an isolated MongoDB-compatible server, run the backend with `DB_NAME=aayna_pytest APP_ENV=test EMAIL_MODE=capture EMAIL_CAPTURE_FILE=…`, serve `frontend/build` with `/api` proxied to it, seed test-only role users, then run each script with `BASE_URL`, `EMAIL_CAPTURE_FILE`, `ADMIN_EMAIL`/`ADMIN_PASSWORD` (test admin), `ROLE_USERS_JSON` and `DB_CMD` (a helper that only touches the local test database). Test identities are generated per run; no password is printed or committed. Never point these scripts at `aayna_prod`.

## 8. Test preview (isolated)

* URL: `https://aayna-webapp-git-feat-customer-accounts-20261018-go2-grocer.vercel.app` (Vercel login required).
* Database: `aayna_preview` on the same cluster, used by a separate user `aayna_preview_app` with readWrite on `aayna_preview` only - it cannot read `aayna_prod`. Demo catalogue seeded there (`ALLOW_PRODUCTION_SEED=true` scoped to this branch only).
* Non-secret variables are set per branch. Secrets (`MONGO_URL`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `RESEND_API_KEY`, optional `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`) are entered by the owner as Sensitive, Preview, branch `feat/customer-accounts-20261018`.
* The production-data admin preview (`chore/production-consolidation-20261015`) is unaffected: its variables are scoped to its own branch.

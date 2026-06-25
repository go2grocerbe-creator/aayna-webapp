# AAYNA — Women's Accessories E-commerce (Bangladesh)

React + FastAPI + MongoDB. Mobile-first storefront (Milestone 1) + admin dashboard (Milestone 2), with launch security hardening (Milestone 3A).

---

## Environment Variables

All backend secrets are loaded from `backend/.env` (never committed). Copy `backend/.env.example` to `backend/.env` and fill in real values.

### Required
| Variable | Purpose |
|---|---|
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | Database name |
| `JWT_SECRET` | Secret used to sign admin JWT tokens. **Required in production.** |
| `ADMIN_EMAIL` | Email of the seeded dashboard admin account |
| `ADMIN_PASSWORD` | Password of the seeded dashboard admin account |
| `APP_ENV` | `development` (default) or `production` |

### Optional / placeholders
| Variable | Purpose |
|---|---|
| `CORS_ORIGINS` | Comma-separated allowed origins (use the real frontend URL in production) |
| `EMERGENT_LLM_KEY` | Emergent-managed object storage (product/category image uploads) |
| `ORDER_WEBHOOK_ENABLED` / `ORDER_WEBHOOK_URL` / `ORDER_WEBHOOK_SECRET` | Order notification webhook (see Milestone 3B section) |
| `OBJECT_STORAGE_*` | Placeholders only — for teams who later switch to an S3-compatible provider |

The frontend uses only `REACT_APP_BACKEND_URL` (in `frontend/.env`). **No secrets live in frontend code.**

---

## Setting the admin email / password locally

1. `cp backend/.env.example backend/.env`
2. Edit `backend/.env`:
   ```
   ADMIN_EMAIL=you@example.com
   ADMIN_PASSWORD=your-strong-password
   ```
3. Restart the backend. On startup the app seeds (or updates) the admin account from these values.
4. Log in at `/admin/login` with those credentials.

> In **development** (`APP_ENV=development`), if `ADMIN_EMAIL`/`ADMIN_PASSWORD` are not set, the app falls back to `admin@aayna.xyz` / `ChangeMe123!` **for local convenience only** and logs a warning.

---

## ⚠️ Production warning — do NOT use default credentials

When `APP_ENV=production`, the backend **refuses to start** if:
- `JWT_SECRET`, `ADMIN_EMAIL`, or `ADMIN_PASSWORD` is missing, **or**
- `ADMIN_PASSWORD` is still the default `ChangeMe123!`, **or**
- `JWT_SECRET` is still the development fallback.

Always set a unique admin email, a strong unique admin password, and a strong random `JWT_SECRET` before deploying. Never reuse the local development defaults in production.

---

## Generating a strong JWT secret

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the 64-character output into `JWT_SECRET` in your production `.env`.

---

## Security notes (Milestone 3A)

- **No hardcoded production credentials** — admin email/password and JWT secret come from environment variables.
- **JWT secret** is loaded from `JWT_SECRET`; production fails fast if it is missing or default.
- **Login rate limiting** — after 5 failed admin login attempts for the same email, login is temporarily blocked for 15 minutes (in-memory). The error is generic ("Invalid email or password") and never reveals whether the email or password was wrong; a lockout returns "Too many failed attempts. Please try again in a few minutes."
- `.env` is git-ignored; only `.env.example` (placeholders) is committed.

---

## Order Notification Webhook (Milestone 3B)

After a customer successfully places an order, the backend can POST that order to an
external automation tool (e.g. **Make.com**, Zapier, n8n). This is **off by default**.

### Environment variables
| Variable | Purpose |
|---|---|
| `ORDER_WEBHOOK_ENABLED` | `true` to send webhooks, `false` (default) to disable |
| `ORDER_WEBHOOK_URL` | The destination URL that receives the POST |
| `ORDER_WEBHOOK_SECRET` | Optional. If set, an HMAC-SHA256 signature header is added |
| `NOTIFICATION_ROUTER_NAME` | Logical router name recorded in logs (default `generic_webhook`) |
| `NOTIFICATION_ROUTER_MODE` | Delivery mode recorded in logs (default `webhook`) |

### Enable / disable
- **Enable:** set `ORDER_WEBHOOK_ENABLED=true` **and** `ORDER_WEBHOOK_URL=<your-url>`, then restart the backend.
- **Disable:** set `ORDER_WEBHOOK_ENABLED=false` (or leave `ORDER_WEBHOOK_URL` empty). No call is made and nothing is logged.
- ⚠️ **Never commit a real `ORDER_WEBHOOK_URL` or `ORDER_WEBHOOK_SECRET`.** Keep them in your local/production `.env` only (git-ignored).

### Behaviour & safety
- The webhook fires **after** the order is saved. It is fire-and-forget and **never blocks or duplicates the order**.
- If the webhook fails (network error or non-2xx), the **order is still created successfully** and the failure is logged in `notification_logs` (`status: failed`). The admin dashboard's **Failed Notifications** card reflects these failures.
- Logs never store the webhook URL or secret.

### Payload sent (JSON)
```json
{
  "order_id": "0d6f...uuid",
  "order_number": "ORD-1037",
  "customer_name": "Ayesha Rahman",
  "customer_phone": "+8801712345678",
  "district": "Dhaka",
  "delivery_address": "House 12, Road 5, Dhanmondi",
  "payment_method": "Cash on Delivery",
  "order_total": 880,
  "delivery_fee": 80,
  "order_status": "New",
  "created_at": "2026-06-22T17:30:00+00:00",
  "items": [
    { "product_name": "Gold Pearl Hoop Earrings", "quantity": 2, "unit_price": 400, "subtotal": 800 }
  ],
  "items_summary": "Gold Pearl Hoop Earrings x2",
  "admin_message": "New AAYNA order received: ORD-1037. Customer: Ayesha Rahman, Phone: +8801712345678, District: Dhaka. Address: House 12, Road 5, Dhanmondi. Payment: Cash on Delivery. Total: ৳880. Items: Gold Pearl Hoop Earrings x2. Please check the admin dashboard and confirm the order.",
  "customer_message": "Thank you for your order from AAYNA. Your order ORD-1037 has been received. Total: ৳880. Payment: Cash on Delivery. Delivery district: Dhaka. Our team will contact you soon to confirm the order."
}
```
The payload deliberately **excludes** `cost_price`, `internal_notes`, DB `_id`, JWT tokens, admin data, and secrets.

### Ready-to-use message templates (Milestone 3C)
The payload includes three ready-made text fields so Blackbox AI / Make.com can forward them without building strings:
- **`items_summary`** — readable item list, e.g. `"Gold Pearl Hoop Earrings x2, Heart Pendant Necklace x1"`.
- **`admin_message`** — short operational alert (order number, customer name + phone, district, address, payment, total, items, and a "check the admin dashboard" reminder). Route this to your admin WhatsApp/Telegram/email in Make.com.
- **`customer_message`** — polite brand-friendly confirmation (order number, total, payment, delivery district, "we'll confirm soon"). It intentionally **omits the phone and address**. Route this to the customer's SMS/WhatsApp in Make.com.

> The app **does not send any SMS, WhatsApp, or email itself** — it only includes these message strings in the webhook payload. Blackbox/Make.com decides where each message goes.

### Signature verification (optional)
If `ORDER_WEBHOOK_SECRET` is set, the request includes:
```
X-AAYNA-Signature: sha256=<hex>
```
where `<hex> = HMAC_SHA256(secret, raw_request_body)`. The receiver recomputes the HMAC over the exact raw body and compares — if they match, the request genuinely came from this backend.

### Receiving in Make.com
1. Create a scenario with a **Custom Webhook** trigger and copy its URL.
2. Put that URL in `ORDER_WEBHOOK_URL` and set `ORDER_WEBHOOK_ENABLED=true`; restart the backend.
3. Place a test order — Make.com receives the JSON above and you can map fields to Google Sheets, email, SMS, etc.
4. (Optional) Set `ORDER_WEBHOOK_SECRET` and add a Make.com filter/module that verifies the `X-AAYNA-Signature` HMAC before processing.

### Notification router metadata (Milestone 3D)
The app stays **webhook-only** — it never bundles SMS/WhatsApp/email SDKs. `ORDER_WEBHOOK_URL` is the single outbound endpoint and can point to any router (Make.com, Blackbox AI, n8n, Zapier). For traceability, every `notification_logs` entry records:
- `router_name` — from `NOTIFICATION_ROUTER_NAME` (default `generic_webhook`).
- `router_mode` — from `NOTIFICATION_ROUTER_MODE` (default `webhook`).

These are logs/metadata only and never appear in the outbound payload or leak secrets.

---

## SEO & Analytics (Milestone 3E / 3G)

### `PUBLIC_SITE_URL` (production domain)
All absolute SEO URLs (canonical, Open Graph, robots.txt sitemap reference, and sitemap.xml entries) are built from a single configurable base:

| Variable | Where | Purpose |
|---|---|---|
| `PUBLIC_SITE_URL` | `backend/.env` | Base URL used by the backend `robots.txt` + `sitemap.xml`. Safe local fallback: `http://localhost:3000`. |
| `REACT_APP_PUBLIC_SITE_URL` | `frontend/.env` | Same base used by the frontend for canonical / OG URLs (public, build-time). |

Set both to your real domain (e.g. `https://www.aayna.com.bd`) before launch.

### Dynamic robots.txt & sitemap.xml
These are generated by the backend (DB-driven) and served at:
- `GET /api/robots.txt` and `GET /api/sitemap.xml` (always reachable through the ingress).
- `GET /robots.txt` and `GET /sitemap.xml` at the app root (for direct backend access / deployment-level routing).

> **Routing note:** the Kubernetes ingress sends `/api/*` to the backend and everything else to the React app, so the dynamic SEO files are reliably reachable at `{PUBLIC_SITE_URL}/api/sitemap.xml` and `/api/robots.txt`. The backend **also** serves them at its root (`/sitemap.xml`, `/robots.txt`), so a host/CDN rewrite to the backend exposes the clean root paths. `robots.txt` advertises `{PUBLIC_SITE_URL}/sitemap.xml`. Each product/category `<url>` carries a `<lastmod>` (from its `updated_at`) so crawlers re-index changed items faster; static pages omit `<lastmod>`.

### 🚀 SEO production routing
Before/at launch:
1. Set `PUBLIC_SITE_URL` (`backend/.env`) and `REACT_APP_PUBLIC_SITE_URL` (`frontend/.env`) to your real domain (e.g. `https://www.aayna.com.bd`), then rebuild the frontend.
2. Make `/sitemap.xml` and `/robots.txt` publicly reachable at the **root** of your domain. The dynamic source is the backend `/api/sitemap.xml` and `/api/robots.txt`.
3. Make `/sitemap.xml` and `/robots.txt` reachable at the **root** of your domain. They are served dynamically by the backend at `/api/sitemap.xml` and `/api/robots.txt` (and at the backend root). Because the ingress routes non-`/api` paths to the React app, add a **CDN/host rewrite** so the root paths map to the backend:
   - `/sitemap.xml` → backend `/api/sitemap.xml`
   - `/robots.txt`  → backend `/api/robots.txt`
   (e.g. Nginx `location = /sitemap.xml { proxy_pass http://backend/api/sitemap.xml; }`, or a Cloudflare/Vercel rewrite rule.) Until then, submit the `/api/sitemap.xml` URL directly.
4. Submit `{PUBLIC_SITE_URL}/sitemap.xml` to **Google Search Console**.
5. Re-submit the sitemap after major product/category updates (URLs and `lastmod` refresh automatically).

**Sitemap includes** (absolute URLs from `PUBLIC_SITE_URL`):
- Static: `/`, `/shop`, `/contact`, `/track-order`, `/delivery-policy`, `/returns`, `/privacy`, `/terms`.
- All **active** category pages (`/category/{slug}`) from the DB.
- All **active / out-of-stock** product pages (`/product/{slug}`) from the DB.

**Sitemap excludes:** `/admin`, `/cart`, `/checkout`, `/order-confirmation`, and all internal `/api` / admin routes.

**robots.txt** allows the storefront and disallows `/admin`, `/cart`, `/checkout`, `/order-confirmation`, `/api/admin`, `/api/auth`; it ends with `Sitemap: {PUBLIC_SITE_URL}/sitemap.xml`.

### Per-page SEO & structured data
- Every storefront page sets its own `<title>`, meta description, Open Graph and Twitter tags, and a canonical URL (dependency-free `useSeo` hook in `src/lib/seo.js`). Canonical/OG URLs use `REACT_APP_PUBLIC_SITE_URL` when set.
- **Product pages:** title = `Product Name | AAYNA`; description includes product name, category, short description and price; product-specific OG image; canonical URL; plus **Product JSON-LD** (`@type: Product`) with name, images, description, brand AAYNA, category, price, `priceCurrency: BDT`, and stock-based availability. JSON-LD never includes `cost_price`, `internal_notes`, private IDs, admin data, or secrets.
- **Category pages:** title = `Category Name | AAYNA`; description mentions women's accessories in Bangladesh; canonical URL.
- Cart / Checkout / Order-confirmation pages are marked `noindex`.

### Analytics pixels (config/env-based)
Pixels are loaded **only** when their public ID is provided, and **never** on `/admin` routes. Set these in `frontend/.env` (public, build-time — pixel IDs are public identifiers, **never put secret keys here**):

| Variable | Purpose |
|---|---|
| `REACT_APP_GA_MEASUREMENT_ID` | Google Analytics 4 Measurement ID (e.g. `G-XXXXXXX`). Empty ⇒ GA4 not loaded. (Legacy `REACT_APP_GA4_ID` is also accepted.) |
| `REACT_APP_META_PIXEL_ID` | Meta/Facebook Pixel ID. Empty ⇒ Meta Pixel not loaded. |
| `REACT_APP_TIKTOK_PIXEL_ID` | TikTok Pixel ID. Empty ⇒ TikTok Pixel not loaded. |

After editing `frontend/.env`, rebuild/restart the frontend so the new values are picked up.

---

## 🚀 Launch checklist

**Security**
- [ ] Set `APP_ENV=production` in `backend/.env`.
- [ ] Set a strong unique `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and a 64-char random `JWT_SECRET`.
- [ ] Set `CORS_ORIGINS` to your real frontend domain (not `*`).
- [ ] Confirm `.env` files are NOT committed (only `.env.example` is).

**Storefront content**
- [ ] Update WhatsApp / bKash / Nagad numbers and social links in Admin → Settings.
- [ ] Replace placeholder product/category/hero images via the admin dashboard.
- [ ] Review delivery charges (Dhaka / outside Dhaka) in Settings.

**Notifications**
- [ ] Set `ORDER_WEBHOOK_URL` + `ORDER_WEBHOOK_ENABLED=true` (and optionally `ORDER_WEBHOOK_SECRET`).
- [ ] (Optional) Set `NOTIFICATION_ROUTER_NAME` / `NOTIFICATION_ROUTER_MODE`.
- [ ] Place a test order and confirm the router (Make.com/Blackbox) receives it.

**SEO & analytics**
- [ ] Set `PUBLIC_SITE_URL` (`backend/.env`) and `REACT_APP_PUBLIC_SITE_URL` (`frontend/.env`) to the live domain; rebuild the frontend.
- [ ] (Optional) Add a host/CDN rule so `/sitemap.xml` and `/robots.txt` route to the backend; otherwise submit `{PUBLIC_SITE_URL}/api/sitemap.xml` to Search Console.
- [ ] Add `REACT_APP_GA_MEASUREMENT_ID` / `REACT_APP_META_PIXEL_ID` / `REACT_APP_TIKTOK_PIXEL_ID` if tracking is desired; rebuild the frontend.
- [ ] Verify pixels do **not** fire on `/admin` routes.

**Final**
- [ ] Run the backend test suite (`pytest`) — all green.
- [ ] Smoke-test full guest flow: browse → cart → checkout → confirmation → track.

---

## Production deployment (Milestone 4A)

### Production environment checklist
Set these before deploying. The backend **refuses to start in production** if the critical ones are missing or unsafe (see "Production safety validation" below).

| Variable | Where | Required | Notes |
|---|---|---|---|
| `APP_ENV` | backend | ✅ | Set to `production`. |
| `ADMIN_EMAIL` | backend | ✅ | Seeded admin login email. |
| `ADMIN_PASSWORD` | backend | ✅ | Strong, unique. Must NOT be the dev default. |
| `JWT_SECRET` | backend | ✅ | 64-char random (`python -c "import secrets;print(secrets.token_hex(32))"`). |
| `MONGO_URL` | backend | ✅ | Production MongoDB connection string. |
| `DB_NAME` | backend | ✅ | Production database name. |
| `CORS_ORIGINS` | backend | ✅ | Real frontend origin(s), comma-separated. Must NOT be `*`. |
| `PUBLIC_SITE_URL` | backend | ✅ | Live domain. Must NOT be empty or `localhost`. |
| `REACT_APP_PUBLIC_SITE_URL` | frontend | ✅ | Same live domain (build-time). |
| `ORDER_WEBHOOK_ENABLED` | backend | optional | `true`/`false`. If `true`, `ORDER_WEBHOOK_URL` is required. |
| `ORDER_WEBHOOK_URL` | backend | conditional | Required when webhook is enabled. |
| `ORDER_WEBHOOK_SECRET` | backend | optional | Adds HMAC signature header. |
| `REACT_APP_GA_MEASUREMENT_ID` | frontend | optional | GA4 ID. Empty ⇒ not loaded. |
| `REACT_APP_META_PIXEL_ID` | frontend | optional | Meta Pixel ID. Empty ⇒ not loaded. |
| `REACT_APP_TIKTOK_PIXEL_ID` | frontend | optional | TikTok Pixel ID. Empty ⇒ not loaded. |
| `EMERGENT_LLM_KEY` | backend | optional | Object storage for image uploads (admin). |

### Production safety validation
On startup with `APP_ENV=production`, the backend fails fast (refuses to boot) when:
- `JWT_SECRET`, `ADMIN_EMAIL`, or `ADMIN_PASSWORD` is missing.
- `ADMIN_PASSWORD` is still the dev default, or `JWT_SECRET` is the dev fallback.
- `PUBLIC_SITE_URL` is empty or points at `localhost` / `127.0.0.1`.
- `CORS_ORIGINS` is empty or `*`.
- `ORDER_WEBHOOK_ENABLED=true` but `ORDER_WEBHOOK_URL` is empty.

Development (`APP_ENV=development`) keeps simple local fallbacks and skips these checks.

### Health check
`GET /api/health` → `{"status":"ok","app":"aayna","environment":"production|development"}`. Returns safe status only — no secrets, DB URL, admin email, webhook URL, or internal config.

### Liveness vs readiness (Milestone 4B)
- **`GET /api/health` (liveness):** fast, does **not** touch MongoDB. Confirms the process is up. Use for liveness probes.
- **`GET /api/health/ready` (readiness):** checks the process is up, **pings MongoDB**, and (in production) re-validates required config. Returns **200** `{"status":"ready",...}` when ready, or **503** `{"status":"not_ready",...}` when the DB is unreachable or config is invalid. Hosting platforms should use this to decide whether the backend should receive traffic (and to restart/hold a pod when not ready).
- **`GET /api/health/version`:** safe build info only — `{app, environment, version}` (version from optional `APP_VERSION`, default `1.0.0`).
- None of these endpoints expose secrets, the MongoDB URL, admin email, webhook URL/secret, storage keys, or stack traces.

### Smoke test (non-destructive)
Read-only checks of public endpoints (does **not** place orders):
```bash
BASE_URL=https://your-domain.com ./scripts/smoke_test.sh
```
Or by hand:
```bash
curl -s https://your-domain.com/api/health
curl -s https://your-domain.com/api/products
curl -s https://your-domain.com/api/categories
curl -s https://your-domain.com/api/sitemap.xml
curl -s https://your-domain.com/api/robots.txt
```

### Production Launch QA (manual)
- [ ] Home loads
- [ ] Shop loads
- [ ] Category page loads
- [ ] Product detail loads
- [ ] Add to cart works
- [ ] Checkout works
- [ ] Order confirmation appears
- [ ] Track order works
- [ ] Admin login works
- [ ] Wrong admin password fails (generic error)
- [ ] Product stock reduces after an order
- [ ] Admin order status update reflects on the track page
- [ ] Webhook notification logs success/failure (Admin → notifications / `notification_logs`)
- [ ] `robots.txt` reachable (root via CDN rewrite, or `/api/robots.txt`)
- [ ] `sitemap.xml` reachable, or `/api/sitemap.xml` submitted to Search Console
- [ ] Analytics scripts load **only** when IDs are set
- [ ] Admin pages are **not** tracked by analytics
- [ ] Mobile layout checked (storefront + checkout)

---

## 🚀 Deployment runbook (Milestone 4C)

Step-by-step to take AAYNA from this repo to a live production deployment.

### 1. Database
- Provision a production MongoDB (Atlas or self-hosted). Create a database and a user with read/write on it.
- Set `MONGO_URL` and `DB_NAME` in `backend/.env`. On first boot the app seeds categories, products, settings, and the admin account.

### 2. Backend production env (`backend/.env`)
- `APP_ENV=production`
- `JWT_SECRET` = 64-char random (`python -c "import secrets;print(secrets.token_hex(32))"`)
- `ADMIN_EMAIL` + `ADMIN_PASSWORD` (strong, unique — never the dev default)
- `CORS_ORIGINS` = your real frontend origin(s), comma-separated (never `*`)
- `PUBLIC_SITE_URL` = your live domain (never empty/localhost)
- Webhook (optional): `ORDER_WEBHOOK_ENABLED=true` + `ORDER_WEBHOOK_URL` (+ optional `ORDER_WEBHOOK_SECRET`, `NOTIFICATION_ROUTER_NAME`, `NOTIFICATION_ROUTER_MODE`)
- Object storage (optional, for admin image uploads): `EMERGENT_LLM_KEY`
> The backend **refuses to start** if production config is missing/unsafe (see "Production safety validation").

### 3. Frontend production env (`frontend/.env`)
- `REACT_APP_BACKEND_URL` = backend public URL
- `REACT_APP_PUBLIC_SITE_URL` = your live domain
- Analytics (optional): `REACT_APP_GA_MEASUREMENT_ID`, `REACT_APP_META_PIXEL_ID`, `REACT_APP_TIKTOK_PIXEL_ID`
- Rebuild the frontend after changing any `REACT_APP_*` value (they are inlined at build time).

### 4. Admin credentials
- Set `ADMIN_EMAIL`/`ADMIN_PASSWORD` before first boot; log in at `/admin/login`.

### 5. SEO routing rule (host/CDN)
Add a rewrite so the clean root paths map to the backend's dynamic endpoints:
```
/sitemap.xml  →  backend /api/sitemap.xml
/robots.txt   →  backend /api/robots.txt
```
Then submit `{PUBLIC_SITE_URL}/sitemap.xml` to Google Search Console. Until the rewrite exists, submit `/api/sitemap.xml` directly.

### 6. Probes (hosting platform)
- Liveness → `GET /api/health`
- Readiness → `GET /api/health/ready` (gates traffic; 503 when DB/config not ready)

### Production env template (no real values)
| Variable | Side | Required | Example placeholder | Sensitive |
|---|---|---|---|---|
| `APP_ENV` | backend | ✅ | `production` | no |
| `MONGO_URL` | backend | ✅ | `mongodb+srv://user:***@cluster/db` | 🔒 yes |
| `DB_NAME` | backend | ✅ | `aayna_prod` | no |
| `JWT_SECRET` | backend | ✅ | `<64-char hex>` | 🔒 yes |
| `ADMIN_EMAIL` | backend | ✅ | `owner@your-domain.com` | 🔒 yes |
| `ADMIN_PASSWORD` | backend | ✅ | `<strong-unique-password>` | 🔒 yes |
| `CORS_ORIGINS` | backend | ✅ | `https://your-domain.com` | no |
| `PUBLIC_SITE_URL` | backend | ✅ | `https://your-domain.com` | no |
| `ORDER_WEBHOOK_ENABLED` | backend | optional | `false` | no |
| `ORDER_WEBHOOK_URL` | backend | conditional | `https://hooks.make.com/xxxxx` | 🔒 yes |
| `ORDER_WEBHOOK_SECRET` | backend | optional | `<random-string>` | 🔒 yes |
| `NOTIFICATION_ROUTER_NAME` | backend | optional | `generic_webhook` | no |
| `NOTIFICATION_ROUTER_MODE` | backend | optional | `webhook` | no |
| `EMERGENT_LLM_KEY` | backend | optional | `<key>` | 🔒 yes |
| `APP_VERSION` | backend | optional | `1.0.0` | no |
| `REACT_APP_BACKEND_URL` | frontend | ✅ | `https://api.your-domain.com` | no |
| `REACT_APP_PUBLIC_SITE_URL` | frontend | ✅ | `https://your-domain.com` | no |
| `REACT_APP_GA_MEASUREMENT_ID` | frontend | optional | `G-XXXXXXXXXX` | no (public ID) |
| `REACT_APP_META_PIXEL_ID` | frontend | optional | `123456789012345` | no (public ID) |
| `REACT_APP_TIKTOK_PIXEL_ID` | frontend | optional | `CXXXXXXXXXXXXXXXXXXX` | no (public ID) |
> Keep all 🔒 values in environment variables only — never in code or git. Only `backend/.env.example` (placeholders) is committed.

### Final QA script
`scripts/smoke_test.sh` is **read-only** (no orders, no stock changes, no admin login). Run against the live domain:
```bash
BASE_URL=https://your-live-domain.com ./scripts/smoke_test.sh
```
It checks `/api/health`, `/api/health/ready`, products, categories, settings, `/api/sitemap.xml`, `/api/robots.txt`.

### Final manual launch checklist
- [ ] Home loads
- [ ] Shop loads
- [ ] Category page loads
- [ ] Product detail loads
- [ ] Add to cart works
- [ ] Checkout works
- [ ] Order confirmation appears
- [ ] Track order works
- [ ] Admin login works
- [ ] Wrong admin login fails (generic error)
- [ ] Product CRUD works (create / edit / deactivate)
- [ ] Order status update reflects on the track page
- [ ] Inventory stock reduces after a test order
- [ ] Webhook notification logs success
- [ ] Failed webhook logs appear safely (no URL/secret leaked)
- [ ] `/api/health` works
- [ ] `/api/health/ready` works (200 ready)
- [ ] `/api/health/version` works
- [ ] `/api/sitemap.xml` works
- [ ] `/api/robots.txt` works
- [ ] Root `/sitemap.xml` and `/robots.txt` work after the host rewrite
- [ ] Mobile layout checked (storefront + checkout)
- [ ] Analytics only loads when IDs are configured
- [ ] Admin routes are **not** tracked

---

## Running tests

```bash
cd backend
python -m pytest tests/test_aayna_admin.py tests/test_aayna_storefront.py -q
```
Tests read admin credentials from the environment (`backend/.env`), not hardcoded values.

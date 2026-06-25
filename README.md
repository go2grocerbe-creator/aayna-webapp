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

## SEO & Analytics (Milestone 3E)

### SEO
- Every storefront page sets its own `<title>`, `meta description`, Open Graph and Twitter card tags, and a canonical URL (via the dependency-free `useSeo` hook in `src/lib/seo.js`).
- Cart / Checkout / Order-confirmation pages are marked `noindex` (transactional, not for search engines).
- `public/robots.txt` allows the storefront and disallows `/admin`, `/cart`, `/checkout`, `/order-confirmation`.
- `public/sitemap.xml` lists the main public pages.
- ⚠️ **Before launch, replace `https://www.aayna.com.bd` in both `robots.txt` and `sitemap.xml` with your real domain.**

### Analytics pixels (config/env-based)
Pixels are loaded **only** when their public ID is provided, and **never** on `/admin` routes. Set these in `frontend/.env` (public, build-time — pixel IDs are public identifiers, **never put secret keys here**):

| Variable | Purpose |
|---|---|
| `REACT_APP_GA4_ID` | Google Analytics 4 Measurement ID (e.g. `G-XXXXXXX`). Empty ⇒ GA4 not loaded. |
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
- [ ] Replace `https://www.aayna.com.bd` in `public/robots.txt` and `public/sitemap.xml` with the live domain.
- [ ] Add `REACT_APP_GA4_ID` / `REACT_APP_META_PIXEL_ID` / `REACT_APP_TIKTOK_PIXEL_ID` if tracking is desired; rebuild the frontend.
- [ ] Verify pixels do **not** fire on `/admin` routes.

**Final**
- [ ] Run the backend test suite (`pytest`) — all green.
- [ ] Smoke-test full guest flow: browse → cart → checkout → confirmation → track.

---

## Running tests

```bash
cd backend
python -m pytest tests/test_aayna_admin.py tests/test_aayna_storefront.py -q
```
Tests read admin credentials from the environment (`backend/.env`), not hardcoded values.

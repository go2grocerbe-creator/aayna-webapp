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
| `MAKE_WEBHOOK_URL` | Order notification webhook (placeholder for now) |
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

## Running tests

```bash
cd backend
python -m pytest tests/test_aayna_admin.py tests/test_aayna_storefront.py -q
```
Tests read admin credentials from the environment (`backend/.env`), not hardcoded values.

# AAYNA Production Environment Checklist

No secret values appear in this file. This is the variable inventory —
what exists, where it's read, whether a real production value has been
supplied. "Value supplied: NO" is the expected, correct state for every
row until real infrastructure exists — this file records readiness to
configure, not that configuration has happened.

## Backend (`backend/.env` in production)

| Variable | Required | Sensitive | Dev value type | Production value supplied? | Validation |
|---|---|---|---|---|---|
| `APP_ENV` | Yes | No | `development` | NO | Must literally be `production`; `validate_security_config()` gates everything below on this |
| `MONGO_URL` | Yes | Yes | `mongodb://localhost:27017` | NO | Must point at a real, separate production MongoDB instance — never `aayna_dev`/`aayna_pytest`/`aayna_test` |
| `DB_NAME` | Yes | No | `aayna_dev` | NO | Must be a new, dedicated production database name (e.g. `aayna_prod`) — never one of the three existing dev/test DB names |
| `JWT_SECRET` | Yes | Yes | dev fallback string | NO | Startup **refuses to boot** if missing, or equal to the known dev fallback value |
| `ADMIN_EMAIL` | Yes | Yes | `admin@aayna.xyz` | NO | Founder-chosen; startup refuses to boot in production if unset |
| `ADMIN_PASSWORD` | Yes | Yes | dev default | NO | Founder-chosen, strong, unique; startup refuses to boot if unset or equal to the known dev default |
| `CORS_ORIGINS` | Yes | No | `*` | NO | Startup refuses `*`/empty in production; must be the real frontend origin(s), comma-separated |
| `PUBLIC_SITE_URL` | Yes | No | `http://localhost:3000` | NO | Startup refuses empty/`localhost`/`127.0.0.1` in production; drives sitemap/robots/canonical |
| `ORDER_WEBHOOK_ENABLED` | Optional | No | `false` | NO | If `true`, `ORDER_WEBHOOK_URL` becomes required (enforced at startup) |
| `ORDER_WEBHOOK_URL` | Conditional | Yes | empty | NO | Required only if webhook enabled — a Make.com/n8n/Zapier-style endpoint, not built by this app |
| `ORDER_WEBHOOK_SECRET` | Optional | Yes | empty | NO | Adds an HMAC signature header if set; not required |
| `NOTIFICATION_ROUTER_NAME` | Optional | No | `generic_webhook` | NO | Metadata/logging label only |
| `NOTIFICATION_ROUTER_MODE` | Optional | No | `webhook` | NO | Metadata/logging label only |
| `EMERGENT_LLM_KEY` | Optional | Yes | empty (fails safe) | NO | Only required if Admin image upload (`/api/admin/upload`) is used — see "Object storage" below; without it, uploads fail cleanly (returns a 502, does not crash the app) |
| `APP_VERSION` | Optional | No | unset (defaults `1.0.0`) | NO | Cosmetic, shown at `/api/health/version` |

## Frontend (`frontend/.env`, inlined at build time)

| Variable | Required | Sensitive | Dev value type | Production value supplied? | Validation |
|---|---|---|---|---|---|
| `REACT_APP_BACKEND_URL` | Yes | No | `http://localhost:8000` | NO | Must be the real production backend URL — never `localhost`/`:8000`/`:8001`/a dev tunnel. No runtime check exists for this (a bad build-time value just silently breaks API calls) — verify manually after every production build |
| `REACT_APP_PUBLIC_SITE_URL` | Yes | No | unset (falls back to `window.location.origin`) | NO | Drives canonical/OG URLs; safe to leave unset (self-corrects at runtime) but the **static** `index.html` OG fallback (L4) is hardcoded to `https://shopaayna.com` and does not read this var — update that file directly if the real domain differs |
| `REACT_APP_GA_MEASUREMENT_ID` | Optional | No (public ID) | unset | NO | Not to be set per this engagement's explicit no-tracking instruction unless the founder later decides otherwise |
| `REACT_APP_META_PIXEL_ID` | Optional | No (public ID) | unset | NO | Same as above |
| `REACT_APP_TIKTOK_PIXEL_ID` | Optional | No (public ID) | unset | NO | Same as above |

## Not required / legacy

| Variable | Status |
|---|---|
| `OBJECT_STORAGE_BUCKET` / `OBJECT_STORAGE_ENDPOINT` / `OBJECT_STORAGE_ACCESS_KEY` / `OBJECT_STORAGE_SECRET_KEY` | Present (empty) in `backend/.env.test` but **not read anywhere in the codebase** — `storage.py` only uses `EMERGENT_LLM_KEY`. Dead/legacy placeholders from an earlier iteration; not required for anything. Noted here so nobody spends time trying to configure them. |

## Summary

**Zero production secrets exist anywhere in this repository or its
history** — confirmed by the presence of only `.env.example` (placeholder
values) tracked in git, `.env`/`.env.test` gitignored and local-only. Every
row above is legitimately `NO` because no production infrastructure has
been chosen yet (see `L5_DEPLOYMENT_READINESS.md`). This file becomes
actionable the moment a hosting/DB provider is selected — fill in "value
supplied" as each variable is actually set, do not pre-fill.

# AAYNA Production Environment Checklist

No secret values appear in this file. This is the variable inventory —
what exists, where it's read, and whether a real production value is
known/set. Non-secret values that are now *known* (because the L5.1
infrastructure decision fixed them — `INFRASTRUCTURE_BASELINE.md`) are
shown directly; secrets stay `NO` until a founder/system actually
generates and sets them in Railway. Nothing in this file has actually
been configured in any provider yet — see the Summary below.

Set these in **Railway's** environment-variable UI for the backend
service (root directory `backend`, region `asia-southeast1-eqsg3a`) —
never committed, never in this repo.

## Backend (Railway service env)

| Variable | Required | Sensitive | Dev value | Production value | Validation |
|---|---|---|---|---|---|
| `APP_ENV` | Yes | No | `development` | `production` (known, not yet set) | Must literally be `production`; `validate_security_config()` gates everything below on this |
| `MONGO_URL` | Yes | Yes | `mongodb://localhost:27017` | NO — Atlas Flex (Singapore) connection string, founder/system must generate | Must point at a real, separate production MongoDB instance — never `aayna_dev`/`aayna_pytest`/`aayna_test` |
| `DB_NAME` | Yes | No | `aayna_dev` | `aayna_prod` (known, not yet set) | Dedicated production database name — never one of the three existing dev/test names |
| `JWT_SECRET` | Yes | Yes | dev fallback string | NO — founder/system must generate (`python -c "import secrets;print(secrets.token_hex(32))"`) | Startup **refuses to boot** if missing, or equal to the known dev fallback value |
| `ADMIN_EMAIL` | Yes | Yes | `admin@aayna.xyz` | NO — founder-chosen | Startup refuses to boot in production if unset |
| `ADMIN_PASSWORD` | Yes | Yes | dev default | NO — founder-chosen, strong, unique | Startup refuses to boot if unset or equal to the known dev default |
| `CORS_ORIGINS` | Yes | No | `*` | `https://shopaayna.com` (known, not yet set — no `www` unless www is actually served, §21) | Startup refuses `*`/empty in production; must be the real frontend origin(s), comma-separated |
| `PUBLIC_SITE_URL` | Yes | No | `http://localhost:3000` | `https://shopaayna.com` (known, not yet set) | Startup refuses empty/`localhost`/`127.0.0.1` in production; drives sitemap/robots/canonical |
| `ORDER_WEBHOOK_ENABLED` | Optional | No | `false` | Founder decision, unchanged from L5 | If `true`, `ORDER_WEBHOOK_URL` becomes required (enforced at startup) |
| `ORDER_WEBHOOK_URL` | Conditional | Yes | empty | NO | Required only if webhook enabled — a Make.com/n8n/Zapier-style endpoint, not built by this app |
| `ORDER_WEBHOOK_SECRET` | Optional | Yes | empty | NO | Adds an HMAC signature header if set; not required |
| `NOTIFICATION_ROUTER_NAME` | Optional | No | `generic_webhook` | Unchanged | Metadata/logging label only |
| `NOTIFICATION_ROUTER_MODE` | Optional | No | `webhook` | Unchanged | Metadata/logging label only |
| `EMERGENT_LLM_KEY` | Not required at launch | Yes | empty (fails safe) | Deferred — object storage decision postponed, `INFRASTRUCTURE_BASELINE.md` | Only needed if Admin image upload is used; without it uploads fail cleanly (502), app doesn't crash |
| `APP_VERSION` | Optional | No | unset (defaults `1.0.0`) | Optional | Cosmetic, shown at `/api/health/version` |
| `PORT` | Yes | No | `8000`/`8001` (manual, dev) | Set automatically by Railway | Railway injects this; the start command in `backend/railway.json` already reads `$PORT` — do not hardcode a port |

## Frontend (Cloudflare Pages project env — Production and Preview set separately)

| Variable | Required | Sensitive | Dev value | Production value | Preview/staging value |
|---|---|---|---|---|---|
| `REACT_APP_BACKEND_URL` | Yes | No | `http://localhost:8000` | `https://api.shopaayna.com` (known, not yet set — depends on Railway custom domain being live first, §10 of `DEPLOYMENT_RUNBOOK.md`) | The Railway-generated service URL (`*.up.railway.app`) — never the production API, never localhost |
| `REACT_APP_PUBLIC_SITE_URL` | Yes | No | unset (falls back to `window.location.origin`) | `https://shopaayna.com` (known, not yet set) | Leave unset — self-corrects to the Cloudflare Pages preview URL at runtime |
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
values) tracked in git, `.env`/`.env.test` gitignored and local-only. The
non-secret production values above (`APP_ENV`, `DB_NAME`, `CORS_ORIGINS`,
`PUBLIC_SITE_URL`, `REACT_APP_PUBLIC_SITE_URL`, `REACT_APP_BACKEND_URL`)
are now *known* because the L5.1 infrastructure decision fixed the
architecture — but **none have been set anywhere yet**; this file records
what to type in once Railway/Atlas/Cloudflare Pages projects actually
exist, not that it's been done. Every secret row stays `NO` until a
founder/system actually generates it.

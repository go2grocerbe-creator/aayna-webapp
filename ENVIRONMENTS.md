# AAYNA — Environments

AAYNA uses three logically separate databases, distinguished by name only
(the same local MongoDB instance is fine for development and test — only
production needs, and should get, separate infrastructure/credentials).

| | Development | Test | Production |
|---|---|---|---|
| Purpose | local backend, local frontend, founder QA | pytest / automated backend tests **only** | deployed, real customer traffic |
| DB name (local convention) | `aayna_dev` | `aayna_pytest` | set via real deployment config, never hardcoded here |
| Env file | `backend/.env` | `backend/.env.test` (gitignored, not committed) | real deployment secrets manager — never a file in this repo |
| `APP_ENV` | `development` | `test` | `production` |
| Seed data permitted | yes (idempotent — only inserts when a collection is empty) | yes, but the test DB is dropped after every session so it starts empty each run | **no**, unless `ALLOW_PRODUCTION_SEED=true` is explicitly set |
| Destructive test operations permitted | **no** | yes, but only against this DB | **no** |

## Why this exists

Before this milestone, `backend/.env`'s `DB_NAME` was `aayna_test` — but that
database held real founder data (51 real orders, a real product catalogue),
not disposable test fixtures. The backend test suite in `backend/tests/` is
a set of HTTP-level integration tests: each file hits whatever backend
process happens to be running at `REACT_APP_BACKEND_URL` and issues real
writes through the real admin/storefront API. Nothing verified that the
backend under test was actually isolated, so running `pytest` against a
locally-running dev backend left records like `TEST Imported` and
`TEST_HistProduct` mixed into real data — confirmed by grepping the test
files themselves (`test_aayna_admin.py`'s CSV-import test literally creates
a product named `TEST Imported` with a `TEST-IMP-*` SKU).

The fix has two parts:

1. **Rename, don't delete.** Every document from the old `aayna_test`
   database was copied (read + `insert_many`, no deletes) into a new,
   honestly-named `aayna_dev` database, with collection-by-collection counts
   verified to match exactly. `backend/.env` now points at `aayna_dev`. The
   original `aayna_test` database was left completely untouched in MongoDB
   as an implicit backup — nothing was dropped or renamed at the database
   level.
2. **A real safety gate, not developer memory.** `backend/tests/conftest.py`
   adds two independent checks (some test files talk to MongoDB in-process,
   not just over HTTP — see "Test-database safety rules" below for why one
   check isn't enough): a module-level check at collection time, and a
   session-scoped fixture that calls `GET /api/health` (which now also
   reports the configured `database` name — never the connection string or
   credentials). Both hard-refuse to run a single test unless the database
   name contains `"test"`. There is no fallback to "just use whatever's
   running." At the end of the session the fixture drops that exact,
   just-verified database — never development, never production, because
   the drop only ever targets the name that passed the check immediately
   before.

## Running the backend locally (development)

```
cd backend
./venv/Scripts/uvicorn.exe server:app --host 0.0.0.0 --port 8000
```

Uses `backend/.env` as-is (`DB_NAME=aayna_dev`, `APP_ENV=development`).

## Running the backend for tests (test)

`backend/db.py` loads `backend/.env` by a fixed path — it does not
auto-select `.env.test`. `load_dotenv` never overrides variables already
present in the shell environment, so the reliable way to start a
test-isolated backend instance is to export `backend/.env.test`'s variables
into the shell *before* launching uvicorn, on a different port from your
normal dev instance so both can run side by side:

```bash
cd backend
set -a; source .env.test; set +a
./venv/Scripts/uvicorn.exe server:app --host 0.0.0.0 --port 8001
```

Then run pytest **in that same shell** (the one with `.env.test` already
sourced into it), pointed at that instance:

```bash
cd backend
REACT_APP_BACKEND_URL=http://localhost:8001 ./venv/Scripts/python.exe -m pytest tests/ -q
```

This matters for a reason beyond hitting the right HTTP port: a few test
files (e.g. `test_aayna_qa_4e.py`) `import server` directly and touch
`server.db` in-process for setup/teardown, bypassing the HTTP layer
entirely. That in-process connection resolves `DB_NAME` from **this pytest
process's own environment** — which is exactly why `.env.test` must be
sourced into the same shell pytest runs in, not just passed to the uvicorn
instance. `conftest.py` enforces both independently: a module-level check
(runs at collection time, before any test file is imported) refuses to
collect anything if the pytest process's own `DB_NAME` isn't test-named,
and a session fixture refuses to run anything if the HTTP backend at
`REACT_APP_BACKEND_URL` doesn't report one either.

## Production

Do not create a production `.env` file in this repo. Production configuration
comes entirely from the real deployment environment (secrets manager /
hosting platform env vars). `backend/auth.py`'s `validate_security_config()`
already refuses to start in production if any of the following are true:

- `JWT_SECRET`, `ADMIN_EMAIL`, or `ADMIN_PASSWORD` are missing
- `ADMIN_PASSWORD` is still the local dev default
- `JWT_SECRET` is still the local dev fallback value
- `PUBLIC_SITE_URL` is empty or points at `localhost`
- `CORS_ORIGINS` is empty or `*`
- `ORDER_WEBHOOK_ENABLED=true` but `ORDER_WEBHOOK_URL` is not set

This check runs on every startup and is also re-checked by
`GET /api/health/ready`. Placeholder-gated, disabled payment methods
(bKash/Nagad manual numbers) are **not** required for production startup —
only settings that are actually enabled need to be configured.

`DB_NAME` in production is not validated to be any particular string (it's
production's own real database, name decided by whoever provisions it) —
but it must obviously never be `aayna_dev` or `aayna_pytest`.

## Test-database safety rules

- Most test files only talk to the backend over HTTP, same as a real client
  would. A few (e.g. `test_aayna_qa_4e.py`) `import server` and touch
  `server.db` in-process for setup/teardown of synthetic fixtures — this was
  confirmed live during L1: running pytest with only `REACT_APP_BACKEND_URL`
  overridden left that file's direct DB connection resolved to the real
  `aayna_dev` database, independent of which backend was being tested over
  HTTP. `conftest.py` has two independent guards for this reason, not one:
  - a **module-level check**, which runs at collection time before any test
    file is imported, refusing to collect anything if this pytest process's
    own `DB_NAME` doesn't contain `"test"` — this is what protects the
    `import server` pattern;
  - a **session-scoped, autouse fixture**, which refuses to run anything if
    `GET /api/health` on the HTTP backend at `REACT_APP_BACKEND_URL` doesn't
    report a database name containing `"test"`, or reports
    `APP_ENV=production` — this is what protects the HTTP-only test files.
- The only destructive operation in the entire test-tooling layer is that
  session fixture's teardown `drop_database(...)` call, and it only ever
  targets the exact name that fixture just verified — there is no code path
  that can drop development or production data, even with a misconfigured
  `MONGO_URL`, because the name check happens against the live backend's own
  reported state, not against a value the test process trusts blindly.

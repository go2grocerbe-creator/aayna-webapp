"""
AAYNA test-database safety gate (L1 — Environment + Database Safety).

The tests in this suite are HTTP-level integration tests: they hit whatever
backend process is running at REACT_APP_BACKEND_URL and issue real writes
through the real admin/storefront API. Before this file existed, nothing
verified that the backend under test was actually pointed at an isolated
test database - tests were free to (and did) run against the shared
development database, leaving behind records like "TEST Imported" and
"TEST_HistProduct" that a founder later found mixed in with real data.

This fixture is the fix: it is session-scoped and autouse, so it runs
before any test in the suite, and it hard-refuses to let a single test
execute unless GET /api/health reports a database name that clearly
identifies it as a test database (must contain "test", e.g. "aayna_pytest").
No fallback to "just use whatever's running" is provided - a misconfigured
environment fails loudly instead of silently polluting real data.

At the end of the session it drops that same, just-verified test database,
so runs stay repeatable. It never touches development or production data:
the drop only ever targets the exact name that was checked above.

See ENVIRONMENTS.md for how to start a backend instance against the
isolated test database before running pytest.
"""
import os
import pytest
import requests
import pymongo
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)

# Best-effort .env loading, matching the pattern the individual test files
# already use (Emergent-platform absolute path first, local repo path as a
# fallback for non-Emergent environments). load_dotenv does not override
# variables already set in the shell, so `DB_NAME=aayna_pytest pytest ...`
# style invocations always win over whatever the .env file contains.
for candidate in ("/app/backend/.env", os.path.join(_BACKEND_DIR, ".env")):
    try:
        load_dotenv(candidate)
    except Exception:
        pass

# Second, independent guard - module level, so it runs at collection time,
# BEFORE pytest imports any test file. This matters because some test files
# (e.g. test_aayna_qa_4e.py) `import server` directly and manipulate
# `server.db` in-process for setup/teardown, bypassing the HTTP layer
# entirely. That in-process `server.db` connection resolves DB_NAME from
# THIS PROCESS's own environment (backend/db.py's load_dotenv), which has
# nothing to do with which backend REACT_APP_BACKEND_URL happens to point
# at. Confirmed live: running pytest with only REACT_APP_BACKEND_URL
# overridden left this process's own DB_NAME resolved to the real
# development database ("aayna_dev") - a distinct pollution path from the
# HTTP-only one the session fixture below covers. Both guards are required.
_PROCESS_DB_NAME = (os.environ.get("DB_NAME") or "").strip()
if "test" not in _PROCESS_DB_NAME.lower():
    raise RuntimeError(
        f"Refusing to collect any tests: this pytest process's own DB_NAME is "
        f"{_PROCESS_DB_NAME!r}, which does not look like a test database (must "
        f"contain 'test'). Some test files import `server` and touch its DB "
        f"connection directly, so the pytest process itself - not just the "
        f"backend it's calling over HTTP - must be started with the test "
        f"environment's variables. Run `set -a; source .env.test; set +a` (or "
        f"equivalent) before invoking pytest. See ENVIRONMENTS.md."
    )


def _resolve_base_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        frontend_env = os.path.join(_REPO_ROOT, "frontend", ".env")
        try:
            with open(frontend_env) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not url:
        raise RuntimeError(
            "REACT_APP_BACKEND_URL is not set and frontend/.env was not found - "
            "cannot determine which backend the test suite should target."
        )
    return url.rstrip("/")


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_database():
    base_url = _resolve_base_url()
    api = f"{base_url}/api"

    try:
        r = requests.get(f"{api}/health", timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        raise RuntimeError(
            f"Could not reach {api}/health to verify test-database safety before running "
            f"any tests ({exc}). Start a backend instance pointed at an isolated test "
            f"database first - see ENVIRONMENTS.md."
        ) from exc

    db_name = (data.get("database") or "").strip()
    environment = (data.get("environment") or "").strip().lower()

    if not db_name:
        raise RuntimeError(
            "GET /api/health did not report a database name. Refusing to run tests: "
            "there is no way to confirm this backend isn't pointed at development or "
            "production data. See ENVIRONMENTS.md."
        )
    if "test" not in db_name.lower():
        raise RuntimeError(
            f"Refusing to run tests: the backend at {base_url} reports database "
            f"{db_name!r}, which does not look like a test database (the name must "
            f"contain 'test', e.g. 'aayna_pytest'). Start a backend instance with "
            f"DB_NAME set to the isolated test database before running pytest. "
            f"See ENVIRONMENTS.md."
        )
    if environment == "production":
        raise RuntimeError(
            "Refusing to run tests: the backend under test reports APP_ENV=production."
        )

    yield db_name

    # Teardown: reset the isolated test database so runs stay repeatable.
    # Re-asserts the safety condition immediately before the only destructive
    # call in this file - never trust a value without re-checking it right
    # before using it destructively.
    mongo_url = os.environ.get("MONGO_URL")
    if mongo_url and "test" in db_name.lower():
        client = pymongo.MongoClient(mongo_url)
        client.drop_database(db_name)
        client.close()

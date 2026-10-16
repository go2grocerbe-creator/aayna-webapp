"""Single source of truth for which MongoDB targets automated tests may WRITE to.

Two targets are allowed, nothing else:

  local   loopback host (127.0.0.1 / localhost / ::1) and DB_NAME exactly `aayna_pytest`
          (the throwaway instance used by the sandbox harness and run_isolated_mongo_checks.py)

  atlas   mongodb+srv://aayna_test_app@aayna-dev.gzn5qto.mongodb.net (EXACT host), DB_NAME exactly
          `aayna_release_test`, AND (live check) the authenticated user has no
          write-capable privilege on any other database or on the cluster.

Everything else is refused, including names that merely contain "test"
(`test_database` is Emergent's project database and holds real data).

`classify()` is the static check (no network); `verify_live()` adds the checks that
need a connection. Neither prints the connection string or password.
"""
import os
from urllib.parse import unquote, urlsplit

LOCAL_TEST_DB = "aayna_pytest"
ATLAS_TEST_DB = "aayna_release_test"
ATLAS_TEST_USER = "aayna_test_app"
ATLAS_CLUSTER = "aayna-dev"
# Exact SRV hostname of the founder's Atlas test cluster (project AAYNA, cluster aayna-dev),
# read from the authenticated Atlas "Connect" dialog on 2026-10-17. Not a secret.
# Pinned exactly: another Atlas project can also have a cluster named "aayna-dev".
ATLAS_APPROVED_HOST = "aayna-dev.gzn5qto.mongodb.net"
ATLAS_MEMBER_SUFFIX = "." + ATLAS_APPROVED_HOST.split(".", 1)[1]   # ".gzn5qto.mongodb.net"
REAL_DB_NAMES = {"test_database", "aayna_dev", "aayna_test", "aayna_prod", "aayna_staging"}
DENIED = REAL_DB_NAMES | {"admin", "local", "config"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
# Actions that cannot change data. Any other action on a resource outside the
# test database makes the target unsafe.
READ_ONLY_ACTIONS = {
    "find", "listCollections", "listIndexes", "listSearchIndexes", "collStats", "dbStats", "dbHash",
    "indexStats", "killCursors", "changeStream", "listDatabases", "planCacheRead", "validate",
    "serverStatus", "hostInfo", "connPoolStats", "getCmdLineOpts", "listSessions", "getParameter",
    "replSetGetStatus", "replSetGetConfig", "getDefaultRWConcern", "bypassDefaultMaxTimeMS",
}


class UnsafeTarget(RuntimeError):
    pass


def _hosts(mongo_url):
    netloc = urlsplit(mongo_url).netloc.rsplit("@", 1)[-1]
    out = []
    for h in netloc.split(","):
        h = h.strip()
        if h.startswith("["):
            out.append(h[1:h.index("]")])
        else:
            out.append(h.split(":")[0])
    return [h.lower() for h in out if h]


def classify(mongo_url, db_name):
    """Static target check. Returns {"kind": "local"|"atlas", ...} or raises UnsafeTarget."""
    db_name = (db_name or "").strip()
    if not mongo_url:
        raise UnsafeTarget("MONGO_URL is empty")
    if db_name.lower() in DENIED:
        raise UnsafeTarget(f"DB_NAME {db_name!r} is a protected database; tests may never write to it")
    parts = urlsplit(mongo_url)
    hosts = _hosts(mongo_url)
    if hosts and all(h in LOOPBACK for h in hosts):
        if db_name != LOCAL_TEST_DB:
            raise UnsafeTarget(f"local test runs must use DB_NAME={LOCAL_TEST_DB!r}, got {db_name!r}")
        return {"kind": "local", "db": db_name}
    if parts.scheme != "mongodb+srv" or len(hosts) != 1:
        raise UnsafeTarget("remote test target must be a single mongodb+srv:// Atlas address")
    host = hosts[0]
    if not host.isascii() or host != ATLAS_APPROVED_HOST:
        raise UnsafeTarget(f"remote test target is not the approved Atlas cluster {ATLAS_CLUSTER!r} "
                           f"(host must be exactly {ATLAS_APPROVED_HOST})")
    labels = host.split(".")
    if unquote(parts.username or "") != ATLAS_TEST_USER:
        raise UnsafeTarget(f"remote test target must authenticate as the dedicated user {ATLAS_TEST_USER!r}")
    if db_name != ATLAS_TEST_DB:
        raise UnsafeTarget(f"Atlas test runs must use DB_NAME={ATLAS_TEST_DB!r}, got {db_name!r}")
    return {"kind": "atlas", "db": db_name, "cluster": labels[0], "host": host}


def verify_live(client, mongo_url, db_name):
    """Connection-level checks. Returns a metadata dict (no secrets) or raises UnsafeTarget."""
    info = classify(mongo_url, db_name)
    build = client.admin.command("buildInfo")
    info["engine"] = (f"FerretDB {build['ferretdbVersion']}" if "ferretdbVersion" in build
                      else f"MongoDB {build.get('version')}")
    info["official_mongodb"] = "ferretdbVersion" not in build
    try:
        visible = set(client.list_database_names())
    except Exception:  # noqa: BLE001 - user without listDatabases sees only its own DBs anyway
        visible = set()
    info["visible_databases"] = sorted(visible)
    if info["kind"] == "local" and visible & REAL_DB_NAMES:
        raise UnsafeTarget(f"local instance also holds real data {sorted(visible & REAL_DB_NAMES)}; "
                           "use an isolated instance")
    if info["kind"] == "atlas":
        hello = client.admin.command("hello")
        members = [m.split(":")[0].lower() for m in hello.get("hosts", [])]
        if not members or not all(m.isascii() and m.endswith(ATLAS_MEMBER_SUFFIX) and
                                  m.count(".") == ATLAS_MEMBER_SUFFIX.count(".") for m in members):
            raise UnsafeTarget("connected replica-set members are not part of the approved Atlas cluster")
        info["replica_set"] = bool(hello.get("setName"))
        info["members"] = len(members)
        auth = client.admin.command("connectionStatus", showPrivileges=True)["authInfo"]
        users = [(u.get("user"), u.get("db")) for u in auth.get("authenticatedUsers", [])]
        if users != [(ATLAS_TEST_USER, "admin")]:
            raise UnsafeTarget(f"connection is not authenticated solely as {ATLAS_TEST_USER!r}")
        info["roles"] = sorted(f"{r['role']}@{r['db']}" for r in auth.get("authenticatedUserRoles", []))
        problems = []
        for p in auth.get("authenticatedUserPrivileges", []):
            res = p.get("resource", {})
            if res.get("db") == ATLAS_TEST_DB:
                continue
            writes = sorted(set(p.get("actions", [])) - READ_ONLY_ACTIONS)
            if writes:
                problems.append(f"{res}: {writes[:6]}")
        if problems:
            raise UnsafeTarget(f"{ATLAS_TEST_USER!r} can change data outside {ATLAS_TEST_DB!r}: " + "; ".join(problems[:5]))
        info["write_privileges_outside_test_db"] = "none"
    return info


def require_safe(mongo_url, db_name, client=None):
    """Exit-style helper for scripts: static check, then live check when a client is given."""
    try:
        return verify_live(client, mongo_url, db_name) if client is not None else classify(mongo_url, db_name)
    except UnsafeTarget as exc:
        raise SystemExit(f"Refusing to run: {exc}")

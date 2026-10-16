"""Run the AAYNA release checks against an ISOLATED, official MongoDB test target.

Two modes, nothing else:

  --mongod PATH       start a THROWAWAY mongod (fresh empty data dir, non-default port,
                      loopback only, --auth with a generated user), DB `aayna_pytest`.
                      The data dir is deleted afterwards.

  --atlas-env FILE    use the dedicated Atlas test database `aayna_release_test` on the
                      approved cluster `aayna-dev`, as the dedicated user `aayna_test_app`.
                      FILE is a local, gitignored file containing one line
                          MONGO_URL=mongodb+srv://aayna_test_app:<password>@aayna-dev.<id>.mongodb.net/
                      The URI is never printed and is scrubbed from every saved log.

Before ANY write, scripts/verify/release_target_guard.py verifies the exact target:
allowlisted DB name (never `test_database`, `aayna_dev`, `aayna_test`, `aayna_prod`,
`aayna_staging`), and for Atlas: cluster name, replica-set members on the same Atlas
domain, authenticated as the dedicated user only, and no write-capable privilege on
any other database or the cluster. If any check fails, nothing is written.

Every environment variable the backend reads is set explicitly, so nothing falls
through to backend/.env (order webhook OFF, Emergent storage key empty). Between
suites the test database is reset by dropping its collections (needs readWrite only).

Usage (from the repo root, with the backend's Python environment):
    python scripts/verify/run_isolated_mongo_checks.py --atlas-env .env.release-test
    python scripts/verify/run_isolated_mongo_checks.py --mongod "C:\\Program Files\\MongoDB\\Server\\8.0\\bin\\mongod.exe"

Options:
    --suites LIST     comma list of: merge, release, backend, pytest   (default: release,backend,pytest)
                      merge   = scripts/verify/merge_rehearsal.py (duplicate-customer merge + rollback
                                + unique phone index, on synthetic data)
                      release also runs scripts/diagnostics/data_integrity.py (read-only)
    --apply-indexes   after each reset, apply the production index plan
                      (scripts/diagnostics/index_migration.py --apply) so suites run with the
                      unique indexes in place
    --out DIR         where to write the scrubbed logs and summary (default: a new temp dir)
    --check-only      Atlas mode: run the connection + isolation checks, write nothing
    --no-auth         mongod mode only: start without --auth (engines lacking auth)
    --keep-data       mongod mode only: keep the throwaway data directory

Exit code 0 only if the engine is official MongoDB AND every suite passed.
"""
import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote_plus, unquote, urlsplit

import pymongo

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(REPO, "backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from release_target_guard import (ATLAS_TEST_DB, LOCAL_TEST_DB, UnsafeTarget,  # noqa: E402
                                  classify, verify_live)

ORIGIN = "http://localhost:3000"

# Every variable the backend, its tests and the verify scripts read. All are set
# explicitly so load_dotenv() (which never overrides) cannot pull anything from
# the developer's backend/.env.
CONTROLLED_VARS = [
    "MONGO_URL", "DATABASE_URL", "DB_NAME", "APP_ENV", "JWT_SECRET", "ADMIN_EMAIL", "ADMIN_PASSWORD",
    "CORS_ORIGINS", "PUBLIC_SITE_URL", "REACT_APP_BACKEND_URL", "TRUSTED_PROXY_HOPS", "EMERGENT_LLM_KEY",
    "ORDER_WEBHOOK_ENABLED", "ORDER_WEBHOOK_URL", "ORDER_WEBHOOK_SECRET", "NOTIFICATION_ROUTER_MODE",
    "NOTIFICATION_ROUTER_NAME", "ALLOW_PRODUCTION_SEED", "API", "ORIGIN",
]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port, proc, secs=60):
    end = time.time() + secs
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            socket.create_connection(("127.0.0.1", port), 1).close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(10)


def read_atlas_env(path):
    """Read MONGO_URL from a local file that git must not track."""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        sys.exit(f"Atlas env file not found: {path}")
    folder = os.path.dirname(path)
    try:
        inside = subprocess.run(["git", "-C", folder, "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True).stdout.strip() == "true"
    except FileNotFoundError:  # git not installed: a folder git cannot see cannot be committed by it
        inside = False
    if inside:
        tracked = subprocess.run(["git", "-C", folder, "ls-files", "--error-unmatch", path],
                                 capture_output=True).returncode == 0
        ignored = subprocess.run(["git", "-C", folder, "check-ignore", "-q", path]).returncode == 0
        if tracked or not ignored:
            sys.exit(f"Refusing: {os.path.basename(path)} is {'tracked' if tracked else 'not gitignored'} "
                     "in this repository; credentials must stay out of git")
    url = ""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("MONGO_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not url:
        sys.exit(f"{os.path.basename(path)} has no MONGO_URL= line")
    return url


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mongod")
    mode.add_argument("--atlas-env")
    ap.add_argument("--suites", default="release,backend,pytest")
    ap.add_argument("--out")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--apply-indexes", action="store_true")
    ap.add_argument("--no-auth", action="store_true")
    ap.add_argument("--keep-data", action="store_true")
    a = ap.parse_args()
    suites = [x.strip() for x in a.suites.split(",") if x.strip()]
    bad = [x for x in suites if x not in ("merge", "release", "backend", "pytest")]
    if bad:
        sys.exit(f"unknown suite(s): {bad}")
    atlas = bool(a.atlas_env)
    test_db = ATLAS_TEST_DB if atlas else LOCAL_TEST_DB
    if not atlas and not os.path.isfile(a.mongod):
        sys.exit(f"mongod not found: {a.mongod}")

    out = a.out or tempfile.mkdtemp(prefix="aayna-release-report-")
    os.makedirs(out, exist_ok=True)
    bport = free_port()
    gen = {  # never printed; scrubbed from logs
        "mongo_user": "aayna_rel_" + secrets.token_hex(4),
        "mongo_pw": secrets.token_urlsafe(24),
        "jwt": secrets.token_urlsafe(48),
        "admin_email": f"release-qa-{secrets.token_hex(3)}@example.test",
        "admin_pw": secrets.token_urlsafe(18),
    }
    summary = {"started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "mode": "atlas" if atlas else "throwaway-mongod", "test_db": test_db, "isolation": {}, "suites": {}}
    mongod = backend = None
    dbpath = None
    secret_values = [gen["mongo_pw"], gen["jwt"], gen["admin_pw"], gen["admin_email"], gen["mongo_user"]]

    def scrub(text):
        for v in secret_values:
            if v:
                text = text.replace(v, "<redacted>")
        return text

    try:
        if atlas:
            mongo_url = read_atlas_env(a.atlas_env)
            parts = urlsplit(mongo_url)
            secret_values[:0] = [mongo_url, parts.password or "", unquote(parts.password or ""),
                                 parts.netloc.rsplit("@", 1)[-1]]
        else:
            mport = free_port()
            if 27017 in (mport, bport):
                sys.exit("Refusing: picked the default MongoDB port 27017")
            dbpath = tempfile.mkdtemp(prefix="aayna-isolated-mongo-")
            if os.listdir(dbpath):
                sys.exit("Refusing: throwaway data directory is not empty")
            cmd = [a.mongod, "--dbpath", dbpath, "--port", str(mport), "--bind_ip", "127.0.0.1",
                   "--logpath", os.path.join(dbpath, "mongod.log")]
            if not a.no_auth:
                cmd.append("--auth")
            mongod = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            if not wait_port(mport, mongod):
                sys.exit("mongod did not start (see its log in the data directory; rerun with --keep-data)")
            local = pymongo.MongoClient(f"mongodb://127.0.0.1:{mport}/", directConnection=True,
                                        serverSelectionTimeoutMS=10000)
            if a.no_auth:
                mongo_url = f"mongodb://127.0.0.1:{mport}/?directConnection=true"
            else:  # localhost exception: first user on a fresh instance
                try:
                    local.admin.command("createUser", gen["mongo_user"], pwd=gen["mongo_pw"],
                                        roles=[{"role": "readWrite", "db": test_db}, {"role": "dbAdmin", "db": test_db}])
                except pymongo.errors.OperationFailure as exc:
                    sys.exit(f"could not create the throwaway test user ({exc.code}: {exc.details.get('codeName')}); "
                             "this engine may not be official MongoDB")
                mongo_url = (f"mongodb://{quote_plus(gen['mongo_user'])}:{quote_plus(gen['mongo_pw'])}"
                             f"@127.0.0.1:{mport}/?authSource=admin&directConnection=true")
            secret_values[:0] = [mongo_url, quote_plus(gen["mongo_pw"])]
            summary["isolation"].update({"fresh_empty_data_dir_created_by_runner": True, "port_is_not_27017": True,
                                         "bound_to_loopback_only": True, "auth": not a.no_auth})

        try:
            classify(mongo_url, test_db)  # static allowlist check before any network access
            client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=20000)
            info = verify_live(client, mongo_url, test_db)
        except pymongo.errors.ConfigurationError as exc:
            sys.exit(f"Cannot resolve the database address ({type(exc).__name__}); check the cluster host in the "
                     "env file and this computer's DNS/network")
        except pymongo.errors.ServerSelectionTimeoutError:
            summary["isolation"]["reachable"] = False
            sys.exit("Cannot reach the database. For Atlas: add THIS computer's current public IP in Atlas > "
                     "Network Access (a single /32 entry). Do NOT add 0.0.0.0/0.")
        except pymongo.errors.OperationFailure as exc:
            sys.exit(f"Database refused the connection ({exc.code}: {exc.details.get('codeName')}); "
                     "check the user name/password in the env file")
        except UnsafeTarget as exc:
            summary["isolation"]["refused"] = str(exc)
            sys.exit(f"Refusing to run: {exc}")
        summary["engine"] = info["engine"]
        summary["engine_is_official_mongodb"] = info["official_mongodb"]
        summary["isolation"].update(info)  # recorded before any further database call
        try:
            existing = client[test_db].list_collection_names()
        except pymongo.errors.OperationFailure as exc:
            summary["isolation"]["list_collections_error"] = f"{exc.code} {exc.details.get('codeName')}: {exc.details.get('errmsg')}"
            for k in ("roles", "privileges"):
                print(f"  {k}: {info.get(k)}")
            sys.exit(f"Atlas reports the expected role but refused listCollections on {test_db} "
                     f"({exc.details.get('errmsg')}). No writes were made.")
        summary["isolation"].update({"collections_in_test_db_at_start": len(existing),
                                     "order_webhook": "disabled", "emergent_storage_key": "empty"})
        print(f"engine: {info['engine']}  |  target: {info['kind']}  |  db {test_db}")
        for k in ("cluster", "replica_set", "members", "roles", "write_privileges_outside_test_db",
                  "visible_databases"):
            if k in info:
                print(f"  {k}: {info[k]}")
        print(f"  collections already in {test_db}: {len(existing)} (dropped before each suite)")
        if a.check_only:
            print("check-only: no writes performed")
            summary["check_only"] = True
            return

        env = {k: v for k, v in os.environ.items() if k not in CONTROLLED_VARS}
        env.update({
            "MONGO_URL": mongo_url, "DATABASE_URL": "", "DB_NAME": test_db, "APP_ENV": "test",
            "JWT_SECRET": gen["jwt"], "ADMIN_EMAIL": gen["admin_email"], "ADMIN_PASSWORD": gen["admin_pw"],
            "CORS_ORIGINS": f"{ORIGIN},http://localhost:3001", "PUBLIC_SITE_URL": ORIGIN,
            "REACT_APP_BACKEND_URL": f"http://127.0.0.1:{bport}", "TRUSTED_PROXY_HOPS": "1",
            "EMERGENT_LLM_KEY": "", "ORDER_WEBHOOK_ENABLED": "false", "ORDER_WEBHOOK_URL": "",
            "ORDER_WEBHOOK_SECRET": "", "NOTIFICATION_ROUTER_MODE": "", "NOTIFICATION_ROUTER_NAME": "",
            "ALLOW_PRODUCTION_SEED": "false", "API": f"http://127.0.0.1:{bport}/api", "ORIGIN": ORIGIN,
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
        })

        def reset_test_db():
            verify_live(client, mongo_url, test_db)  # re-check right before the destructive step
            for name in client[test_db].list_collection_names():
                if not name.startswith("system."):
                    client[test_db].drop_collection(name)

        def fresh_backend():
            nonlocal backend
            stop(backend)
            reset_test_db()
            with open(os.path.join(out, "backend.log"), "a") as log:
                backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1",
                                            "--port", str(bport)], cwd=BACKEND, env=env, stdout=log,
                                           stderr=subprocess.STDOUT)
            if not wait_port(bport, backend, 120):
                raise RuntimeError("test backend did not start (see backend.log)")
            for _ in range(90):
                try:
                    h = json.load(urllib.request.urlopen(f"http://127.0.0.1:{bport}/api/health", timeout=5))
                    if h.get("database") == test_db:
                        return
                    raise RuntimeError(f"backend reports database {h.get('database')!r}, expected {test_db!r}")
                except OSError:
                    time.sleep(1)
            raise RuntimeError("test backend health check timed out")

        def run(name, argv, cwd=REPO, timeout=1500):
            t = time.time()
            try:
                p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=timeout)
                code, text = p.returncode, p.stdout + p.stderr
            except subprocess.TimeoutExpired as exc:
                code, text = "timeout", f"{exc}"
            with open(os.path.join(out, f"{name}.txt"), "w", encoding="utf-8") as fh:
                fh.write(scrub(text))
            tail = [ln for ln in text.strip().splitlines() if ln.strip()][-1:] or [""]
            summary["suites"][name] = {"exit": code, "seconds": round(time.time() - t), "last_line": scrub(tail[0])[:200]}
            print(f"  {name:10s} exit={code}  {scrub(tail[0])[:120]}")

        py = sys.executable
        summary["apply_indexes"] = a.apply_indexes
        for s in suites:
            fresh_backend()
            if a.apply_indexes and s != "merge":
                run(f"indexes_{s}", [py, "scripts/diagnostics/index_migration.py", "--apply"], timeout=300)
            if s == "merge":
                run("merge", [py, "scripts/verify/merge_rehearsal.py"])
            elif s == "release":
                run("release", [py, "scripts/verify/mongo_release_checks.py"])
                run("integrity", [py, "scripts/diagnostics/data_integrity.py"], timeout=300)
            elif s == "backend":
                run("backend", [py, "scripts/verify/backend_admin_checks.py"])
            elif s == "pytest":
                run("pytest", [py, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"], cwd=BACKEND)
        stop(backend)
        backend = None
        reset_test_db()  # leave the dedicated test database empty
        summary["test_db_emptied_after_run"] = True
    finally:
        stop(backend)
        stop(mongod)
        if dbpath:
            if a.keep_data:
                summary["data_dir_kept"] = dbpath
            else:
                shutil.rmtree(dbpath, ignore_errors=True)
                summary["data_dir_deleted"] = not os.path.exists(dbpath)
        blog = os.path.join(out, "backend.log")
        if os.path.exists(blog):
            with open(blog, encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
            with open(blog, "w", encoding="utf-8") as fh:
                fh.write(scrub(txt))
        summary["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:
            fh.write(scrub(json.dumps(summary, indent=2)))
        print(f"report: {out}")
    if summary.get("check_only"):
        sys.exit(0)

    # data_integrity exits 1 on REVIEW items (expected after deliberate concurrency runs); 2 = BLOCKER
    ok = summary.get("engine_is_official_mongodb") and all(
        (v["exit"] == 0 or (k == "integrity" and v["exit"] == 1)) for k, v in summary["suites"].items())
    if not summary.get("engine_is_official_mongodb"):
        print("VERDICT: NOT VERIFIED - engine is not official MongoDB")
    print("VERDICT:", "PASS" if ok else "NOT PASSED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

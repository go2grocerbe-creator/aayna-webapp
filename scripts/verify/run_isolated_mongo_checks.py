"""Run the AAYNA release checks against a THROWAWAY, ISOLATED official MongoDB.

Why: the five checks in mongo_release_checks.py (dashboard aggregation, low-stock
filter, customer list/detail, 10 concurrent orders for 3 units, concurrent
multi-item atomicity) only count as verified on real MongoDB. A different
database name on the instance that holds real data is NOT isolation, so this
runner starts its OWN mongod process:

  * a brand-new, empty data directory it creates itself (deleted afterwards)
  * a port other than 27017, bound to 127.0.0.1 only
  * --auth with a freshly generated user that can only touch `aayna_pytest`
  * freshly generated admin e-mail / password / JWT secret for the test backend
  * every environment variable the backend reads is set explicitly, so nothing
    falls through to backend/.env (order webhook OFF, Emergent storage key empty)

It refuses to run if the port is 27017, if the data directory is not empty, or if
the instance contains any real AAYNA database name. Generated secrets are never
printed and are scrubbed from the saved logs.

Usage (from the repo root, with the backend's Python environment):
    python scripts/verify/run_isolated_mongo_checks.py --mongod "C:\\Program Files\\MongoDB\\Server\\8.0\\bin\\mongod.exe"
    python scripts/verify/run_isolated_mongo_checks.py --mongod /usr/bin/mongod --suites release,pytest

Options:
    --mongod PATH     official mongod binary (required)
    --suites LIST     comma list of: release, backend, pytest   (default: all three)
                      release also runs scripts/diagnostics/data_integrity.py (read-only)
    --out DIR         where to write the scrubbed logs and summary (default: a new temp dir)
    --no-auth         start mongod without --auth (only for engines that lack auth;
                      the loopback binding and fresh data dir still apply)
    --keep-data       do not delete the throwaway data directory afterwards

Exit code 0 only if the engine is official MongoDB AND every suite exited 0.
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
from urllib.parse import quote_plus

import pymongo

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(REPO, "backend")
TEST_DB = "aayna_pytest"
REAL_DB_NAMES = {"aayna_dev", "aayna_test", "aayna_prod", "aayna_staging"}
SYSTEM_DBS = {"admin", "config", "local"}
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mongod", required=True)
    ap.add_argument("--suites", default="release,backend,pytest")
    ap.add_argument("--out")
    ap.add_argument("--no-auth", action="store_true")
    ap.add_argument("--keep-data", action="store_true")
    a = ap.parse_args()
    suites = [x.strip() for x in a.suites.split(",") if x.strip()]
    bad = [x for x in suites if x not in ("release", "backend", "pytest")]
    if bad:
        sys.exit(f"unknown suite(s): {bad}")
    if not os.path.isfile(a.mongod):
        sys.exit(f"mongod not found: {a.mongod}")

    out = a.out or tempfile.mkdtemp(prefix="aayna-isolated-report-")
    os.makedirs(out, exist_ok=True)
    mport, bport = free_port(), free_port()
    if 27017 in (mport, bport):
        sys.exit("Refusing: picked the default MongoDB port 27017")
    dbpath = tempfile.mkdtemp(prefix="aayna-isolated-mongo-")
    if os.listdir(dbpath):
        sys.exit("Refusing: throwaway data directory is not empty")

    gen = {  # never printed; scrubbed from logs
        "mongo_user": "aayna_rel_" + secrets.token_hex(4),
        "mongo_pw": secrets.token_urlsafe(24),
        "jwt": secrets.token_urlsafe(48),
        "admin_email": f"release-qa-{secrets.token_hex(3)}@example.test",
        "admin_pw": secrets.token_urlsafe(18),
    }
    summary = {"started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mongod_binary": a.mongod,
               "mongod_port": mport, "bind": "127.0.0.1", "auth": not a.no_auth, "test_db": TEST_DB,
               "isolation": {}, "suites": {}}
    mongod = backend = None
    secret_values = []

    def scrub(text):
        for v in secret_values:
            if v:
                text = text.replace(v, "<redacted>")
        return text

    try:
        cmd = [a.mongod, "--dbpath", dbpath, "--port", str(mport), "--bind_ip", "127.0.0.1",
               "--logpath", os.path.join(dbpath, "mongod.log")]
        if not a.no_auth:
            cmd.append("--auth")
        mongod = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if not wait_port(mport, mongod):
            sys.exit("mongod did not start (see its log in the data directory; rerun with --keep-data)")

        local = pymongo.MongoClient(f"mongodb://127.0.0.1:{mport}/", directConnection=True, serverSelectionTimeoutMS=10000)
        if a.no_auth:
            mongo_url = f"mongodb://127.0.0.1:{mport}/?directConnection=true"
        else:  # localhost exception: first user on a fresh instance
            try:
                local.admin.command("createUser", gen["mongo_user"], pwd=gen["mongo_pw"],
                                    roles=[{"role": "readWrite", "db": TEST_DB}, {"role": "dbAdmin", "db": TEST_DB}])
            except pymongo.errors.OperationFailure as exc:
                sys.exit(f"could not create the throwaway test user ({exc.code}: {exc.details.get('codeName')}); "
                         "this engine may not be official MongoDB")
            mongo_url = (f"mongodb://{quote_plus(gen['mongo_user'])}:{quote_plus(gen['mongo_pw'])}"
                         f"@127.0.0.1:{mport}/?authSource=admin&directConnection=true")
        secret_values[:] = [mongo_url, gen["mongo_pw"], gen["jwt"], gen["admin_pw"], quote_plus(gen["mongo_pw"]),
                            gen["admin_email"], gen["mongo_user"]]
        client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=10000)

        build = client[TEST_DB].command("buildInfo")
        official = "ferretdbVersion" not in build and bool(build.get("version"))
        engine = f"MongoDB {build.get('version')}" if official else f"FerretDB {build.get('ferretdbVersion')}"
        names = set(client.list_database_names())
        real = names & REAL_DB_NAMES
        unexpected = names - SYSTEM_DBS - {TEST_DB}
        summary["engine"] = engine
        summary["engine_is_official_mongodb"] = official
        summary["isolation"] = {
            "fresh_empty_data_dir_created_by_runner": True,
            "port_is_not_27017": mport != 27017,
            "bound_to_loopback_only": True,
            "databases_present_at_start": sorted(names),
            "real_aayna_databases_present": sorted(real),
            "test_user_scoped_to": None if a.no_auth else TEST_DB,
            "order_webhook": "disabled", "emergent_storage_key": "empty",
        }
        if real or unexpected:
            sys.exit(f"Refusing: instance is not empty/isolated (found {sorted(real | unexpected)})")
        print(f"engine: {engine}  |  isolated instance on 127.0.0.1:{mport}  |  db {TEST_DB}")

        env = {k: v for k, v in os.environ.items() if k not in CONTROLLED_VARS}
        env.update({
            "MONGO_URL": mongo_url, "DATABASE_URL": "", "DB_NAME": TEST_DB, "APP_ENV": "test",
            "JWT_SECRET": gen["jwt"], "ADMIN_EMAIL": gen["admin_email"], "ADMIN_PASSWORD": gen["admin_pw"],
            "CORS_ORIGINS": f"{ORIGIN},http://localhost:3001", "PUBLIC_SITE_URL": ORIGIN,
            "REACT_APP_BACKEND_URL": f"http://127.0.0.1:{bport}", "TRUSTED_PROXY_HOPS": "1",
            "EMERGENT_LLM_KEY": "", "ORDER_WEBHOOK_ENABLED": "false", "ORDER_WEBHOOK_URL": "",
            "ORDER_WEBHOOK_SECRET": "", "NOTIFICATION_ROUTER_MODE": "", "NOTIFICATION_ROUTER_NAME": "",
            "ALLOW_PRODUCTION_SEED": "false", "API": f"http://127.0.0.1:{bport}/api", "ORIGIN": ORIGIN,
            "PYTHONDONTWRITEBYTECODE": "1",
        })

        def fresh_backend():
            nonlocal backend
            stop(backend)
            client.drop_database(TEST_DB)
            log = open(os.path.join(out, "backend.log"), "a")
            backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1",
                                        "--port", str(bport)], cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT)
            if not wait_port(bport, backend, 90):
                raise RuntimeError("test backend did not start (see backend.log)")
            for _ in range(60):
                try:
                    h = json.load(urllib.request.urlopen(f"http://127.0.0.1:{bport}/api/health", timeout=5))
                    if h.get("database") == TEST_DB:
                        return
                    raise RuntimeError(f"backend reports database {h.get('database')!r}, expected {TEST_DB!r}")
                except OSError:
                    time.sleep(1)
            raise RuntimeError("test backend health check timed out")

        def run(name, argv, cwd=REPO, timeout=900):
            t = time.time()
            try:
                p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
                code, text = p.returncode, p.stdout + p.stderr
            except subprocess.TimeoutExpired as exc:
                code, text = "timeout", f"{exc}"
            with open(os.path.join(out, f"{name}.txt"), "w", encoding="utf-8") as fh:
                fh.write(scrub(text))
            tail = [ln for ln in text.strip().splitlines() if ln.strip()][-1:] or [""]
            summary["suites"][name] = {"exit": code, "seconds": round(time.time() - t), "last_line": scrub(tail[0])[:200]}
            print(f"  {name:10s} exit={code}  {scrub(tail[0])[:120]}")

        py = sys.executable
        for s in suites:
            fresh_backend()
            if s == "release":
                run("release", [py, "scripts/verify/mongo_release_checks.py"])
                run("integrity", [py, "scripts/diagnostics/data_integrity.py"], timeout=300)
            elif s == "backend":
                run("backend", [py, "scripts/verify/backend_admin_checks.py"])
            elif s == "pytest":
                run("pytest", [py, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"], cwd=BACKEND)
        stop(backend)
        backend = None
    finally:
        stop(backend)
        stop(mongod)
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

    # data_integrity exits 1 on REVIEW items (expected after deliberate concurrency runs); 2 = BLOCKER
    ok = summary.get("engine_is_official_mongodb") and all(
        (v["exit"] == 0 or (k == "integrity" and v["exit"] == 1)) for k, v in summary["suites"].items())
    if not summary.get("engine_is_official_mongodb"):
        print("VERDICT: NOT VERIFIED — engine is not official MongoDB")
    print("VERDICT:", "PASS" if ok else "NOT PASSED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

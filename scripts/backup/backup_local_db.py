"""Back up the LOCAL AAYNA MongoDB databases and verify the backup. Read-only on the database.

    python scripts/backup/backup_local_db.py --env-file ..\\Aayna-Webapp\\backend\\.env ^
        --dbs aayna_dev,aayna_test --out-root ..\\aayna-private-backups [--probe]

* Refuses any MONGO_URL that is not a loopback host (this is the founder-PC tool).
* Uses `mongodump --gzip --out` when the MongoDB Database Tools are installed;
  otherwise writes the same directory layout itself (<db>/<collection>.bson +
  <collection>.metadata.json) from raw BSON, which `mongorestore` can restore.
* Verifies every collection: document count and an order-independent SHA-256 over
  the raw BSON bytes of every document must match the live database exactly.
* Writes manifest.json (counts, hashes, sizes, index names; no records) and
  RESTORE.txt. Prints aggregate numbers only - never documents or the URI.

--probe only reports engine, tools and per-database collection counts.
Exit code 0 only when the backup was written AND verified.
"""
import argparse
import glob
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

import bson
import pymongo
from bson.codec_options import CodecOptions
from bson.raw_bson import RawBSONDocument

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
RAW = CodecOptions(document_class=RawBSONDocument)


def read_env(path):
    vals = {}
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def find_mongodump():
    found = shutil.which("mongodump")
    if found:
        return found
    pats = [r"C:\Program Files\MongoDB\Tools\*\bin\mongodump.exe", r"C:\Program Files\MongoDB\Server\*\bin\mongodump.exe"]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def content_digest(raw_docs):
    """Order-independent digest of a collection: sha256 of the sorted per-document sha256s."""
    hashes = sorted(hashlib.sha256(d.raw).hexdigest() for d in raw_docs)
    h = hashlib.sha256()
    for x in hashes:
        h.update(x.encode())
    return len(hashes), h.hexdigest()


def read_backup_docs(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return list(bson.decode_file_iter(fh, codec_options=RAW))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--dbs", default="aayna_dev,aayna_test")
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--force-python-export", action="store_true", help="ignore mongodump (testing)")
    a = ap.parse_args()

    env = read_env(a.env_file)
    url = env.get("MONGO_URL", "")
    hosts = [h.split(":")[0].strip("[]").lower() for h in urlsplit(url).netloc.rsplit("@", 1)[-1].split(",") if h]
    if not url or not hosts or not all(h in LOOPBACK for h in hosts):
        sys.exit("Refusing: MONGO_URL in the env file is not a local (loopback) MongoDB")
    client = pymongo.MongoClient(url, serverSelectionTimeoutMS=8000)
    try:
        client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Local MongoDB is not reachable ({type(exc).__name__}). Is the MongoDB service running?")
    build = client.admin.command("buildInfo")
    engine = (f"FerretDB {build['ferretdbVersion']}" if "ferretdbVersion" in build
              else f"MongoDB {build.get('version')}")
    hello = client.admin.command("hello")
    present = set(client.list_database_names())
    dbs = [d.strip() for d in a.dbs.split(",") if d.strip()]
    dump_tool = None if a.force_python_export else find_mongodump()
    print(f"engine: {engine} | modules: {build.get('modules') or 'community'} | "
          f"topology: {'replica set' if hello.get('setName') else 'standalone'} | host OS: {platform.system()}")
    print(f"mongodump: {'found' if dump_tool else 'not found (raw-BSON export will be used)'}")
    print(f"databases on this server: {len(present)} | requested: {dbs}")
    for d in dbs:
        if d not in present:
            print(f"  {d}: NOT PRESENT")
            continue
        names = sorted(client[d].list_collection_names())
        print(f"  {d}: {len(names)} collections, {sum(client[d][c].estimated_document_count() for c in names)} documents")
    if a.probe:
        return 0
    missing = [d for d in dbs if d not in present]
    if missing:
        sys.exit(f"Refusing: requested database(s) not present: {missing}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = os.path.abspath(os.path.join(a.out_root, f"aayna-local-{stamp}"))
    if os.path.exists(root):
        sys.exit(f"Refusing: {root} already exists")
    dump_dir = os.path.join(root, "dump")
    os.makedirs(dump_dir)
    manifest = {"created_utc": stamp, "engine": engine, "method": None, "databases": {}}

    # Live snapshot of counts/digests (the local dev DB is expected to be idle during backup).
    live = {d: {c: content_digest(client[d].get_collection(c, codec_options=RAW).find())
                for c in sorted(client[d].list_collection_names()) if not c.startswith("system.")}
            for d in dbs}

    if dump_tool:
        manifest["method"] = "mongodump --gzip"
        for d in dbs:
            r = subprocess.run([dump_tool, f"--uri={url}", f"--db={d}", f"--out={dump_dir}", "--gzip", "--quiet"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit(f"mongodump failed for {d} (exit {r.returncode}); backup NOT valid")
    else:
        manifest["method"] = "raw BSON export (mongorestore-compatible directory layout)"
        for d in dbs:
            os.makedirs(os.path.join(dump_dir, d))
            for c in live[d]:
                coll = client[d].get_collection(c, codec_options=RAW)
                with open(os.path.join(dump_dir, d, f"{c}.bson"), "wb") as fh:
                    for doc in coll.find().sort("_id", 1):
                        fh.write(doc.raw)
                idx = [dict(v, name=k, key=dict(v["key"])) for k, v in client[d][c].index_information().items()]
                for i in idx:
                    i.pop("ns", None)
                with open(os.path.join(dump_dir, d, f"{c}.metadata.json"), "w", encoding="utf-8") as fh:
                    json.dump({"collectionName": c, "options": {}, "indexes": idx}, fh, default=str)

    # Verify: every collection in the backup must match the live digest exactly.
    ok = True
    for d in dbs:
        entry = {}
        for c, (n_live, h_live) in live[d].items():
            files = [os.path.join(dump_dir, d, f"{c}.bson{ext}") for ext in (".gz", "")]
            path = next((f for f in files if os.path.exists(f)), None)
            if not path:
                ok = False
                entry[c] = {"status": "MISSING FILE", "live_count": n_live}
                continue
            n_bak, h_bak = content_digest(read_backup_docs(path))
            match = (n_bak, h_bak) == (n_live, h_live)
            ok &= match
            entry[c] = {"status": "verified" if match else "MISMATCH", "count": n_bak, "live_count": n_live,
                        "content_sha256": h_bak, "file": os.path.relpath(path, root),
                        "bytes": os.path.getsize(path),
                        "indexes": sorted(client[d][c].index_information())}
        manifest["databases"][d] = entry
    manifest["verified"] = ok
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    with open(os.path.join(root, "RESTORE.txt"), "w", encoding="utf-8") as fh:
        fh.write("PRIVATE: contains real customer data. Do not commit, upload or share.\n\n"
                 "Restore into a NEW database name first and compare before replacing anything, e.g.\n"
                 "  mongorestore --uri=mongodb://localhost:27017 --nsFrom=\"aayna_dev.*\" "
                 "--nsTo=\"aayna_dev_restored.*\" " + ("--gzip " if dump_tool else "") + "dump\n")
    print(f"\nbackup folder: {root}\nmethod: {manifest['method']}")
    for d, colls in manifest["databases"].items():
        bad = [c for c, e in colls.items() if e["status"] != "verified"]
        print(f"  {d}: {len(colls)} collections, {sum(e.get('count', 0) for e in colls.values())} documents, "
              f"{'ALL VERIFIED' if not bad else 'PROBLEMS: ' + ', '.join(bad)}")
    print("VERIFIED" if ok else "BACKUP NOT VERIFIED - do not proceed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

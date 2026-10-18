# Deployment probe only (branch probe/vercel-python-api): can a Python function in the
# CRA project see ../backend? Returns file presence only. No DB, no secrets.
import os, sys, pathlib
from fastapi import FastAPI

app = FastAPI()
HERE = pathlib.Path(__file__).resolve()

@app.get("/api/{rest:path}")
def probe(rest: str = ""):
    listing = sorted(os.listdir("/var/task"))[:60]
    sym = pathlib.Path("/var/task/aayna_backend")
    info = {"exists": sym.exists(), "is_symlink": sym.is_symlink(), "db_py": (sym / "db.py").exists(),
            "files": sorted(os.listdir(sym))[:15] if sym.exists() else None}
    cands = [HERE.parents[i] / "backend" for i in range(0, 4)] + [pathlib.Path("/var/task/backend"), pathlib.Path.cwd() / "backend", pathlib.Path.cwd() / "../backend"]
    return {"probe": True, "py": sys.version.split()[0], "here": str(HERE), "cwd": os.getcwd(),
            "region": os.environ.get("VERCEL_REGION"),
            "listing": listing, "symlink": info, "backend": {str(c): (c / "db.py").exists() for c in cands}}

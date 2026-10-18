# Deployment probe only (branch probe/vercel-python-api). No DB, no secrets.
import asyncio, os
from fastapi import FastAPI

app = FastAPI()
STATE = {"n": 0, "loops": [], "startup": False}

@app.on_event("startup")
async def _s():
    STATE["startup"] = True

@app.get("/api/{rest:path}")
async def probe(rest: str = ""):
    STATE["n"] += 1
    lid = id(asyncio.get_running_loop())
    if lid not in STATE["loops"]:
        STATE["loops"].append(lid)
    return {"pid": os.getpid(), "n": STATE["n"], "distinct_loops": len(STATE["loops"]), "startup_ran": STATE["startup"],
            "backend_copied": os.path.exists("/var/task/aayna_backend/db.py")}

"""
Vercel entry point for the AAYNA FastAPI backend (same project and domain as the
React frontend, so /api is same-origin: no CORS, one HTTPS URL).

The backend source lives in ../backend. Vercel only bundles files inside this
project's root directory (frontend/), so the build command in vercel.json copies
backend/*.py into frontend/aayna_backend/ before the function is packaged.
That copy is a build artifact (git-ignored); backend/ remains the only source.

All configuration (APP_ENV, MONGO_URL, DB_NAME, JWT_SECRET, CORS_ORIGINS,
PUBLIC_SITE_URL, ...) comes from the Vercel project's environment variables.
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "aayna_backend"
if not (_BACKEND / "server.py").exists():  # fail loudly rather than serve a half-configured API
    raise RuntimeError("Backend sources missing from the bundle (vercel.json buildCommand must copy them)")
sys.path.insert(0, str(_BACKEND))

from server import app  # noqa: E402,F401  (ASGI app picked up by the Vercel Python runtime)

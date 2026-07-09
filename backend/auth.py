import os
import time
import uuid
import bcrypt
import jwt
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from db import db, now_iso

logger = logging.getLogger("aayna.auth")

JWT_ALGORITHM = "HS256"
ACCESS_TTL_DAYS = 7
ADMIN_ROLES = {"super_admin", "admin", "order_manager", "product_manager"}

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in ("production", "prod")
_KNOWN_LOCAL_ENVS = {"development", "dev", "local", "test", "testing"}
_DEV_FALLBACK_SECRET = "dev-only-insecure-secret-do-not-use-in-production"
_DEV_FALLBACK_ADMIN = ("admin@aayna.xyz", "ChangeMe123!")

# Hosting-platform env vars that indicate this process is running on a real
# deployment target rather than a developer's machine.
_HOST_PLATFORM_MARKERS = (
    "RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "DYNO",
    "KUBERNETES_SERVICE_HOST", "WEBSITE_SITE_NAME", "K_SERVICE",
    "AWS_LAMBDA_FUNCTION_NAME", "VERCEL",
)


def _looks_like_non_local_deployment() -> bool:
    if any(os.environ.get(marker) for marker in _HOST_PLATFORM_MARKERS):
        return True
    site_url = (os.environ.get("PUBLIC_SITE_URL") or "").strip().lower()
    if site_url and "localhost" not in site_url and "127.0.0.1" not in site_url:
        return True
    return False

# --- Simple in-memory login rate limiting (single instance) ---
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60       # block for 15 minutes after too many failures
ATTEMPT_WINDOW_SECONDS = 15 * 60  # failures older than this are forgotten
_failed_logins = {}  # "ip:email" -> {count, first_ts, locked_until}

auth_router = APIRouter(prefix="/api/admin")


def get_jwt_secret() -> str:
    """JWT secret must come from the environment. Fail fast in production; allow a dev fallback locally."""
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    if IS_PRODUCTION:
        raise RuntimeError("JWT_SECRET environment variable is required in production but is not set.")
    logger.warning("JWT_SECRET is not set — using an INSECURE development fallback. Set JWT_SECRET before deploying.")
    return _DEV_FALLBACK_SECRET


def _secret() -> str:
    return get_jwt_secret()


def get_admin_credentials():
    """Admin credentials come from ADMIN_EMAIL / ADMIN_PASSWORD. No insecure default is created in production."""
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if email and password:
        return email.strip().lower(), password
    if IS_PRODUCTION:
        return None, None
    logger.warning("ADMIN_EMAIL/ADMIN_PASSWORD not set — using local dev defaults. Set them before deploying.")
    return _DEV_FALLBACK_ADMIN[0], _DEV_FALLBACK_ADMIN[1]


def validate_security_config():
    """Called on startup. In production, refuse to start with missing or default secrets."""
    if not IS_PRODUCTION:
        if APP_ENV not in _KNOWN_LOCAL_ENVS and _looks_like_non_local_deployment():
            using_dev_secret = not os.environ.get("JWT_SECRET")
            using_default_admin = not (os.environ.get("ADMIN_EMAIL") and os.environ.get("ADMIN_PASSWORD"))
            if using_dev_secret or using_default_admin:
                raise RuntimeError(
                    f"APP_ENV={APP_ENV!r} is not recognized as production, but this deployment "
                    "looks non-local (hosting platform or PUBLIC_SITE_URL detected) and is missing "
                    "JWT_SECRET and/or ADMIN_EMAIL+ADMIN_PASSWORD. Refusing to boot with dev "
                    "defaults. Set APP_ENV=production and configure real secrets/credentials."
                )
            logger.critical(
                "APP_ENV=%r is not recognized as 'production' but this deployment looks non-local "
                "(hosting platform or PUBLIC_SITE_URL detected). Set APP_ENV=production to enable "
                "full production safety checks (CORS_ORIGINS, PUBLIC_SITE_URL, webhook config).",
                APP_ENV,
            )
        return
    missing = [k for k in ("JWT_SECRET", "ADMIN_EMAIL", "ADMIN_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required production environment variables: {', '.join(missing)}")
    if os.environ.get("ADMIN_PASSWORD") == _DEV_FALLBACK_ADMIN[1]:
        raise RuntimeError("Refusing to start in production with the default ADMIN_PASSWORD. Set a strong ADMIN_PASSWORD.")
    if os.environ.get("JWT_SECRET") == _DEV_FALLBACK_SECRET:
        raise RuntimeError("Refusing to start in production with the development JWT_SECRET. Set a strong JWT_SECRET.")

    # Milestone 4A — additional production safety checks.
    site_url = (os.environ.get("PUBLIC_SITE_URL") or "").strip()
    if not site_url or "localhost" in site_url or "127.0.0.1" in site_url:
        raise RuntimeError("PUBLIC_SITE_URL must be set to your real domain in production (not empty or localhost).")
    cors = (os.environ.get("CORS_ORIGINS") or "").strip()
    if cors in ("", "*"):
        raise RuntimeError("CORS_ORIGINS must be restricted to your real frontend origin(s) in production, not '*'.")
    webhook_enabled = str(os.environ.get("ORDER_WEBHOOK_ENABLED", "")).strip().lower() in ("1", "true", "yes", "on")
    if webhook_enabled and not (os.environ.get("ORDER_WEBHOOK_URL") or "").strip():
        raise RuntimeError("ORDER_WEBHOOK_ENABLED is true but ORDER_WEBHOOK_URL is not set.")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user.get("name"),
        "email": user["email"],
        "role": user["role"],
        "status": user.get("status", "active"),
    }


async def get_current_admin(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user or user.get("status") != "active":
        raise HTTPException(status_code=401, detail="Account not found or inactive")
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    user.pop("password_hash", None)
    return user


class LoginRequest(BaseModel):
    email: str
    password: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rl_key(ip: str, email: str) -> str:
    # Keyed by IP+email so an attacker hammering one email from a single
    # source cannot lock the real admin out from their own IP (H2). A load
    # balancer rotating a legitimate user's IP just resets their own counter.
    return f"{ip}:{email}"


def check_login_allowed(ip: str, email: str):
    """Raise 429 if this IP+email is temporarily locked out."""
    rec = _failed_logins.get(_rl_key(ip, email))
    if not rec:
        return
    now = time.time()
    if rec["locked_until"] > now:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please try again in a few minutes.")
    if now - rec["first_ts"] > ATTEMPT_WINDOW_SECONDS:
        _failed_logins.pop(_rl_key(ip, email), None)


def record_failed_login(ip: str, email: str):
    key = _rl_key(ip, email)
    now = time.time()
    rec = _failed_logins.get(key)
    if not rec or now - rec["first_ts"] > ATTEMPT_WINDOW_SECONDS:
        rec = {"count": 0, "first_ts": now, "locked_until": 0}
    rec["count"] += 1
    if rec["count"] >= MAX_FAILED_ATTEMPTS:
        rec["locked_until"] = now + LOCKOUT_SECONDS
    _failed_logins[key] = rec


def clear_failed_logins(ip: str, email: str):
    _failed_logins.pop(_rl_key(ip, email), None)


@auth_router.post("/login")
async def login(body: LoginRequest, request: Request):
    email = body.email.strip().lower()
    ip = _client_ip(request)
    check_login_allowed(ip, email)
    user = await db.users.find_one({"email": email})
    # Generic error — never reveal whether the email or the password was wrong.
    if not user or not verify_password(body.password, user["password_hash"]) or user.get("status") != "active":
        record_failed_login(ip, email)
        logger.warning("Failed admin login for %s from %s", email, ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    clear_failed_logins(ip, email)
    token = create_access_token(user)
    return {"token": token, "user": public_user(user)}


@auth_router.get("/me")
async def me(current=Depends(get_current_admin)):
    return public_user(current)


@auth_router.post("/logout")
async def logout(current=Depends(get_current_admin)):
    return {"ok": True}


async def seed_admin():
    email, password = get_admin_credentials()
    if not email or not password:
        logger.warning(
            "ADMIN_EMAIL/ADMIN_PASSWORD are not set in production — skipping admin seeding. "
            "Set them and restart to create the admin account."
        )
        return
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "name": "Super Admin",
            "email": email,
            "password_hash": hash_password(password),
            "role": "super_admin",
            "status": "active",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hash_password(password), "updated_at": now_iso()}},
        )


async def ensure_indexes():
    try:
        await db.users.create_index("email", unique=True)
        await db.products.create_index("slug")
        await db.orders.create_index("order_number")
        await db.customers.create_index("phone")
    except Exception:
        pass

"""
AAYNA customer identity: accounts, sessions, email verification, password
recovery, Google sign-in, profile/addresses/security and account-linked orders.

Deliberately separate from admin authentication (auth.py):
  * different collections (customer_accounts / customer_identities / customer_sessions,
    never `users`);
  * different credential: an opaque random session id in an HttpOnly cookie
    (only its SHA-256 is stored) instead of the admin's signed Bearer JWT. A
    customer cookie is never read by admin endpoints and an admin JWT is never
    read here, so neither can stand in for the other;
  * no role field a client could influence.

CSRF: state-changing customer requests must carry the custom header
X-AAYNA-CSRF (browsers cannot add it cross-site without a CORS preflight, which
only the site's own origins pass) and, when present, an allowed Origin. The
session cookie is also SameSite=Lax.

Tokens sent by email (verify, reset, email change, order claim) are 256-bit
random values; only their SHA-256 is stored, each has a purpose and expiry and
is consumed atomically (single use). Links carry the token in the URL fragment
(#token=...), which browsers never send to servers or in Referer headers.
"""
import base64
import hashlib
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlencode

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

import emailer
import ratelimit
from auth import IS_PRODUCTION, _client_ip, require
from db import db, now_iso
from seed_data import BD_DISTRICTS

logger = logging.getLogger("aayna.customer")

customer_router = APIRouter(prefix="/api")
customer_admin_router = APIRouter(prefix="/api/admin")

SESSION_TTL_DAYS = 30
SESSION_IDLE_DAYS = 14
VERIFY_TTL_HOURS = 24
RESET_TTL_MINUTES = 15
EMAIL_CHANGE_TTL_HOURS = 24
CLAIM_TTL_HOURS = 24
GOOGLE_LINK_TTL_MINUTES = 15
OAUTH_STATE_TTL_MINUTES = 10
RECENT_LOGIN_MINUTES = 15
RESEND_COOLDOWN_SECONDS = 60
MIN_PASSWORD_LEN = 12
MAX_PASSWORD_LEN = 256
MAX_ADDRESSES = 10

GENERIC_REGISTER_MSG = ("Thanks! If this email address can be used, we've sent a confirmation link to it. "
                        "Please check your inbox (and spam folder) to activate your account.")
GENERIC_RESET_MSG = "If an eligible account exists for this email, we've sent password reset instructions."
GENERIC_RESEND_MSG = "If this email belongs to an account awaiting confirmation, we've sent a new link."
LOGIN_FAILED_MSG = "Invalid email or password"

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
PHONE_RE = re.compile(r"^(?:\+?880|0)1[3-9]\d{8}$")
NEXT_RE = re.compile(r"^/(?:account|checkout|cart|shop|track-order|order-confirmation|product|category)?(?:[/A-Za-z0-9_\-]*)$")

# Very common passwords that satisfy the length rule (shorter ones are already refused).
COMMON_PASSWORDS = {
    "123456789012", "1234567890123", "12345678901234", "123456123456", "111111111111",
    "000000000000", "121212121212", "123123123123", "password1234", "password12345",
    "password123456", "passwordpassword", "qwertyuiopas", "qwerty123456", "qwertyqwerty",
    "1q2w3e4r5t6y", "1qaz2wsx3edc", "asdfghjkl123", "iloveyou1234", "iloveyouiloveyou",
    "aaaaaaaaaaaa", "abcdefghijkl", "abc123abc123", "abcd1234abcd", "letmein12345",
    "welcome12345", "welcome123456", "admin1234567", "administrator", "changeme1234",
    "football1234", "baseball1234", "monkey123456", "dragon123456", "sunshine1234",
    "princess1234", "bangladesh123", "bangladesh1234", "dhaka1234567", "aayna1234567",
    "aaynaaayna12", "shopaayna123", "password!234", "p@ssw0rd1234", "p@ssword1234",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> Optional[str]:
    e = (email or "").strip()
    if len(e) > 254 or not EMAIL_RE.match(e):
        return None
    local, domain = e.rsplit("@", 1)
    return f"{local}@{domain.lower()}".lower()


def normalize_phone(phone: str) -> Optional[str]:
    p = re.sub(r"[\s\-]", "", phone or "")
    if not PHONE_RE.match(p):
        return None
    digits = re.sub(r"\D", "", p)
    if digits.startswith("880"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    return "+880" + digits


def clean_text(value: str, limit: int) -> str:
    v = re.sub(r"[\x00-\x1f\x7f]", " ", value or "").strip()
    return re.sub(r"\s{2,}", " ", v)[:limit]


def password_problem(password: str, email: str = "") -> Optional[str]:
    pw = password or ""
    if len(pw) < MIN_PASSWORD_LEN:
        return f"Use at least {MIN_PASSWORD_LEN} characters. A short phrase of a few words works well."
    if len(pw) > MAX_PASSWORD_LEN:
        return f"Use at most {MAX_PASSWORD_LEN} characters."
    low = pw.lower()
    if low in COMMON_PASSWORDS or len(set(pw)) <= 2:
        return "This password is too common. Please choose something harder to guess."
    if re.fullmatch(r"(\d)\1*|0123456789\d*|1234567890\d*", pw):
        return "This password is too easy to guess. Please choose something harder to guess."
    local = (email or "").split("@")[0].lower()
    if len(local) >= 4 and local in low:
        return "Your password should not contain your email address."
    return None


def hash_password(password: str) -> str:
    # bcrypt reads only the first 72 bytes; pre-hashing keeps every character of
    # long passphrases significant. "v2$" marks the scheme.
    digest = base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())
    return "v2$" + bcrypt.hashpw(digest, bcrypt.gensalt(rounds=12)).decode("utf-8")


_DUMMY_HASH = None


def verify_password(password: str, stored: Optional[str]) -> bool:
    global _DUMMY_HASH
    if not stored or not stored.startswith("v2$"):
        # Burn comparable time so unknown accounts are not faster to reject.
        if _DUMMY_HASH is None:
            _DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(rounds=12))
        bcrypt.checkpw(b"x", _DUMMY_HASH)
        return False
    digest = base64.b64encode(hashlib.sha256((password or "").encode("utf-8")).digest())
    try:
        return bcrypt.checkpw(digest, stored[3:].encode("utf-8"))
    except ValueError:
        return False


def _ua(request: Request) -> str:
    return clean_text(request.headers.get("user-agent", ""), 160)


def _ip_hash(request: Request) -> str:
    return _sha("ip|" + _client_ip(request))[:24]


async def security_event(account_id: str, kind: str, request: Optional[Request] = None, detail: str = ""):
    await db.security_events.insert_one({
        "id": str(uuid.uuid4()), "account_id": account_id, "type": kind, "detail": detail[:200],
        "ip_hash": _ip_hash(request) if request else None, "user_agent": _ua(request) if request else None,
        "created_at": now_iso(),
    })


def _allowed_origins() -> set:
    origins = {o.strip().rstrip("/") for o in (os.environ.get("CORS_ORIGINS") or "").split(",") if o.strip() and o.strip() != "*"}
    site = (os.environ.get("PUBLIC_SITE_URL") or "").strip().rstrip("/")
    if site:
        origins.add(site)
    return origins


async def csrf_guard(request: Request):
    """Required on every state-changing customer endpoint."""
    if request.headers.get("x-aayna-csrf") != "1":
        raise HTTPException(status_code=403, detail="Request blocked. Please reload the page and try again.")
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin and origin not in _allowed_origins():
        raise HTTPException(status_code=403, detail="Request blocked. Please reload the page and try again.")


# ---------------------------------------------------------------------------
# Sessions (opaque cookie, server-side record)
# ---------------------------------------------------------------------------
def _secure_cookies(request: Request) -> bool:
    if IS_PRODUCTION:
        return True
    if (os.environ.get("COOKIE_SECURE") or "").strip().lower() in ("1", "true", "yes"):
        return True
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


def session_cookie_name(request: Request) -> str:
    # __Host- cookies must be Secure, Path=/ and host-only: they cannot be set by
    # a sibling subdomain or overwritten over plain HTTP.
    return "__Host-aayna_sid" if _secure_cookies(request) else "aayna_sid"


def _set_cookie(response: Response, request: Request, name: str, value: str, max_age: int, path: str = "/"):
    secure = _secure_cookies(request)
    if secure and name.startswith("__Host-"):
        path = "/"
    response.set_cookie(name, value, max_age=max_age, httponly=True, secure=secure, samesite="lax", path=path)


def _read_session_token(request: Request) -> Optional[str]:
    return request.cookies.get("__Host-aayna_sid") or request.cookies.get("aayna_sid")


async def create_session(response: Response, request: Request, account: dict, method: str) -> dict:
    raw = secrets.token_urlsafe(32)
    now = _now()
    sess = {
        "id": str(uuid.uuid4()), "account_id": account["id"], "token_hash": _sha(raw), "method": method,
        "created_at": _iso(now), "last_seen_at": _iso(now),
        "expires_at": _iso(now + timedelta(days=SESSION_TTL_DAYS)), "revoked_at": None,
        "user_agent": _ua(request), "ip_hash": _ip_hash(request),
    }
    await db.customer_sessions.insert_one({**sess})
    _set_cookie(response, request, session_cookie_name(request), raw, SESSION_TTL_DAYS * 86400)
    await db.customer_accounts.update_one({"id": account["id"]}, {"$set": {"last_login_at": now_iso()}})
    await security_event(account["id"], f"login_{method}", request)
    return sess


def clear_session_cookie(response: Response, request: Request):
    for name in ("__Host-aayna_sid", "aayna_sid"):
        response.delete_cookie(name, path="/", secure=_secure_cookies(request) if name.startswith("__Host-") else False,
                               httponly=True, samesite="lax")


async def revoke_sessions(account_id: str, except_session_id: Optional[str] = None) -> int:
    q = {"account_id": account_id, "revoked_at": None}
    if except_session_id:
        q["id"] = {"$ne": except_session_id}
    res = await db.customer_sessions.update_many(q, {"$set": {"revoked_at": now_iso()}})
    return res.modified_count


async def _session_from_request(request: Request):
    raw = _read_session_token(request)
    if not raw or len(raw) > 100:
        return None, None
    sess = await db.customer_sessions.find_one({"token_hash": _sha(raw), "revoked_at": None}, {"_id": 0})
    if not sess:
        return None, None
    now = _now()
    if sess["expires_at"] <= _iso(now) or sess["last_seen_at"] <= _iso(now - timedelta(days=SESSION_IDLE_DAYS)):
        return None, None
    account = await db.customer_accounts.find_one({"id": sess["account_id"]}, {"_id": 0})
    if not account or account.get("status") != "active":
        return None, None
    if sess["last_seen_at"] <= _iso(now - timedelta(minutes=10)):
        await db.customer_sessions.update_one({"id": sess["id"]}, {"$set": {"last_seen_at": _iso(now)}})
    return sess, account


async def current_customer(request: Request) -> dict:
    sess, account = await _session_from_request(request)
    if not account:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    account["_session"] = sess
    return account


async def optional_customer(request: Request) -> Optional[dict]:
    """For endpoints usable by guests and signed-in customers (checkout, cart)."""
    sess, account = await _session_from_request(request)
    if account:
        account["_session"] = sess
    return account


def _recent_login(account: dict) -> bool:
    created = (account.get("_session") or {}).get("created_at", "")
    return created >= _iso(_now() - timedelta(minutes=RECENT_LOGIN_MINUTES))


# ---------------------------------------------------------------------------
# One-time tokens
# ---------------------------------------------------------------------------
async def issue_token(account_id: str, purpose: str, ttl: timedelta, data: Optional[dict] = None,
                      supersede: bool = True) -> str:
    raw = secrets.token_urlsafe(32)
    if supersede:
        await db.customer_tokens.update_many(
            {"account_id": account_id, "purpose": purpose, "used_at": None},
            {"$set": {"used_at": now_iso(), "superseded": True}})
    await db.customer_tokens.insert_one({
        "id": str(uuid.uuid4()), "account_id": account_id, "purpose": purpose, "token_hash": _sha(raw),
        "data": data or {}, "created_at": now_iso(), "expires_at": _iso(_now() + ttl), "used_at": None,
    })
    return raw


async def consume_token(raw: str, purpose: str) -> dict:
    """Atomically mark a token used. Raises 400 with code invalid|expired."""
    if not raw or len(raw) > 100:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "This link is not valid."})
    th = _sha(raw)
    doc = await db.customer_tokens.find_one_and_update(
        {"token_hash": th, "purpose": purpose, "used_at": None, "expires_at": {"$gt": now_iso()}},
        {"$set": {"used_at": now_iso()}}, return_document=ReturnDocument.AFTER)
    if doc:
        doc.pop("_id", None)
        return doc
    old = await db.customer_tokens.find_one({"token_hash": th, "purpose": purpose}, {"_id": 0})
    if old and old.get("used_at") is None:
        raise HTTPException(status_code=400, detail={"code": "expired", "message": "This link has expired. Please request a new one."})
    if old:
        raise HTTPException(status_code=400, detail={"code": "used", "message": "This link has already been used."})
    raise HTTPException(status_code=400, detail={"code": "invalid", "message": "This link is not valid."})


# ---------------------------------------------------------------------------
# Account representation
# ---------------------------------------------------------------------------
async def identities_for(account_id: str) -> List[dict]:
    return await db.customer_identities.find({"account_id": account_id}, {"_id": 0}).to_list(10)


async def public_account(account: dict) -> dict:
    ids = await identities_for(account["id"])
    providers = sorted({i["provider"] for i in ids})
    default_addr = await db.customer_addresses.find_one({"account_id": account["id"], "is_default": True}, {"_id": 0, "account_id": 0})
    return {
        "id": account["id"], "full_name": account.get("full_name", ""), "email": account.get("email"),
        "email_verified": bool(account.get("email_verified")), "phone": account.get("phone"),
        "login_methods": providers, "has_password": bool(account.get("password_hash")),
        "created_at": account.get("created_at"), "default_address": default_addr,
        "deletion_requested_at": account.get("deletion_requested_at"),
    }


def _verify_link(token: str) -> str:
    return emailer.site_link(f"/verify-email#token={token}")


async def _send_verification(account: dict, event: str = "verify_email") -> str:
    raw = await issue_token(account["id"], "verify_email", timedelta(hours=VERIFY_TTL_HOURS))
    res = await emailer.send(event, "verify_email", account["email"],
                             {"name": account.get("full_name"), "url": _verify_link(raw), "expires_hours": VERIFY_TTL_HOURS},
                             account_id=account["id"])
    await db.customer_accounts.update_one({"id": account["id"]}, {"$set": {
        "last_verification_sent_at": now_iso(), "verification_email_status": res["status"]}})
    return res["status"]


async def _welcome_hook(account: dict):
    try:
        import promotions
        await promotions.issue_welcome(account)
    except Exception as exc:  # noqa: BLE001 - a reward must never break sign-in
        logger.warning("welcome issuance skipped for account: %s", type(exc).__name__)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class RegisterBody(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str
    confirm_password: str
    accept_terms: bool = False


class LoginBody(BaseModel):
    email: str
    password: str


class EmailBody(BaseModel):
    email: str


class TokenBody(BaseModel):
    token: str


class ResetBody(BaseModel):
    token: str
    password: str
    confirm_password: str


class ProfileBody(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


class PasswordChangeBody(BaseModel):
    current_password: Optional[str] = None
    new_password: str
    confirm_password: str


class EmailChangeBody(BaseModel):
    new_email: str
    current_password: Optional[str] = None


class AddressBody(BaseModel):
    label: Optional[str] = ""
    recipient_name: str
    phone: str
    district: str
    address: str
    instructions: Optional[str] = ""
    is_default: bool = False


class ClaimBody(BaseModel):
    order_number: str
    confirmation_token: Optional[str] = None


class DeleteRequestBody(BaseModel):
    confirm: str


# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------
def google_config():
    cid = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    secret = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    return (cid, secret) if cid and secret else (None, None)


def google_redirect_uri() -> str:
    # Must equal the URI registered with Google exactly: never carries the
    # preview share code that site_link() may add to email links.
    return emailer.site_base() + "/api/auth/google/callback"


@customer_router.get("/customer/config")
async def customer_config():
    cid, _ = google_config()
    return {"google_enabled": bool(cid), "email_enabled": emailer.is_configured(),
            "password_min_length": MIN_PASSWORD_LEN}


# ---------------------------------------------------------------------------
# Registration, verification, login, logout
# ---------------------------------------------------------------------------
@customer_router.post("/customer/register", dependencies=[Depends(csrf_guard)])
async def register(body: RegisterBody, request: Request):
    await ratelimit.enforce("register-ip", _client_ip(request), 10, 3600)
    name = clean_text(body.full_name, 80)
    email = normalize_email(body.email)
    phone = normalize_phone(body.phone)
    errors = {}
    if len(name) < 2:
        errors["full_name"] = "Please enter your full name."
    if not email:
        errors["email"] = "Please enter a valid email address."
    if not phone:
        errors["phone"] = "Please enter a valid Bangladesh mobile number, e.g. 01712345678."
    problem = password_problem(body.password, email or "")
    if problem:
        errors["password"] = problem
    if body.password != body.confirm_password:
        errors["confirm_password"] = "The passwords do not match."
    if not body.accept_terms:
        errors["accept_terms"] = "Please accept the Terms and Privacy Policy to continue."
    if errors:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": errors,
                                                     "message": "Please check the highlighted fields."})

    existing = await db.customer_accounts.find_one({"email": email}, {"_id": 0})
    if existing:
        # Same public response; the real owner gets a notice instead of a second account.
        if not await ratelimit.exceeded("account-exists-mail", email, 2, 86400):
            google_only = not existing.get("password_hash")
            if existing.get("status") == "pending_verification" and not google_only:
                await _send_verification(existing, "resend_verification")
            else:
                await emailer.send("account_exists", "account_exists", email,
                                   {"google_only": google_only, "url": emailer.site_link("/login")},
                                   account_id=existing["id"])
        return {"ok": True, "message": GENERIC_REGISTER_MSG}

    account = {
        "id": str(uuid.uuid4()), "email": email, "email_verified": False, "full_name": name, "phone": phone,
        "password_hash": hash_password(body.password), "status": "pending_verification",
        "marketing_opt_in": False, "terms_accepted_at": now_iso(),
        "created_at": now_iso(), "updated_at": now_iso(), "created_via": "password",
    }
    try:
        await db.customer_accounts.insert_one({**account})
    except DuplicateKeyError:
        return {"ok": True, "message": GENERIC_REGISTER_MSG}
    await db.customer_identities.insert_one({"id": str(uuid.uuid4()), "account_id": account["id"], "provider": "password",
                                             "subject": account["id"], "email": email, "created_at": now_iso()})
    await security_event(account["id"], "registered_password", request)
    await _send_verification(account)
    return {"ok": True, "message": GENERIC_REGISTER_MSG}


@customer_router.post("/customer/resend-verification", dependencies=[Depends(csrf_guard)])
async def resend_verification(body: EmailBody, request: Request):
    await ratelimit.enforce("resend-ip", _client_ip(request), 10, 3600)
    email = normalize_email(body.email)
    if email:
        acct = await db.customer_accounts.find_one({"email": email, "status": "pending_verification"}, {"_id": 0})
        if acct:
            last = acct.get("last_verification_sent_at") or ""
            cooled = last <= _iso(_now() - timedelta(seconds=RESEND_COOLDOWN_SECONDS))
            if cooled and not await ratelimit.exceeded("resend-acct", acct["id"], 5, 86400):
                await _send_verification(acct, "resend_verification")
    return {"ok": True, "message": GENERIC_RESEND_MSG}


@customer_router.post("/customer/verify-email", dependencies=[Depends(csrf_guard)])
async def verify_email(body: TokenBody, request: Request, response: Response):
    await ratelimit.enforce("verify-ip", _client_ip(request), 30, 3600)
    tok = await consume_token(body.token, "verify_email")
    acct = await db.customer_accounts.find_one({"id": tok["account_id"]}, {"_id": 0})
    if not acct or acct.get("status") == "suspended":
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "This link is not valid."})
    if acct.get("status") == "pending_verification":
        acct = await db.customer_accounts.find_one_and_update(
            {"id": acct["id"]},
            {"$set": {"status": "active", "email_verified": True, "verified_at": now_iso(), "updated_at": now_iso()}},
            return_document=ReturnDocument.AFTER)
        acct.pop("_id", None)
        await security_event(acct["id"], "email_verified", request)
        await _welcome_hook(acct)
    await create_session(response, request, acct, "email_link")
    return {"ok": True, "account": await public_account(acct)}


async def _login_rate(request: Request, email: str):
    ip = _client_ip(request)
    await ratelimit.enforce("login-ip", ip, 40, 900)
    if await ratelimit.count("login-fail", f"{ip}|{email}", 900) >= 5 or \
            await ratelimit.count("login-fail-acct", email, 3600) >= 20:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please wait 15 minutes or reset your password.")


@customer_router.post("/customer/login", dependencies=[Depends(csrf_guard)])
async def customer_login(body: LoginBody, request: Request, response: Response):
    email = normalize_email(body.email) or (body.email or "").strip().lower()[:254]
    await _login_rate(request, email)
    acct = await db.customer_accounts.find_one({"email": email}, {"_id": 0}) if email else None
    ok = verify_password(body.password or "", (acct or {}).get("password_hash"))
    if not acct or not ok:
        await ratelimit.hit("login-fail", f"{_client_ip(request)}|{email}", 5, 900)
        await ratelimit.hit("login-fail-acct", email, 20, 3600)
        if acct:
            await security_event(acct["id"], "login_failed", request)
        raise HTTPException(status_code=401, detail=LOGIN_FAILED_MSG)
    # Only reached with the correct password, so these do not leak account existence.
    if acct.get("status") == "pending_verification":
        raise HTTPException(status_code=403, detail={"code": "email_unverified",
                                                     "message": "Please confirm your email address first. We can send you a new link."})
    if acct.get("status") != "active":
        raise HTTPException(status_code=403, detail={"code": "unavailable",
                                                     "message": "This account is not available. Please contact us for help."})
    await ratelimit.reset("login-fail", f"{_client_ip(request)}|{email}", 900)
    await create_session(response, request, acct, "password")
    return {"ok": True, "account": await public_account(acct)}


@customer_router.post("/customer/logout", dependencies=[Depends(csrf_guard)])
async def customer_logout(request: Request, response: Response):
    sess, account = await _session_from_request(request)
    if sess:
        await db.customer_sessions.update_one({"id": sess["id"]}, {"$set": {"revoked_at": now_iso()}})
        await security_event(account["id"], "logout", request)
    clear_session_cookie(response, request)
    return {"ok": True}


@customer_router.get("/customer/session")
async def customer_session(request: Request):
    """Lightweight 'am I signed in?' probe for the storefront header. Never 401s."""
    account = await optional_customer(request)
    if not account:
        return {"authenticated": False}
    return {"authenticated": True, "account": await public_account(account)}


# ---------------------------------------------------------------------------
# Password recovery
# ---------------------------------------------------------------------------
@customer_router.post("/customer/forgot-password", dependencies=[Depends(csrf_guard)])
async def forgot_password(body: EmailBody, request: Request):
    await ratelimit.enforce("forgot-ip", _client_ip(request), 10, 3600)
    email = normalize_email(body.email)
    if email:
        acct = await db.customer_accounts.find_one({"email": email}, {"_id": 0})
        eligible = acct and acct.get("password_hash") and acct.get("status") in ("active", "pending_verification")
        if eligible and not await ratelimit.exceeded("forgot-acct", acct["id"], 3, 900):
            raw = await issue_token(acct["id"], "password_reset", timedelta(minutes=RESET_TTL_MINUTES))
            await emailer.send("password_reset", "password_reset", acct["email"],
                               {"name": acct.get("full_name"), "url": emailer.site_link(f"/reset-password#token={raw}"),
                                "expires_minutes": RESET_TTL_MINUTES}, account_id=acct["id"])
            await security_event(acct["id"], "password_reset_requested", request)
    return {"ok": True, "message": GENERIC_RESET_MSG}


@customer_router.post("/customer/reset-password", dependencies=[Depends(csrf_guard)])
async def reset_password(body: ResetBody, request: Request):
    await ratelimit.enforce("reset-ip", _client_ip(request), 20, 3600)
    if body.password != body.confirm_password:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": {"confirm_password": "The passwords do not match."},
                                                     "message": "Please check the highlighted fields."})
    # Validate the new password before spending the single-use token.
    th = _sha(body.token or "")
    pending = await db.customer_tokens.find_one({"token_hash": th, "purpose": "password_reset"}, {"_id": 0, "account_id": 1})
    acct_preview = await db.customer_accounts.find_one({"id": (pending or {}).get("account_id")}, {"_id": 0, "email": 1}) if pending else None
    problem = password_problem(body.password, (acct_preview or {}).get("email", ""))
    if problem:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": {"password": problem},
                                                     "message": "Please choose a stronger password."})
    tok = await consume_token(body.token, "password_reset")
    acct = await db.customer_accounts.find_one({"id": tok["account_id"]}, {"_id": 0})
    if not acct or not acct.get("password_hash") or acct.get("status") == "suspended":
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "This link is not valid."})
    updates = {"password_hash": hash_password(body.password), "updated_at": now_iso(), "password_changed_at": now_iso()}
    if acct.get("status") == "pending_verification":
        # Receiving the reset email proves control of the address.
        updates.update(status="active", email_verified=True, verified_at=now_iso())
    await db.customer_accounts.update_one({"id": acct["id"]}, {"$set": updates})
    await db.customer_tokens.update_many({"account_id": acct["id"], "purpose": "password_reset", "used_at": None},
                                         {"$set": {"used_at": now_iso(), "superseded": True}})
    revoked = await revoke_sessions(acct["id"])
    await security_event(acct["id"], "password_reset", request, f"sessions_revoked={revoked}")
    await emailer.send("password_changed", "password_changed", acct["email"],
                       {"name": acct.get("full_name"), "url": emailer.site_link("/login")}, account_id=acct["id"])
    if updates.get("status") == "active":
        await _welcome_hook({**acct, **updates})
    return {"ok": True, "message": "Your password has been changed. Please sign in with your new password."}


# ---------------------------------------------------------------------------
# Google sign-in (OIDC authorization code flow + PKCE)
# ---------------------------------------------------------------------------
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
_jwks_cache = {"keys": None, "at": 0.0}


async def _fetch_jwks() -> dict:
    if _jwks_cache["keys"] and time.time() - _jwks_cache["at"] < 3600:
        return _jwks_cache["keys"]
    async with httpx.AsyncClient(timeout=8) as cli:
        resp = await cli.get(GOOGLE_JWKS_URL)
        resp.raise_for_status()
        keys = resp.json()
    _jwks_cache.update(keys=keys, at=time.time())
    return keys


async def _exchange_code(code: str, verifier: str) -> dict:
    cid, secret = google_config()
    async with httpx.AsyncClient(timeout=10) as cli:
        resp = await cli.post(GOOGLE_TOKEN_URL, data={
            "code": code, "client_id": cid, "client_secret": secret, "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code", "code_verifier": verifier})
    if resp.status_code != 200:
        raise ValueError(f"token exchange HTTP {resp.status_code}")
    return resp.json()


async def verify_google_id_token(id_token: str, nonce: str) -> dict:
    """Signature (Google JWKS, RS256), issuer, audience, expiry, nonce. Raises ValueError."""
    cid, _ = google_config()
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.InvalidTokenError as exc:
        raise ValueError("malformed token") from exc
    if header.get("alg") != "RS256":
        raise ValueError("unexpected algorithm")
    jwks = await _fetch_jwks()
    match = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if not match:
        _jwks_cache["at"] = 0  # keys may have rotated; refetch next time
        raise ValueError("unknown signing key")
    key = jwt.PyJWK(match).key
    try:
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=cid, issuer=list(GOOGLE_ISSUERS),
                            options={"require": ["exp", "iat", "iss", "aud", "sub"]}, leeway=60)
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"invalid token: {type(exc).__name__}") from exc
    if not nonce or not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValueError("nonce mismatch")
    if claims.get("azp") and claims["azp"] != cid:
        raise ValueError("authorized party mismatch")
    return claims


def _safe_next(value: Optional[str]) -> str:
    v = (value or "").strip()
    if not v or v.startswith("//") or "\\" in v or not NEXT_RE.match(v) or len(v) > 200:
        return "/account"
    return v


def _login_redirect(error: str) -> RedirectResponse:
    return RedirectResponse(f"/login?{urlencode({'error': error})}", status_code=303)


@customer_router.get("/auth/google/start")
async def google_start(request: Request, next: Optional[str] = None, mode: str = "login"):
    cid, _ = google_config()
    if not cid:
        return _login_redirect("google_unavailable")
    await ratelimit.enforce("google-start", _client_ip(request), 30, 600)
    account_id = None
    if mode == "link":
        account = await optional_customer(request)
        if not account:
            return _login_redirect("signin_required")
        account_id = account["id"]
    elif mode != "login":
        mode = "login"
    state, nonce, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    await db.oauth_states.insert_one({
        "_id": _sha(state), "nonce": nonce, "verifier": verifier, "binding_hash": _sha(binding),
        "next": _safe_next(next), "mode": mode, "account_id": account_id, "created_at": now_iso(),
        "expires_at": _iso(_now() + timedelta(minutes=OAUTH_STATE_TTL_MINUTES)),
    })
    params = {"client_id": cid, "redirect_uri": google_redirect_uri(), "response_type": "code",
              "scope": "openid email profile", "state": state, "nonce": nonce,
              "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account"}
    resp = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=303)
    _set_cookie(resp, request, "aayna_oauth", binding, OAUTH_STATE_TTL_MINUTES * 60, path="/api/auth/google")
    return resp


@customer_router.get("/auth/google/callback")
async def google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None,
                          error: Optional[str] = None):
    if not google_config()[0]:
        return _login_redirect("google_unavailable")
    await ratelimit.enforce("google-callback", _client_ip(request), 30, 600)
    if not state or len(state) > 100:
        return _login_redirect("google_failed")
    # Single use: the state record is removed as it is read, so a replayed callback finds nothing.
    st = await db.oauth_states.find_one_and_delete({"_id": _sha(state)})
    binding = request.cookies.get("aayna_oauth") or ""
    if not st or st["expires_at"] <= now_iso() or not binding or not secrets.compare_digest(_sha(binding), st["binding_hash"]):
        return _login_redirect("google_failed")
    if error:
        return _login_redirect("google_cancelled" if error == "access_denied" else "google_failed")
    if not code or len(code) > 2048:
        return _login_redirect("google_failed")
    try:
        tokens = await _exchange_code(code, st["verifier"])
        claims = await verify_google_id_token(tokens.get("id_token") or "", st["nonce"])
    except Exception as exc:  # noqa: BLE001 - never log tokens, only the failure class
        logger.warning("Google sign-in rejected: %s", str(exc)[:80])
        return _login_redirect("google_failed")

    sub = str(claims["sub"])
    email = normalize_email(claims.get("email") or "")
    email_verified = claims.get("email_verified") is True or claims.get("email_verified") == "true"
    identity = await db.customer_identities.find_one({"provider": "google", "subject": sub}, {"_id": 0})

    if st["mode"] == "link":
        current = await optional_customer(request)
        if not current or current["id"] != st.get("account_id"):
            return _login_redirect("signin_required")
        if identity and identity["account_id"] != current["id"]:
            return RedirectResponse("/account/security?google=in_use", status_code=303)
        if not identity:
            await db.customer_identities.insert_one({"id": str(uuid.uuid4()), "account_id": current["id"], "provider": "google",
                                                     "subject": sub, "email": email, "created_at": now_iso()})
            await security_event(current["id"], "google_linked", request)
        return RedirectResponse("/account/security?google=linked", status_code=303)

    resp = RedirectResponse(st["next"], status_code=303)
    resp.delete_cookie("aayna_oauth", path="/api/auth/google")
    if identity:
        acct = await db.customer_accounts.find_one({"id": identity["account_id"]}, {"_id": 0})
        if not acct or acct.get("status") != "active":
            return _login_redirect("account_unavailable")
        await create_session(resp, request, acct, "google")
        return resp
    if not email or not email_verified:
        return _login_redirect("google_email_unverified")
    existing = await db.customer_accounts.find_one({"email": email}, {"_id": 0})
    if existing:
        # Never merge on a matching email alone: the owner must sign in to the
        # existing account first; the pending Google identity waits in a short-lived,
        # browser-bound cookie and is attached only after that sign-in.
        link_raw = secrets.token_urlsafe(32)
        await db.customer_tokens.insert_one({
            "id": str(uuid.uuid4()), "account_id": existing["id"], "purpose": "google_link", "token_hash": _sha(link_raw),
            "data": {"sub": sub, "email": email}, "created_at": now_iso(),
            "expires_at": _iso(_now() + timedelta(minutes=GOOGLE_LINK_TTL_MINUTES)), "used_at": None})
        link_resp = RedirectResponse("/login?link=google", status_code=303)
        link_resp.delete_cookie("aayna_oauth", path="/api/auth/google")
        _set_cookie(link_resp, request, "aayna_glink", link_raw, GOOGLE_LINK_TTL_MINUTES * 60, path="/api/account")
        return link_resp
    acct = {
        "id": str(uuid.uuid4()), "email": email, "email_verified": True, "verified_at": now_iso(),
        "full_name": clean_text(claims.get("name") or email.split("@")[0], 80), "phone": None,
        "password_hash": None, "status": "active", "marketing_opt_in": False, "terms_accepted_at": now_iso(),
        "created_at": now_iso(), "updated_at": now_iso(), "created_via": "google",
    }
    try:
        await db.customer_accounts.insert_one({**acct})
        await db.customer_identities.insert_one({"id": str(uuid.uuid4()), "account_id": acct["id"], "provider": "google",
                                                 "subject": sub, "email": email, "created_at": now_iso()})
    except DuplicateKeyError:
        return _login_redirect("google_failed")
    await security_event(acct["id"], "registered_google", request)
    await _welcome_hook(acct)
    await create_session(resp, request, acct, "google")
    return resp


@customer_router.post("/account/link/google/confirm", dependencies=[Depends(csrf_guard)])
async def confirm_google_link(request: Request, response: Response, account=Depends(current_customer)):
    raw = request.cookies.get("aayna_glink")
    if not raw:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "There is no Google account waiting to be linked."})
    tok = await consume_token(raw, "google_link")
    response.delete_cookie("aayna_glink", path="/api/account")
    if tok["account_id"] != account["id"]:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "Sign in to the account that uses this email address to link Google."})
    sub = tok["data"]["sub"]
    if await db.customer_identities.find_one({"provider": "google", "subject": sub}):
        return {"ok": True, "linked": True}
    await db.customer_identities.insert_one({"id": str(uuid.uuid4()), "account_id": account["id"], "provider": "google",
                                             "subject": sub, "email": tok["data"].get("email"), "created_at": now_iso()})
    await security_event(account["id"], "google_linked", request)
    return {"ok": True, "linked": True}


@customer_router.delete("/account/link/google", dependencies=[Depends(csrf_guard)])
async def unlink_google(request: Request, account=Depends(current_customer)):
    if not account.get("password_hash"):
        raise HTTPException(status_code=400, detail="Set a password first, so you can still sign in after removing Google.")
    res = await db.customer_identities.delete_many({"account_id": account["id"], "provider": "google"})
    if res.deleted_count:
        await security_event(account["id"], "google_unlinked", request)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Account: profile, security, sessions, email change, deletion request
# ---------------------------------------------------------------------------
@customer_router.get("/account/me")
async def account_me(account=Depends(current_customer)):
    return await public_account(account)


@customer_router.patch("/account/profile", dependencies=[Depends(csrf_guard)])
async def update_profile(body: ProfileBody, request: Request, account=Depends(current_customer)):
    updates, errors = {}, {}
    if body.full_name is not None:
        name = clean_text(body.full_name, 80)
        if len(name) < 2:
            errors["full_name"] = "Please enter your full name."
        updates["full_name"] = name
    if body.phone is not None:
        if body.phone.strip() == "":
            updates["phone"] = None
        else:
            phone = normalize_phone(body.phone)
            if not phone:
                errors["phone"] = "Please enter a valid Bangladesh mobile number, e.g. 01712345678."
            updates["phone"] = phone
    if errors:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": errors, "message": "Please check the highlighted fields."})
    if updates:
        updates["updated_at"] = now_iso()
        await db.customer_accounts.update_one({"id": account["id"]}, {"$set": updates})
        await security_event(account["id"], "profile_updated", request, ",".join(k for k in updates if k != "updated_at"))
    fresh = await db.customer_accounts.find_one({"id": account["id"]}, {"_id": 0})
    return await public_account(fresh)


@customer_router.get("/account/security")
async def account_security(account=Depends(current_customer)):
    sessions = await db.customer_sessions.find(
        {"account_id": account["id"], "revoked_at": None, "expires_at": {"$gt": now_iso()}},
        {"_id": 0, "token_hash": 0, "ip_hash": 0}).sort("last_seen_at", -1).to_list(50)
    current_id = account["_session"]["id"]
    events = await db.security_events.find({"account_id": account["id"]}, {"_id": 0, "ip_hash": 0}).sort("created_at", -1).to_list(15)
    providers = {i["provider"] for i in await identities_for(account["id"])}
    cid, _ = google_config()
    return {
        "has_password": bool(account.get("password_hash")), "google_linked": "google" in providers,
        "google_available": bool(cid), "recent_login": _recent_login(account),
        "sessions": [{**s, "current": s["id"] == current_id} for s in sessions],
        "events": [{"type": e["type"], "created_at": e["created_at"], "user_agent": e.get("user_agent")} for e in events],
    }


@customer_router.post("/account/password", dependencies=[Depends(csrf_guard)])
async def change_password(body: PasswordChangeBody, request: Request, account=Depends(current_customer)):
    await ratelimit.enforce("pw-change", account["id"], 10, 3600)
    if account.get("password_hash"):
        if not verify_password(body.current_password or "", account["password_hash"]):
            raise HTTPException(status_code=400, detail={"code": "validation", "fields": {"current_password": "Your current password is not correct."},
                                                         "message": "Your current password is not correct."})
    elif not _recent_login(account):
        # Google-only account adding a password: require a fresh sign-in.
        raise HTTPException(status_code=403, detail={"code": "reauth", "message": "For your security, sign in again with Google, then set your password within 15 minutes."})
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": {"confirm_password": "The passwords do not match."}, "message": "The passwords do not match."})
    problem = password_problem(body.new_password, account["email"])
    if problem:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": {"new_password": problem}, "message": problem})
    had_password = bool(account.get("password_hash"))
    await db.customer_accounts.update_one({"id": account["id"]}, {"$set": {
        "password_hash": hash_password(body.new_password), "password_changed_at": now_iso(), "updated_at": now_iso()}})
    if not had_password:
        await db.customer_identities.update_one(
            {"account_id": account["id"], "provider": "password"},
            {"$setOnInsert": {"id": str(uuid.uuid4()), "account_id": account["id"], "provider": "password",
                              "subject": account["id"], "email": account["email"], "created_at": now_iso()}}, upsert=True)
    revoked = await revoke_sessions(account["id"], except_session_id=account["_session"]["id"])
    await security_event(account["id"], "password_changed" if had_password else "password_set", request, f"other_sessions_revoked={revoked}")
    await emailer.send("password_changed", "password_changed", account["email"],
                       {"name": account.get("full_name"), "url": emailer.site_link("/login")}, account_id=account["id"])
    return {"ok": True, "other_sessions_signed_out": revoked}


@customer_router.post("/account/sessions/revoke-others", dependencies=[Depends(csrf_guard)])
async def revoke_other_sessions(request: Request, account=Depends(current_customer)):
    n = await revoke_sessions(account["id"], except_session_id=account["_session"]["id"])
    await security_event(account["id"], "sessions_revoked", request, f"count={n}")
    return {"ok": True, "revoked": n}


@customer_router.post("/account/logout-all", dependencies=[Depends(csrf_guard)])
async def logout_all(request: Request, response: Response, account=Depends(current_customer)):
    n = await revoke_sessions(account["id"])
    await security_event(account["id"], "logout_all", request, f"count={n}")
    clear_session_cookie(response, request)
    return {"ok": True, "revoked": n}


@customer_router.delete("/account/sessions/{session_id}", dependencies=[Depends(csrf_guard)])
async def revoke_session(session_id: str, request: Request, account=Depends(current_customer)):
    res = await db.customer_sessions.update_one({"id": session_id, "account_id": account["id"], "revoked_at": None},
                                                {"$set": {"revoked_at": now_iso()}})
    if not res.modified_count:
        raise HTTPException(status_code=404, detail="Session not found")
    await security_event(account["id"], "session_revoked", request)
    return {"ok": True}


@customer_router.post("/account/email", dependencies=[Depends(csrf_guard)])
async def request_email_change(body: EmailChangeBody, request: Request, account=Depends(current_customer)):
    await ratelimit.enforce("email-change", account["id"], 5, 86400)
    if not account.get("password_hash"):
        raise HTTPException(status_code=400, detail="Your email address comes from your Google account, so it can't be changed here.")
    if not verify_password(body.current_password or "", account["password_hash"]):
        raise HTTPException(status_code=400, detail={"code": "validation", "fields": {"current_password": "Your current password is not correct."},
                                                     "message": "Your current password is not correct."})
    new_email = normalize_email(body.new_email)
    if not new_email:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": {"new_email": "Please enter a valid email address."}, "message": "Please enter a valid email address."})
    if new_email == account["email"]:
        raise HTTPException(status_code=400, detail="That is already your email address.")
    # Same answer whether or not the address is taken; a taken address simply gets no link.
    if not await db.customer_accounts.find_one({"email": new_email}):
        raw = await issue_token(account["id"], "email_change", timedelta(hours=EMAIL_CHANGE_TTL_HOURS), {"new_email": new_email})
        await emailer.send("email_change", "email_change", new_email,
                           {"name": account.get("full_name"), "url": emailer.site_link(f"/confirm-email#token={raw}"),
                            "expires_hours": EMAIL_CHANGE_TTL_HOURS}, account_id=account["id"])
    await security_event(account["id"], "email_change_requested", request)
    return {"ok": True, "message": "If this address can be used, we've sent a confirmation link to it. Your email changes once you confirm."}


@customer_router.post("/customer/confirm-email-change", dependencies=[Depends(csrf_guard)])
async def confirm_email_change(body: TokenBody, request: Request):
    tok = await consume_token(body.token, "email_change")
    new_email = tok["data"].get("new_email")
    acct = await db.customer_accounts.find_one({"id": tok["account_id"], "status": "active"}, {"_id": 0})
    if not acct or not new_email:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "This link is not valid."})
    try:
        await db.customer_accounts.update_one({"id": acct["id"]}, {"$set": {"email": new_email, "email_verified": True, "updated_at": now_iso()}})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail={"code": "taken", "message": "This email address is already used by another account."})
    await db.customer_identities.update_many({"account_id": acct["id"], "provider": "password"}, {"$set": {"email": new_email}})
    revoked = await revoke_sessions(acct["id"])
    await security_event(acct["id"], "email_changed", request, f"sessions_revoked={revoked}")
    return {"ok": True, "message": "Your email address has been updated. Please sign in again."}


@customer_router.post("/account/delete-request", dependencies=[Depends(csrf_guard)])
async def delete_request(body: DeleteRequestBody, request: Request, account=Depends(current_customer)):
    if body.confirm.strip().upper() != "DELETE":
        raise HTTPException(status_code=400, detail="Type DELETE to confirm.")
    await db.customer_accounts.update_one({"id": account["id"]}, {"$set": {"deletion_requested_at": now_iso(), "updated_at": now_iso()}})
    await security_event(account["id"], "deletion_requested", request)
    return {"ok": True, "message": "We've received your request. Our team will delete your account and contact you by email. Order records we must keep by law are retained."}


# ---------------------------------------------------------------------------
# Saved addresses
# ---------------------------------------------------------------------------
def _validate_address(body: AddressBody) -> dict:
    errors = {}
    name = clean_text(body.recipient_name, 80)
    phone = normalize_phone(body.phone)
    address = clean_text(body.address, 300)
    if len(name) < 2:
        errors["recipient_name"] = "Please enter the recipient's name."
    if not phone:
        errors["phone"] = "Please enter a valid Bangladesh mobile number."
    if body.district not in BD_DISTRICTS:
        errors["district"] = "Please choose a district."
    if len(address) < 8:
        errors["address"] = "Please enter the full delivery address (house, road, area)."
    if errors:
        raise HTTPException(status_code=422, detail={"code": "validation", "fields": errors, "message": "Please check the highlighted fields."})
    return {"label": clean_text(body.label or "", 30), "recipient_name": name, "phone": phone, "district": body.district,
            "address": address, "instructions": clean_text(body.instructions or "", 200)}


async def _set_default(account_id: str, address_id: str):
    await db.customer_addresses.update_many({"account_id": account_id, "id": {"$ne": address_id}}, {"$set": {"is_default": False}})
    await db.customer_addresses.update_one({"account_id": account_id, "id": address_id}, {"$set": {"is_default": True}})


@customer_router.get("/account/addresses")
async def list_addresses(account=Depends(current_customer)):
    return await db.customer_addresses.find({"account_id": account["id"]}, {"_id": 0, "account_id": 0}).sort("created_at", 1).to_list(MAX_ADDRESSES)


@customer_router.post("/account/addresses", dependencies=[Depends(csrf_guard)])
async def add_address(body: AddressBody, account=Depends(current_customer)):
    fields = _validate_address(body)
    count = await db.customer_addresses.count_documents({"account_id": account["id"]})
    if count >= MAX_ADDRESSES:
        raise HTTPException(status_code=400, detail=f"You can save up to {MAX_ADDRESSES} addresses.")
    doc = {"id": str(uuid.uuid4()), "account_id": account["id"], **fields, "is_default": False,
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.customer_addresses.insert_one({**doc})
    if body.is_default or count == 0:
        await _set_default(account["id"], doc["id"])
    return await db.customer_addresses.find_one({"id": doc["id"]}, {"_id": 0, "account_id": 0})


@customer_router.put("/account/addresses/{address_id}", dependencies=[Depends(csrf_guard)])
async def update_address(address_id: str, body: AddressBody, account=Depends(current_customer)):
    fields = _validate_address(body)
    res = await db.customer_addresses.update_one({"id": address_id, "account_id": account["id"]},
                                                 {"$set": {**fields, "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Address not found")
    if body.is_default:
        await _set_default(account["id"], address_id)
    return await db.customer_addresses.find_one({"id": address_id}, {"_id": 0, "account_id": 0})


@customer_router.delete("/account/addresses/{address_id}", dependencies=[Depends(csrf_guard)])
async def delete_address(address_id: str, account=Depends(current_customer)):
    doc = await db.customer_addresses.find_one_and_delete({"id": address_id, "account_id": account["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Address not found")
    if doc.get("is_default"):
        nxt = await db.customer_addresses.find_one({"account_id": account["id"]}, sort=[("created_at", 1)])
        if nxt:
            await _set_default(account["id"], nxt["id"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# Orders owned by the signed-in account
# ---------------------------------------------------------------------------
CUSTOMER_TIMELINE = [("New", "Order received"), ("Confirmed", "Order confirmed"), ("Packed", "Preparing your order"),
                     ("Sent to Courier", "Handed to courier"), ("Delivered", "Delivered")]
EXCEPTION_STATUSES = {"Cancelled": "Cancelled", "Returned": "Returned"}


async def order_timeline(order: dict) -> dict:
    """Only recorded events carry timestamps. Orders from before event logging
    show their current status honestly, with no invented dates for earlier steps."""
    events = await db.order_events.find({"order_id": order["id"]}, {"_id": 0, "status": 1, "created_at": 1}).sort("created_at", 1).to_list(50)
    when = {}
    for e in events:
        when.setdefault(e["status"], e["created_at"])
    when.setdefault("New", order.get("created_at"))  # creation time is a genuine record
    status = order.get("order_status")
    order_idx = [s for s, _ in CUSTOMER_TIMELINE]
    reached = order_idx.index(status) if status in order_idx else -1
    steps = [{"status": s, "label": label, "done": i <= reached, "current": i == reached, "at": when.get(s)}
             for i, (s, label) in enumerate(CUSTOMER_TIMELINE)]
    exception = None
    if status in EXCEPTION_STATUSES:
        exception = {"status": status, "label": EXCEPTION_STATUSES[status], "at": when.get(status)}
    return {"steps": steps, "exception": exception, "history_complete": bool(events)}


def customer_order_view(order: dict, detail: bool = False) -> dict:
    view = {
        "order_number": order["order_number"], "created_at": order["created_at"], "order_status": order["order_status"],
        "payment_method": order.get("payment_method"), "payment_status": order.get("payment_status"),
        "subtotal": order.get("subtotal"), "delivery_charge": order.get("delivery_charge"), "free_delivery": bool(order.get("free_delivery")),
        "discount_amount": order.get("discount_amount") or 0, "coupon_code": order.get("coupon_code"),
        "total_amount": order.get("total_amount"),
        "items": [{"product_name": it["product_name_snapshot"], "quantity": it["quantity"], "unit_price": it["unit_price"],
                   "total_price": it["total_price"], "image": it.get("image")} for it in order.get("items", [])],
    }
    if detail:
        from steadfast import customer_courier_status  # customer-safe label only
        view.update({"courier_name": order.get("courier_name"), "courier_tracking_code": order.get("courier_tracking_code"),
                     "courier_status": customer_courier_status(order),
                     "district": order.get("district"), "delivery_address": order.get("delivery_address"),
                     "customer_name": order.get("customer_name")})
    return view


@customer_router.get("/account/orders")
async def account_orders(account=Depends(current_customer)):
    orders = await db.orders.find({"account_id": account["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [customer_order_view(o) for o in orders]


@customer_router.get("/account/orders/{order_number}")
async def account_order_detail(order_number: str, account=Depends(current_customer)):
    order = await db.orders.find_one({"order_number": order_number.strip().upper(), "account_id": account["id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {**customer_order_view(order, detail=True), "timeline": await order_timeline(order)}


@customer_router.post("/account/orders/claim", dependencies=[Depends(csrf_guard)])
async def claim_order(body: ClaimBody, request: Request, account=Depends(current_customer)):
    """Attach a guest order using the high-entropy confirmation token issued at
    checkout (only the person who placed the order has it)."""
    await ratelimit.enforce("claim", account["id"], 20, 3600)
    not_found = HTTPException(status_code=404, detail="We couldn't match that order. Use the link from your order confirmation page.")
    number = (body.order_number or "").strip().upper()
    if not number or not body.confirmation_token or len(body.confirmation_token) > 100:
        raise not_found
    res = await db.orders.update_one(
        {"order_number": number, "order_confirmation_token_hash": _sha(body.confirmation_token),
         "$or": [{"account_id": None}, {"account_id": {"$exists": False}}]},
        {"$set": {"account_id": account["id"], "account_linked_at": now_iso(), "account_link_method": "confirmation_token"}})
    if not res.modified_count:
        owned = await db.orders.find_one({"order_number": number, "account_id": account["id"]}, {"_id": 1})
        if owned:
            return {"ok": True, "already_linked": True}
        raise not_found
    await security_event(account["id"], "order_claimed", request, number)
    return {"ok": True}


@customer_router.post("/account/orders/claim-by-email", dependencies=[Depends(csrf_guard)])
async def claim_order_by_email(body: ClaimBody, request: Request, account=Depends(current_customer)):
    """For guest orders whose recorded email equals this account's verified email:
    a confirmation link goes to that recorded address. Same answer in every case."""
    await ratelimit.enforce("claim-email", account["id"], 10, 86400)
    number = (body.order_number or "").strip().upper()
    order = await db.orders.find_one({"order_number": number}, {"_id": 0, "id": 1, "customer_email": 1, "account_id": 1})
    if order and not order.get("account_id") and account.get("email_verified") and \
            (order.get("customer_email") or "").strip().lower() == account["email"]:
        raw = await issue_token(account["id"], "order_claim", timedelta(hours=CLAIM_TTL_HOURS), {"order_id": order["id"], "order_number": number}, supersede=False)
        await emailer.send("order_claim", "order_claim", account["email"],
                           {"name": account.get("full_name"), "order_number": number, "expires_hours": CLAIM_TTL_HOURS,
                            "url": emailer.site_link(f"/account/orders/claim#token={raw}")}, account_id=account["id"])
    return {"ok": True, "message": "If this order was placed with your account's email address, we've emailed you a link to add it."}


@customer_router.post("/account/orders/confirm-claim", dependencies=[Depends(csrf_guard)])
async def confirm_claim(body: TokenBody, request: Request, account=Depends(current_customer)):
    # Check the owner BEFORE spending the single-use link, so opening it while
    # signed in to another account does not burn the real owner's link.
    pending = await db.customer_tokens.find_one({"token_hash": _sha(body.token or ""), "purpose": "order_claim"},
                                                {"_id": 0, "account_id": 1})
    if pending and pending["account_id"] != account["id"]:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "Sign in to the account that requested this link."})
    tok = await consume_token(body.token, "order_claim")
    if tok["account_id"] != account["id"]:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "Sign in to the account that requested this link."})
    res = await db.orders.update_one(
        {"id": tok["data"]["order_id"], "$or": [{"account_id": None}, {"account_id": {"$exists": False}}]},
        {"$set": {"account_id": account["id"], "account_linked_at": now_iso(), "account_link_method": "email_link"}})
    if not res.modified_count:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "This order can't be added to your account."})
    await security_event(account["id"], "order_claimed", request, tok["data"].get("order_number", ""))
    return {"ok": True, "order_number": tok["data"].get("order_number")}


@customer_router.get("/account/rewards")
async def account_rewards(account=Depends(current_customer)):
    import promotions
    return await promotions.rewards_for(account)


# ---------------------------------------------------------------------------
# Admin: customer accounts (read + suspend; never passwords, tokens or sessions secrets)
# ---------------------------------------------------------------------------
@customer_admin_router.get("/customer-accounts")
async def admin_list_accounts(search: Optional[str] = None, method: Optional[str] = None, status: Optional[str] = None,
                              current=Depends(require("customers.view"))):
    q = {}
    if search:
        pat = re.escape(search.strip()[:80])
        q["$or"] = [{"email": {"$regex": pat, "$options": "i"}}, {"full_name": {"$regex": pat, "$options": "i"}},
                    {"phone": {"$regex": pat, "$options": "i"}}]
    if status in ("active", "pending_verification", "suspended"):
        q["status"] = status
    accounts = await db.customer_accounts.find(q, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(1000)
    ids = [a["id"] for a in accounts]
    idents = await db.customer_identities.find({"account_id": {"$in": ids}}, {"_id": 0, "account_id": 1, "provider": 1}).to_list(5000)
    by_acct = {}
    for i in idents:
        by_acct.setdefault(i["account_id"], set()).add(i["provider"])
    out = []
    for a in accounts:
        methods = sorted(by_acct.get(a["id"], set()))
        if method in ("google", "password") and method not in methods:
            continue
        out.append({"id": a["id"], "full_name": a.get("full_name"), "email": a.get("email"), "phone": a.get("phone"),
                    "status": a.get("status"), "email_verified": bool(a.get("email_verified")), "login_methods": methods,
                    "created_at": a.get("created_at"), "last_login_at": a.get("last_login_at"),
                    "deletion_requested_at": a.get("deletion_requested_at"),
                    "orders": await db.orders.count_documents({"account_id": a["id"]})})
    return out


@customer_admin_router.get("/customer-accounts/{account_id}")
async def admin_account_detail(account_id: str, current=Depends(require("customers.view"))):
    a = await db.customer_accounts.find_one({"id": account_id}, {"_id": 0, "password_hash": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Account not found")
    idents = await db.customer_identities.find({"account_id": account_id}, {"_id": 0, "provider": 1, "created_at": 1}).to_list(10)
    orders = await db.orders.find({"account_id": account_id}, {"_id": 0, "order_number": 1, "created_at": 1, "order_status": 1,
                                                                "total_amount": 1, "coupon_code": 1}).sort("created_at", -1).to_list(200)
    events = await db.security_events.find({"account_id": account_id}, {"_id": 0, "ip_hash": 0}).sort("created_at", -1).to_list(30)
    emails = await db.email_logs.find({"account_id": account_id}, {"_id": 0, "to_hash": 0, "dedupe_key": 0}).sort("created_at", -1).to_list(30)
    active_sessions = await db.customer_sessions.count_documents({"account_id": account_id, "revoked_at": None, "expires_at": {"$gt": now_iso()}})
    return {"account": {k: a.get(k) for k in ("id", "full_name", "email", "phone", "status", "email_verified", "created_at", "verified_at",
                                              "last_login_at", "created_via", "deletion_requested_at", "verification_email_status")},
            "login_methods": [{"provider": i["provider"], "created_at": i["created_at"]} for i in idents],
            "addresses": await db.customer_addresses.count_documents({"account_id": account_id}),
            "active_sessions": active_sessions, "orders": orders, "security_events": events, "emails": emails}


class AccountStatusBody(BaseModel):
    reason: Optional[str] = ""


@customer_admin_router.post("/customer-accounts/{account_id}/suspend")
async def admin_suspend(account_id: str, body: AccountStatusBody, current=Depends(require("customers.manage"))):
    res = await db.customer_accounts.update_one({"id": account_id, "status": {"$ne": "suspended"}},
                                                {"$set": {"status": "suspended", "suspended_at": now_iso(), "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Account not found or already suspended")
    n = await revoke_sessions(account_id)
    await security_event(account_id, "suspended_by_admin", None, f"by={current['email']} reason={clean_text(body.reason or '', 120)} sessions={n}")
    return {"ok": True, "sessions_revoked": n}


@customer_admin_router.post("/customer-accounts/{account_id}/reactivate")
async def admin_reactivate(account_id: str, body: AccountStatusBody, current=Depends(require("customers.manage"))):
    acct = await db.customer_accounts.find_one({"id": account_id, "status": "suspended"}, {"_id": 0})
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found or not suspended")
    new_status = "active" if acct.get("email_verified") else "pending_verification"
    await db.customer_accounts.update_one({"id": account_id}, {"$set": {"status": new_status, "updated_at": now_iso()}})
    await security_event(account_id, "reactivated_by_admin", None, f"by={current['email']}")
    return {"ok": True, "status": new_status}


# ---------------------------------------------------------------------------
# Indexes (idempotent; new collections plus one non-unique index on orders)
# ---------------------------------------------------------------------------
CUSTOMER_INDEXES = [
    ("customer_accounts", [("id", 1)], {"unique": True, "name": "id_unique"}),
    ("customer_accounts", [("email", 1)], {"unique": True, "name": "email_unique"}),
    ("customer_identities", [("provider", 1), ("subject", 1)], {"unique": True, "name": "provider_subject_unique"}),
    ("customer_identities", [("account_id", 1)], {"name": "account_id"}),
    ("customer_sessions", [("token_hash", 1)], {"unique": True, "name": "token_hash_unique"}),
    ("customer_sessions", [("account_id", 1)], {"name": "account_id"}),
    ("customer_tokens", [("token_hash", 1)], {"unique": True, "name": "token_hash_unique"}),
    ("customer_tokens", [("account_id", 1), ("purpose", 1)], {"name": "account_purpose"}),
    ("customer_addresses", [("account_id", 1)], {"name": "account_id"}),
    ("security_events", [("account_id", 1), ("created_at", -1)], {"name": "account_created"}),
    ("email_logs", [("account_id", 1)], {"name": "account_id"}),
    ("order_events", [("order_id", 1), ("created_at", 1)], {"name": "order_created"}),
    ("orders", [("account_id", 1)], {"name": "account_id"}),
]


async def ensure_customer_indexes():
    for coll, keys, opts in CUSTOMER_INDEXES:
        try:
            existing = await db[coll].index_information()
            if any(list(i.get("key", [])) == keys for i in existing.values()):
                continue
            await db[coll].create_index(keys, **opts)
        except Exception:  # noqa: BLE001
            logger.warning("could not ensure index %s %s", coll, keys)

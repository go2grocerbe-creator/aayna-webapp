"""
Offline tests: customer identity, sessions, email verification, password reset,
Google OIDC (mocked provider, real RS256 verification with a locally generated
key), account-linked orders, guest-order claiming, tracking timeline,
promotions/coupons, the welcome campaign and the transactional email engine.

mongomock-motor + FastAPI TestClient. No network. EMAIL_MODE=capture keeps every
message in memory; nothing is sent anywhere. Fake data only.
"""
import asyncio
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("MONGO_URL", "mongodb://mock")
os.environ.setdefault("DB_NAME", "aayna_import_test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-offline-import-tests-only-0000")

from mongomock_motor import AsyncMongoMockClient  # noqa: E402
import db as dbmod  # noqa: E402

if "mongomock" not in type(dbmod.db).__module__:
    dbmod.db = AsyncMongoMockClient()["aayna_import_test"]

import auth  # noqa: E402
import admin_routes  # noqa: E402
import customer_auth as ca  # noqa: E402
import emailer  # noqa: E402
import promotions  # noqa: E402
import ratelimit  # noqa: E402
import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CSRF = {"X-AAYNA-CSRF": "1"}
PW = "a long and memorable passphrase"
COLLECTIONS = ("users", "products", "categories", "inventory_logs", "orders", "customers", "website_settings",
               "customer_accounts", "customer_identities", "customer_sessions", "customer_tokens", "customer_addresses",
               "security_events", "email_logs", "email_dedupe", "rate_limits", "oauth_states", "order_events",
               "promotions", "promotion_usage", "promotion_redemptions", "promotion_audit", "promotion_campaigns",
               "welcome_issuance", "checkout_requests", "counters", "notification_logs")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def env(monkeypatch):
    db = dbmod.db
    for m in (auth, admin_routes, server, ca, emailer, promotions, ratelimit):
        monkeypatch.setattr(m, "db", db)
    monkeypatch.setenv("EMAIL_MODE", "capture")
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://preview.example.test")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    emailer.CAPTURED.clear()
    auth._failed_logins.clear()

    async def seed():
        for c in COLLECTIONS:
            await db[c].delete_many({})
            await db[c].drop_indexes()
        await ca.ensure_customer_indexes()
        await promotions.ensure_promotion_indexes()
        users = {}
        for r in ("super_admin", "admin", "product_manager", "order_manager"):
            u = {"id": f"u-{r}", "email": f"{r}@example.test", "name": r, "role": r, "status": "active",
                 "password_hash": auth.hash_password(f"pw-{r}-long-enough")}
            await db.users.insert_one(dict(u))
            users[r] = u
        await db.categories.insert_many([
            {"id": "c1", "name": "Earrings", "slug": "earrings", "status": "active", "sort_order": 1},
            {"id": "c2", "name": "Rings", "slug": "rings", "status": "active", "sort_order": 2}])
        for pid, cat, price, stock in (("p1", "rings", 1290, 5), ("p2", "earrings", 990, 5), ("p3", "rings", 300, 1)):
            await db.products.insert_one({
                "id": pid, "sku": f"AYN-TST-{pid}", "slug": f"prod-{pid}", "product_name": f"Product {pid}",
                "category_slug": cat, "category_name": cat.title(), "selling_price": price, "discount_price": None,
                "cost_price": 100.0, "stock_quantity": stock, "status": "active", "images": [],
                "created_at": "2026-10-18T00:00:00+00:00"})
        await db.website_settings.insert_many([
            {"setting_key": "delivery_charge_inside_dhaka", "setting_value": 80},
            {"setting_key": "delivery_charge_outside_dhaka", "setting_value": 130}])
        return users
    users = run(seed())
    tok = {r: auth.create_access_token(u) for r, u in users.items()}
    return {"db": db, "tok": tok, "app": server.app}


def client():
    return TestClient(server.app)


def admin_h(env, role="super_admin"):
    return {"Authorization": f"Bearer {env['tok'][role]}"}


def last_link(kind_path: str) -> str:
    for m in reversed(emailer.CAPTURED):
        found = re.search(r"https://preview\.example\.test" + re.escape(kind_path) + r"#token=([A-Za-z0-9_\-]+)", m["text"])
        if found:
            return found.group(1)
    raise AssertionError(f"no captured link for {kind_path}")


def register(c, email="maya@example.test", phone="01712345678", password=PW, name="Maya Rahman"):
    return c.post("/api/customer/register", headers=CSRF, json={
        "full_name": name, "email": email, "phone": phone, "password": password,
        "confirm_password": password, "accept_terms": True})


def verified_client(email="maya@example.test", phone="01712345678"):
    c = client()
    assert register(c, email=email, phone=phone).status_code == 200
    r = c.post("/api/customer/verify-email", headers=CSRF, json={"token": last_link("/verify-email")})
    assert r.status_code == 200, r.text
    return c


def checkout(c, items=(("p1", 1),), phone="01712345678", coupon=None, rid=None, email=""):
    body = {"customer_name": "Maya Rahman", "customer_phone": phone, "district": "Dhaka",
            "delivery_address": "House 1, Road 2, Dhanmondi", "payment_method": "cod", "customer_email": email,
            "items": [{"product_id": p, "quantity": q} for p, q in items]}
    if coupon:
        body["coupon_code"] = coupon
    if rid:
        body["client_request_id"] = rid
    return c.post("/api/checkout", json=body)


# ---------------------------------------------------------------------------
# Registration, verification, login, sessions
# ---------------------------------------------------------------------------
def test_register_validation_and_policy(env):
    c = client()
    r = c.post("/api/customer/register", headers=CSRF, json={"full_name": "M", "email": "bad", "phone": "123",
                                                              "password": "short", "confirm_password": "x", "accept_terms": False})
    assert r.status_code == 422
    f = r.json()["detail"]["fields"]
    assert set(f) == {"full_name", "email", "phone", "password", "confirm_password", "accept_terms"}
    assert register(c, password="password123456").status_code == 422          # common
    assert register(c, password="maya.rahman.secret", email="maya.rahman@example.test").status_code == 422  # contains email
    assert ca.password_problem("1" * 20) and ca.password_problem("x" * 300)
    assert ca.password_problem("correct horse battery staple") is None


def test_password_hashing_long_passphrases(env):
    long_a = "w" * 80 + "A"
    long_b = "w" * 80 + "B"
    h = ca.hash_password(long_a)
    assert h.startswith("v2$") and long_a not in h
    assert ca.verify_password(long_a, h) and not ca.verify_password(long_b, h)  # chars beyond 72 bytes count
    assert not ca.verify_password(long_a, None)


def test_register_verify_login_flow(env):
    c = client()
    r = register(c)
    assert r.status_code == 200 and "If this email address can be used" in r.json()["message"]
    acct = run(env["db"].customer_accounts.find_one({"email": "maya@example.test"}))
    assert acct["status"] == "pending_verification" and not acct["email_verified"] and acct["phone"] == "+8801712345678"
    assert PW not in str(acct)
    mail = emailer.CAPTURED[-1]
    assert mail["from"].endswith("<accounts@shopaayna.com>") and mail["html"] and mail["text"]
    # token only stored hashed
    raw = last_link("/verify-email")
    assert run(env["db"].customer_tokens.find_one({"token_hash": raw})) is None
    # login blocked until verified (only revealed with the right password)
    assert c.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": "wrong password here"}).status_code == 401
    r = c.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "email_unverified"
    # verify -> signed in
    r = c.post("/api/customer/verify-email", headers=CSRF, json={"token": raw})
    assert r.status_code == 200 and r.json()["account"]["email_verified"]
    assert "aayna_sid" in c.cookies
    me = c.get("/api/account/me").json()
    assert me["email"] == "maya@example.test" and "password_hash" not in me and me["login_methods"] == ["password"]
    # replay / tamper
    assert c.post("/api/customer/verify-email", headers=CSRF, json={"token": raw}).json()["detail"]["code"] == "used"
    assert c.post("/api/customer/verify-email", headers=CSRF, json={"token": raw[:-2] + "xx"}).json()["detail"]["code"] == "invalid"
    # logout, then login with password
    assert c.post("/api/customer/logout", headers=CSRF).status_code == 200
    assert c.get("/api/account/me").status_code == 401
    r = c.post("/api/customer/login", headers=CSRF, json={"email": " MAYA@example.test ", "password": PW})
    assert r.status_code == 200 and c.get("/api/account/me").status_code == 200


def test_expired_verification_and_resend_cooldown(env):
    c = client()
    register(c)
    raw = last_link("/verify-email")
    run(env["db"].customer_tokens.update_many({}, {"$set": {"expires_at": "2000-01-01T00:00:00+00:00"}}))
    assert c.post("/api/customer/verify-email", headers=CSRF, json={"token": raw}).json()["detail"]["code"] == "expired"
    n = len(emailer.CAPTURED)
    run(env["db"].customer_accounts.update_many({}, {"$set": {"last_verification_sent_at": "2000-01-01T00:00:00+00:00"}}))
    assert c.post("/api/customer/resend-verification", headers=CSRF, json={"email": "maya@example.test"}).status_code == 200
    assert len(emailer.CAPTURED) == n + 1
    # cooldown: an immediate second request sends nothing but answers the same
    r = c.post("/api/customer/resend-verification", headers=CSRF, json={"email": "maya@example.test"})
    assert r.status_code == 200 and len(emailer.CAPTURED) == n + 1
    # unknown email: same answer, nothing sent
    r2 = c.post("/api/customer/resend-verification", headers=CSRF, json={"email": "nobody@example.test"})
    assert r2.json() == r.json() and len(emailer.CAPTURED) == n + 1
    # the newest link works; the older one was superseded
    assert c.post("/api/customer/verify-email", headers=CSRF, json={"token": last_link("/verify-email")}).status_code == 200


def test_duplicate_registration_is_not_enumerable(env):
    c = verified_client()
    other = client()
    r = register(other, password="a different long passphrase")
    assert r.status_code == 200 and r.json()["message"] == ca.GENERIC_REGISTER_MSG
    assert run(env["db"].customer_accounts.count_documents({"email": "maya@example.test"})) == 1
    assert emailer.CAPTURED[-1]["template"] == "account_exists"
    assert c.get("/api/account/me").status_code == 200


def test_csrf_and_origin_guard(env):
    c = client()
    body = {"email": "x@example.test", "password": PW}
    assert c.post("/api/customer/login", json=body).status_code == 403
    assert c.post("/api/customer/login", json=body, headers={**CSRF, "Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/customer/login", json=body, headers={**CSRF, "Origin": "https://preview.example.test"}).status_code == 401


def test_login_bruteforce_lockout(env):
    verified_client()
    c = client()
    for _ in range(5):
        assert c.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": "nope nope nope"}).status_code == 401
    r = c.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW})
    assert r.status_code == 429


def test_session_revocation_and_logout_all(env):
    a = verified_client()
    b = client()
    assert b.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW}).status_code == 200
    sec = a.get("/api/account/security").json()
    assert len(sec["sessions"]) == 2 and sum(s["current"] for s in sec["sessions"]) == 1
    assert a.post("/api/account/sessions/revoke-others", headers=CSRF).json()["revoked"] == 1
    assert b.get("/api/account/me").status_code == 401 and a.get("/api/account/me").status_code == 200
    assert a.post("/api/account/logout-all", headers=CSRF).status_code == 200
    assert a.get("/api/account/me").status_code == 401
    # expired session record is refused
    c = client()
    c.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW})
    run(env["db"].customer_sessions.update_many({"revoked_at": None}, {"$set": {"expires_at": "2000-01-01T00:00:00+00:00"}}))
    assert c.get("/api/account/me").status_code == 401
    assert c.get("/api/customer/session").json() == {"authenticated": False}


def test_admin_and_customer_credentials_are_separate(env):
    c = verified_client()
    assert c.get("/api/admin/products").status_code == 401
    assert c.get("/api/admin/me").status_code == 401
    raw = c.cookies.get("aayna_sid")
    assert client().get("/api/admin/products", headers={"Authorization": f"Bearer {raw}"}).status_code == 401
    adm = client()
    assert adm.get("/api/account/me", headers=admin_h(env)).status_code == 401
    adm.cookies.set("aayna_sid", env["tok"]["super_admin"])
    assert adm.get("/api/account/me").status_code == 401
    # a client cannot grant itself anything: unknown fields are ignored
    r = c.patch("/api/account/profile", headers=CSRF, json={"full_name": "Maya R", "role": "super_admin",
                                                            "email_verified": False, "id": "x", "status": "suspended"})
    acct = run(env["db"].customer_accounts.find_one({"email": "maya@example.test"}))
    assert r.status_code == 200 and acct["full_name"] == "Maya R" and acct["status"] == "active" and "role" not in acct


# ---------------------------------------------------------------------------
# Password recovery
# ---------------------------------------------------------------------------
def test_forgot_password_constant_response_and_eligibility(env):
    verified_client()
    run(env["db"].customer_accounts.insert_one({"id": "g1", "email": "gonly@example.test", "status": "active",
                                                "email_verified": True, "password_hash": None}))
    c = client()
    n = len(emailer.CAPTURED)
    answers = {e: c.post("/api/customer/forgot-password", headers=CSRF, json={"email": e}).json()
               for e in ("nobody@example.test", "gonly@example.test", "maya@example.test")}
    assert len({str(v) for v in answers.values()}) == 1
    assert answers["maya@example.test"]["message"] == ca.GENERIC_RESET_MSG
    assert len(emailer.CAPTURED) == n + 1 and emailer.CAPTURED[-1]["to"] == "maya@example.test"


def test_reset_password_full_flow(env):
    a = verified_client()
    other = client()
    other.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW})
    c = client()
    c.post("/api/customer/forgot-password", headers=CSRF, json={"email": "maya@example.test"})
    raw = last_link("/reset-password")
    tok = run(env["db"].customer_tokens.find_one({"purpose": "password_reset"}))
    exp = datetime.fromisoformat(tok["expires_at"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=14) < exp <= timedelta(minutes=15)
    # weak new password does not spend the token
    assert c.post("/api/customer/reset-password", headers=CSRF, json={"token": raw, "password": "short", "confirm_password": "short"}).status_code == 422
    assert c.post("/api/customer/reset-password", headers=CSRF, json={"token": raw + "x", "password": "brand new passphrase 1", "confirm_password": "brand new passphrase 1"}).status_code == 400
    r = c.post("/api/customer/reset-password", headers=CSRF, json={"token": raw, "password": "brand new passphrase 1", "confirm_password": "brand new passphrase 1"})
    assert r.status_code == 200
    # replay
    r2 = c.post("/api/customer/reset-password", headers=CSRF, json={"token": raw, "password": "another new phrase 22", "confirm_password": "another new phrase 22"})
    assert r2.status_code == 400 and r2.json()["detail"]["code"] == "used"
    # every previous session is gone; old password refused; new accepted
    assert a.get("/api/account/me").status_code == 401 and other.get("/api/account/me").status_code == 401
    assert c.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW}).status_code == 401
    assert c.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": "brand new passphrase 1"}).status_code == 200
    assert emailer.CAPTURED[-1]["template"] == "password_changed"
    assert "brand new passphrase" not in str(list(run(env["db"].security_events.find({}).to_list(100))))


def test_reset_token_expired_and_concurrent_use(env):
    verified_client()
    c = client()
    c.post("/api/customer/forgot-password", headers=CSRF, json={"email": "maya@example.test"})
    raw = last_link("/reset-password")

    async def both():
        return await asyncio.gather(ca.consume_token(raw, "password_reset"), ca.consume_token(raw, "password_reset"),
                                    return_exceptions=True)
    results = run(both())
    assert sum(1 for r in results if isinstance(r, dict)) == 1
    c2 = client()
    run(env["db"].customer_tokens.delete_many({}))
    run(env["db"].rate_limits.delete_many({}))
    c2.post("/api/customer/forgot-password", headers=CSRF, json={"email": "maya@example.test"})
    raw2 = last_link("/reset-password")
    run(env["db"].customer_tokens.update_many({}, {"$set": {"expires_at": "2000-01-01T00:00:00+00:00"}}))
    r = c2.post("/api/customer/reset-password", headers=CSRF, json={"token": raw2, "password": "brand new passphrase 1", "confirm_password": "brand new passphrase 1"})
    assert r.json()["detail"]["code"] == "expired"


def test_forgot_password_per_account_throttle(env):
    verified_client()
    c = client()
    n = len(emailer.CAPTURED)
    for _ in range(5):
        assert c.post("/api/customer/forgot-password", headers=CSRF, json={"email": "maya@example.test"}).status_code == 200
    assert len(emailer.CAPTURED) == n + 3


# ---------------------------------------------------------------------------
# Google OIDC (mocked provider, real signature checks)
# ---------------------------------------------------------------------------
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = {**__import__("json").loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())), "kid": "k1", "alg": "RS256", "use": "sig"}
CID = "test-client.apps.googleusercontent.com"


@pytest.fixture()
def google(env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    claims_box = {}

    async def fake_jwks():
        return {"keys": [JWK]}

    async def fake_exchange(code, verifier):
        assert code == "good-code" and len(verifier) >= 43
        c = dict(claims_box["claims"])
        key = claims_box.get("key", KEY)
        return {"id_token": jwt.encode(c, key, algorithm="RS256", headers={"kid": claims_box.get("kid", "k1")})}
    monkeypatch.setattr(ca, "_fetch_jwks", fake_jwks)
    monkeypatch.setattr(ca, "_exchange_code", fake_exchange)
    return claims_box


def google_login(c, box, **over):
    r = c.get("/api/auth/google/start?next=/account/orders", follow_redirects=False)
    assert r.status_code == 303
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["client_id"] == [CID]
    assert q["redirect_uri"] == ["https://preview.example.test/api/auth/google/callback"]
    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": CID, "azp": CID, "sub": "google-sub-1",
              "email": "gina@example.test", "email_verified": True, "name": "Gina Akter",
              "iat": now, "exp": now + 600, "nonce": q["nonce"][0]}
    claims.update(over.pop("claims", {}))
    box["claims"] = claims
    box.update(over)
    state = over.get("state", q["state"][0])
    return c.get(f"/api/auth/google/callback?code=good-code&state={state}", follow_redirects=False), q


def test_google_new_account_and_repeat_login(env, google):
    c = client()
    r, _ = google_login(c, google)
    assert r.status_code == 303 and r.headers["location"] == "/account/orders"
    me = c.get("/api/account/me").json()
    assert me["email"] == "gina@example.test" and me["email_verified"] and me["login_methods"] == ["google"] and not me["has_password"]
    c2 = client()
    r, _ = google_login(c2, google)
    assert r.headers["location"] == "/account/orders"
    assert run(env["db"].customer_accounts.count_documents({})) == 1
    assert run(env["db"].customer_identities.count_documents({"provider": "google"})) == 1


@pytest.mark.parametrize("bad", [
    {"claims": {"aud": "someone-else"}}, {"claims": {"iss": "https://evil.example"}},
    {"claims": {"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200}}, {"claims": {"nonce": "wrong"}},
    {"claims": {"azp": "other-app"}}, {"key": OTHER_KEY}, {"kid": "unknown"},
])
def test_google_rejects_invalid_tokens(env, google, bad):
    c = client()
    r, _ = google_login(c, google, **bad)
    assert r.status_code == 303 and r.headers["location"].startswith("/login?error=google_failed")
    assert run(env["db"].customer_accounts.count_documents({})) == 0


def test_google_state_binding_and_replay(env, google):
    c = client()
    r, q = google_login(c, google)
    assert r.headers["location"] == "/account/orders"
    # replay the same callback
    c.cookies.set("aayna_oauth", "whatever", path="/api/auth/google")
    replay = c.get(f"/api/auth/google/callback?code=good-code&state={q['state'][0]}", follow_redirects=False)
    assert "google_failed" in replay.headers["location"]
    # missing state
    assert "google_failed" in client().get("/api/auth/google/callback?code=good-code", follow_redirects=False).headers["location"]
    # login CSRF: a callback with a valid state but from a different browser (no binding cookie)
    attacker = client()
    s = attacker.get("/api/auth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(s.headers["location"]).query)["state"][0]
    victim = client()
    assert "google_failed" in victim.get(f"/api/auth/google/callback?code=good-code&state={state}", follow_redirects=False).headers["location"]


def test_google_cancel_unverified_email_and_unconfigured(env, google, monkeypatch):
    c = client()
    s = c.get("/api/auth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(s.headers["location"]).query)["state"][0]
    r = c.get(f"/api/auth/google/callback?error=access_denied&state={state}", follow_redirects=False)
    assert r.headers["location"] == "/login?error=google_cancelled"
    r, _ = google_login(client(), google, claims={"email_verified": False})
    assert r.headers["location"] == "/login?error=google_email_unverified"
    # open redirect attempt is neutralised
    r = client().get("/api/auth/google/start?next=//evil.example/x", follow_redirects=False)
    st = run(env["db"].oauth_states.find_one({}, sort=[("created_at", -1)]))
    assert st["next"] == "/account"
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    assert client().get("/api/auth/google/start", follow_redirects=False).headers["location"] == "/login?error=google_unavailable"
    assert client().get("/api/customer/config").json()["google_enabled"] is False


def test_google_never_merges_on_email_alone(env, google):
    verified_client(email="gina@example.test")
    c = client()
    r, _ = google_login(c, google)
    assert r.headers["location"] == "/login?link=google"
    assert c.get("/api/account/me").status_code == 401  # not signed in to the existing account
    assert run(env["db"].customer_identities.count_documents({"provider": "google"})) == 0
    # someone else's session cannot consume the pending link
    intruder = verified_client(email="intruder@example.test", phone="01812345678")
    intruder.cookies.set("aayna_glink", c.cookies.get("aayna_glink"), path="/api/account")
    assert intruder.post("/api/account/link/google/confirm", headers=CSRF).status_code == 400
    # the owner proves the password, then links
    c2 = client()
    r, _ = google_login(c2, google)
    assert c2.post("/api/customer/login", headers=CSRF, json={"email": "gina@example.test", "password": PW}).status_code == 200
    assert c2.post("/api/account/link/google/confirm", headers=CSRF).json()["linked"]
    c3 = client()
    r, _ = google_login(c3, google)
    assert r.headers["location"] == "/account/orders"
    assert c3.get("/api/account/me").json()["login_methods"] == ["google", "password"]


def test_google_only_account_password_rules(env, google):
    c = client()
    google_login(c, google)
    # forgot-password never gives a Google-only account a password
    n = len(emailer.CAPTURED)
    client().post("/api/customer/forgot-password", headers=CSRF, json={"email": "gina@example.test"})
    assert len(emailer.CAPTURED) == n
    # explicit set-password flow requires a recent sign-in
    run(env["db"].customer_sessions.update_many({}, {"$set": {"created_at": "2020-01-01T00:00:00+00:00"}}))
    r = c.post("/api/account/password", headers=CSRF, json={"new_password": "my brand new phrase", "confirm_password": "my brand new phrase"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "reauth"
    c2 = client()
    google_login(c2, google)
    assert c2.post("/api/account/password", headers=CSRF, json={"new_password": "my brand new phrase", "confirm_password": "my brand new phrase"}).status_code == 200
    assert c2.get("/api/account/me").json()["has_password"]
    # cannot unlink the last way in, but can once a password exists
    assert c2.delete("/api/account/link/google", headers=CSRF).status_code == 200


# ---------------------------------------------------------------------------
# Profile, addresses
# ---------------------------------------------------------------------------
def test_profile_and_addresses_isolation(env):
    a = verified_client()
    b = verified_client(email="other@example.test", phone="01812345678")
    assert a.patch("/api/account/profile", headers=CSRF, json={"phone": "12"}).status_code == 422
    assert a.patch("/api/account/profile", headers=CSRF, json={"phone": "+8801912345678"}).json()["phone"] == "+8801912345678"
    bad = a.post("/api/account/addresses", headers=CSRF, json={"recipient_name": "", "phone": "1", "district": "Mars", "address": "x"})
    assert bad.status_code == 422 and set(bad.json()["detail"]["fields"]) == {"recipient_name", "phone", "district", "address"}
    good = {"recipient_name": "Maya", "phone": "01712345678", "district": "Dhaka", "address": "House 5, Road 7, Banani"}
    first = a.post("/api/account/addresses", headers=CSRF, json=good).json()
    second = a.post("/api/account/addresses", headers=CSRF, json={**good, "label": "Office", "is_default": True}).json()
    lst = a.get("/api/account/addresses").json()
    assert [x["is_default"] for x in lst] == [False, True] and "account_id" not in lst[0]
    # another customer cannot read, edit or delete them
    assert b.get("/api/account/addresses").json() == []
    assert b.put(f"/api/account/addresses/{first['id']}", headers=CSRF, json=good).status_code == 404
    assert b.delete(f"/api/account/addresses/{first['id']}", headers=CSRF).status_code == 404
    assert a.delete(f"/api/account/addresses/{second['id']}", headers=CSRF).status_code == 200
    assert a.get("/api/account/addresses").json()[0]["is_default"] is True
    assert a.get("/api/account/me").json()["default_address"]["id"] == first["id"]


def test_email_change_requires_password_and_confirmation(env):
    a = verified_client()
    r = a.post("/api/account/email", headers=CSRF, json={"new_email": "new@example.test", "current_password": "wrong one entirely"})
    assert r.status_code == 400
    r = a.post("/api/account/email", headers=CSRF, json={"new_email": "new@example.test", "current_password": PW})
    assert r.status_code == 200 and a.get("/api/account/me").json()["email"] == "maya@example.test"
    raw = last_link("/confirm-email")
    assert client().post("/api/customer/confirm-email-change", headers=CSRF, json={"token": raw}).status_code == 200
    assert a.get("/api/account/me").status_code == 401  # signed out everywhere
    c = client()
    assert c.post("/api/customer/login", headers=CSRF, json={"email": "new@example.test", "password": PW}).status_code == 200


# ---------------------------------------------------------------------------
# Orders: guest, authenticated, ownership, claiming, tracking
# ---------------------------------------------------------------------------
def test_guest_checkout_still_works_and_stays_unlinked(env):
    r = checkout(client())
    assert r.status_code == 200, r.text
    order = run(env["db"].orders.find_one({"order_number": r.json()["order_number"]}))
    assert order["account_id"] is None and order["discount_amount"] == 0
    assert run(env["db"].products.find_one({"id": "p1"}))["stock_quantity"] == 4
    ev = run(env["db"].order_events.find_one({"order_id": order["id"]}))
    assert ev["status"] == "New"


def test_authenticated_checkout_links_account_and_body_cannot_choose(env):
    a = verified_client()
    b = verified_client(email="other@example.test", phone="01812345678")
    b_id = b.get("/api/account/me").json()["id"]
    body = {"customer_name": "Maya", "customer_phone": "01712345678", "district": "Dhaka",
            "delivery_address": "House 1, Road 2", "payment_method": "cod",
            "items": [{"product_id": "p2", "quantity": 1}], "account_id": b_id, "customer_id": "x"}
    r = a.post("/api/checkout", json=body)
    assert r.status_code == 200
    num = r.json()["order_number"]
    order = run(env["db"].orders.find_one({"order_number": num}))
    me = a.get("/api/account/me").json()
    assert order["account_id"] == me["id"] and order["customer_email"] == "maya@example.test"
    assert [o["order_number"] for o in a.get("/api/account/orders").json()] == [num]
    assert b.get("/api/account/orders").json() == []
    assert b.get(f"/api/account/orders/{num}").status_code == 404
    detail = a.get(f"/api/account/orders/{num}").json()
    assert detail["timeline"]["steps"][0]["at"] and detail["timeline"]["steps"][1]["at"] is None
    assert "order_confirmation_token_hash" not in str(detail) and "customer_phone" not in detail
    tmpl = [m["template"] for m in emailer.CAPTURED]
    assert "order_confirmation" in tmpl and emailer.CAPTURED[-1]["from"].endswith("<orders@shopaayna.com>")


def test_claim_guest_order_with_confirmation_token_only(env):
    r = checkout(client(), items=(("p2", 1),))
    num, token = r.json()["order_number"], r.json()["order_confirmation_token"]
    a = verified_client()
    b = verified_client(email="other@example.test", phone="01812345678")
    # phone match alone is not proof
    assert a.get("/api/account/orders").json() == []
    assert a.post("/api/account/orders/claim", headers=CSRF, json={"order_number": num}).status_code == 404
    assert a.post("/api/account/orders/claim", headers=CSRF, json={"order_number": num, "confirmation_token": "guess"}).status_code == 404
    assert a.post("/api/account/orders/claim", headers=CSRF, json={"order_number": num, "confirmation_token": token}).status_code == 200
    assert [o["order_number"] for o in a.get("/api/account/orders").json()] == [num]
    # a second account cannot take it over even with the token
    assert b.post("/api/account/orders/claim", headers=CSRF, json={"order_number": num, "confirmation_token": token}).status_code == 404


def test_claim_by_recorded_email_link(env):
    r = checkout(client(), items=(("p2", 1),), email="maya@example.test")
    num = r.json()["order_number"]
    a = verified_client()
    b = verified_client(email="other@example.test", phone="01812345678")
    n = len(emailer.CAPTURED)
    rb = b.post("/api/account/orders/claim-by-email", headers=CSRF, json={"order_number": num})
    ra = a.post("/api/account/orders/claim-by-email", headers=CSRF, json={"order_number": num})
    assert rb.json() == ra.json()
    assert len(emailer.CAPTURED) == n + 1 and emailer.CAPTURED[-1]["to"] == "maya@example.test"
    raw = last_link("/account/orders/claim")
    assert b.post("/api/account/orders/confirm-claim", headers=CSRF, json={"token": raw}).status_code == 400
    a2 = client()
    a2.post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW})
    run(env["db"].customer_tokens.update_many({"purpose": "order_claim"}, {"$set": {"used_at": None}}))
    assert a2.post("/api/account/orders/confirm-claim", headers=CSRF, json={"token": raw}).status_code == 200
    assert [o["order_number"] for o in a2.get("/api/account/orders").json()] == [num]


def test_tracking_timeline_records_real_transitions_and_rate_limit(env):
    r = checkout(client(), email="guest@example.test")
    num = r.json()["order_number"]
    c = client()
    t = c.post("/api/track", json={"order_number": num, "phone": "01712345678"}).json()[0]
    assert t["timeline"]["steps"][0]["done"] and not t["timeline"]["steps"][1]["done"]
    assert "delivery_address" not in t and "customer_phone" not in t
    assert c.put(f"/api/admin/orders/{num}", headers=admin_h(env, "order_manager"),
                 json={"order_status": "Confirmed", "courier_name": "Pathao"}).status_code == 200
    t = c.post("/api/track", json={"order_number": num, "phone": "01712345678"}).json()[0]
    assert t["timeline"]["steps"][1]["done"] and t["timeline"]["steps"][1]["at"] and t["courier_name"] == "Pathao"
    assert emailer.CAPTURED[-1]["template"] == "order_status"
    # same status again: no duplicate email or event
    n = len(emailer.CAPTURED)
    c.put(f"/api/admin/orders/{num}", headers=admin_h(env), json={"order_status": "Confirmed"})
    assert len(emailer.CAPTURED) == n
    # history-less legacy order: current status only, no invented dates
    run(env["db"].order_events.delete_many({}))
    run(env["db"].orders.update_one({"order_number": num}, {"$set": {"order_status": "Packed"}}))
    t = c.post("/api/track", json={"order_number": num, "phone": "01712345678"}).json()[0]
    assert t["timeline"]["steps"][2]["current"] and t["timeline"]["steps"][2]["at"] is None and t["timeline"]["steps"][1]["at"] is None
    # wrong phone: generic; then rate limited
    assert c.post("/api/track", json={"order_number": num, "phone": "01999999999"}).status_code == 404
    codes = [c.post("/api/track", json={"order_number": "ORD-9", "phone": "01999999999"}).status_code for _ in range(20)]
    assert 429 in codes


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------
def make_promo(env, role="super_admin", activate=True, **over):
    body = {"code": "SAVE10", "name": "Ten percent", "type": "percent", "value": 10, "usage_limit_total": None,
            "usage_limit_per_customer": 1, "min_subtotal": 0, **over}
    c = client()
    r = c.post("/api/admin/promotions", headers=admin_h(env, role), json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["status"] == "draft"
    if activate:
        a = c.post(f"/api/admin/promotions/{p['id']}/activate", headers=admin_h(env), json={"confirm": True})
        assert a.status_code == 200, a.text
    return p


def test_promotion_permissions(env):
    c = client()
    body = {"code": "X10", "name": "x", "type": "percent", "value": 10}
    for role in ("product_manager", "order_manager"):
        assert c.get("/api/admin/promotions", headers=admin_h(env, role)).status_code == 403
        assert c.post("/api/admin/promotions", headers=admin_h(env, role), json=body).status_code == 403
    p = make_promo(env, role="admin", activate=False)
    assert c.post(f"/api/admin/promotions/{p['id']}/activate", headers=admin_h(env, "admin"), json={"confirm": True}).status_code == 403
    assert c.post(f"/api/admin/promotions/{p['id']}/activate", headers=admin_h(env), json={}).status_code == 400
    assert c.put("/api/admin/promotions/campaigns/welcome", headers=admin_h(env, "admin"), json={"enabled": True}).status_code == 403
    verified = verified_client()
    assert verified.get("/api/admin/promotions").status_code == 401
    # validation
    assert c.post("/api/admin/promotions", headers=admin_h(env), json={**body, "value": 150}).status_code == 422
    assert c.post("/api/admin/promotions", headers=admin_h(env), json={**body, "code": "WELCOME-ABC"}).status_code == 422
    assert c.post("/api/admin/promotions", headers=admin_h(env), json={**body, "code": "SAVE10"}).status_code == 409


def test_coupon_applies_server_side_to_merchandise_only(env):
    make_promo(env, max_discount_bdt=100)
    c = client()
    v = c.post("/api/cart/validate", json={"items": [{"product_id": "p1", "quantity": 1}], "district": "Dhaka", "coupon_code": " save10 "}).json()
    assert v["coupon"]["valid"] and v["discount_amount"] == 100 and v["total"] == 1290 - 100 + 80
    r = checkout(c, coupon="SAVE10")
    assert r.status_code == 200, r.text
    order = run(env["db"].orders.find_one({"order_number": r.json()["order_number"]}))
    assert order["discount_amount"] == 100 and order["delivery_charge"] == 80 and order["total_amount"] == 1270
    assert order["subtotal"] == 1290 and order["coupon_code"] == "SAVE10"
    red = run(env["db"].promotion_redemptions.find_one({"order_id": order["id"]}))
    assert red["discount_amount"] == 100
    # catalogue untouched
    p1 = run(env["db"].products.find_one({"id": "p1"}))
    assert p1["selling_price"] == 1290 and p1["cost_price"] == 100.0
    # browser cannot dictate a discount
    body = {"customer_name": "M", "customer_phone": "01812345678", "district": "Dhaka", "delivery_address": "House 1, Road 2",
            "payment_method": "cod", "items": [{"product_id": "p2", "quantity": 1}], "discount_amount": 900, "total_amount": 1}
    o2 = run(env["db"].orders.find_one({"order_number": c.post("/api/checkout", json=body).json()["order_number"]}))
    assert o2["discount_amount"] == 0 and o2["total_amount"] == 990 + 80


def test_coupon_rules(env):
    now = datetime.now(timezone.utc)
    make_promo(env, code="MIN2000", min_subtotal=2000)
    make_promo(env, code="FIXED500", type="fixed", value=500, max_percent_of_subtotal=20)
    make_promo(env, code="RINGSONLY", eligible_category_slugs=["rings"])
    make_promo(env, code="LATER", starts_at=(now + timedelta(days=2)).isoformat())
    make_promo(env, code="OVER", starts_at=(now - timedelta(days=3)).isoformat(), ends_at=(now - timedelta(days=1)).isoformat(), activate=False)
    run(env["db"].promotions.update_one({"code": "OVER"}, {"$set": {"status": "active"}}))
    make_promo(env, code="FIRSTONLY", first_order_only=True)
    paused = make_promo(env, code="PAUSED")
    client().post(f"/api/admin/promotions/{paused['id']}/pause", headers=admin_h(env))

    def val(code, items=(("p1", 1),), phone=None, c=None):
        return (c or client()).post("/api/cart/validate", json={"items": [{"product_id": p, "quantity": q} for p, q in items],
                                                                 "coupon_code": code, "phone": phone}).json()["coupon"]
    assert val("MIN2000")["reason"] == "minimum"
    assert val("MIN2000", items=(("p1", 1), ("p2", 1)))["discount"] == 228
    assert val("FIXED500")["discount"] == 258  # capped at 20% of 1290
    assert val("RINGSONLY", items=(("p2", 1),))["reason"] == "not_applicable"
    assert val("RINGSONLY", items=(("p1", 1), ("p2", 1)))["discount"] == 129
    assert val("LATER")["reason"] == "scheduled"
    assert val("OVER")["reason"] == "expired"
    assert val("PAUSED")["reason"] == "paused"
    assert val("NOPE")["valid"] is False and val("DRAFTX")["message"] == "This code isn't valid."
    checkout(client(), items=(("p2", 1),))  # a previous order from this phone
    assert val("FIRSTONLY", phone="01712345678")["reason"] == "first_order"
    assert checkout(client(), coupon="FIRSTONLY").status_code == 400


def test_coupon_limits_and_failed_checkout_does_not_consume(env):
    p = make_promo(env, code="ONCE", usage_limit_total=1)
    # out-of-stock checkout with the code: nothing consumed, stock unchanged
    r = checkout(client(), items=(("p3", 5),), coupon="ONCE")
    assert r.status_code == 400
    doc = run(env["db"].promotions.find_one({"code": "ONCE"}))
    assert doc["remaining_uses"] == 1 and doc["redeemed_count"] == 0
    assert run(env["db"].products.find_one({"id": "p3"}))["stock_quantity"] == 1
    # idempotent retry does not double count
    r1 = checkout(client(), coupon="ONCE", rid="req-1")
    r2 = checkout(client(), coupon="ONCE", rid="req-1")
    assert r1.status_code == 200 and r2.json()["duplicate"] is True
    doc = run(env["db"].promotions.find_one({"code": "ONCE"}))
    assert doc["remaining_uses"] == 0 and doc["redeemed_count"] == 1
    assert checkout(client(), phone="01812345678", coupon="ONCE").status_code == 400
    detail = client().get(f"/api/admin/promotions/{p['id']}", headers=admin_h(env)).json()
    assert detail["redemptions"] == 1 and detail["state"] == "exhausted" and detail["audit"]


def test_per_customer_limit_and_concurrent_reservation(env):
    make_promo(env, code="PERPHONE", usage_limit_per_customer=1)
    assert checkout(client(), coupon="PERPHONE").status_code == 200
    r = checkout(client(), items=(("p2", 1),), coupon="PERPHONE")
    assert r.status_code == 400 and "already used" in r.json()["detail"]
    make_promo(env, code="LASTONE", usage_limit_total=1, usage_limit_per_customer=None)

    async def race():
        ev = await promotions.evaluate("LASTONE", None, None, [{"product_id": "p1", "category_slug": "rings", "line_total": 1290}])
        return await asyncio.gather(*[promotions.reserve(ev) for _ in range(5)], return_exceptions=True)
    results = run(race())
    assert sum(1 for x in results if isinstance(x, dict)) == 1
    doc = run(env["db"].promotions.find_one({"code": "LASTONE"}))
    assert doc["remaining_uses"] == 0 and doc["redeemed_count"] == 1


def test_restore_redemption_only_for_cancelled_orders(env):
    make_promo(env, code="BACK", usage_limit_total=1)
    num = checkout(client(), coupon="BACK").json()["order_number"]
    red = run(env["db"].promotion_redemptions.find_one({}))
    c = client()
    assert c.post(f"/api/admin/promotions/redemptions/{red['id']}/restore", headers=admin_h(env), json={"confirm": True}).status_code == 400
    c.put(f"/api/admin/orders/{num}", headers=admin_h(env), json={"order_status": "Cancelled"})
    assert run(env["db"].promotions.find_one({"code": "BACK"}))["remaining_uses"] == 0  # not automatic
    assert c.post(f"/api/admin/promotions/redemptions/{red['id']}/restore", headers=admin_h(env, "order_manager"), json={"confirm": True}).status_code == 403
    assert c.post(f"/api/admin/promotions/redemptions/{red['id']}/restore", headers=admin_h(env), json={"confirm": True}).status_code == 200
    assert run(env["db"].promotions.find_one({"code": "BACK"}))["remaining_uses"] == 1


def test_customer_specific_coupon(env):
    a = verified_client()
    make_promo(env, code="VIPMAYA", customer_emails=["maya@example.test"])
    assert client().post("/api/cart/validate", json={"items": [{"product_id": "p1", "quantity": 1}], "coupon_code": "VIPMAYA"}).json()["coupon"]["reason"] == "signin"
    b = verified_client(email="other@example.test", phone="01812345678")
    assert b.post("/api/cart/validate", json={"items": [{"product_id": "p1", "quantity": 1}], "coupon_code": "VIPMAYA"}).json()["coupon"]["valid"] is False
    assert a.post("/api/cart/validate", json={"items": [{"product_id": "p1", "quantity": 1}], "coupon_code": "VIPMAYA"}).json()["coupon"]["valid"]


def test_admin_preview_is_exact(env):
    r = client().post("/api/admin/promotions/preview", headers=admin_h(env),
                      json={"type": "percent", "value": 10, "max_discount_bdt": 150, "min_subtotal": 1000, "subtotal": 2400, "delivery_charge": 80}).json()
    assert r == {"meets_minimum": True, "discount": 150, "merchandise_after": 2250, "total_with_delivery": 2330, "effective_percent": 6.25}
    r = client().post("/api/admin/promotions/preview", headers=admin_h(env),
                      json={"type": "percent", "value": 10, "min_subtotal": 1000, "subtotal": 900}).json()
    assert r["meets_minimum"] is False and r["discount"] == 0


# ---------------------------------------------------------------------------
# Welcome campaign
# ---------------------------------------------------------------------------
def test_welcome_disabled_by_default_issues_nothing(env):
    assert client().get("/api/promotions/welcome").json() == {"enabled": False}
    a = verified_client()
    assert a.get("/api/account/rewards").json() == {"welcome_enabled": False, "coupons": []}
    cfg = client().get("/api/admin/promotions/campaigns/welcome", headers=admin_h(env)).json()
    assert cfg["enabled"] is False and cfg["min_subtotal"] is None and cfg["proposed"] == {"min_subtotal": 1000, "max_discount_bdt": 150}


def test_welcome_enable_requires_explicit_limits_and_confirmation(env):
    c = client()
    assert c.put("/api/admin/promotions/campaigns/welcome", headers=admin_h(env), json={"enabled": True, "confirm": True}).status_code == 400
    assert c.put("/api/admin/promotions/campaigns/welcome", headers=admin_h(env),
                 json={"enabled": True, "min_subtotal": 1000, "max_discount_bdt": 150}).status_code == 400
    r = c.put("/api/admin/promotions/campaigns/welcome", headers=admin_h(env),
              json={"enabled": True, "min_subtotal": 1000, "max_discount_bdt": 150, "confirm": True})
    assert r.status_code == 200 and r.json()["approved_by"] == "super_admin@example.test"
    pub = client().get("/api/promotions/welcome").json()
    assert pub["enabled"] and pub["value"] == 10 and pub["validity_days"] == 30
    # verified customer gets exactly one personal, single-use, 30-day coupon
    a = verified_client()
    rewards = a.get("/api/account/rewards").json()["coupons"]
    assert len(rewards) == 1 and rewards[0]["code"].startswith("WELCOME-") and rewards[0]["state"] == "active"
    ends = datetime.fromisoformat(rewards[0]["ends_at"]) - datetime.now(timezone.utc)
    assert timedelta(days=29, hours=23) < ends <= timedelta(days=30)
    acct = run(env["db"].customer_accounts.find_one({"email": "maya@example.test"}))
    assert run(promotions.issue_welcome(acct)) is None
    code = rewards[0]["code"]
    # someone else cannot use it; the owner can, once, above the minimum, capped at 150
    b = verified_client(email="other@example.test", phone="01812345678")
    assert b.post("/api/cart/validate", json={"items": [{"product_id": "p1", "quantity": 1}], "coupon_code": code}).json()["coupon"]["valid"] is False
    assert a.post("/api/cart/validate", json={"items": [{"product_id": "p2", "quantity": 1}], "coupon_code": code}).json()["coupon"]["reason"] == "minimum"
    r = checkout(a, items=(("p1", 1), ("p2", 1)), coupon=code)
    assert r.status_code == 200
    o = run(env["db"].orders.find_one({"order_number": r.json()["order_number"]}))
    assert o["discount_amount"] == 150
    assert checkout(a, items=(("p1", 1),), coupon=code).status_code == 400
    assert a.get("/api/account/rewards").json()["coupons"][0]["state"] == "used"
    # unverified accounts never receive one
    u = client()
    register(u, email="pending@example.test", phone="01612345678")
    # maya + other (both verified) hold one each; the pending account holds none
    assert run(env["db"].promotions.count_documents({"kind": "welcome_issued"})) == 2
    pending = run(env["db"].customer_accounts.find_one({"email": "pending@example.test"}))
    assert run(env["db"].promotions.count_documents({"customer_account_ids": pending["id"]})) == 0


# ---------------------------------------------------------------------------
# Admin customer accounts
# ---------------------------------------------------------------------------
def test_admin_customer_accounts_view_and_suspend(env):
    a = verified_client()
    acct_id = a.get("/api/account/me").json()["id"]
    c = client()
    lst = c.get("/api/admin/customer-accounts?method=password", headers=admin_h(env, "order_manager")).json()
    assert lst[0]["email"] == "maya@example.test" and lst[0]["login_methods"] == ["password"]
    detail = c.get(f"/api/admin/customer-accounts/{acct_id}", headers=admin_h(env, "order_manager")).json()
    text = str(detail)
    assert "password_hash" not in text and "token_hash" not in text and detail["active_sessions"] == 1
    assert c.get("/api/admin/customer-accounts", headers=admin_h(env, "product_manager")).status_code == 403
    assert c.post(f"/api/admin/customer-accounts/{acct_id}/suspend", headers=admin_h(env, "order_manager"), json={}).status_code == 403
    assert c.post(f"/api/admin/customer-accounts/{acct_id}/suspend", headers=admin_h(env, "admin"), json={"reason": "test"}).json()["sessions_revoked"] == 1
    assert a.get("/api/account/me").status_code == 401
    r = client().post("/api/customer/login", headers=CSRF, json={"email": "maya@example.test", "password": PW})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "unavailable"
    assert c.post(f"/api/admin/customer-accounts/{acct_id}/reactivate", headers=admin_h(env), json={}).json()["status"] == "active"


# ---------------------------------------------------------------------------
# Email engine
# ---------------------------------------------------------------------------
def test_email_not_configured_is_never_reported_as_sent(env, monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "resend")
    res = run(emailer.send("verify_email", "verify_email", "a@example.test", {"name": "A", "url": "https://x/y", "expires_hours": 24}))
    assert res["status"] == "not_configured"
    log = run(env["db"].email_logs.find_one({"id": res["log_id"]}))
    assert log["to_masked"] == "a***@example.test" and "https://x/y" not in str(log)


def test_email_capture_refused_in_production(env, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    assert emailer.email_mode() == "resend"


def test_email_dedupe_and_retry_after_failure(env, monkeypatch):
    ctx = {"name": "A", "url": "https://x/y", "expires_hours": 24}
    assert run(emailer.send("e", "verify_email", "a@example.test", ctx, dedupe_key="k1"))["status"] == "sent"
    assert run(emailer.send("e", "verify_email", "a@example.test", ctx, dedupe_key="k1"))["status"] == "duplicate"
    monkeypatch.setenv("EMAIL_MODE", "resend")
    assert run(emailer.send("e", "verify_email", "a@example.test", ctx, dedupe_key="k2"))["status"] == "not_configured"
    monkeypatch.setenv("EMAIL_MODE", "capture")
    assert run(emailer.send("e", "verify_email", "a@example.test", ctx, dedupe_key="k2"))["status"] == "sent"


def test_resend_client_handles_errors_without_leaking(env, monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_not_a_real_key_000000")
    calls = []

    class Resp:
        def __init__(self, code, body):
            self.status_code, self._b = code, body

        def json(self):
            return self._b

    class Cli:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json, headers):
            calls.append((json, headers))
            return Resp(503, {}) if len(calls) == 1 else Resp(200, {"id": "msg-123"})
    monkeypatch.setattr(emailer.httpx, "AsyncClient", Cli)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(emailer.asyncio, "sleep", lambda s: real_sleep(0))
    res = run(emailer.send("e", "password_reset", "a@example.test", {"name": "A", "url": "https://x/r", "expires_minutes": 15}))
    log = run(env["db"].email_logs.find_one({"id": res["log_id"]}))
    assert res["status"] == "sent" and log["provider_id"] == "msg-123" and log["attempts"] == 2
    payload, headers = calls[-1]
    assert payload["from"] == "AAYNA Accounts <accounts@shopaayna.com>" and payload["reply_to"] == "shopaayna.bd@gmail.com"
    assert payload["text"] and payload["html"] and "re_test" not in str(log)


def test_templates_escape_and_render(env):
    evil = "<script>alert(1)</script>"
    for t, ctx in (("verify_email", {"name": evil, "url": "https://x", "expires_hours": 24}),
                   ("password_reset", {"name": evil, "url": "https://x", "expires_minutes": 15}),
                   ("password_changed", {"name": evil, "url": "https://x"}),
                   ("account_exists", {"google_only": True, "url": "https://x"}),
                   ("email_change", {"name": evil, "url": "https://x", "expires_hours": 24}),
                   ("order_claim", {"name": evil, "url": "https://x", "order_number": "ORD-1", "expires_hours": 24}),
                   ("order_confirmation", {"name": evil, "url": "https://x", "order": {
                       "order_number": "ORD-1", "items": [{"product_name_snapshot": evil, "quantity": 1, "total_price": 10}],
                       "subtotal": 10, "delivery_charge": 80, "discount_amount": 1, "coupon_code": "X", "total_amount": 89,
                       "payment_method": "Cash on Delivery"}}),
                   ("order_status", {"name": evil, "url": "https://x", "label": "Delivered", "order": {"order_number": "ORD-1", "courier_name": "Pathao"}})):
        m = emailer.render(t, ctx)
        assert "<script>" not in m["html"] and m["text"] and m["subject"]

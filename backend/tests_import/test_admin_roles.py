"""
Offline security tests for the admin API: authentication, session invalidation,
role-based authorization, private-field redaction, SKU identity, stock workflow,
category/settings validation and production-safe admin seeding.

mongomock-motor + FastAPI TestClient. No network, fake users and fixtures only.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest

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
import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROLES = ("super_admin", "admin", "product_manager", "order_manager")
PRIVATE = ("cost_price", "internal_notes", "pricing", "price_history", "previous_selling_price", "source")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def env(monkeypatch):
    db = dbmod.db
    for m in (auth, admin_routes, server):
        monkeypatch.setattr(m, "db", db)
    auth._failed_logins.clear()

    async def seed():
        for c in ("users", "products", "categories", "inventory_logs", "orders", "customers", "website_settings"):
            await db[c].delete_many({})
        users = {}
        for r in ROLES:
            u = {"id": f"u-{r}", "email": f"{r}@example.test", "name": r, "role": r, "status": "active",
                 "password_hash": auth.hash_password(f"pw-{r}-long-enough")}
            await db.users.insert_one(dict(u))
            users[r] = u
        await db.users.insert_one({"id": "u-off", "email": "off@example.test", "role": "admin", "status": "inactive",
                                   "password_hash": auth.hash_password("pw-off-long-enough")})
        await db.categories.insert_many([
            {"id": "c1", "name": "Earrings", "slug": "earrings", "status": "active", "sort_order": 1},
            {"id": "c2", "name": "Rings", "slug": "rings", "status": "active", "sort_order": 2}])
        await db.products.insert_one({
            "id": "p1", "sku": "AYN-TST-001", "slug": "test-ring", "product_name": "Test Ring", "category_slug": "rings",
            "category_name": "Rings", "selling_price": 1290, "discount_price": None, "cost_price": 111.0,
            "internal_notes": "private", "pricing": {"rule": "x"}, "source": {"type": "inventory_xlsx"},
            "stock_quantity": 5, "low_stock_alert": 3, "status": "draft", "images": [],
            "created_at": "2026-10-18T00:00:00+00:00"})
        return users
    users = run(seed())
    client = TestClient(server.app)
    tok = {r: auth.create_access_token(u) for r, u in users.items()}
    return {"c": client, "db": db, "tok": tok, "users": users}


def H(env, role):
    return {"Authorization": f"Bearer {env['tok'][role]}"}


# ---------------------------------------------------------------- authentication
def test_unauthenticated_and_bad_tokens_get_401(env):
    c = env["c"]
    for path in ("/api/admin/products", "/api/admin/orders", "/api/admin/dashboard", "/api/admin/settings", "/api/admin/me"):
        assert c.get(path).status_code == 401
    assert c.get("/api/admin/products", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    forged = jwt.encode({"sub": "u-super_admin", "role": "super_admin", "type": "access",
                         "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-secret-0000000000000000000000", "HS256")
    assert c.get("/api/admin/products", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    expired = jwt.encode({"sub": "u-super_admin", "type": "access", "sv": 0,
                          "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, auth.get_jwt_secret(), "HS256")
    r = c.get("/api/admin/products", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()
    # token in the URL is never accepted
    assert c.get(f"/api/admin/products?token={env['tok']['super_admin']}").status_code == 401


def test_token_lifetime_is_short():
    t = auth.create_access_token({"id": "x", "email": "x@example.test", "role": "admin"})
    exp = jwt.decode(t, auth.get_jwt_secret(), algorithms=["HS256"])["exp"]
    assert exp - datetime.now(timezone.utc).timestamp() <= 12 * 3600 + 5


def test_login_errors_are_generic_and_rate_limited(env):
    c = env["c"]
    unknown = c.post("/api/admin/login", json={"email": "nobody@example.test", "password": "whatever-123456"})
    wrong = c.post("/api/admin/login", json={"email": "admin@example.test", "password": "wrong-password-1"})
    inactive = c.post("/api/admin/login", json={"email": "off@example.test", "password": "pw-off-long-enough"})
    assert unknown.status_code == wrong.status_code == inactive.status_code == 401
    assert unknown.json() == wrong.json() == inactive.json()
    ok = c.post("/api/admin/login", json={"email": "ADMIN@example.test ", "password": "pw-admin-long-enough"})
    assert ok.status_code == 200 and "password_hash" not in ok.text and ok.json()["user"]["role"] == "admin"
    assert "products.cost" in ok.json()["user"]["permissions"]
    for _ in range(5):
        c.post("/api/admin/login", json={"email": "product_manager@example.test", "password": "bad-guess-000"})
    locked = c.post("/api/admin/login", json={"email": "product_manager@example.test", "password": "pw-product_manager-long-enough"})
    assert locked.status_code == 429


def test_logout_invalidates_existing_tokens(env):
    c = env["c"]
    h = H(env, "admin")
    assert c.get("/api/admin/me", headers=h).status_code == 200
    assert c.post("/api/admin/logout", headers=h).status_code == 200
    assert c.get("/api/admin/me", headers=h).status_code == 401
    # a fresh login works again
    r = c.post("/api/admin/login", json={"email": "admin@example.test", "password": "pw-admin-long-enough"})
    assert c.get("/api/admin/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 200


def test_disabled_account_token_rejected(env):
    run(env["db"].users.update_one({"id": "u-admin"}, {"$set": {"status": "inactive"}}))
    assert env["c"].get("/api/admin/me", headers=H(env, "admin")).status_code == 401


# ---------------------------------------------------------------- authorization matrix
MATRIX = [
    # (method, path, json, allowed roles)
    ("get", "/api/admin/products", None, set(ROLES)),
    ("get", "/api/admin/orders", None, {"super_admin", "admin", "order_manager"}),
    ("get", "/api/admin/customers", None, {"super_admin", "admin", "order_manager"}),
    ("get", "/api/admin/settings", None, {"super_admin", "admin"}),
    ("put", "/api/admin/settings", {"store_name": "AAYNA"}, {"super_admin", "admin"}),
    ("get", "/api/admin/export/products", None, {"super_admin", "admin"}),
    ("get", "/api/admin/export/orders", None, {"super_admin", "admin", "order_manager"}),
    ("put", "/api/admin/products/p1", {"product_name": "Test Ring"}, {"super_admin", "admin", "product_manager"}),
    ("post", "/api/admin/categories", {"name": "Anklets"}, {"super_admin", "admin", "product_manager"}),
    ("post", "/api/admin/inventory/p1/adjust", {"change_type": "stock_in", "quantity_change": 1, "reason": "count"},
     {"super_admin", "admin", "product_manager"}),
    ("get", "/api/admin/inventory", None, set(ROLES)),
]


@pytest.mark.parametrize("method,path,body,allowed", MATRIX)
def test_role_matrix(env, method, path, body, allowed):
    for role in ROLES:
        if path.endswith("/categories") and role in allowed:
            body = {"name": f"Anklets {role}"}
        r = getattr(env["c"], method)(path, headers=H(env, role), **({"json": body} if body is not None else {}))
        if role in allowed:
            assert r.status_code in (200, 201), (role, path, r.status_code, r.text)
        else:
            assert r.status_code == 403, (role, path, r.status_code)


def test_delete_product_only_super_admin_and_admin(env):
    for role in ("product_manager", "order_manager"):
        assert env["c"].delete("/api/admin/products/p1", headers=H(env, role)).status_code == 403
    assert run(env["db"].products.count_documents({"id": "p1"})) == 1


def test_private_fields_only_for_super_admin_and_admin(env):
    c = env["c"]
    for role in ROLES:
        lst = c.get("/api/admin/products", headers=H(env, role)).json()
        one = c.get("/api/admin/products/p1", headers=H(env, role)).json()
        inv = c.get("/api/admin/inventory", headers=H(env, role)).json()
        visible = role in ("super_admin", "admin")
        for doc in (lst[0], one):
            assert ("cost_price" in doc) == visible, role
            if not visible:
                assert not any(f in doc for f in PRIVATE), role
        assert all("cost_price" not in p for p in inv)


def test_product_manager_cannot_change_cost(env):
    c = env["c"]
    r = c.put("/api/admin/products/p1", headers=H(env, "product_manager"), json={"cost_price": 1})
    assert r.status_code == 403
    r = c.put("/api/admin/products/p1", headers=H(env, "product_manager"), json={"selling_price": 1300})
    assert r.status_code == 200 and "cost_price" not in r.json()
    p = run(env["db"].products.find_one({"id": "p1"}))
    assert p["cost_price"] == 111.0 and p["selling_price"] == 1300


# ---------------------------------------------------------------- products, stock, categories, settings
def test_sku_is_immutable_and_unique(env):
    c, h = env["c"], H(env, "admin")
    assert c.put("/api/admin/products/p1", headers=h, json={"sku": "CHANGED"}).status_code == 400
    assert c.put("/api/admin/products/p1", headers=h, json={"sku": "AYN-TST-001", "product_name": "Renamed"}).status_code == 200
    dup = c.post("/api/admin/products", headers=h, json={"product_name": "X", "sku": "AYN-TST-001", "category_slug": "rings",
                                                           "selling_price": 10, "stock_quantity": 1})
    assert dup.status_code == 409
    assert run(env["db"].products.find_one({"id": "p1"}))["sku"] == "AYN-TST-001"


def test_new_product_defaults_to_draft(env):
    r = env["c"].post("/api/admin/products", headers=H(env, "product_manager"),
                      json={"product_name": "New", "sku": "AYN-NEW-1", "category_slug": "rings", "selling_price": 10,
                            "stock_quantity": 2})
    assert r.status_code == 200 and r.json()["status"] == "draft"
    assert env["c"].get(f"/api/products/{r.json()['slug']}").status_code == 404


def test_stock_adjustment_rules(env):
    c, h = env["c"], H(env, "product_manager")
    url = "/api/admin/inventory/p1/adjust"
    assert c.post(url, headers=h, json={"change_type": "damage", "quantity_change": -6, "reason": "broken"}).status_code == 400
    assert c.post(url, headers=h, json={"change_type": "stock_in", "quantity_change": 0, "reason": "x"}).status_code == 400
    assert c.post(url, headers=h, json={"change_type": "stock_in", "quantity_change": 2, "reason": " "}).status_code == 400
    assert c.post(url, headers=h, json={"change_type": "teleport", "quantity_change": 2, "reason": "x"}).status_code == 400
    ok = c.post(url, headers=h, json={"change_type": "damage", "quantity_change": -5, "reason": "count correction"})
    assert ok.status_code == 200 and ok.json() == {"stock_quantity": 0, "status": "draft"}  # draft never published
    logs = c.get("/api/admin/inventory/p1/logs", headers=h).json()
    assert logs[0]["created_by"] == "product_manager@example.test" and logs[0]["reason"] == "count correction"
    assert logs[0]["previous_stock"] == 5 and logs[0]["new_stock"] == 0


def test_category_validation(env):
    c, h = env["c"], H(env, "admin")
    assert c.post("/api/admin/categories", headers=h, json={"name": "  "}).status_code == 400
    assert c.post("/api/admin/categories", headers=h, json={"name": "earrings"}).status_code == 409
    assert c.post("/api/admin/categories", headers=h, json={"name": "New", "slug": "rings"}).status_code == 409
    assert c.put("/api/admin/categories/c1", headers=h, json={"slug": "ear"}).status_code == 400
    assert c.put("/api/admin/categories/c1", headers=h, json={"name": "Rings"}).status_code == 409
    assert c.put("/api/admin/categories/c1", headers=h, json={"status": "deleted"}).status_code == 400
    assert c.put("/api/admin/categories/c1", headers=h, json={"name": "Earrings & Studs"}).status_code == 200


def test_settings_reject_secret_like_keys(env):
    c, h = env["c"], H(env, "super_admin")
    for key in ("jwt_secret", "mongo_url", "admin_password", "api_key", "Bad Key"):
        assert c.put("/api/admin/settings", headers=h, json={key: "x"}).status_code == 400
    assert c.put("/api/admin/settings", headers=h, json={"store_name": "AAYNA"}).status_code == 200


def test_public_api_never_returns_private_fields(env):
    run(env["db"].products.update_one({"id": "p1"}, {"$set": {"status": "active"}}))
    body = env["c"].get("/api/products/test-ring").text
    for f in PRIVATE:
        assert f'"{f}"' not in body


# ---------------------------------------------------------------- production seeding
def test_production_seed_never_overwrites_or_duplicates_admin(env, monkeypatch):
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    before = run(env["db"].users.find_one({"id": "u-super_admin"}))["password_hash"]
    monkeypatch.setenv("ADMIN_EMAIL", "super_admin@example.test")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-completely-different-password")
    run(auth.seed_admin())
    assert run(env["db"].users.find_one({"id": "u-super_admin"}))["password_hash"] == before
    monkeypatch.setenv("ADMIN_EMAIL", "someone-new@example.test")
    n = run(env["db"].users.count_documents({}))
    run(auth.seed_admin())
    assert run(env["db"].users.count_documents({})) == n  # an admin exists: no second account


def test_production_config_requires_jwt_but_not_admin_password(monkeypatch):
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    for k in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "ORDER_WEBHOOK_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("DB_NAME", "aayna_prod")
    monkeypatch.setenv("MONGO_URL", "mongodb+srv://user:pw@cluster.example.test/")
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://aayna-admin.example.test")
    monkeypatch.setenv("CORS_ORIGINS", "https://aayna-admin.example.test")
    auth.validate_security_config()
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


# --- preview-only admin bootstrap (PREVIEW_ADMIN_BOOTSTRAP) -------------------------------
def _preview_env(monkeypatch, mode="sync", db_name="aayna_preview", site="https://aayna-webapp-git-x-go2-grocer.vercel.app",
                 email=" Preview.Admin@Example.test ", pw="preview-admin-password-1 \n"):
    monkeypatch.setenv("PREVIEW_ADMIN_BOOTSTRAP", mode)
    monkeypatch.setenv("DB_NAME", db_name)
    monkeypatch.setenv("PUBLIC_SITE_URL", site)
    monkeypatch.setenv("ADMIN_EMAIL", email)
    monkeypatch.setenv("ADMIN_PASSWORD", pw)


@pytest.mark.parametrize("db_name,site", [("aayna_prod", "https://aayna-webapp-git-x-go2-grocer.vercel.app"),
                                          ("aayna_preview", "https://shopaayna.com"), ("aayna_dev", "https://x.vercel.app")])
def test_preview_bootstrap_refuses_outside_the_preview(env, monkeypatch, db_name, site):
    _preview_env(monkeypatch, db_name=db_name, site=site)
    before = run(env["db"].users.count_documents({}))
    assert run(auth.preview_admin_bootstrap()) == {"refused": True}
    assert run(env["db"].users.count_documents({})) == before


def test_preview_bootstrap_off_by_default(env, monkeypatch):
    monkeypatch.delenv("PREVIEW_ADMIN_BOOTSTRAP", raising=False)
    assert run(auth.preview_admin_bootstrap()) is None


def test_preview_bootstrap_check_changes_nothing_and_reports_whitespace(env, monkeypatch):
    _preview_env(monkeypatch, mode="check")
    r = run(auth.preview_admin_bootstrap())
    assert r["account_exists"] is False and r["action"] == "none" and r["password_has_outer_whitespace"] is True
    assert run(env["db"].users.find_one({"email": "preview.admin@example.test"})) is None


def test_preview_bootstrap_sync_creates_once_and_repairs(env, monkeypatch):
    _preview_env(monkeypatch)
    sa = run(env["db"].users.find_one({"role": "super_admin"}))
    r1 = run(auth.preview_admin_bootstrap())
    assert r1["action"] == "created"
    r2 = run(auth.preview_admin_bootstrap())
    assert r2["action"] == "none" and r2["password_verifies_trimmed"] is True
    assert run(env["db"].users.count_documents({"email": "preview.admin@example.test"})) == 1
    # trimmed password signs in through the real login endpoint
    ok = env["c"].post("/api/admin/login", json={"email": "preview.admin@example.test", "password": "preview-admin-password-1"})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "super_admin"
    # broken hash + disabled -> repaired, old sessions signed out
    run(env["db"].users.update_one({"email": "preview.admin@example.test"}, {"$set": {"password_hash": auth.hash_password("something-else-1234"), "status": "inactive"}}))
    r3 = run(auth.preview_admin_bootstrap())
    u = run(env["db"].users.find_one({"email": "preview.admin@example.test"}))
    assert r3["action"] == "reset" and u["status"] == "active" and u.get("session_version") == 1
    # other accounts are never touched
    assert run(env["db"].users.find_one({"id": sa["id"]}))["password_hash"] == sa["password_hash"]
    assert "preview-admin-password" not in str(r3)

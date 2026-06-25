"""Milestone 4A — health endpoint + production config validation tests."""
import pytest
from fastapi.testclient import TestClient

import auth
import server

client = TestClient(server.app)


# ---------------- /api/health ----------------
def test_health_returns_safe_status():
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["app"] == "aayna"
    assert "environment" in d
    # only these three keys — nothing else
    assert set(d.keys()) == {"status", "app", "environment"}


def test_health_does_not_leak_secrets():
    raw = client.get("/api/health").text.lower()
    for bad in ["jwt", "secret", "password", "mongodb://", "mongo_url",
                "webhook", "admin@", "sk-emergent", "token"]:
        assert bad not in raw, f"health endpoint leaked {bad}"


# ---------------- production config validation ----------------
SAFE_PROD = {
    "JWT_SECRET": "x" * 48,
    "ADMIN_EMAIL": "owner@aayna.com.bd",
    "ADMIN_PASSWORD": "Str0ng-Launch-Pass!",
    "PUBLIC_SITE_URL": "https://www.aayna.com.bd",
    "CORS_ORIGINS": "https://www.aayna.com.bd",
    "ORDER_WEBHOOK_ENABLED": "false",
    "ORDER_WEBHOOK_URL": "",
}


def _prod_env(monkeypatch, **overrides):
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    env = {**SAFE_PROD, **overrides}
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_prod_valid_config_passes(monkeypatch):
    _prod_env(monkeypatch)
    auth.validate_security_config()  # must not raise


def test_prod_rejects_default_admin_password(monkeypatch):
    _prod_env(monkeypatch, ADMIN_PASSWORD="ChangeMe123!")
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


def test_prod_rejects_default_jwt_secret(monkeypatch):
    _prod_env(monkeypatch, JWT_SECRET="dev-only-insecure-secret-do-not-use-in-production")
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


def test_prod_rejects_localhost_public_site_url(monkeypatch):
    _prod_env(monkeypatch, PUBLIC_SITE_URL="http://localhost:3000")
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


def test_prod_rejects_empty_public_site_url(monkeypatch):
    _prod_env(monkeypatch, PUBLIC_SITE_URL="")
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


def test_prod_rejects_open_cors(monkeypatch):
    _prod_env(monkeypatch, CORS_ORIGINS="*")
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


def test_prod_webhook_enabled_requires_url(monkeypatch):
    _prod_env(monkeypatch, ORDER_WEBHOOK_ENABLED="true", ORDER_WEBHOOK_URL="")
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


def test_prod_webhook_enabled_with_url_ok(monkeypatch):
    _prod_env(monkeypatch, ORDER_WEBHOOK_ENABLED="true",
              ORDER_WEBHOOK_URL="https://hooks.example.com/aayna")
    auth.validate_security_config()  # must not raise


def test_dev_skips_validation(monkeypatch):
    monkeypatch.setattr(auth, "IS_PRODUCTION", False)
    monkeypatch.delenv("PUBLIC_SITE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    auth.validate_security_config()  # must not raise in development

"""Offline tests: production refuses weak JWT secrets and admin passwords."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://mock")
os.environ.setdefault("DB_NAME", "aayna_import_test")

import auth  # noqa: E402

PROD = {"JWT_SECRET": "k" * 64, "ADMIN_EMAIL": "owner@example.test", "ADMIN_PASSWORD": "Very-Strong-Pass-123!",
        "PUBLIC_SITE_URL": "https://shop.example.test", "CORS_ORIGINS": "https://shop.example.test",
        "ORDER_WEBHOOK_ENABLED": "false", "DB_NAME": "aayna_prod",
        "MONGO_URL": "mongodb+srv://u:p@cluster.example.mongodb.net"}


def _prod(monkeypatch, **kw):
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    for k, v in {**PROD, **kw}.items():
        monkeypatch.setenv(k, v)


def test_strong_values_accepted(monkeypatch):
    _prod(monkeypatch)
    auth.validate_security_config()


@pytest.mark.parametrize("kw", [{"JWT_SECRET": "abc"}, {"JWT_SECRET": "x" * 31},
                                {"ADMIN_PASSWORD": "123"}, {"ADMIN_PASSWORD": "password"}, {"ADMIN_PASSWORD": "x" * 11}])
def test_weak_values_refused(monkeypatch, kw):
    _prod(monkeypatch, **kw)
    with pytest.raises(RuntimeError):
        auth.validate_security_config()


def test_minimums_not_applied_outside_production(monkeypatch):
    monkeypatch.setattr(auth, "IS_PRODUCTION", False)
    monkeypatch.setenv("JWT_SECRET", "abc")
    auth.validate_security_config()

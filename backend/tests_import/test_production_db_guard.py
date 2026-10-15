"""Offline tests: production must refuse a dev/test database or a localhost MONGO_URL.

The DB-guard tests from commit 1340203 on feat/aayna-real-inventory-v1, without
that commit's S3/R2 storage test (storage provider is not chosen yet).
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://mock")
os.environ.setdefault("DB_NAME", "aayna_import_test")

import auth  # noqa: E402

PROD = {"JWT_SECRET": "x" * 48, "ADMIN_EMAIL": "owner@example.test", "ADMIN_PASSWORD": "Str0ng-Test-Pass!",
        "PUBLIC_SITE_URL": "https://shop.example.test", "CORS_ORIGINS": "https://shop.example.test",
        "ORDER_WEBHOOK_ENABLED": "false", "DB_NAME": "aayna_prod",
        "MONGO_URL": "mongodb+srv://u:p@cluster.example.mongodb.net"}


def _prod(monkeypatch, **kw):
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    for k, v in {**PROD, **kw}.items():
        monkeypatch.setenv(k, v)


def test_prod_accepts_aayna_prod(monkeypatch):
    _prod(monkeypatch)
    auth.validate_security_config()


@pytest.mark.parametrize("kw", [{"DB_NAME": "aayna_dev"}, {"DB_NAME": "aayna_pytest"}, {"DB_NAME": ""},
                                {"MONGO_URL": "mongodb://localhost:27017"}])
def test_prod_refuses_dev_or_local_db(monkeypatch, kw):
    _prod(monkeypatch, **kw)
    with pytest.raises(RuntimeError):
        auth.validate_security_config()

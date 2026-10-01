"""Offline tests: production DB guard and S3-compatible (R2) storage backend."""
import importlib
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


class FakeS3:
    def __init__(self):
        self.store = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.store[(Bucket, Key)] = (Body, ContentType)

    def get_object(self, Bucket, Key):
        import io
        body, ct = self.store[(Bucket, Key)]
        return {"Body": io.BytesIO(body), "ContentType": ct}


def test_s3_backend_selected_and_roundtrips(monkeypatch):
    for k, v in {"OBJECT_STORAGE_BUCKET": "aayna-product-images", "OBJECT_STORAGE_ENDPOINT": "https://acct.r2.example",
                 "OBJECT_STORAGE_ACCESS_KEY": "a", "OBJECT_STORAGE_SECRET_KEY": "b"}.items():
        monkeypatch.setenv(k, v)
    import storage
    storage = importlib.reload(storage)
    assert storage.storage_backend() == "s3"
    fake = FakeS3()
    monkeypatch.setattr(storage, "_s3_client", fake)
    assert storage.put_object("aayna/uploads/x.webp", b"img", "image/webp") == {"path": "aayna/uploads/x.webp", "size": 3}
    assert storage.get_object("aayna/uploads/x.webp") == (b"img", "image/webp")
    for k in ("OBJECT_STORAGE_BUCKET", "OBJECT_STORAGE_ENDPOINT", "OBJECT_STORAGE_ACCESS_KEY", "OBJECT_STORAGE_SECRET_KEY",
              "EMERGENT_LLM_KEY"):
        monkeypatch.delenv(k, raising=False)
    storage = importlib.reload(storage)
    assert storage.storage_backend() == "none"

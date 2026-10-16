"""Offline tests: storage is skipped entirely when EMERGENT_LLM_KEY is empty (no network),
configured uploads still work, and ensure_indexes keeps stricter unique indexes."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "aayna_pytest")

import storage  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class NoNetwork:
    calls = 0

    def __call__(self, *a, **k):
        NoNetwork.calls += 1
        raise AssertionError(f"network call made: {a[:1]}")


class FakeFiles:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def find_one(self, q):
        return next((d for d in self.docs if d["storage_path"] == q["storage_path"]), None)


class FakeDB:
    def __init__(self):
        self.files = FakeFiles()


def make_app(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(storage, "db", fake)
    app = FastAPI()
    app.include_router(storage.storage_router)
    app.include_router(storage.files_router)
    app.dependency_overrides[storage.get_current_admin] = lambda: {"email": "qa@example.test"}
    return TestClient(app), fake


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setenv("EMERGENT_LLM_KEY", "")
    monkeypatch.setattr(storage, "_storage_key", None)
    NoNetwork.calls = 0
    for verb in ("post", "get", "put"):
        monkeypatch.setattr(storage.requests, verb, NoNetwork())


def test_startup_makes_no_network_call_when_disabled(disabled, caplog):
    caplog.set_level("INFO", logger="aayna.storage")
    storage.init_storage_safe()
    assert NoNetwork.calls == 0
    assert "disabled" in caplog.text and "failed" not in caplog.text.lower()


def test_init_storage_raises_without_network_when_disabled(disabled):
    with pytest.raises(storage.StorageDisabled):
        storage.init_storage()
    assert NoNetwork.calls == 0


@pytest.mark.parametrize("value", ["", "   ", None])
def test_blank_or_missing_key_counts_as_disabled(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    else:
        monkeypatch.setenv("EMERGENT_LLM_KEY", value)
    assert storage.storage_enabled() is False


def test_upload_returns_503_without_network_when_disabled(disabled, monkeypatch):
    client, fake = make_app(monkeypatch)
    r = client.post("/api/admin/upload", files={"file": ("a.jpg", b"\xff\xd8data", "image/jpeg")})
    assert r.status_code == 503 and "not configured" in r.json()["detail"]
    assert NoNetwork.calls == 0 and fake.files.docs == []


def test_serve_file_404_without_network_when_disabled(disabled, monkeypatch):
    client, fake = make_app(monkeypatch)
    fake.files.docs.append({"storage_path": "aayna/uploads/x.jpg", "is_deleted": False})
    assert client.get("/api/files/aayna/uploads/x.jpg").status_code == 404
    assert NoNetwork.calls == 0


def test_configured_upload_and_serve_still_work(monkeypatch):
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-not-real")
    monkeypatch.setattr(storage, "_storage_key", None)
    seen = []

    class Resp:
        def __init__(self, payload=None, content=b"", status=200):
            self.payload, self.content, self.status_code = payload, content, status
            self.headers = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    monkeypatch.setattr(storage.requests, "post", lambda url, **k: seen.append(("init", k["json"])) or Resp({"storage_key": "sk"}))
    monkeypatch.setattr(storage.requests, "put", lambda url, **k: seen.append(("put", url)) or Resp({"path": url.split("/objects/")[1], "size": 6}))
    monkeypatch.setattr(storage.requests, "get", lambda url, **k: Resp(content=b"IMGDATA"))
    client, fake = make_app(monkeypatch)
    r = client.post("/api/admin/upload", files={"file": ("a.jpg", b"\xff\xd8data", "image/jpeg")})
    assert r.status_code == 200, r.text
    path = r.json()["path"]
    assert seen[0] == ("init", {"emergent_key": "sk-test-not-real"}) and seen[1][0] == "put"
    assert fake.files.docs[0]["storage_path"] == path
    got = client.get(f"/api/files/{path}")
    assert got.status_code == 200 and got.content == b"IMGDATA"


def test_ensure_indexes_keeps_unique_indexes_and_creates_missing(monkeypatch):
    mongomock_motor = pytest.importorskip("mongomock_motor")
    import auth  # noqa: E402
    db = mongomock_motor.AsyncMongoMockClient()["aayna_pytest"]
    monkeypatch.setattr(auth, "db", db)

    async def go():
        await db.customers.create_index("phone", unique=True)
        await db.orders.create_index("order_number", unique=True)
        await auth.ensure_indexes()
        await auth.ensure_indexes()          # idempotent
        return (await db.customers.index_information(), await db.orders.index_information(),
                await db.products.index_information(), await db.users.index_information())

    cust, orders, products, users = asyncio.run(go())
    assert cust["phone_1"].get("unique") is True
    assert orders["order_number_1"].get("unique") is True
    assert "slug_1" in products
    assert users["email_1"].get("unique") is True

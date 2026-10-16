"""Offline tests: which address the login lockout is keyed on (auth._client_ip)."""
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://mock")
os.environ.setdefault("DB_NAME", "aayna_import_test")

import auth  # noqa: E402


def req(xff=None, peer="10.0.0.5"):
    headers = {"X-Forwarded-For": xff} if xff else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_no_trusted_proxy_ignores_forwarded_header(monkeypatch):
    monkeypatch.setattr(auth, "TRUSTED_PROXY_HOPS", 0)
    assert auth._client_ip(req("203.0.113.9")) == "10.0.0.5"
    assert auth._client_ip(req("1.1.1.1, 2.2.2.2")) == "10.0.0.5"


def test_one_trusted_proxy_uses_the_address_it_appended(monkeypatch):
    monkeypatch.setattr(auth, "TRUSTED_PROXY_HOPS", 1)
    # client spoofed "203.0.113.9"; the proxy appended the real client 198.51.100.7
    assert auth._client_ip(req("203.0.113.9, 198.51.100.7")) == "198.51.100.7"
    assert auth._client_ip(req("198.51.100.7")) == "198.51.100.7"


def test_two_trusted_proxies(monkeypatch):
    monkeypatch.setattr(auth, "TRUSTED_PROXY_HOPS", 2)
    assert auth._client_ip(req("spoof, 198.51.100.7, 10.1.1.1")) == "198.51.100.7"


def test_missing_header_falls_back_to_peer(monkeypatch):
    monkeypatch.setattr(auth, "TRUSTED_PROXY_HOPS", 1)
    assert auth._client_ip(req(None)) == "10.0.0.5"

"""Milestone 3G — SEO indexing tests (dynamic sitemap.xml + robots.txt).

Live HTTP tests hit the running backend under /api. Unit tests exercise the
robots renderer + PUBLIC_SITE_URL helper directly via monkeypatch.
"""
import os
import re

import requests
import server

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


def _sitemap_base():
    """Derive the configured public base from the robots.txt Sitemap line."""
    r = requests.get(f"{API}/robots.txt", timeout=30)
    m = re.search(r"^Sitemap:\s*(\S+?)/sitemap\.xml", r.text, re.MULTILINE)
    assert m, "robots.txt must declare a Sitemap URL"
    return m.group(1)


# ---------------- robots.txt ----------------
class TestRobots:
    def test_robots_200_and_type(self):
        r = requests.get(f"{API}/robots.txt", timeout=30)
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")

    def test_robots_disallows_admin(self):
        body = requests.get(f"{API}/robots.txt", timeout=30).text
        assert "Disallow: /admin" in body
        assert "Disallow: /api/admin" in body

    def test_robots_allows_storefront_and_has_sitemap(self):
        body = requests.get(f"{API}/robots.txt", timeout=30).text
        assert "Allow: /" in body
        assert re.search(r"^Sitemap:\s*\S+/sitemap\.xml", body, re.MULTILINE)


# ---------------- sitemap.xml ----------------
class TestSitemap:
    def test_sitemap_200_and_xml(self):
        r = requests.get(f"{API}/sitemap.xml", timeout=30)
        assert r.status_code == 200
        assert "xml" in r.headers.get("content-type", "")
        assert r.text.strip().startswith("<?xml")
        assert "<urlset" in r.text

    def test_sitemap_includes_public_pages(self):
        base = _sitemap_base()
        body = requests.get(f"{API}/sitemap.xml", timeout=30).text
        for path in ["/", "/shop", "/contact", "/track-order",
                     "/delivery-policy", "/returns", "/privacy", "/terms"]:
            assert f"<loc>{base}{path}</loc>" in body, f"missing {path}"

    def test_sitemap_includes_active_categories_and_products(self):
        base = _sitemap_base()
        body = requests.get(f"{API}/sitemap.xml", timeout=30).text
        cats = requests.get(f"{API}/categories", timeout=30).json()
        prods = requests.get(f"{API}/products", timeout=30).json()
        assert cats and prods
        assert f"{base}/category/{cats[0]['slug']}" in body
        assert f"{base}/product/{prods[0]['slug']}" in body

    def test_sitemap_excludes_private_routes(self):
        body = requests.get(f"{API}/sitemap.xml", timeout=30).text
        for bad in ["/admin", "/cart", "/checkout", "/order-confirmation", "/api/", "/auth"]:
            assert bad not in body, f"sitemap must not expose {bad}"

    def test_sitemap_uses_public_site_url(self):
        base = _sitemap_base()
        body = requests.get(f"{API}/sitemap.xml", timeout=30).text
        locs = re.findall(r"<loc>(.*?)</loc>", body)
        assert locs
        for loc in locs:
            assert loc.startswith(base), f"{loc} does not use configured PUBLIC_SITE_URL {base}"

    def test_sitemap_is_valid_xml(self):
        import xml.etree.ElementTree as ET
        body = requests.get(f"{API}/sitemap.xml", timeout=30).text
        root = ET.fromstring(body)  # raises on invalid XML
        assert root.tag.endswith("urlset")

    def test_sitemap_has_lastmod_for_products(self):
        body = requests.get(f"{API}/sitemap.xml", timeout=30).text
        prods = requests.get(f"{API}/products", timeout=30).json()
        base = _sitemap_base()
        # at least one product entry should carry a <lastmod> (updated_at exists in seed)
        assert "<lastmod>" in body
        slug = prods[0]["slug"]
        block = re.search(
            rf"<url><loc>{re.escape(base)}/product/{re.escape(slug)}</loc>(.*?)</url>", body
        )
        assert block and "<lastmod>" in block.group(1)


# ---------------- backend root paths (reachable when CDN/host rewrites to backend) ----------------
class TestBackendRootSeoPaths:
    def test_backend_serves_root_sitemap(self):
        from fastapi.testclient import TestClient
        client = TestClient(server.app)
        r = client.get("/sitemap.xml")
        assert r.status_code == 200
        assert "<urlset" in r.text and r.text.strip().startswith("<?xml")

    def test_backend_serves_root_robots(self):
        from fastapi.testclient import TestClient
        client = TestClient(server.app)
        r = client.get("/robots.txt")
        assert r.status_code == 200
        assert "Sitemap:" in r.text and "Disallow: /admin" in r.text


# ---------------- PUBLIC_SITE_URL helper (unit) ----------------
def test_public_site_url_default(monkeypatch):
    monkeypatch.delenv("PUBLIC_SITE_URL", raising=False)
    assert server._public_site_url() == "http://localhost:3000"


def test_public_site_url_trims_trailing_slash(monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://shop.example.com/")
    assert server._public_site_url() == "https://shop.example.com"


def test_robots_render_uses_configured_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://shop.example.com")
    body = server._render_robots()
    assert "Sitemap: https://shop.example.com/sitemap.xml" in body
    assert "Disallow: /admin" in body
    assert "Disallow: /api/admin" in body
    # never leaks secrets
    for bad in ["jwt", "secret", "password", "mongodb://"]:
        assert bad not in body.lower()

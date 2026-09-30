"""
Offline tests for scripts/import_inventory.py and the draft/public boundary.

Runs without MongoDB or object storage: uses mongomock-motor and an in-memory
storage stub. Kept outside backend/tests/ because that suite is HTTP-level and
gated on a live test backend (see backend/tests/conftest.py).

    pip install mongomock-motor pytest
    pytest backend/tests_import -q
"""
import asyncio
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("MONGO_URL", "mongodb://mock")
os.environ.setdefault("DB_NAME", "aayna_import_test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-offline-import-tests-only-0000")

from mongomock_motor import AsyncMongoMockClient  # noqa: E402
import db as dbmod  # noqa: E402

dbmod.db = AsyncMongoMockClient()["aayna_import_test"]

spec = importlib.util.spec_from_file_location("import_inventory", ROOT / "scripts" / "import_inventory.py")
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

HEADER = ["SKU", "Product name", "Category", "Color / finish", "Size specification", "Stock unit",
          "Qty", "Individual items", "Unit cost (BDT)", "Unit cost (RMB)", "Stock value (BDT)",
          "Stock value (RMB)", "Notes"]


class FakeStorage:
    APP_NAME = "aayna"
    now_iso = staticmethod(dbmod.now_iso)

    def __init__(self):
        self.objects = {}

    def put_object(self, path, data, content_type):
        self.objects[path] = (data, content_type)
        return {"path": path, "size": len(data)}


def _xlsx(tmp, rows, price_col=False):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"
    ws.append(["AAYNA Product Inventory"])
    ws.append([])
    ws.append(HEADER + (["Selling price (BDT)"] if price_col else []))
    for r in rows:
        ws.append(r)
    ws.append([])
    ws.append(["Rejected inventory"])
    ws.append(HEADER)
    ws.append(["REJ-1", "Seashell Earrings", "Earrings", "Unspecified", "", "Pair", 10, 20, 1, 1, 1, 1, "rej"])
    p = tmp / "inv.xlsx"
    wb.save(p)
    return p


def _photos(tmp, names):
    from PIL import Image
    d = tmp / "photos"
    d.mkdir(exist_ok=True)
    for i, n in enumerate(names):
        Image.new("RGB", (40, 40), (i * 20 % 255, 100, 100)).save(d / n)
    return d


ROWS = [
    ["AYN-RNG-CLS-GLD", "Aayna Classic Statement Ring", "Ring", "Golden", '0.7" diameter', "Piece", 5, 5, 100, 5, 500, 25, None],
    ["AYN-EAR-FLR-GLD", "Aayna Floral Bloom Earrings", "Earrings", "Golden", '1"', "Pair", 5, 10, 100, 5, 500, 25, "2 per pair"],
    ["AYN-EAR-FLR-SLV", "Aayna Floral Bloom Earrings", "Earrings", "Silver", '1"', "Pair", 5, 10, 100, 5, 500, 25, "2 per pair"],
]
PHOTOS = ["Classic Statement Ring Golden 2.png", "Classic Statement Ring Golden 1.png",
          "Floral Bloom Earring Golden 1.png", "Floral Bloom Earring Silver 1.png",
          "Floral Bloom Earring Silver 2.png", "Naira_Floral Bloom Earring.png", "notes.txt"]


def test_manifest_blocks_missing_price_and_matches_images(tmp_path):
    x = _xlsx(tmp_path, ROWS)
    d = _photos(tmp_path, [p for p in PHOTOS if p.endswith(".png")])
    (d / "notes.txt").write_text("x")
    man = imp.build_manifest(x, d)
    s = man["summary"]
    assert s["products"] == 3                      # rejected row excluded
    assert s["ready"] == 0                         # no selling price -> nothing importable
    by = {p["sku"]: p for p in man["products"]}
    ring = by["AYN-RNG-CLS-GLD"]
    assert ring["images"] == ["Classic Statement Ring Golden 1.png", "Classic Statement Ring Golden 2.png"]
    assert ring["stock_quantity"] == 5 and ring["cost_price"] == 100 and ring["category_slug"] == "rings"
    assert by["AYN-EAR-FLR-SLV"]["images"] == ["Floral Bloom Earring Silver 1.png", "Floral Bloom Earring Silver 2.png"]
    assert by["AYN-EAR-FLR-GLD"]["display_name"].endswith("- Golden")
    assert "notes.txt" in [o["file"] for o in s["orphan_images"]]
    # colour-less file matches both colours -> ambiguous, never auto-attached
    assert any(a["file"] == "Naira_Floral Bloom Earring.png" for a in s["ambiguous_images"])


@pytest.fixture()
def seeded(tmp_path):
    async def _seed():
        for c in ("products", "categories", "files", "inventory_logs"):
            await dbmod.db[c].delete_many({})
        await dbmod.db.categories.insert_many([
            {"id": "c1", "name": "Rings", "slug": "rings", "status": "active", "sort_order": 1},
            {"id": "c2", "name": "Earrings", "slug": "earrings", "status": "active", "sort_order": 2},
        ])
    asyncio.run(_seed())
    x = _xlsx(tmp_path, [r + [990] for r in ROWS], price_col=True)  # fixture values only - not real AAYNA prices/costs
    d = _photos(tmp_path, [p for p in PHOTOS if p.endswith(".png") and not p.startswith("Naira")])
    return imp.build_manifest(x, d), d


def test_import_is_draft_idempotent_and_private(seeded):
    man, d = seeded
    assert man["summary"]["ready"] == 3
    st = FakeStorage()
    base = "https://api.example.test"
    rep = asyncio.run(imp.import_products(man, d, base, db=dbmod.db, storage=st))
    assert sorted(rep["created"]) == sorted(p["sku"] for p in man["products"]) and not rep["failed"]
    assert rep["images_uploaded"] == 5 and all(ct == "image/webp" for _, ct in st.objects.values())

    rep2 = asyncio.run(imp.import_products(man, d, base, db=dbmod.db, storage=st))
    assert rep2["created"] == [] and len(rep2["updated"]) == 3 and rep2["images_uploaded"] == 0

    async def check():
        assert await dbmod.db.products.count_documents({}) == 3
        p = await dbmod.db.products.find_one({"sku": "AYN-RNG-CLS-GLD"})
        assert p["status"] == "draft" and p["stock_quantity"] == 5 and p["cost_price"] == 100
        assert p["images"][0]["is_main"] and p["images"][0]["image_url"].startswith(base + "/api/files/aayna/uploads/")
        assert all(":\\" not in i["image_url"] and "/mnt/" not in i["image_url"] for i in p["images"])
        slugs = {x["slug"] async for x in dbmod.db.products.find({}, {"slug": 1})}
        assert len(slugs) == 3
        return p
    p = asyncio.run(check())

    from fastapi.testclient import TestClient
    import server
    server.db = dbmod.db
    c = TestClient(server.app)
    # drafts are invisible and not purchasable
    assert c.get("/api/products").json() == []
    assert c.get(f"/api/products/{p['slug']}").status_code == 404
    v = c.post("/api/cart/validate", json={"items": [{"product_id": p["id"], "quantity": 1}]}).json()
    assert v["items"][0]["available"] is False and v["has_issue"]

    # after founder publishes: visible, correct, no private fields
    asyncio.run(dbmod.db.products.update_one({"id": p["id"]}, {"$set": {"status": "active"}}))
    r = c.get(f"/api/products/{p['slug']}")
    assert r.status_code == 200
    body = r.text
    for secret in ("cost_price", "internal_notes", "source", "inventory_xlsx"):
        assert f'"{secret}"' not in body
    v = c.post("/api/cart/validate", json={"items": [{"product_id": p["id"], "quantity": 1}]}).json()
    assert v["items"][0]["available"] is True and v["items"][0]["unit_price"] == 990

    # re-import after publish must not touch status or live stock
    asyncio.run(dbmod.db.products.update_one({"id": p["id"]}, {"$set": {"stock_quantity": 3}}))
    asyncio.run(imp.import_products(man, d, base, db=dbmod.db, storage=st))
    after = asyncio.run(dbmod.db.products.find_one({"id": p["id"]}))
    assert after["status"] == "active" and after["stock_quantity"] == 3

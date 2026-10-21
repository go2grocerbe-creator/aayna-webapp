"""Product photo order / cover (21 Oct 2026): static photos are preserved, the chosen first photo is
the cover everywhere, stale saves get 409, every change is audited, only product editors may change it,
and uploads stay off (honestly) until permanent storage exists."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_customer_accounts import env as _env, client, admin_h, run, checkout  # noqa: E402,F401

import gallery  # noqa: E402
import gallery_contract as gc  # noqa: E402
from static_gallery_data import STATIC_GALLERY  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SKU = "AYN-RNG-CLS-GLD"


@pytest.fixture
def env(_env, monkeypatch):
    monkeypatch.setattr(gallery, "db", _env["db"])
    for k in ("IMAGE_UPLOADS_ENABLED",) + gallery.R2_SETTINGS:
        monkeypatch.delenv(k, raising=False)
    run(_env["db"].products.update_one({"id": "p1"}, {"$set": {"sku": SKU}}))
    run(_env["db"].product_gallery_history.delete_many({}))
    return _env


def g(env, role="super_admin"):
    return client().get("/api/admin/products/p1/gallery", headers=admin_h(env, role))


def save(env, ids, rev, role="super_admin"):
    return client().put("/api/admin/products/p1/gallery/order", headers=admin_h(env, role),
                        json={"expected_revision": rev, "ordered_ids": ids})


def test_backend_copy_matches_the_reviewed_static_gallery_31_photos():
    front = json.loads((ROOT / "frontend/src/data/productGallery.json").read_text(encoding="utf-8"))["products"]
    assert {k: [i["src"] for i in v["images"]] for k, v in front.items()} == {k: [i["src"] for i in v] for k, v in STATIC_GALLERY.items()}
    assert sum(len(v) for v in STATIC_GALLERY.values()) == 31 and len(STATIC_GALLERY) == 10
    for v in STATIC_GALLERY.values():          # every photo is a local reviewed asset that exists on disk
        for i in v:
            assert gc.valid_url(i["src"]) and (ROOT / "frontend/public" / i["src"].lstrip("/")).is_file()


def test_reorder_sets_cover_everywhere_and_is_audited(env):
    v = g(env).json()
    assert v["source"] == "static" and v["editable"] and v["revision"] == 0 and len(v["images"]) == 4
    assert v["cover"] == STATIC_GALLERY[SKU][0]["src"] and v["uploads"]["enabled"] is False
    ids = [i["id"] for i in v["images"]]
    new = [ids[2]] + [i for i in ids if i != ids[2]]
    r = save(env, new, 0)
    assert r.status_code == 200, r.text
    v2 = r.json()
    assert v2["revision"] == 1 and [i["id"] for i in v2["images"]] == new and v2["cover"] == STATIC_GALLERY[SKU][2]["src"]
    # public product payload carries the order (storefront cards/product page/cart use it)
    pub = client().get("/api/products/prod-p1").json()["product"]
    assert pub["gallery_order"][0] == STATIC_GALLERY[SKU][2]["src"]
    # server-side cover: cart line and the order snapshot
    line = client().post("/api/cart/validate", json={"items": [{"product_id": "p1", "quantity": 1}], "district": "Dhaka"}).json()
    assert [x for x in line["items"] if x["product_id"] == "p1"][0]["image"] == STATIC_GALLERY[SKU][2]["src"]
    n = checkout(client()).json()["order_number"]
    order = run(env["db"].orders.find_one({"order_number": n}))
    assert order["items"][0]["image"] == STATIC_GALLERY[SKU][2]["src"]
    # audit trail
    h = client().get("/api/admin/products/p1/gallery/history", headers=admin_h(env)).json()
    assert len(h) == 1 and h[0]["revision"] == 1 and h[0]["actor"] == "super_admin@example.test"
    assert h[0]["cover_before"] == STATIC_GALLERY[SKU][0]["src"] and h[0]["cover_after"] == STATIC_GALLERY[SKU][2]["src"]
    # nothing else on the product changed
    p = run(env["db"].products.find_one({"id": "p1"}))
    assert p["images"] == [] and p["selling_price"] == 1290 and p["status"] == "active"


def test_stale_revision_gets_409_and_changes_nothing(env):
    ids = [i["id"] for i in g(env).json()["images"]]
    assert save(env, ids[::-1], 0).status_code == 200
    r = save(env, ids, 0)                                # someone else already saved revision 1
    assert r.status_code == 409 and "reload" in r.json()["detail"].lower()
    assert g(env).json()["revision"] == 1 and len(run(env["db"].product_gallery_history.find({}).to_list(10))) == 1


def test_order_must_be_an_exact_permutation(env):
    ids = [i["id"] for i in g(env).json()["images"]]
    assert save(env, ids[:-1], 0).status_code in (400, 409)          # a photo missing
    assert save(env, [ids[0]] * len(ids), 0).status_code in (400, 409)  # duplicates
    assert save(env, ids[:-1] + ["legacy_0000000000000000"], 0).status_code in (400, 409)  # unknown photo
    assert g(env).json()["revision"] == 0


def test_only_product_editors_can_reorder(env):
    ids = [i["id"] for i in g(env, "order_manager").json()["images"]]   # everyone with products.view can look
    assert save(env, ids[::-1], 0, role="order_manager").status_code == 403
    assert client().put("/api/admin/products/p1/gallery/order", json={"expected_revision": 0, "ordered_ids": ids}).status_code in (401, 403)
    assert save(env, ids[::-1], 0, role="product_manager").status_code == 200


def test_uploads_never_pretend_to_work(env, monkeypatch):
    r = client().post("/api/admin/products/p1/gallery/upload-intent", headers=admin_h(env))
    assert r.status_code == 503 and "R2_BUCKET" in r.json()["detail"]
    monkeypatch.setenv("IMAGE_UPLOADS_ENABLED", "true")
    st = gallery.uploads_status()
    assert st["enabled"] is False and "R2_ACCOUNT_ID" in st["reason"]


def test_products_with_uploaded_images_keep_their_own_order(env):
    run(env["db"].products.update_one({"id": "p1"}, {"$set": {"images": [{"image_url": "/api/files/a.webp", "is_main": True}]}}))
    v = g(env).json()
    assert v["source"] == "database" and v["editable"] is False and v["cover"] == "/api/files/a.webp"
    assert save(env, [i["id"] for i in v["images"]], 0).status_code == 409

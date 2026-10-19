"""+৳100 price update (2026-10-19): idempotent, all-or-nothing, touches only price fields."""
import copy
import importlib.util
import sys
from pathlib import Path

import mongomock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("price_update", ROOT / "scripts/prices/apply_price_update_20261019.py")
pu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pu)
from price_targets import PRICE_TARGETS  # noqa: E402


def make_db():
    db = mongomock.MongoClient()["aayna_prod_sim"]
    for i, (sku, (old, _)) in enumerate(sorted(PRICE_TARGETS.items())):
        db.products.insert_one({"id": f"p{i}", "sku": sku, "selling_price": old, "discount_price": None, "status": "draft",
                                "cost_price": 123.0 + i, "stock_quantity": i + 1, "pricing": {"selling_price": old},
                                "images": [{"image_url": "x"}], "updated_at": "2026-10-18T13:25:44+00:00"})
    db.orders.insert_one({"order_number": "AYN-1", "items": [{"sku_snapshot": "AYN-RNG-CLS-GLD", "unit_price": 1290}], "total_amount": 1390})
    return db


def strip(doc, keys=("selling_price", "previous_selling_price", "price_history", "updated_at", "_id")):
    return {k: v for k, v in doc.items() if k not in keys}


def test_targets_are_exactly_plus_100_and_match_founder_figures():
    assert len(PRICE_TARGETS) == 10
    assert all(new == old + 100 for old, new in PRICE_TARGETS.values())
    assert PRICE_TARGETS["AYN-EAR-CHK-GLD"][1] == 970 and PRICE_TARGETS["AYN-CUF-STN-GLD"][1] == 1090
    assert PRICE_TARGETS["AYN-EAR-FLR-GLD"][1] == 1510 and PRICE_TARGETS["AYN-EAR-FLR-SLV"][1] == 1510


def test_dry_run_writes_nothing_then_apply_is_idempotent():
    db = make_db()
    before = [copy.deepcopy(d) for d in db.products.find({}, {"_id": 0})]
    order_before = db.orders.find_one({}, {"_id": 0})
    log = []
    assert pu.run(db, "dry-run", log.append) == 0
    assert [d for d in db.products.find({}, {"_id": 0})] == before
    assert any("10 product(s) would change" in line for line in log)
    assert pu.run(db, "verify", log.append) == 1
    # apply
    assert pu.run(db, "apply", log.append) == 0
    for d in db.products.find({}, {"_id": 0}):
        old, new = PRICE_TARGETS[d["sku"]]
        assert d["selling_price"] == new and d["previous_selling_price"] == old
        assert isinstance(d["selling_price"], float)  # type preserved (production stores doubles)
        assert len(d["price_history"]) == 1 and d["price_history"][0]["from"] == old and d["price_history"][0]["to"] == new
        orig = next(b for b in before if b["sku"] == d["sku"])
        assert strip(d) == strip(orig)  # cost, pricing, stock, status, images untouched
    assert db.orders.find_one({}, {"_id": 0}) == order_before  # existing order totals untouched
    # second apply: nothing changes, never +200
    log2 = []
    assert pu.run(db, "apply", log2.append) == 0
    assert any("Applied: 0 product(s) changed" in line for line in log2)
    assert all(len(d["price_history"]) == 1 for d in db.products.find({}))
    assert pu.run(db, "verify", log.append) == 0


def test_all_or_nothing_on_unexpected_state():
    db = make_db()
    db.products.update_one({"sku": "AYN-RNG-CLS-GLD"}, {"$set": {"selling_price": 1300}})  # changed by hand
    log = []
    assert pu.run(db, "apply", log.append) == 2
    assert any("STOPPED - nothing written" in line for line in log)
    assert db.products.count_documents({"previous_selling_price": {"$exists": True}}) == 0
    db = make_db()
    db.products.delete_one({"sku": "AYN-NKL-LUN-GLD"})
    assert pu.run(db, "apply", log.append) == 2
    db = make_db()
    db.products.update_one({"sku": "AYN-NKL-LUN-GLD"}, {"$set": {"discount_price": 1200}})
    assert pu.run(db, "apply", log.append) == 2


def test_partial_previous_run_completes_without_double_increase():
    db = make_db()
    db.products.update_one({"sku": "AYN-CUF-STN-GLD"}, {"$set": {"selling_price": 1090}})  # already at target
    assert pu.run(db, "apply", [].append) == 0
    assert db.products.find_one({"sku": "AYN-CUF-STN-GLD"})["selling_price"] == 1090
    assert db.products.find_one({"sku": "AYN-CUF-STN-GLD"}).get("price_history") is None


def test_rollback_restores_before_prices():
    db = make_db()
    pu.run(db, "apply", [].append)
    assert pu.run(db, "rollback", [].append) == 0
    assert all(d["selling_price"] == PRICE_TARGETS[d["sku"]][0] for d in db.products.find({}))


def test_production_guard_refuses_other_databases(tmp_path):
    env = tmp_path / "e.env"
    env.write_text("MONGO_URL=mongodb+srv://aayna_preview_app:x@example.mongodb.net/\nDB_NAME=aayna_preview\n")
    assert pu.main(["--env-file", str(env)]) == 2
    env.write_text("MONGO_URL=mongodb+srv://aayna_prod_app:x@example.mongodb.net/\nDB_NAME=aayna_prod\n")
    assert pu.main(["--env-file", str(env), "--apply"]) == 2  # no --confirm
    assert pu.main(["--env-file", str(env), "--apply", "--confirm", "aayna_preview"]) == 2

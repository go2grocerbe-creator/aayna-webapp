"""Offline tests for scripts/diagnostics/data_integrity.py (mongomock).

Plants every problem the diagnostic looks for, checks each one is reported,
checks a clean database reports nothing, and checks the script never writes.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import mongomock
import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(monkeypatch, client):
    monkeypatch.setenv("MONGO_URL", "mongodb://mock")
    monkeypatch.setenv("DB_NAME", "aayna_diag_test")
    spec = importlib.util.spec_from_file_location("data_integrity", ROOT / "scripts" / "diagnostics" / "data_integrity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.pymongo, "MongoClient", lambda *a, **k: client)
    return mod


def snapshot(db):
    return {c: sorted((json.dumps(d, default=str, sort_keys=True) for d in db[c].find({})))
            for c in db.list_collection_names()}


def good_product(i, **kw):
    p = {"id": f"p{i}", "sku": f"SKU{i}", "slug": f"slug-{i}", "product_name": f"P{i}", "status": "active",
         "selling_price": 500, "discount_price": None, "stock_quantity": 5,
         "images": [{"image_url": f"/api/files/aayna/uploads/{i}.jpg"}]}
    p.update(kw)
    return p


def order(n, items, **kw):
    sub = sum(it["unit_price"] * it["quantity"] for it in items)
    o = {"id": f"o{n}", "order_number": f"ORD-{1000 + n}", "client_request_id": f"rid{n}", "items": items,
         "subtotal": sub, "delivery_charge": 60, "discount_amount": 0, "total_amount": sub + 60,
         "order_status": "New", "created_at": f"2026-10-0{n}T00:00:00+00:00", "customer_id": "c1"}
    o.update(kw)
    return o


def run(mod, monkeypatch, tmp_path):
    out = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["data_integrity.py", "--json", str(out)])
    code = mod.main()
    return code, {f["check"]: f["count"] for f in json.loads(out.read_text())["findings"]}


def test_clean_database_reports_nothing(monkeypatch, tmp_path):
    client = mongomock.MongoClient()
    db = client["aayna_diag_test"]
    db.products.insert_many([good_product(1), good_product(2)])
    db.orders.insert_many([order(1, [{"product_id": "p1", "unit_price": 500, "quantity": 1}])])
    db.counters.insert_one({"_id": "order_number", "seq": 1})
    db.customers.insert_one({"id": "c1", "phone": "+8801700000001"})
    mod = load(monkeypatch, client)
    code, counts = run(mod, monkeypatch, tmp_path)
    assert code == 0, counts
    assert all(v == 0 for v in counts.values()), counts


def test_every_planted_problem_is_found_and_nothing_is_written(monkeypatch, tmp_path):
    client = mongomock.MongoClient()
    db = client["aayna_diag_test"]
    db.products.insert_many([
        good_product(1), good_product(2, sku="SKU1"),                    # duplicate sku
        good_product(3, slug="slug-1"),                                   # duplicate slug
        good_product(4, stock_quantity=-2),                               # negative stock
        good_product(5, status="published"),                              # invalid status
        good_product(6, selling_price=0),                                 # bad price (public)
        good_product(7, discount_price=900),                              # discount >= price
        good_product(8, status="out_of_stock", stock_quantity=0,
                     source={"type": "inventory_xlsx", "row": 4}, price_is_temporary=True),   # imported draft now public
        good_product(9, status="out_of_stock", stock_quantity=0),         # zeroed by admin, never sold
        good_product(10, sku=""),                                         # missing SKU
        good_product(11, images=[]),                                      # public, no image
    ])
    db.inventory_logs.insert_many([
        {"product_id": "p9", "change_type": "damage", "quantity_change": -5, "previous_stock": 5, "new_stock": 0,
         "reason": "qa", "created_at": "2026-10-01T00:00:00+00:00"},
        {"product_id": "p1", "change_type": "stock_in", "quantity_change": 9, "previous_stock": 0, "new_stock": 9,
         "reason": "", "created_at": "2026-10-01T00:00:00+00:00"},                            # p1 has 5, log says 9
    ])
    it = [{"product_id": "p1", "unit_price": 500, "quantity": 1}]
    db.orders.insert_many([
        order(1, it), order(2, it, order_number="ORD-1001"),            # duplicate order_number
        order(3, it, client_request_id="rid1"),                          # duplicate idempotency key
        order(4, [{"product_id": "gone", "unit_price": 500, "quantity": 1}]),   # missing product
        order(5, it, total_amount=1),                                    # totals do not add up
        order(9, it),                                                    # ORD-1009 > counter
        order(6, it, customer_id="ghost"),                               # customer record missing
    ])
    db.counters.insert_one({"_id": "order_number", "seq": 5})            # next would be ORD-1006, but 1009 exists
    db.customers.insert_many([{"id": "c1", "phone": "8801700000001"}, {"id": "c2", "phone": "8801700000001"},
                              {"id": "c3", "phone": "01711111111"}, {"id": "c4", "phone": "+8801711111111"},
                              {"id": "c5", "phone": "12345"}])
    db.checkout_requests.insert_one({"_id": "stuck", "status": "processing", "created_at": "2026-01-01T00:00:00+00:00"})

    before = snapshot(db)
    mod = load(monkeypatch, client)
    code, c = run(mod, monkeypatch, tmp_path)
    assert snapshot(db) == before, "diagnostics must not write"
    assert code == 2
    expected = [
        "duplicate products.sku", "duplicate products.slug", "duplicate orders.order_number",
        "duplicate orders.client_request_id", "order-number counter behind highest existing order number",
        "negative or non-integer stock_quantity", "invalid product status", "public product with invalid price",
        "drafts possibly published by the pre-Phase-4 stock bug", "duplicate customers.phone",
        "orders referencing missing products", "order totals that do not add up",
        "stock differs from the latest inventory-log entry", "checkout_requests stuck in 'processing' > 15 min",
        "duplicate customers after phone normalization", "customer phones not stored in normalized form",
        "customer phones that are not valid BD mobile numbers", "orders whose customer_id has no customer record",
        "products without a SKU", "public products without an image",
    ]
    missing = [e for e in expected if not c.get(e)]
    assert not missing, f"not detected: {missing} — {c}"
    assert c["public product with invalid price"] == 2
    assert c["drafts possibly published by the pre-Phase-4 stock bug"] == 2

    assert c["duplicate customers after phone normalization"] == 2   # 8801700000001 x2, 017.../+880... pair


def test_output_never_contains_phone_numbers(monkeypatch, tmp_path, capsys):
    client = mongomock.MongoClient()
    db = client["aayna_diag_test"]
    db.customers.insert_many([{"id": "c1", "phone": "01711111111"}, {"id": "c2", "phone": "+8801711111111"},
                              {"id": "c3", "phone": "+8801711111111"}])
    mod = load(monkeypatch, client)
    for argv in (["data_integrity.py"], ["data_integrity.py", "--aggregate-only", "--json", str(tmp_path / "a.json")]):
        monkeypatch.setattr(sys, "argv", argv)
        mod.main()
    text = capsys.readouterr().out + (tmp_path / "a.json").read_text()
    assert "1711111111" not in text
    assert "phone#" in text or "--aggregate-only" in " ".join(argv)

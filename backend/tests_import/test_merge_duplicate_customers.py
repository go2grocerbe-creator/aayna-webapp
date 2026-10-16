"""Offline tests for scripts/diagnostics/merge_duplicate_customers.py (mongomock, fake data only)."""
import copy
import json
import os
import sys

import mongomock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "diagnostics"))
import merge_duplicate_customers as m  # noqa: E402


def seed():
    db = mongomock.MongoClient()["aayna_release_test"]
    db.customers.insert_many([
        # same person, three formats, created in this order
        {"id": "c-b", "phone": "+8801711111111", "full_name": "", "email": "", "default_address": "Old Rd",
         "district": "Dhaka", "total_orders": 1, "successful_orders": 0, "cancelled_orders": 0,
         "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
        {"id": "c-a", "phone": "01711111111", "full_name": "Rina", "email": "rina@example.test",
         "default_address": "New Rd", "district": "Dhaka", "total_orders": 1, "successful_orders": 1,
         "cancelled_orders": 0, "created_at": "2026-02-01T00:00:00", "updated_at": "2026-03-01T00:00:00"},
        {"id": "c-c", "phone": "8801711111111", "full_name": "Rina K", "email": "", "default_address": "",
         "district": "", "total_orders": 2, "successful_orders": 0, "cancelled_orders": 1,
         "created_at": "2026-02-01T00:00:00", "updated_at": "2026-02-15T00:00:00"},
        # singleton stored in legacy format
        {"id": "c-s", "phone": "01822222222", "full_name": "Solo", "total_orders": 1, "successful_orders": 0,
         "cancelled_orders": 0, "created_at": "2026-01-05T00:00:00"},
        # invalid phone: reported, never touched
        {"id": "c-x", "phone": "12345", "full_name": "Bad", "total_orders": 0, "successful_orders": 0,
         "cancelled_orders": 0, "created_at": "2026-01-06T00:00:00"},
    ])
    db.orders.insert_many([
        {"order_number": "ORD-1", "customer_id": "c-b", "order_status": "Pending"},
        {"order_number": "ORD-2", "customer_id": "c-a", "order_status": "Delivered"},
        {"order_number": "ORD-3", "customer_id": "c-c", "order_status": "Cancelled"},
        {"order_number": "ORD-4", "customer_id": "c-c", "order_status": "Pending"},
        {"order_number": "ORD-5", "customer_id": "c-s", "order_status": "Pending"},
    ])
    return db


def snapshot(db):
    return {c: sorted((dict(d, _id=None) for d in db[c].find()), key=lambda d: json.dumps(d, sort_keys=True, default=str))
            for c in ("customers", "orders", "customers_merged_archive")}


def test_normalize_matches_backend():
    os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
    os.environ.setdefault("DB_NAME", "aayna_pytest")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import server  # noqa: E402
    assert m.PHONE_RE.pattern == server.PHONE_RE.pattern
    for p in ["01711111111", "+8801711111111", "8801711111111", "017 1111-1111", "0171111111", "12345", "",
              "+880 1911-111111", "01211111111"]:
        assert m.normalize_phone(p) == server.normalize_phone(p), p


def test_plan_is_deterministic_and_correct():
    db = seed()
    p1, p2 = m.build_plan(db), m.build_plan(db)
    assert p1 == p2
    assert len(p1["merges"]) == 1
    g = p1["merges"][0]
    assert g["survivor"] == "c-b"                      # earliest created_at
    assert g["losers"] == ["c-a", "c-c"]               # created_at tie broken by id
    assert sorted(o["order_number"] for o in g["repoint_orders"]) == ["ORD-2", "ORD-3", "ORD-4"]
    assert g["counters"] == {"total_orders": 4, "successful_orders": 1, "cancelled_orders": 1}
    assert g["fill_from"] == {"full_name": "c-a", "email": "c-a"}   # newest-updated loser with a value
    assert p1["phone_updates"] == [{"id": "c-s", "phone_hash": m.phone_hash("+8801822222222")}]
    assert p1["invalid_phone_customers"] == 1


def test_plan_file_and_summary_contain_no_pii():
    db = seed()
    text = json.dumps(m.build_plan(db)) + json.dumps(m.summarize(m.build_plan(db)))
    for pii in ("Rina", "rina@example.test", "Old Rd", "New Rd", "1711111111", "1822222222", "Solo"):
        assert pii not in text


def test_apply_merges_and_verifies_clean():
    db = seed()
    plan = m.build_plan(db)
    m.apply_plan(db, plan, plan["plan_hash"])
    survivor = db.customers.find_one({"id": "c-b"})
    assert survivor["phone"] == "+8801711111111"
    assert survivor["full_name"] == "Rina" and survivor["email"] == "rina@example.test"
    assert survivor["default_address"] == "Old Rd"     # non-empty survivor field never overwritten
    assert (survivor["total_orders"], survivor["successful_orders"], survivor["cancelled_orders"]) == (4, 1, 1)
    assert sorted(survivor["merged_customer_ids"]) == ["c-a", "c-c"]
    assert db.customers.count_documents({"id": {"$in": ["c-a", "c-c"]}}) == 0
    assert db.customers_merged_archive.count_documents({"merged_into": "c-b"}) == 2
    assert {o["customer_id"] for o in db.orders.find({"order_number": {"$in": ["ORD-1", "ORD-2", "ORD-3", "ORD-4"]}})} == {"c-b"}
    assert db.orders.find_one({"order_number": "ORD-3"})["merged_from_customer_id"] == "c-c"
    assert db.customers.find_one({"id": "c-s"})["phone"] == "+8801822222222"
    assert db.customers.find_one({"id": "c-x"})["phone"] == "12345"
    assert m.verify(db) == {"duplicate_normalized_phones": 0, "non_normalized_phones": 0,
                            "orders_with_missing_customer": 0, "customer_counter_mismatch": 0}
    # idempotent: nothing left to do
    again = m.build_plan(db)
    assert again["merges"] == [] and again["phone_updates"] == []


def test_apply_refuses_changed_data_or_wrong_hash():
    db = seed()
    plan = m.build_plan(db)
    with pytest.raises(SystemExit, match="hash mismatch"):
        m.apply_plan(db, plan, "0" * 64)
    db.orders.insert_one({"order_number": "ORD-9", "customer_id": "c-a", "order_status": "Pending"})
    with pytest.raises(SystemExit, match="hash mismatch"):
        m.apply_plan(db, plan, plan["plan_hash"])
    assert db.customers.count_documents({}) == 5      # nothing applied


def test_rollback_restores_exact_previous_state():
    db = seed()
    before = snapshot(db)
    plan = m.build_plan(db)
    run_id = m.apply_plan(db, plan, plan["plan_hash"])
    assert snapshot(db) != before
    steps = m.rollback(db, run_id)
    assert steps == 2                                   # one merge + one normalize
    assert snapshot(db) == before
    assert db.customer_merge_log.count_documents({"run_id": run_id, "status": "rolled_back"}) == 2


def test_cli_refuses_real_database_before_any_write(monkeypatch, capsys):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    for name in ("aayna_dev", "test_database", "aayna_prod"):
        monkeypatch.setenv("DB_NAME", name)
        monkeypatch.setattr(sys, "argv", ["merge", "apply", "--plan", "x", "--confirm", "y"])
        monkeypatch.setattr(m.pymongo, "MongoClient", lambda *a, **k: mongomock.MongoClient())
        with pytest.raises(SystemExit, match="Refusing to run"):
            m.main()

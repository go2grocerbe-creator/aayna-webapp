"""
Offline tests for the cost-based selling-price rule (backend/pricing.py),
the importer's --price-rule and scripts/reprice_from_cost.py.

No MongoDB or network: mongomock-motor. All costs AND the rule parameters are
fake fixture values: the founder's real extra amount/multiplier and purchase
costs are confidential and never go into this (public) repository.

    pytest backend/tests_import -q
"""
import asyncio
import importlib.util
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("MONGO_URL", "mongodb://mock")
os.environ.setdefault("DB_NAME", "aayna_import_test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-offline-import-tests-only-0000")

from mongomock_motor import AsyncMongoMockClient  # noqa: E402
import db as dbmod  # noqa: E402
import pricing  # noqa: E402

if "mongomock" not in type(dbmod.db).__module__:  # never a real DB; reuse the mock if another test set it
    dbmod.db = AsyncMongoMockClient()["aayna_import_test"]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rp = _load("reprice_from_cost", "scripts/reprice_from_cost.py")
imp = _load("import_inventory_p", "scripts/import_inventory.py")


FAKE_RULE = (40, 2.5)  # NOT the real rule

# (cost, adjusted, selling, profit) computed by hand: adjusted = cost + 40, selling = adjusted * 2.5.
EXPECTED = [(100, 140, 350, 210), (250, 290, 725, 435), (75, 115, 287.5, 172.5), (333, 373, 932.5, 559.5),
            (1, 41, 102.5, 61.5)]


@pytest.mark.parametrize("cost,adjusted,selling,profit", EXPECTED)
def test_rule_matches_hand_computed_prices(cost, adjusted, selling, profit):
    bd = pricing.price_from_cost(cost, *FAKE_RULE)
    assert (bd["cost"], bd["extra"], bd["multiplier"], bd["adjusted_cost"], bd["selling_price"], bd["gross_profit"]) == \
        (cost, 40, 2.5, adjusted, selling, profit)
    assert bd["gross_margin_pct"] == 60.0 and bd["rule"] == pricing.RULE_ID


def test_rule_keeps_paisa_precision_and_whole_taka_ints():
    assert pricing.price_from_cost(99.5, *FAKE_RULE)["selling_price"] == 348.75
    assert isinstance(pricing.price_from_cost(100, *FAKE_RULE)["selling_price"], int)


@pytest.mark.parametrize("bad", [None, 0, -5, "abc", "", float("nan"), float("inf"), True, [1]])
def test_rule_rejects_invalid_cost(bad):
    with pytest.raises(pricing.PricingError):
        pricing.price_from_cost(bad, *FAKE_RULE)


def test_rule_parameters_come_only_from_the_environment():
    assert pricing.rule_from_env({"AAYNA_PRICE_EXTRA_BDT": "40", "AAYNA_PRICE_MULTIPLIER": "2.5"}) == (40, 2.5)
    for env in ({}, {"AAYNA_PRICE_EXTRA_BDT": "40"}, {"AAYNA_PRICE_MULTIPLIER": "2.5"},
                {"AAYNA_PRICE_EXTRA_BDT": "x", "AAYNA_PRICE_MULTIPLIER": "2.5"},
                {"AAYNA_PRICE_EXTRA_BDT": "-1", "AAYNA_PRICE_MULTIPLIER": "2.5"},
                {"AAYNA_PRICE_EXTRA_BDT": "40", "AAYNA_PRICE_MULTIPLIER": "1"}):  # would sell at or below cost
        with pytest.raises(pricing.PricingError):
            pricing.rule_from_env(env)


def test_no_real_rule_values_in_code():
    # the confidential values must live only in backend/.env, never in tracked code
    for f in ("backend/pricing.py", "scripts/reprice_from_cost.py", "scripts/import_inventory.py"):
        src = (ROOT / f).read_text(encoding="utf-8")
        assert "rule_from_env" in src  # parameters are read from the environment, no hard-coded rule


# --- importer --cost-price-rule ----------------------------------------------------------
def _sheet(tmp, rows, price_col=False):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"
    hdr = ["SKU", "Product name", "Category", "Color / finish", "Size specification", "Stock unit", "Qty",
           "Individual items", "Unit cost (BDT)", "Unit cost (RMB)", "Stock value (BDT)", "Stock value (RMB)", "Notes"]
    ws.append(hdr + (["Selling price (BDT)"] if price_col else []))
    for r in rows:
        ws.append(r)
    p = tmp / "inv.xlsx"
    wb.save(p)
    return p


def _row(sku, cost, extra=()):
    return [sku, f"Test {sku}", "Ring", "Golden", "1", "Piece", 3, 3, cost, None, None, None, None, *extra]


def test_manifest_price_rule_prices_from_cost_and_blocks_bad_rows(tmp_path):
    x = _sheet(tmp_path, [_row("T-RNG-A-GLD", 100), _row("T-RNG-B-GLD", None), _row("T-RNG-C-GLD", "n/a")])
    (tmp_path / "ph").mkdir()
    man = imp.build_manifest(x, tmp_path / "ph", price_rule=FAKE_RULE)
    by = {p["sku"]: p for p in man["products"]}
    a = by["T-RNG-A-GLD"]
    assert a["selling_price"] == 350 and a["pricing"]["adjusted_cost"] == 140 and a["cost_price"] == 100
    assert not any("selling price" in b.lower() for b in a["blockers"])
    assert any("Cost-based price not possible" in b for b in by["T-RNG-B-GLD"]["blockers"])
    assert "selling_price" not in by["T-RNG-C-GLD"]  # invalid cost: blocked, never guessed
    # without the rule nothing changes: price still missing
    plain = imp.build_manifest(x, tmp_path / "ph")
    assert all("selling_price" not in p for p in plain["products"])


def test_manifest_price_rule_never_applies_on_top_of_a_sheet_price(tmp_path):
    x = _sheet(tmp_path, [_row("T-RNG-A-GLD", 100, (1999,))], price_col=True)
    (tmp_path / "ph").mkdir()
    man = imp.build_manifest(x, tmp_path / "ph", price_rule=FAKE_RULE)
    p = man["products"][0]
    assert p["selling_price"] == 1999 and "pricing" not in p
    assert any("already has a selling price" in b for b in p["blockers"])
    with pytest.raises(ValueError):
        imp.build_manifest(x, tmp_path / "ph", temp_price=500, price_rule=FAKE_RULE)


# --- reprice_from_cost ---------------------------------------------------------------
def _prod(pid, sku, cost, price, status="active", source=True, **extra):
    d = {"id": pid, "sku": sku, "slug": pid, "product_name": f"P {sku}", "category_slug": "rings",
         "category_name": "Rings", "selling_price": price, "discount_price": None, "cost_price": cost,
         "stock_quantity": 5, "status": status, "images": [], "internal_notes": "secret-note"}
    if source:
        d["source"] = {"type": "inventory_xlsx", "row": 10}
    d.update(extra)
    return d


@pytest.fixture()
def repriced_db():
    async def seed():
        for c in ("products", "orders", "categories"):
            await dbmod.db[c].delete_many({})
        await dbmod.db.products.insert_many([
            _prod("p-real", "R-1", 100, 999),                          # eligible -> 350
            _prod("p-draft", "R-2", 250, 0.01, status="draft"),        # eligible draft -> 725
            _prod("p-demo", "D-1", 100, 999, source=False),            # seed/demo -> skip
            _prod("p-nocost", "R-3", None, 500),                       # flag, never guessed
            _prod("p-badcost", "R-4", "abc", 500),                     # flag
            _prod("p-disc", "R-5", 100, 999, discount_price=800),      # 800 >= 350 -> flag
            _prod("p-inactive", "R-6", 100, 999, status="inactive"),   # skip
        ])
        await dbmod.db.orders.insert_one({"id": "o-1", "order_number": "AYN-1", "subtotal": 999.0, "total": 1069.0,
                                          "items": [{"product_id": "p-real", "sku_snapshot": "R-1",
                                                     "unit_price": 999.0, "quantity": 1, "total_price": 999.0}]})
    asyncio.run(seed())
    return dbmod.db


def _by(plans):
    return {p["sku"]: p for p in plans}


def test_dry_run_writes_nothing(repriced_db):
    before = asyncio.run(repriced_db.products.find({}, {"_id": 0}).to_list(None))
    plans = _by(asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=False)))
    after = asyncio.run(repriced_db.products.find({}, {"_id": 0}).to_list(None))
    assert before == after
    assert plans["R-1"]["action"] == "update" and plans["R-1"]["selling_price"] == 350
    assert plans["D-1"]["action"] == "skip" and plans["R-6"]["action"] == "skip"
    assert {plans[s]["action"] for s in ("R-3", "R-4", "R-5")} == {"flag"}


def test_apply_is_idempotent_keeps_cost_history_and_orders(repriced_db):
    plans = _by(asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=True)))
    assert plans["R-1"]["applied"] and plans["R-2"]["applied"]

    async def get(pid):
        return await repriced_db.products.find_one({"id": pid}, {"_id": 0})
    p = asyncio.run(get("p-real"))
    assert p["selling_price"] == 350 and p["previous_selling_price"] == 999 and p["cost_price"] == 100
    assert p["pricing"]["adjusted_cost"] == 140 and len(p["price_history"]) == 1
    assert p["price_history"][0]["from"] == 999 and p["price_history"][0]["to"] == 350
    assert asyncio.run(get("p-draft"))["selling_price"] == 725
    # untouched records
    assert asyncio.run(get("p-demo"))["selling_price"] == 999
    assert asyncio.run(get("p-nocost"))["selling_price"] == 500
    assert asyncio.run(get("p-disc"))["selling_price"] == 999

    # re-run: nothing stacks, nothing written
    snap = asyncio.run(repriced_db.products.find({}, {"_id": 0}).to_list(None))
    again = _by(asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=True)))
    assert again["R-1"]["action"] == "unchanged" and again["R-2"]["action"] == "unchanged"
    assert asyncio.run(repriced_db.products.find({}, {"_id": 0}).to_list(None)) == snap

    # historical order keeps the price it was placed at
    o = asyncio.run(repriced_db.orders.find_one({"id": "o-1"}, {"_id": 0}))
    assert o["items"][0]["unit_price"] == 999.0 and o["subtotal"] == 999.0 and o["total"] == 1069.0


def test_manual_admin_price_is_flagged_not_overwritten(repriced_db):
    asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=True))
    asyncio.run(repriced_db.products.update_one({"id": "p-real"}, {"$set": {"selling_price": 799}}))
    plan = _by(asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=True)))["R-1"]
    assert plan["action"] == "flag" and "manually" in plan["reason"]
    assert asyncio.run(repriced_db.products.find_one({"id": "p-real"}))["selling_price"] == 799
    plan = _by(asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=True, override_manual=True)))["R-1"]
    p = asyncio.run(repriced_db.products.find_one({"id": "p-real"}))
    assert plan["applied"] and p["selling_price"] == 350 and len(p["price_history"]) == 2


def test_public_api_shows_new_price_but_no_cost_or_pricing_fields(repriced_db):
    asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=True))
    from fastapi.testclient import TestClient
    import server
    server.db = repriced_db
    c = TestClient(server.app)
    for body in (c.get("/api/products").text, c.get("/api/products/p-real").text):
        for secret in ("cost_price", "pricing", "price_history", "previous_selling_price", "adjusted_cost",
                       "gross_profit", "gross_margin", "multiplier", "internal_notes", "secret-note", "inventory_xlsx"):
            assert secret not in body
    assert c.get("/api/products/p-real").json()["product"]["selling_price"] == 350
    v = c.post("/api/cart/validate", json={"items": [{"product_id": "p-real", "quantity": 2}]}).json()
    assert v["items"][0]["unit_price"] == 350 and v["subtotal"] == 700
    assert "cost" not in str(v) and "pricing" not in str(v)
    # draft repriced product stays invisible
    assert c.get("/api/products/p-draft").status_code == 404


def test_apply_cli_refuses_test_database(monkeypatch):
    monkeypatch.setenv("DB_NAME", "aayna_release_test")
    monkeypatch.setenv("AAYNA_PRICE_EXTRA_BDT", "40")
    monkeypatch.setenv("AAYNA_PRICE_MULTIPLIER", "2.5")
    monkeypatch.setattr(sys, "argv", ["reprice_from_cost.py", "--apply", "--target-db", "aayna_release_test", "--yes"])
    called = []
    monkeypatch.setattr(rp, "reprice", lambda *a, **k: called.append(1))
    with pytest.raises(SystemExit) as e:
        rp.main()
    assert "Refused" in str(e.value) and not called


def test_rule_change_is_applied_once_and_recorded(repriced_db):
    asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, FAKE_RULE, apply=True))
    plans = _by(asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, (60, 2.5), apply=True)))
    p = asyncio.run(repriced_db.products.find_one({"id": "p-real"}))
    assert plans["R-1"]["action"] == "update" and p["selling_price"] == 400  # (100 + 60) * 2.5
    assert p["previous_selling_price"] == 350 and p["price_history"][-1]["extra"] == 60
    again = _by(asyncio.run(rp.reprice(repriced_db, dbmod.now_iso, (60, 2.5), apply=True)))
    assert again["R-1"]["action"] == "unchanged"


def test_cli_without_configured_rule_exits_before_db(monkeypatch):
    monkeypatch.delenv("AAYNA_PRICE_EXTRA_BDT", raising=False)
    monkeypatch.delenv("AAYNA_PRICE_MULTIPLIER", raising=False)
    monkeypatch.setattr(sys, "argv", ["reprice_from_cost.py"])
    monkeypatch.setattr(rp, "reprice", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    with pytest.raises(SystemExit) as e:
        rp.main()
    assert "not configured" in str(e.value)

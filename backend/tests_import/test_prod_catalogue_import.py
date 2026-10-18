"""
Offline tests for scripts/prod_catalogue_import.py guards and read-back checks.
No network, no real credentials: fake connection strings and mongomock only.
"""
import importlib.util
import json
import sys
from pathlib import Path

import mongomock
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prod_catalogue_import", ROOT / "scripts" / "prod_catalogue_import.py")
pci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pci)

FAKE_URL = "mongodb+srv://aayna_prod_app:not-a-real-password@cluster.example.test/?retryWrites=true"


def _env(**over):
    v = {"MONGO_URL": FAKE_URL, "DB_NAME": "aayna_prod", "AAYNA_PRICE_EXTRA_BDT": "40", "AAYNA_PRICE_MULTIPLIER": "2.5"}
    v.update(over)
    return v


def test_env_file_parsing_and_missing_keys(tmp_path):
    f = tmp_path / ".env.prod-import"
    f.write_text("# comment\nMONGO_URL=" + FAKE_URL + "\nDB_NAME=aayna_prod\n", encoding="utf-8")
    with pytest.raises(pci.Stop) as e:
        pci.load_env_file(f)
    assert "AAYNA_PRICE_EXTRA_BDT" in str(e.value) and "not-a-real-password" not in str(e.value)
    f.write_text(f.read_text() + "AAYNA_PRICE_EXTRA_BDT=40\nAAYNA_PRICE_MULTIPLIER='2.5'\n", encoding="utf-8")
    assert pci.load_env_file(f)["AAYNA_PRICE_MULTIPLIER"] == "2.5"
    with pytest.raises(pci.Stop):
        pci.load_env_file(tmp_path / "missing.env")


@pytest.mark.parametrize("vals,confirm", [
    (_env(DB_NAME="aayna_release_test"), None),
    (_env(DB_NAME="aayna_dev"), None),
    (_env(), "aayna_dev"),                                                      # wrong confirmation
    (_env(MONGO_URL="mongodb+srv://admin:x@cluster.example.test/"), None),      # not the app user
    (_env(MONGO_URL="https://cluster.example.test"), None),
])
def test_target_guard_refuses(vals, confirm):
    with pytest.raises(pci.Stop):
        pci.check_target(vals, confirm)


def test_target_guard_accepts_app_user_on_aayna_prod():
    assert pci.check_target(_env(), "aayna_prod") == "cluster.example.test"


def test_redact_never_shows_credentials():
    msg = f"failed to connect to {FAKE_URL} and mongodb://u:p@h/db"
    r = pci.redact(msg, _env())
    assert "not-a-real-password" not in r and "u:p@" not in r


def _info(products=(), cats=("earrings", "necklaces", "rings", "bracelets"), status="active"):
    return {"categories": [{"slug": s, "status": status} for s in cats], "products": list(products)}


def test_preflight_db_rules():
    assert pci.preflight_db(_info()) == []
    assert any("missing categories" in p for p in pci.preflight_db(_info(cats=("earrings",))))
    assert any("not active" in p for p in pci.preflight_db(_info(status="inactive")))
    foreign = [{"sku": "DEMO-1", "source": {}}]
    assert any("other products" in p for p in pci.preflight_db(_info(products=foreign)))
    ours = [{"sku": "AYN-RNG-CLS-GLD", "source": {"type": "inventory_xlsx"}}]
    assert any("already exist" in p for p in pci.preflight_db(_info(products=ours)))
    assert pci.preflight_db(_info(products=ours), allow_existing_import=True) == []
    dup = ours * 2
    assert any("duplicate" in p for p in pci.preflight_db(_info(products=dup), allow_existing_import=True))


def _seed(db):
    gallery = json.loads((ROOT / "frontend/src/data/productGallery.json").read_text(encoding="utf-8"))["products"]
    db.categories.insert_many([{"slug": s, "name": s.title(), "status": "active"}
                               for s in ("earrings", "necklaces", "rings", "bracelets")])
    man = {"products": []}
    for i, (sku, price) in enumerate(pci.CONFIRMED_PRICES.items()):
        cat = {"NKL": "necklaces", "EAR": "earrings", "RNG": "rings"}.get(sku.split("-")[1], "bracelets")
        m = {"sku": sku, "stock_quantity": 3, "category_slug": cat, "source_row": 10 + i, "cost_price": 100,
             "color": "Golden", "size": "1"}
        man["products"].append(m)
        db.products.insert_one({"id": f"id{i}", "sku": sku, "slug": f"s{i}", "selling_price": price,
                                "discount_price": None, "stock_quantity": 3, "category_slug": cat,
                                "category_name": cat.title(), "status": "draft",
                                "source": {"type": "inventory_xlsx", "row": 10 + i}, "cost_price": 100.0,
                                "pricing": {"selling_price": price}, "images": [], "color": "Golden", "size": "1"})
        db.inventory_logs.insert_one({"product_id": f"id{i}", "change_type": "stock_in"})
        assert sku in gallery
    return man


def test_verify_records_and_idempotency_pass_on_correct_data():
    db = mongomock.MongoClient()["aayna_prod"]
    man = _seed(db)
    lines, problems = pci.verify_records(db, man)
    assert problems == [] and len(lines) == 10
    assert pci.verify_idempotent(db, man)[1] == []


def test_verify_records_catches_wrong_price_status_duplicates_and_images():
    db = mongomock.MongoClient()["aayna_prod"]
    man = _seed(db)
    db.products.update_one({"sku": "AYN-BRC-FLR-GLD"}, {"$set": {"selling_price": 1302}})
    db.products.update_one({"sku": "AYN-RNG-CLS-GLD"}, {"$set": {"status": "active"}})
    db.products.update_one({"sku": "AYN-EAR-CHK-GLD"}, {"$set": {"images": [{"image_url": "x"}]}})
    db.products.insert_one({"sku": "AYN-NKL-LUN-GLD", "slug": "dup"})
    _, problems = pci.verify_records(db, man)
    text = " ".join(problems)
    for expect in ("AYN-BRC-FLR-GLD: failed ['price'", "AYN-RNG-CLS-GLD: failed ['draft'", "no_db_images",
                   "AYN-NKL-LUN-GLD: 2 records", "products in database: 11"):
        assert expect in text
    assert any("duplicated" in p for p in pci.verify_idempotent(db, man)[1])


def test_confirmed_prices_match_the_pricing_doc():
    doc = (ROOT / "docs/audits/PRODUCT_PRICING_UPDATE.md").read_text(encoding="utf-8")
    for sku, price in pci.CONFIRMED_PRICES.items():
        assert f"| {sku} |" in doc and f"৳{price:,}" in doc.split(f"| {sku} |")[1].split("\n")[0]


# --- scripts/admin_account.py (owner-run password reset) -------------------------------
def _acct():
    spec2 = importlib.util.spec_from_file_location("admin_account", ROOT / "scripts" / "admin_account.py")
    m = importlib.util.module_from_spec(spec2)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec2.loader.exec_module(m)
    return m


def test_admin_password_reset_hashes_and_signs_out(monkeypatch):
    import bcrypt
    acct = _acct()
    db = mongomock.MongoClient()["aayna_prod"]
    db.users.insert_one({"id": "u1", "email": "owner@example.test", "role": "super_admin", "status": "active",
                         "password_hash": "old", "session_version": 2})
    answers = iter(["a-new-strong-password", "a-new-strong-password"])
    monkeypatch.setattr(acct.getpass, "getpass", lambda prompt="": next(answers))
    acct.set_password(db, " Owner@Example.test ")
    u = db.users.find_one({"id": "u1"})
    assert bcrypt.checkpw(b"a-new-strong-password", u["password_hash"].encode()) and u["session_version"] == 3
    assert u["role"] == "super_admin" and u["status"] == "active"


@pytest.mark.parametrize("pw1,pw2", [("short", "short"), ("a-new-strong-password", "different-password-1")])
def test_admin_password_reset_refuses_bad_input(monkeypatch, pw1, pw2):
    acct = _acct()
    db = mongomock.MongoClient()["aayna_prod"]
    db.users.insert_one({"id": "u1", "email": "owner@example.test", "role": "super_admin", "password_hash": "old"})
    answers = iter([pw1, pw2])
    monkeypatch.setattr(acct.getpass, "getpass", lambda prompt="": next(answers))
    with pytest.raises(acct.Stop):
        acct.set_password(db, "owner@example.test")
    assert db.users.find_one({"id": "u1"})["password_hash"] == "old"
    with pytest.raises(acct.Stop):
        acct.set_password(db, "nobody@example.test")

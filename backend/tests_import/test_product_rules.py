"""Offline tests: product status/stock rules and validation (admin_routes)."""
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://mock")
os.environ.setdefault("DB_NAME", "aayna_import_test")

from admin_routes import status_for_stock, validate_product_fields  # noqa: E402


@pytest.mark.parametrize("current,stock,expected", [
    ("active", 0, "out_of_stock"), ("active", 3, "active"),
    ("out_of_stock", 2, "active"), ("out_of_stock", 0, "out_of_stock"),
    ("draft", 0, "draft"), ("draft", 9, "draft"),
    ("inactive", 0, "inactive"), ("inactive", 4, "inactive"),
])
def test_status_for_stock_never_publishes_draft_or_inactive(current, stock, expected):
    assert status_for_stock(current, stock) == expected


OK = {"selling_price": 500, "discount_price": None, "stock_quantity": 3, "low_stock_alert": 3, "status": "active"}


@pytest.mark.parametrize("bad", [
    {"selling_price": 0}, {"selling_price": -1}, {"selling_price": None},
    {"discount_price": 500}, {"discount_price": 700}, {"discount_price": -5},
    {"stock_quantity": -1}, {"low_stock_alert": -1}, {"status": "published"}, {"status": None},
])
def test_invalid_product_fields_rejected(bad):
    with pytest.raises(HTTPException):
        validate_product_fields({**OK, **bad})


@pytest.mark.parametrize("good", [{}, {"discount_price": 0}, {"discount_price": 450}, {"status": "draft", "stock_quantity": 0}])
def test_valid_product_fields_accepted(good):
    validate_product_fields({**OK, **good})

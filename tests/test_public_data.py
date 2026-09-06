"""Invariants on the committed snapshot. These run in CI on every push, so an
accidental rebuild that leaked an email or a raw customer id fails the build."""
import json
import re

# Product titles legitimately contain "@" ("Only @ Target"); what must never appear is an address.
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

import pytest

from recsys.data import PUBLIC_DIR, read_jsonl

ORDERS = PUBLIC_DIR / "orders.jsonl"
PRODUCTS = PUBLIC_DIR / "products.jsonl"
pytestmark = pytest.mark.skipif(not ORDERS.exists(), reason="no public snapshot built")


def test_orders_carry_only_the_allowed_fields_and_nothing_identifying():
    hexish = re.compile(r"^[0-9a-f]{16}$")
    for o in read_jsonl(ORDERS):
        assert set(o) == {"order_id", "date", "source", "customer", "items"}
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", o["date"])
        assert o["source"] in {"pos", "web", "app", "draft", "other"}
        assert o["customer"] is None or hexish.match(o["customer"])
        assert o["items"], "empty basket in public data"
        for i in o["items"]:
            assert set(i) == {"variant_id", "product_id", "title", "quantity", "unit_price"}
            assert isinstance(i["variant_id"], int) and i["quantity"] >= 1
        assert not EMAIL.search(json.dumps(o))


def test_products_carry_only_catalog_fields():
    for p in read_jsonl(PRODUCTS):
        assert set(p) == {"variant_id", "product_id", "title", "tags", "price", "created_at", "status", "image_url"}
        assert not EMAIL.search(json.dumps(p))


def test_orders_are_in_date_order_with_sequential_ids():
    prev_id, prev_date = 0, ""
    for o in read_jsonl(ORDERS):
        assert o["order_id"] == prev_id + 1 and o["date"] >= prev_date
        prev_id, prev_date = o["order_id"], o["date"]

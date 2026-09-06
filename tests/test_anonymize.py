import json

from recsys.data.anonymize import (anonymize_orders, coarse_source, flatten_products, gid_number,
                                   hash_customer, load_or_create_salt)


def test_customer_hash_is_stable_keyed_and_short():
    a = hash_customer("gid://shopify/Customer/1", "salt-a")
    assert a == hash_customer("gid://shopify/Customer/1", "salt-a")
    assert a != hash_customer("gid://shopify/Customer/1", "salt-b")
    assert len(a) == 16 and hash_customer(None, "salt-a") is None


def test_salt_created_once_then_reused(tmp_path):
    p = tmp_path / "salt.txt"
    s1 = load_or_create_salt(p)
    assert len(s1) == 64 and load_or_create_salt(p) == s1


def test_gid_and_source_mapping():
    assert gid_number("gid://shopify/ProductVariant/4567") == 4567 and gid_number(None) is None
    assert coarse_source("pos") == "pos" and coarse_source("web") == "web"
    assert coarse_source("shopify_draft_order") == "draft"
    assert coarse_source("3890849") == "app" and coarse_source("subscription_contract_checkout_one") == "other"
    assert coarse_source(None) == "other"


def test_anonymized_order_carries_nothing_identifying():
    raw = [{"id": "gid://shopify/Order/9", "name": "#1009", "created_at": "2026-03-04T15:22:00Z",
            "source_name": "web", "email": "someone@example.com", "customer_id": "gid://shopify/Customer/77",
            "line_items": [{"variant_id": "gid://shopify/ProductVariant/1", "product_id": "gid://shopify/Product/2",
                            "title": "Thing #1", "quantity": 2, "discounted_unit_price": 9.5, "sku": "X"}]}]
    row = anonymize_orders(raw, "salt")[0]
    assert set(row) == {"order_id", "date", "source", "customer", "items"}
    assert row["date"] == "2026-03-04" and row["source"] == "web"
    assert "@" not in json.dumps(row) and "1009" not in json.dumps(row) and "Customer/77" not in json.dumps(row)
    assert set(row["items"][0]) == {"variant_id", "product_id", "title", "quantity", "unit_price"}


def test_order_ids_are_sequential_in_time_order():
    raw = [{"id": "b", "created_at": "2026-02-01T00:00:00Z", "line_items": []},
           {"id": "a", "created_at": "2026-01-01T00:00:00Z", "line_items": []}]
    rows = anonymize_orders(raw, "s")
    assert [(r["order_id"], r["date"]) for r in rows] == [(1, "2026-01-01"), (2, "2026-02-01")]


def test_flatten_products_one_row_per_variant_with_variant_title_appended():
    p = [{"id": "gid://shopify/Product/2", "title": "Bag", "tags": ["b", "a"], "status": "ACTIVE",
          "image_url": "https://cdn/x.jpg",
          "variants": [{"id": "gid://shopify/ProductVariant/1", "title": "Default Title", "price": 5.0, "created_at": "2026-01-01T00:00:00Z"},
                       {"id": "gid://shopify/ProductVariant/3", "title": "Red", "price": 6.0, "created_at": "2026-01-02T00:00:00Z"}]}]
    rows = flatten_products(p)
    assert [r["title"] for r in rows] == ["Bag", "Bag - Red"]
    assert rows[0]["tags"] == ["a", "b"] and rows[0]["created_at"] == "2026-01-01"

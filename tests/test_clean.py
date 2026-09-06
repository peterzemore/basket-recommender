from recsys.data.clean import clean_orders


def order(**kw):
    base = {"id": "gid://shopify/Order/1", "name": "#1", "created_at": "2026-01-02T10:00:00Z",
            "cancelled_at": None, "test": False, "source_name": "pos", "email": None,
            "customer_id": None, "line_items": []}
    return {**base, **kw}


def line(variant="gid://shopify/ProductVariant/10", title="Thing #1", qty=1, refunded=0):
    return {"id": f"gid://shopify/LineItem/{(variant or 'none')[-2:]}{qty}{title[:3]}", "title": title, "quantity": qty, "sku": "",
            "variant_id": variant, "product_id": "gid://shopify/Product/5",
            "original_unit_price": 12.0, "discounted_unit_price": 10.0, "refunded_quantity": refunded}


def test_tip_and_null_variant_lines_are_dropped_but_order_survives():
    o = order(line_items=[line(), line(variant=None, title="Tip"), line(variant=None, title="Mercari custom")])
    kept, stats = clean_orders([o])
    assert len(kept) == 1 and len(kept[0]["line_items"]) == 1
    assert stats["dropped_line_no_variant"] == 2


def test_order_with_only_junk_lines_is_dropped():
    kept, stats = clean_orders([order(line_items=[line(variant=None, title="Tip")])])
    assert kept == [] and stats["dropped_order_no_lines_left"] == 1


def test_owner_orders_excluded_case_insensitively():
    kept, stats = clean_orders([order(email="Owner@Example.com", line_items=[line()])], {"owner@example.com"})
    assert kept == [] and stats["dropped_excluded_email_order"] == 1


def test_test_and_cancelled_orders_dropped():
    kept, stats = clean_orders([order(test=True, line_items=[line()]),
                                order(cancelled_at="2026-01-03T00:00:00Z", line_items=[line()])])
    assert kept == []
    assert stats["dropped_test_order"] == 1 and stats["dropped_cancelled_order"] == 1


def test_refunds_reduce_quantity_and_full_refund_drops_line():
    o = order(line_items=[line(qty=3, refunded=1), line(variant="gid://shopify/ProductVariant/11", qty=1, refunded=1)])
    kept, stats = clean_orders([o])
    assert [li["quantity"] for li in kept[0]["line_items"]] == [2]
    assert stats["lines_partially_refunded"] == 1 and stats["dropped_line_fully_refunded"] == 1


def test_duplicate_variant_lines_merge():
    o = order(line_items=[line(qty=1), line(qty=2)])
    kept, stats = clean_orders([o])
    assert len(kept[0]["line_items"]) == 1 and kept[0]["line_items"][0]["quantity"] == 3
    assert stats["lines_merged_duplicate_variant"] == 1


def test_input_not_mutated():
    o = order(line_items=[line(qty=1), line(qty=2)])
    clean_orders([o])
    assert len(o["line_items"]) == 2 and o["line_items"][0]["quantity"] == 1

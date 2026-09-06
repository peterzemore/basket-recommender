from recsys.data.report import compute, to_markdown


def test_report_on_tiny_snapshot():
    orders = [
        {"order_id": 1, "date": "2026-01-01", "source": "pos", "customer": None,
         "items": [{"variant_id": 1, "product_id": 1, "title": "A", "quantity": 1, "unit_price": 1.0}]},
        {"order_id": 2, "date": "2026-02-01", "source": "web", "customer": "c1",
         "items": [{"variant_id": 1, "product_id": 1, "title": "A", "quantity": 1, "unit_price": 1.0},
                   {"variant_id": 2, "product_id": 2, "title": "B", "quantity": 2, "unit_price": 1.0}]},
        {"order_id": 3, "date": "2026-03-01", "source": "web", "customer": "c1",
         "items": [{"variant_id": 3, "product_id": 3, "title": "C", "quantity": 1, "unit_price": 1.0}]},
    ]
    products = [{"variant_id": 1, "product_id": 1, "title": "A", "tags": ["x"], "price": 1.0, "created_at": "2025-12-01", "status": "ACTIVE", "image_url": None},
                {"variant_id": 2, "product_id": 2, "title": "B", "tags": [], "price": 1.0, "created_at": "2025-12-01", "status": "ACTIVE", "image_url": None}]
    s = compute(orders, products, cold_days=90)
    assert s["orders"] == 3 and s["months"] == 3
    assert s["multi_item_orders"] == 1 and s["unique_customers"] == 1 and s["repeat_customers"] == 1
    assert s["distinct_variants_sold"] == 3 and s["variants_sold_once_pct"] == "67%"
    assert s["sold_variants_still_in_catalog_pct"] == "67%" and s["tag_coverage"] == "50%"
    md = to_markdown(s)
    assert md.startswith("| | |") and "| Orders |" in md

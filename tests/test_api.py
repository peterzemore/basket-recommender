"""The API against a tiny in-memory snapshot, plus a stock filter with an injected cache."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from recsys.serve import DEFAULT_CONFIG, Recommender, app
from recsys.stock import StockCache


def basket(oid, d, vids):
    return {"order_id": oid, "date": d, "source": "pos", "customer": None,
            "items": [{"variant_id": v, "product_id": v, "title": str(v), "quantity": 1, "unit_price": 1.0} for v in vids]}


def product(v, title, tags, price, status="ACTIVE"):
    return {"variant_id": v, "product_id": v, "title": title, "tags": tags, "price": price,
            "created_at": "2025-01-01", "status": status, "image_url": f"https://cdn/{v}.jpg"}


PRODUCTS = [product(1, "Iron Man #1", ["Marvel"], 12.0), product(2, "Thor #2", ["Marvel"], 12.0),
            product(3, "Naruto #3", ["Anime"], 12.0), product(4, "Sasuke #4", ["Anime"], 12.0),
            product(5, "Hulk #5 (new)", ["Marvel"], 12.0), product(6, "Loki #6 archived", ["Marvel"], 12.0, status="ARCHIVED")]
ORDERS = [basket(1, "2026-01-01", [1, 2]), basket(2, "2026-01-02", [3, 4]), basket(3, "2026-01-03", [1, 2]),
          basket(4, "2026-01-04", [2, 1]), basket(5, "2026-01-05", [3, 4])]


@pytest.fixture
def client():
    rec = Recommender(ORDERS, PRODUCTS, DEFAULT_CONFIG)
    app.state.rec, app.state.config_source = rec, "test"
    app.state.stock = StockCache()
    app.state.stock.enabled = False
    return TestClient(app)


def test_health_reports_provenance(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["fitted_on"]["orders"] == 5 and h["fitted_on"]["through"] == "2026-01-05"
    assert h["stock"]["enabled"] is False and h["stock"]["variants_known"] == 0


def test_recommend_excludes_context_and_archived_and_explains(client):
    r = client.get("/recommend", params={"variant_ids": "1", "k": 10}).json()
    ids = [x["variant_id"] for x in r["recommendations"]]
    assert 1 not in ids and 6 not in ids, "context and archived items are never recommended"
    assert ids[0] == 2, "the repeatedly co-bought Marvel Pop ranks first"
    assert 5 in ids and ids.index(5) < ids.index(3), "a never-sold Marvel Pop outranks anime, via content"
    assert r["stock_filter_applied"] is False and all(x["in_stock"] is None for x in r["recommendations"])
    assert "why" in r["recommendations"][0] and r["recommendations"][0]["why"]


def test_stock_filter_is_hard_when_stock_is_known(client):
    app.state.stock.quantities = {2: 0, 3: 4, 4: 1, 5: 2}
    r = client.get("/recommend", params={"variant_ids": "1", "k": 10}).json()
    ids = [x["variant_id"] for x in r["recommendations"]]
    assert r["stock_filter_applied"] is True and 2 not in ids and ids[0] == 5
    assert all(x["in_stock"] is True for x in r["recommendations"])
    r = client.get("/recommend", params={"variant_ids": "1", "k": 10, "in_stock": "false"}).json()
    assert [x["variant_id"] for x in r["recommendations"]][0] == 2 and r["stock_filter_applied"] is False


def test_similar_and_search_work_for_never_sold_items(client):
    s = client.get("/similar/5").json()
    assert s["item"]["variant_id"] == 5 and s["similar"][0]["variant_id"] in (1, 2)
    hits = client.get("/search", params={"q": "hulk"}).json()
    assert [h["variant_id"] for h in hits] == [5]


def test_unknown_and_malformed_ids(client):
    assert client.get("/recommend", params={"variant_ids": "999"}).status_code == 404
    assert client.get("/recommend", params={"variant_ids": "a,b"}).status_code == 422
    assert client.get("/recommend", params={"variant_ids": ""}).status_code == 422

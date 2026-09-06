"""The dashboard renders from the same Recommender the API uses."""
import pytest
from fastapi.testclient import TestClient

from recsys.serve import DEFAULT_CONFIG, Recommender, app
from recsys.stock import StockCache
from tests.test_api import ORDERS, PRODUCTS


@pytest.fixture
def client():
    app.state.rec, app.state.config_source = Recommender(ORDERS, PRODUCTS, DEFAULT_CONFIG), "test"
    app.state.stock = StockCache(); app.state.stock.enabled = False
    return TestClient(app)


def test_empty_page_invites_action(client):
    html = client.get("/").text
    assert "In the basket" in html and "Add what the customer is holding" in html
    assert "No stock feed" in html


def test_basket_page_shows_tiles_suggestions_and_comparison(client):
    html = client.get("/", params={"ids": "1", "in_stock": 0}).text
    assert 'class="num">1<' in html, "the Pop number is the tile"
    assert "Thor #2" in html and "never sold here yet" in html, "the cold Marvel Pop is suggested and labelled"
    assert "The same basket, model by model" in html and "Selling now" in html and "Looks alike" in html
    assert "Loki #6 archived" not in html.split("Suggest next")[-1].split("model by model")[0]


def test_remove_link_drops_only_that_item(client):
    html = client.get("/", params={"ids": "1,2", "in_stock": 0}).text
    assert 'href="/?ids=2&in_stock=0"' in html and 'href="/?ids=1&in_stock=0"' in html


def test_live_search_partial_and_unknown_ids_are_ignored(client):
    frag = client.get("/ui/search", params={"q": "thor", "ids": "1", "in_stock": 1}).text
    assert 'href="/?ids=1,2&in_stock=1"' in frag and "#2" in frag
    assert client.get("/ui/search", params={"q": "t"}).text.strip() == ""
    assert client.get("/", params={"ids": "999,abc"}).status_code == 200


def test_stock_filter_reflected_in_page(client):
    app.state.stock.quantities = {2: 0, 3: 4, 4: 1, 5: 2}
    html = client.get("/", params={"ids": "1", "in_stock": 1}).text
    assert "Stock synced" not in html and "in stock" in html
    top = html.split('class="sug"')[1].split("</ol>")[0]
    assert "Thor #2" not in top and "Hulk #5" in top

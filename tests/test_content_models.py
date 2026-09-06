import numpy as np

from recsys.eval.index import Index
from recsys.features import build_features, item_tokens, price_band
from recsys.models import AttributeCooccurrence, ContentCosine, Hybrid, ItemItem, Popularity


def basket(oid, d, vids):
    return {"order_id": oid, "date": d, "source": "pos", "customer": None,
            "items": [{"variant_id": v, "product_id": v, "title": str(v), "quantity": 1, "unit_price": 1.0} for v in vids]}


def product(v, title, tags, price, created="2025-01-01"):
    return {"variant_id": v, "product_id": v, "title": title, "tags": tags, "price": price,
            "created_at": created, "status": "ACTIVE", "image_url": None}


PRODUCTS = [
    product(1, "Iron Man #1 (Target Exclusive)", ["Marvel", "Funko Pops!"], 12.0),
    product(2, "Thor #2 Chase", ["Marvel", "Funko Pops!"], 12.0),
    product(3, "Naruto #3 Glows in the Dark", ["Anime", "Funko Pops!"], 12.0),
    product(4, "Sasuke #4", ["Anime", "Funko Pops!"], 12.0),
    product(5, "Stitch mini backpack", ["Disney", "Loungefly"], 80.0),
    product(6, "Captain America #6 (new)", ["Marvel", "Funko Pops!"], 12.0, created="2026-06-01"),  # never sold: cold
]
ORDERS = [basket(1, "2026-01-01", [1, 2]), basket(2, "2026-01-02", [3, 4]), basket(3, "2026-01-03", [1, 2]),
          basket(4, "2026-01-04", [3, 4]), basket(5, "2026-01-05", [1, 5]), basket(6, "2026-01-06", [2, 1])]


def test_tokens_parse_tags_keywords_and_price_band():
    toks = item_tokens(PRODUCTS[0])
    assert "tag:marvel" in toks and "kw:exclusive" in toks and "price:10-15" in toks
    assert "kw:chase" in item_tokens(PRODUCTS[1]) and "kw:glow" in item_tokens(PRODUCTS[2])
    assert price_band(80.0) == "50-100" and price_band(9.99) == "<10" and price_band(250) == "100+"


def test_feature_rows_are_unit_length_and_common_tags_weigh_less():
    ix = Index(ORDERS, PRODUCTS)
    f = build_features(PRODUCTS, ix)
    assert np.allclose(np.linalg.norm(f.X, axis=1), 1.0)
    j_pops, j_marvel = f.vocab.index("tag:funko pops!"), f.vocab.index("tag:marvel")
    assert f.idf[j_pops] < f.idf[j_marvel], "a tag on most items must carry less weight"


def test_content_cosine_scores_a_never_sold_item_by_its_attributes():
    ix = Index(ORDERS, PRODUCTS)
    f = build_features(PRODUCTS, ix)
    m = ContentCosine(f).fit(ORDERS, ix)
    s = m.scores((ix.idx[1],), "2026-07-01")           # context: Iron Man (Marvel, $12)
    assert s[ix.idx[6]] > s[ix.idx[3]] > 0, "cold Marvel Pop outranks an anime Pop"
    assert s[ix.idx[6]] > s[ix.idx[5]], "and outranks a Loungefly bag"
    assert ix.idx[6] not in m.seen


def test_attribute_cooccurrence_learns_marvel_with_marvel_and_scores_the_cold_item():
    ix = Index(ORDERS, PRODUCTS)
    f = build_features(PRODUCTS, ix)
    m = AttributeCooccurrence(f, min_count=1).fit(ORDERS, ix)
    j_m = f.vocab.index("tag:marvel"); j_a = f.vocab.index("tag:anime")
    assert m.M[j_m, j_m] > 0 and m.M[j_a, j_a] > 0
    assert m.M[j_m, j_a] == 0, "marvel and anime never share a basket here"
    s = m.scores((ix.idx[2],), "2026-07-01")            # context: Thor
    assert s[ix.idx[6]] > 0 and s[ix.idx[6]] > s[ix.idx[4]]


def test_attribute_min_count_zeroes_rare_cells():
    ix = Index(ORDERS, PRODUCTS)
    f = build_features(PRODUCTS, ix)
    loose = AttributeCooccurrence(f, min_count=1).fit(ORDERS, ix)
    strict = AttributeCooccurrence(f, min_count=50).fit(ORDERS, ix)
    assert loose.M.sum() > 0 and strict.M.sum() == 0


def test_itemitem_cosine_and_lift_prefer_the_repeated_pair():
    ix = Index(ORDERS, PRODUCTS)
    for sim in ("cosine", "lift"):
        m = ItemItem(sim, shrink=1.0).fit(ORDERS, ix)
        s = m.scores((ix.idx[1],), "2026-07-01")
        assert s[ix.idx[2]] > s[ix.idx[5]] > 0 and s[ix.idx[3]] == 0


def test_unshrunk_lift_cannot_tell_a_pair_seen_once_from_one_seen_three_times():
    """The reason shrinkage exists: (1,2) co-occurs 3x, (1,5) once, and raw lift ties them."""
    ix = Index(ORDERS, PRODUCTS)
    s = ItemItem("lift", shrink=0.0).fit(ORDERS, ix).scores((ix.idx[1],), "2026-07-01")
    assert s[ix.idx[2]] == s[ix.idx[5]]
    s = ItemItem("lift", shrink=1.0).fit(ORDERS, ix).scores((ix.idx[1],), "2026-07-01")
    assert s[ix.idx[2]] > s[ix.idx[5]]
    loose = ItemItem("cosine", shrink=0.0).fit(ORDERS, ix).scores((ix.idx[1],), "2026-07-01")[ix.idx[2]]
    tight = ItemItem("cosine", shrink=10.0).fit(ORDERS, ix).scores((ix.idx[1],), "2026-07-01")[ix.idx[2]]
    assert tight < loose


def test_hybrid_scales_components_and_reaches_cold_items():
    ix = Index(ORDERS, PRODUCTS)
    f = build_features(PRODUCTS, ix)
    item = ItemItem("cosine").fit(ORDERS, ix)
    content = ContentCosine(f).fit(ORDERS, ix)
    h = Hybrid([(item, 1.0), (content, 1.0)]).fit(ORDERS, ix)
    s = h.scores((ix.idx[1],), "2026-07-01")
    assert s[ix.idx[2]] > s[ix.idx[6]] > s[ix.idx[3]], "warm pair first, cold Marvel next, anime last"
    assert s.max() <= 2.0 + 1e-5
    only_item = Hybrid([(item, 1.0), (content, 0.0)]).fit(ORDERS, ix)
    assert len(only_item.components) == 1

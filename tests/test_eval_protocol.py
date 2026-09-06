"""The protocol, held to. These tests are the leakage guards."""
import numpy as np
import pytest

from recsys.eval.bootstrap import basket_bootstrap, paired_difference
from recsys.eval.index import Index
from recsys.eval.metrics import expected_rank, hit, ndcg, reciprocal_rank, top_k
from recsys.eval.queries import make_queries
from recsys.eval.split import split_orders
from recsys.models import CoPurchase, Popularity


def basket(oid, d, items, source="pos", customer=None):
    return {"order_id": oid, "date": d, "source": source, "customer": customer,
            "items": [{"variant_id": v, "product_id": v, "title": str(v), "quantity": q, "unit_price": 1.0}
                      for v, q in items]}


def product(v, created):
    return {"variant_id": v, "product_id": v, "title": str(v), "tags": [], "price": 1.0,
            "created_at": created, "status": "ACTIVE", "image_url": None}


ORDERS = [
    basket(1, "2026-01-10", [(1, 1), (2, 1)]),
    basket(2, "2026-02-10", [(1, 1), (2, 2), (3, 1)]),
    basket(3, "2026-04-15", [(2, 1), (4, 1)]),        # val
    basket(4, "2026-06-20", [(1, 1), (5, 1)], "web"), # test; 5 is cold
    basket(5, "2026-07-01", [(9, 1)]),                # test, single item -> no query
]
PRODUCTS = [product(1, "2025-12-01"), product(2, "2025-12-01"), product(3, "2026-01-01"),
            product(4, "2026-04-01"), product(5, "2026-06-01"), product(9, "2026-06-30"),
            product(7, "2026-08-01")]  # 7 is listed after every basket: never a candidate


def test_split_is_by_date_and_disjoint():
    tr, va, te = split_orders(ORDERS)
    assert [o["order_id"] for o in tr] == [1, 2] and [o["order_id"] for o in va] == [3]
    assert [o["order_id"] for o in te] == [4, 5]
    assert max(o["date"] for o in tr) <= "2026-03-31" < min(o["date"] for o in va)
    assert max(o["date"] for o in va) <= "2026-05-31" < min(o["date"] for o in te)


def test_candidates_exclude_future_items_and_the_context():
    ix = Index(ORDERS, PRODUCTS)
    m = ix.candidates("2026-06-20", exclude=(ix.idx[1],))
    assert not m[ix.idx[7]], "listed 2026-08-01, must not be a candidate in June"
    assert not m[ix.idx[9]], "first exists 2026-06-30, must not be a candidate on 06-20"
    assert not m[ix.idx[1]], "context item excluded"
    assert m[ix.idx[5]] and m[ix.idx[2]]


def test_availability_is_earlier_of_listing_and_first_sale():
    ix = Index([basket(1, "2026-01-05", [(4, 1)])], [product(4, "2026-04-01")])
    assert ix.candidates("2026-01-05")[ix.idx[4]]
    assert not ix.candidates("2026-01-04")[ix.idx[4]]


def test_every_item_takes_a_turn_and_single_item_baskets_make_no_query():
    ix = Index(ORDERS, PRODUCTS)
    qs = make_queries([ORDERS[1], ORDERS[4]], ix)
    assert len(qs) == 3 and all(q.basket_id == 2 for q in qs)
    assert {q.target for q in qs} == {ix.idx[1], ix.idx[2], ix.idx[3]}
    assert all(len(q.context) == 2 and q.target not in q.context for q in qs)


def test_model_fit_on_train_knows_nothing_about_test_items():
    tr, _, te = split_orders(ORDERS)
    ix = Index(ORDERS, PRODUCTS)
    pop = Popularity().fit(tr, ix)
    assert pop.counts[ix.idx[5]] == 0 and ix.idx[5] not in pop.seen
    assert ix.idx[1] in pop.seen


def test_expected_rank_handles_ties_symmetrically():
    scores = np.array([5.0, 3.0, 3.0, 3.0, 1.0, 0.0])
    cands = np.array([True, True, True, True, True, False])  # last one not a candidate
    assert expected_rank(scores, cands, 0) == 1.0
    assert expected_rank(scores, cands, 2) == 3.0          # tied 2nd-4th -> 3
    assert expected_rank(scores, cands, 4) == 5.0
    assert hit(3.0, 5) == 1.0 and hit(10.5, 10) == 0.0
    assert ndcg(1.0, 10) == 1.0 and ndcg(11.0, 10) == 0.0 and 0 < ndcg(3.0, 10) < 1
    assert reciprocal_rank(4.0) == 0.25


def test_top_k_is_deterministic_under_ties():
    scores = np.array([1.0, 2.0, 2.0, 0.0])
    cands = np.array([True, True, True, True])
    assert top_k(scores, cands, 2) == [1, 2]
    assert top_k(scores, np.array([True, False, True, True]), 2) == [2, 0]


def test_copurchase_scores_pairs_and_respects_min_support():
    tr, _, _ = split_orders(ORDERS)
    ix = Index(ORDERS, PRODUCTS)
    m1 = CoPurchase(min_support=1).fit(tr, ix)
    s = m1.scores((ix.idx[1],), "2026-06-20")
    assert s[ix.idx[2]] == 2 and s[ix.idx[3]] == 1 and s[ix.idx[5]] == 0
    m3 = CoPurchase(min_support=3).fit(tr, ix)
    assert m3.scores((ix.idx[1],), "2026-06-20").sum() == 0


def test_pop_tiebreak_only_reorders_within_ties():
    tr, _, _ = split_orders(ORDERS)
    ix = Index(ORDERS, PRODUCTS)
    s = CoPurchase(min_support=1, pop_tiebreak=True).fit(tr, ix).scores((ix.idx[1],), "2026-06-20")
    assert s[ix.idx[2]] > s[ix.idx[3]] > s[ix.idx[5]] >= 0
    assert s[ix.idx[3]] - 1.0 < 1e-5, "tiebreak must be negligible next to a real pair count"


def test_bootstrap_interval_contains_mean_and_is_seeded():
    vals = np.array([1, 0, 1, 1, 0, 0, 1, 1], dtype=float)
    ids = np.array([1, 1, 2, 2, 3, 3, 4, 4])
    m, lo, hi = basket_bootstrap(vals, ids, n_boot=500, seed=1)
    assert lo <= m <= hi and m == 0.625
    assert basket_bootstrap(vals, ids, n_boot=500, seed=1) == (m, lo, hi)
    d, dlo, dhi = paired_difference(vals, vals, ids, n_boot=200, seed=0)
    assert d == 0.0 and dlo == 0.0 and dhi == 0.0

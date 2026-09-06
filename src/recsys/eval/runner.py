"""Run models over queries, summarize with cluster-bootstrap intervals and segments."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from recsys.models.base import Model
from .bootstrap import basket_bootstrap, paired_difference
from .index import Index
from .metrics import expected_rank, hit, ndcg, reciprocal_rank, top_k
from .queries import Query

K_TOP = 10


@dataclass
class QueryResult:
    basket_id: int
    date: str
    source: str
    context_size: int
    target: int
    target_warm: bool
    rank: float
    hit5: float
    hit10: float
    ndcg10: float
    rr: float
    n_scored: int              # candidates with a positive score: did the model have anything to say?
    top10: list[int]


def run(model: Model, queries: list[Query], index: Index) -> list[QueryResult]:
    out = []
    for q in queries:
        cands = index.candidates(q.date, q.context)
        assert cands[q.target], "target must be a candidate: it was in the basket, so it existed"
        s = model.scores(q.context, q.date)
        r = expected_rank(s, cands, q.target)
        out.append(QueryResult(q.basket_id, q.date, q.source, len(q.context), q.target,
                               q.target in model.seen, r, hit(r, 5), hit(r, 10), ndcg(r, 10),
                               reciprocal_rank(r), int((s[cands] > 0).sum()), top_k(s, cands, K_TOP)))
    return out


def _arr(results: list[QueryResult], field: str) -> np.ndarray:
    return np.array([getattr(r, field) for r in results], dtype=float)


def summarize(results: list[QueryResult], index: Index, train_pop: np.ndarray, n_boot: int, seed: int) -> dict:
    baskets = np.array([r.basket_id for r in results])
    out: dict = {"n_queries": len(results), "n_baskets": int(np.unique(baskets).size)}
    for f in ("hit5", "hit10", "ndcg10", "rr"):
        m, lo, hi = basket_bootstrap(_arr(results, f), baskets, n_boot, seed)
        out[f] = {"mean": m, "lo": lo, "hi": hi}

    out["answered"] = float(np.mean([r.n_scored >= 1 for r in results]))
    out["cold_share"] = float(np.mean([not r.target_warm for r in results]))
    last = max(r.date for r in results)
    recommended = {v for r in results for v in r.top10}
    out["coverage10"] = len(recommended) / index.universe_on(last)
    p = (train_pop + 1.0) / (train_pop.sum() + train_pop.size)
    out["novelty10"] = float(np.mean([-np.log2(p[v]) for r in results for v in r.top10]))

    segs = {
        "target": {"warm": lambda r: r.target_warm, "cold": lambda r: not r.target_warm},
        "source": {"pos": lambda r: r.source == "pos", "online": lambda r: r.source != "pos"},
        "context": {"1 item": lambda r: r.context_size == 1, "2+ items": lambda r: r.context_size >= 2},
    }
    out["segments"] = {}
    for group, parts in segs.items():
        out["segments"][group] = {}
        for label, pred in parts.items():
            sub = [r for r in results if pred(r)]
            if sub:
                m, lo, hi = basket_bootstrap(_arr(sub, "hit10"), np.array([r.basket_id for r in sub]), n_boot, seed)
                out["segments"][group][label] = {"n": len(sub), "hit10": m, "lo": lo, "hi": hi}
    return out


def lift(results: list[QueryResult], baseline: list[QueryResult], n_boot: int, seed: int) -> dict:
    assert [r.target for r in results] == [r.target for r in baseline], "same queries required"
    baskets = np.array([r.basket_id for r in results])
    out = {}
    for f in ("hit10", "ndcg10"):
        d, lo, hi = paired_difference(_arr(results, f), _arr(baseline, f), baskets, n_boot, seed)
        out[f] = {"diff": d, "lo": lo, "hi": hi, "distinguishable": bool(lo > 0 or hi < 0)}
    return out


def to_rows(results: list[QueryResult]) -> list[dict]:
    return [asdict(r) for r in results]

"""Leave-one-out queries. Every item of every multi-item basket takes a turn as the
hidden target, with the rest as context. Queries from one basket are correlated,
which is why the bootstrap resamples baskets, not queries."""
from __future__ import annotations

from dataclasses import dataclass

from .index import Index


@dataclass(frozen=True)
class Query:
    basket_id: int
    date: str
    source: str
    context: tuple[int, ...]   # variant indices
    target: int                # variant index


def make_queries(baskets: list[dict], index: Index) -> list[Query]:
    out = []
    for b in baskets:
        items = sorted({index.idx[i["variant_id"]] for i in b["items"]})
        if len(items) < 2:
            continue
        for t in items:
            out.append(Query(b["order_id"], b["date"], b["source"],
                             tuple(x for x in items if x != t), t))
    return out

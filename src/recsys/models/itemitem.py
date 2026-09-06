"""Variant-level association with a similarity instead of a raw count. Shrinkage
keeps a pair seen once from looking like a law."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np

from recsys.eval.index import Index
from .base import Model


class ItemItem(Model):
    def __init__(self, similarity: str = "cosine", shrink: float = 5.0):
        super().__init__()
        assert similarity in ("cosine", "lift")
        self.similarity, self.shrink = similarity, shrink
        self.name = f"itemitem({similarity}, shrink={shrink:g})"
        self.sim: dict[int, dict[int, float]] = {}
        self._n = 0

    def fit(self, baskets: list[dict], index: Index) -> "ItemItem":
        self._mark_seen(baskets, index)
        self._n = index.n
        pair: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        n_item: dict[int, int] = defaultdict(int)
        n_baskets = 0
        for b in baskets:
            items = sorted({index.idx[i["variant_id"]] for i in b["items"]})
            n_baskets += 1
            for a in items:
                n_item[a] += 1
            for a, c in combinations(items, 2):
                pair[a][c] += 1
                pair[c][a] += 1
        self.sim = {}
        for a, nbrs in pair.items():
            self.sim[a] = {}
            for c, k in nbrs.items():
                if self.similarity == "cosine":
                    self.sim[a][c] = k / (np.sqrt(n_item[a] * n_item[c]) + self.shrink)
                else:
                    lift = k * n_baskets / (n_item[a] * n_item[c])
                    self.sim[a][c] = (k / (k + self.shrink)) * lift
        return self

    def scores(self, context: tuple[int, ...], on_date: str) -> np.ndarray:
        s = np.zeros(self._n)
        for a in context:
            for c, v in self.sim.get(a, {}).items():
                s[c] += v
        return s

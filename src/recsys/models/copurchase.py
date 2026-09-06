"""Co-purchase counts: how often each pair of variants appears in the same basket.

This is the store's production baseline - a port of the analysis its analytics agent
already runs, which counts pairs across multi-item orders and keeps those seen at
least `min_support` times. The production version keys on product titles for a
human-readable report; this one keys on variant ids, which is what the evaluation
ranks. A context of several items sums their pair counts.

`pop_tiebreak` adds a vanishing multiple of popularity so that among candidates
with equal co-purchase evidence - including the common case of none at all - the
more popular one ranks first. It changes ordering only inside tie blocks.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np

from recsys.eval.index import Index
from .base import Model
from .popularity import Popularity


class CoPurchase(Model):
    def __init__(self, min_support: int = 3, pop_tiebreak: bool = False):
        super().__init__()
        self.min_support = min_support
        self.pop_tiebreak = pop_tiebreak
        self.name = f"copurchase(min_support={min_support})" + ("+pop" if pop_tiebreak else "")
        self.pairs: dict[int, dict[int, float]] = {}
        self._pop: np.ndarray | None = None
        self._n = 0

    def fit(self, baskets: list[dict], index: Index) -> "CoPurchase":
        self._mark_seen(baskets, index)
        self._n = index.n
        counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for b in baskets:
            items = sorted({index.idx[i["variant_id"]] for i in b["items"]})
            for a, c in combinations(items, 2):
                counts[a][c] += 1
                counts[c][a] += 1
        self.pairs = {a: {c: n for c, n in nbrs.items() if n >= self.min_support} for a, nbrs in counts.items()}
        if self.pop_tiebreak:
            pop = Popularity().fit(baskets, index).counts
            self._pop = pop / (pop.max() or 1.0) * 1e-6
        return self

    def scores(self, context: tuple[int, ...], on_date: str) -> np.ndarray:
        s = np.zeros(self._n)
        for a in context:
            for c, n in self.pairs.get(a, {}).items():
                s[c] += n
        if self._pop is not None:
            s += self._pop
        return s

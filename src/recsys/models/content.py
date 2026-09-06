"""Content models. Neither needs a variant to have sold before; that is the point."""
from __future__ import annotations

import numpy as np

from recsys.eval.index import Index
from recsys.features import Features
from .base import Model


class ContentCosine(Model):
    """Sum of cosine similarities between each context item and the candidate, on
    idf-weighted tag / keyword / price-band vectors. Uses no basket data at all -
    the pure 'looks like what is in the basket' hypothesis."""
    name = "content_cosine"

    def __init__(self, features: Features):
        super().__init__()
        self.f = features

    def fit(self, baskets: list[dict], index: Index) -> "ContentCosine":
        self._mark_seen(baskets, index)   # only so warm/cold segments mean the same thing for every model
        return self

    def scores(self, context: tuple[int, ...], on_date: str) -> np.ndarray:
        v = self.f.X[list(context)].sum(axis=0)
        return (self.f.X @ v).astype(np.float64)


class AttributeCooccurrence(Model):
    """Which attributes go together in a basket, learned from baskets, applied to
    items that have never sold.

    For every pair of distinct items in a training basket, every feature of one is
    counted as co-occurring with every feature of the other. The matrix becomes
    positive pointwise mutual information - how much more often 'tag:marvel' sits
    next to 'tag:marvel' (or 'price:10-15' next to 'kw:chase') than chance - with
    cells seen fewer than `min_count` times zeroed as noise. A candidate is scored
    by how strongly its features are associated with the context's features.

    This is the model the purchasing pattern asks for: variants turn over in
    weeks, but 'anime buyers buy anime in twos' does not.
    """

    def __init__(self, features: Features, min_count: int = 2):
        super().__init__()
        self.f = features
        self.min_count = min_count
        self.name = f"attr_cooccurrence(min_count={min_count})"
        self.M: np.ndarray | None = None

    def fit(self, baskets: list[dict], index: Index) -> "AttributeCooccurrence":
        self._mark_seen(baskets, index)
        F = self.f.n_features
        C = np.zeros((F, F), dtype=np.float64)
        for b in baskets:
            items = sorted({index.idx[i["variant_id"]] for i in b["items"]})
            if len(items) < 2:
                continue
            A = self.f.B[items].astype(np.float64)
            s = A.sum(axis=0)
            C += np.outer(s, s) - A.T @ A        # all ordered pairs of distinct items
        total = C.sum()
        if total == 0:
            self.M = C
            return self
        row, colm = C.sum(axis=1, keepdims=True), C.sum(axis=0, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            pmi = np.log((C * total) / (row @ colm))
        pmi[~np.isfinite(pmi)] = 0.0
        pmi[C < self.min_count] = 0.0
        self.M = np.clip(pmi, 0.0, None)
        return self

    def scores(self, context: tuple[int, ...], on_date: str) -> np.ndarray:
        x = self.f.X[list(context)].sum(axis=0).astype(np.float64)
        return self.f.X.astype(np.float64) @ (self.M.T @ x)

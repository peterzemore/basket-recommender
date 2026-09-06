"""Units sold in the fitting window, optionally decayed by age. Context-free: the
same list for every query, which is exactly why it is the floor."""
from __future__ import annotations

from datetime import date

import numpy as np

from recsys.eval.index import Index
from .base import Model


class Popularity(Model):
    def __init__(self, half_life_days: float | None = None):
        super().__init__()
        self.half_life_days = half_life_days
        self.name = "popularity" if half_life_days is None else f"popularity(hl={int(half_life_days)}d)"
        self.counts: np.ndarray | None = None

    def fit(self, baskets: list[dict], index: Index) -> "Popularity":
        self._mark_seen(baskets, index)
        counts = np.zeros(index.n)
        ref = max(date.fromisoformat(b["date"]) for b in baskets).toordinal()
        for b in baskets:
            w = 1.0
            if self.half_life_days:
                age = ref - date.fromisoformat(b["date"]).toordinal()
                w = 0.5 ** (age / self.half_life_days)
            for i in b["items"]:
                counts[index.idx[i["variant_id"]]] += w * i["quantity"]
        self.counts = counts
        return self

    def scores(self, context: tuple[int, ...], on_date: str) -> np.ndarray:
        return self.counts.copy()

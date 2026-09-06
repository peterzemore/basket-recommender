"""Integer indexing over the variant universe, plus when each variant became
available - the rule behind candidate restriction.

A variant counts as available from the earlier of its catalog listing date and
its first sale anywhere in the data. The listing date alone is wrong for items
entered at the register (listed minutes after they sold); first sale alone is
wrong for items that sat on the shelf. Using first sale across the whole dataset,
including the test period, tells the evaluator only that the item existed on that
day - it is world state, not a label, and it never touches a model's scores.
"""
from __future__ import annotations

from datetime import date

import numpy as np


def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


class Index:
    def __init__(self, orders: list[dict], products: list[dict]):
        avail: dict[int, str] = {p["variant_id"]: p["created_at"] for p in products}
        for o in orders:
            for i in o["items"]:
                v = i["variant_id"]
                avail[v] = min(avail[v], o["date"]) if v in avail else o["date"]
        self.variants = sorted(avail)
        self.idx = {v: i for i, v in enumerate(self.variants)}
        self.n = len(self.variants)
        self.available_from = np.array([_ord(avail[v]) for v in self.variants], dtype=np.int64)

    def candidates(self, on_date: str, exclude: tuple[int, ...] = ()) -> np.ndarray:
        """Boolean mask over the universe: existed on `on_date`, not in the context."""
        mask = self.available_from <= _ord(on_date)
        if exclude:
            mask[list(exclude)] = False
        return mask

    def universe_on(self, on_date: str) -> int:
        return int((self.available_from <= _ord(on_date)).sum())

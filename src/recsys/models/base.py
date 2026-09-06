from __future__ import annotations

import numpy as np

from recsys.eval.index import Index


class Model:
    name = "base"

    def __init__(self):
        self.seen: set[int] = set()   # variant indices present in the fitting data

    def fit(self, baskets: list[dict], index: Index) -> "Model":
        raise NotImplementedError

    def scores(self, context: tuple[int, ...], on_date: str) -> np.ndarray:
        """Scores over the whole universe. Higher is better; ties allowed."""
        raise NotImplementedError

    def _mark_seen(self, baskets: list[dict], index: Index) -> None:
        self.seen = {index.idx[i["variant_id"]] for b in baskets for i in b["items"]}

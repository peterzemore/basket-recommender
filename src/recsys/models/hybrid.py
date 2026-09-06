"""A weighted blend of already-fitted models. Each component's scores are scaled
by their own maximum for the query, so a count-based model and a cosine model
share a range; a vanishing popularity term orders whatever is still tied."""
from __future__ import annotations

import numpy as np

from recsys.eval.index import Index
from .base import Model
from .popularity import Popularity


class Hybrid(Model):
    def __init__(self, components: list[tuple[Model, float]], label: str | None = None):
        super().__init__()
        self.components = [(m, w) for m, w in components if w > 0]
        self.name = label or "hybrid(" + ", ".join(f"{m.name}×{w:g}" for m, w in self.components) + ")"
        self._pop: np.ndarray | None = None

    def fit(self, baskets: list[dict], index: Index) -> "Hybrid":
        """Components are fitted by the caller (so a sweep can reuse them); this only
        fits the tiebreak and the seen-set."""
        self._mark_seen(baskets, index)
        pop = Popularity().fit(baskets, index).counts
        self._pop = pop / (pop.max() or 1.0) * 1e-6
        return self

    def component_scores(self, context: tuple[int, ...], on_date: str) -> dict[str, np.ndarray]:
        """Each component's weighted, max-scaled contribution - what /recommend reports as 'why'."""
        out = {}
        for m, w in self.components:
            s = m.scores(context, on_date)
            mx = s.max()
            out[m.name] = w * (s / mx) if mx > 0 else np.zeros_like(s)
        return out

    def scores(self, context: tuple[int, ...], on_date: str) -> np.ndarray:
        total = np.zeros_like(self._pop)
        for s in self.component_scores(context, on_date).values():
            total += s
        return total + self._pop

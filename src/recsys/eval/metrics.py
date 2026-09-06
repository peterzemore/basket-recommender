"""Rank metrics for a single hidden item.

Ties are the honest problem here: a popularity model gives thousands of long-tail
variants the same score, and where the target lands inside that tie block decides
the metric. The rank used is the expected rank under random tie-breaking - one
plus the number of candidates scored strictly higher, plus half the number tied.
It is deterministic, needs no seed, and neither flatters nor punishes a model for
emitting ties. Metrics are then computed from that (possibly fractional) rank.
"""
from __future__ import annotations

import math

import numpy as np


def expected_rank(scores: np.ndarray, candidates: np.ndarray, target: int) -> float:
    """`scores` over the universe, `candidates` a boolean mask that includes the target."""
    s_t = scores[target]
    cand_scores = scores[candidates]
    greater = int((cand_scores > s_t).sum())
    ties = int((cand_scores == s_t).sum()) - 1  # the target ties with itself
    return 1.0 + greater + ties / 2.0


def hit(rank: float, k: int) -> float:
    return 1.0 if rank <= k else 0.0


def ndcg(rank: float, k: int) -> float:
    return 1.0 / math.log2(rank + 1.0) if rank <= k else 0.0


def reciprocal_rank(rank: float) -> float:
    return 1.0 / rank


def top_k(scores: np.ndarray, candidates: np.ndarray, k: int) -> list[int]:
    """Deterministic top-k over candidates; ties broken by variant index so
    coverage and novelty are reproducible."""
    idx = np.flatnonzero(candidates)
    if idx.size == 0:
        return []
    order = np.lexsort((idx, -scores[idx]))
    return idx[order[:k]].tolist()

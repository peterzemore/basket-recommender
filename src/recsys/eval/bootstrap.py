"""Cluster bootstrap over baskets. Queries from the same basket share a context
and a date, so resampling queries would understate the interval."""
from __future__ import annotations

import numpy as np


def basket_bootstrap(values: np.ndarray, basket_ids: np.ndarray, n_boot: int = 1000,
                     seed: int = 0, alpha: float = 0.05) -> tuple[float, float, float]:
    """Returns (point estimate, lower, upper) for the mean of `values`."""
    uniq, inv = np.unique(basket_ids, return_inverse=True)
    sums = np.bincount(inv, weights=values, minlength=uniq.size)
    counts = np.bincount(inv, minlength=uniq.size).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, uniq.size, size=(n_boot, uniq.size))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(values.mean()), float(lo), float(hi)


def paired_difference(a: np.ndarray, b: np.ndarray, basket_ids: np.ndarray, n_boot: int = 1000,
                      seed: int = 0, alpha: float = 0.05) -> tuple[float, float, float]:
    """Bootstrap of mean(a) - mean(b) over the same resampled baskets."""
    return basket_bootstrap(a - b, basket_ids, n_boot, seed, alpha)

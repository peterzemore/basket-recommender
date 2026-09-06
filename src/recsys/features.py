"""Content features per variant: the store's tags, rarity words parsed from titles
(they are in titles at scale and in tags barely at all), and a price band.

Rows are multi-hot, weighted by inverse document frequency over the catalog so a tag
on most of the catalog ("Funko Pops!") says little and a tag on forty items says a
lot, then L2-normalized so an item with many tags is not louder than one with few.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from recsys.eval.index import Index

KEYWORDS = {
    "exclusive": re.compile(r"exclusive", re.I),
    "chase": re.compile(r"\bchase\b", re.I),
    "vault": re.compile(r"vault", re.I),
    "glow": re.compile(r"glow", re.I),
    "flocked": re.compile(r"flocked", re.I),
    "metallic": re.compile(r"metallic", re.I),
    "diamond": re.compile(r"diamond", re.I),
    "limited": re.compile(r"limited", re.I),
    "convention": re.compile(r"\b(sdcc|nycc|eccc|comic[- ]?con)\b", re.I),
}
PRICE_BANDS = [(0, 10, "<10"), (10, 15, "10-15"), (15, 25, "15-25"), (25, 50, "25-50"),
               (50, 100, "50-100"), (100, math.inf, "100+")]


def price_band(price: float) -> str:
    for lo, hi, label in PRICE_BANDS:
        if lo <= price < hi:
            return label
    return "100+"


def item_tokens(product: dict) -> list[str]:
    toks = [f"tag:{t.strip().lower()}" for t in product.get("tags") or [] if t.strip()]
    toks += [f"kw:{k}" for k, rx in KEYWORDS.items() if rx.search(product.get("title") or "")]
    toks.append(f"price:{price_band(float(product.get('price') or 0.0))}")
    return sorted(set(toks))


@dataclass
class Features:
    vocab: list[str]
    X: np.ndarray        # (n_variants, n_features) idf-weighted, L2-normalized rows
    B: np.ndarray        # (n_variants, n_features) binary presence
    idf: np.ndarray

    @property
    def n_features(self) -> int:
        return len(self.vocab)


def build_features(products: list[dict], index: Index) -> Features:
    by_variant = {p["variant_id"]: p for p in products}
    tokens = [item_tokens(by_variant[v]) if v in by_variant else [] for v in index.variants]
    vocab = sorted({t for ts in tokens for t in ts})
    col = {t: j for j, t in enumerate(vocab)}
    B = np.zeros((index.n, len(vocab)), dtype=np.float32)
    for i, ts in enumerate(tokens):
        for t in ts:
            B[i, col[t]] = 1.0
    df = B.sum(axis=0)
    idf = np.log((index.n + 1.0) / (df + 1.0)) + 1.0
    X = B * idf
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    X = np.divide(X, norms, out=np.zeros_like(X), where=norms > 0)
    return Features(vocab, X, B, idf.astype(np.float32))

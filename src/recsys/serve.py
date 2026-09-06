"""The service. Fits the validated configuration on the whole public snapshot at
startup (a few seconds), serves recommendations with live stock as a hard filter
when credentials are present, and reports its own provenance in /health."""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import date

import numpy as np
from fastapi import FastAPI, HTTPException, Query

from recsys.data import PUBLIC_DIR, ROOT, read_jsonl
from recsys.eval.index import Index
from recsys.features import build_features
from recsys.models import AttributeCooccurrence, ContentCosine, CoPurchase, Hybrid, ItemItem, Popularity
from recsys.stock import StockCache

DEFAULT_CONFIG = {"popularity": {"half_life_days": 30}, "attr": {"min_count": 5}, "content": {},
                  "item": {"family": "itemitem", "similarity": "cosine", "shrink": 5.0},
                  "weights": {"attr": 1.0, "content": 1.0, "item": 0.5}, "label": "hybrid(default)"}


class Recommender:
    def __init__(self, orders: list[dict], products: list[dict], config: dict):
        self.config = config
        self.index = Index(orders, products)
        self.features = build_features(products, self.index)
        self.products = {p["variant_id"]: p for p in products}
        self.n_orders, self.last_date = len(orders), max(o["date"] for o in orders)
        self.today = date.today().isoformat()

        attr = AttributeCooccurrence(self.features, config["attr"]["min_count"]).fit(orders, self.index)
        content = ContentCosine(self.features).fit(orders, self.index)
        it = config["item"]
        item = (ItemItem(it["similarity"], it["shrink"]) if it["family"] == "itemitem"
                else CoPurchase(it["min_support"], it["pop_tiebreak"])).fit(orders, self.index)
        w = config["weights"]
        self.model = Hybrid([(attr, w["attr"]), (content, w["content"]), (item, w["item"])],
                            label=config.get("label")).fit(orders, self.index)
        self.content = content
        self.sellable = np.array([self.products.get(v, {}).get("status") == "ACTIVE" for v in self.index.variants])

    def _ctx(self, variant_ids: list[int]) -> tuple[int, ...]:
        missing = [v for v in variant_ids if v not in self.index.idx]
        if missing:
            raise HTTPException(404, f"unknown variant ids: {missing}")
        return tuple(self.index.idx[v] for v in variant_ids)

    def _rows(self, scores: np.ndarray, mask: np.ndarray, k: int, stock: StockCache, in_stock_only: bool,
              why: dict[str, np.ndarray] | None = None) -> tuple[list[dict], bool]:
        cand = mask & self.sellable
        filtered = False
        if in_stock_only and stock.quantities:
            known = np.array([stock.in_stock(v) or False for v in self.index.variants])
            cand &= known
            filtered = True
        idx = np.flatnonzero(cand)
        order = idx[np.lexsort((idx, -scores[idx]))][:k]
        rows = []
        for i in order:
            v = self.index.variants[i]
            p = self.products.get(v, {})
            row = {"variant_id": v, "title": p.get("title"), "price": p.get("price"), "image_url": p.get("image_url"),
                   "tags": p.get("tags", []), "score": round(float(scores[i]), 6), "in_stock": stock.in_stock(v)}
            if why:
                row["why"] = {name: round(float(a[i]), 4) for name, a in why.items() if a[i] > 0}
            rows.append(row)
        return rows, filtered

    def recommend(self, variant_ids: list[int], k: int, stock: StockCache, in_stock_only: bool) -> dict:
        ctx = self._ctx(variant_ids)
        mask = self.index.candidates(self.today, ctx)
        why = self.model.component_scores(ctx, self.today)
        rows, filtered = self._rows(self.model.scores(ctx, self.today), mask, k, stock, in_stock_only, why)
        return {"context": [self._brief(v) for v in variant_ids], "model": self.model.name,
                "stock_filter_applied": filtered, "recommendations": rows}

    def similar(self, variant_id: int, k: int, stock: StockCache, in_stock_only: bool) -> dict:
        ctx = self._ctx([variant_id])
        mask = self.index.candidates(self.today, ctx)
        rows, filtered = self._rows(self.content.scores(ctx, self.today), mask, k, stock, in_stock_only)
        return {"item": self._brief(variant_id), "model": self.content.name, "stock_filter_applied": filtered,
                "similar": rows}

    def search(self, q: str, k: int) -> list[dict]:
        ql = q.lower().strip()
        hits = [p for p in self.products.values() if ql in (p.get("title") or "").lower() and p.get("status") == "ACTIVE"]
        hits.sort(key=lambda p: ((p["title"] or "").lower().find(ql), p["title"]))
        return [self._brief(p["variant_id"]) for p in hits[:k]]

    def _brief(self, v: int) -> dict:
        p = self.products.get(v, {})
        return {"variant_id": v, "title": p.get("title"), "price": p.get("price"), "image_url": p.get("image_url")}


def load_config() -> tuple[dict, str]:
    path = ROOT / "results" / "serving_config.json"
    if path.exists():
        return json.loads(path.read_text()), "results/serving_config.json"
    return DEFAULT_CONFIG, "built-in default"


def build_recommender() -> tuple[Recommender, str]:
    config, source = load_config()
    orders = list(read_jsonl(PUBLIC_DIR / "orders.jsonl"))
    products = list(read_jsonl(PUBLIC_DIR / "products.jsonl"))
    return Recommender(orders, products, config), source


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rec, app.state.config_source = build_recommender()
    app.state.stock = StockCache(float(os.getenv("STOCK_REFRESH_MINUTES", "15")))
    app.state.stock.start()
    yield
    app.state.stock.stop()


app = FastAPI(title="basket-recommender", lifespan=lifespan)


@app.get("/health")
def health():
    r: Recommender = app.state.rec
    return {"status": "ok", "model": r.model.name, "config_source": app.state.config_source,
            "fitted_on": {"orders": r.n_orders, "through": r.last_date, "variants": r.index.n},
            "stock": app.state.stock.status()}


@app.get("/recommend")
def recommend(variant_ids: str = Query(..., description="comma-separated variant ids in the basket"),
              k: int = Query(10, ge=1, le=50), in_stock: bool = True):
    try:
        ids = [int(x) for x in variant_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "variant_ids must be integers")
    if not ids:
        raise HTTPException(422, "at least one variant id is required")
    return app.state.rec.recommend(ids, k, app.state.stock, in_stock)


@app.get("/similar/{variant_id}")
def similar(variant_id: int, k: int = Query(10, ge=1, le=50), in_stock: bool = True):
    return app.state.rec.similar(variant_id, k, app.state.stock, in_stock)


@app.get("/search")
def search(q: str = Query(..., min_length=2), k: int = Query(10, ge=1, le=50)):
    return app.state.rec.search(q, k)


@app.get("/eval")
def eval_results():
    path = ROOT / "results" / "test.json"
    if not path.exists():
        raise HTTPException(404, "no results/test.json - run `recsys evaluate`")
    return json.loads(path.read_text())

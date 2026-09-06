"""Turn cleaned orders into the public snapshot.

What survives: variant/product ids (public catalog identifiers), titles, quantities,
unit prices, order date (day only), a coarse sales channel, and a keyed hash of the
customer id so repeat purchases stay linkable without the id itself. What doesn't:
emails, names, order names/numbers, timestamps finer than a day, the raw customer id.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

SOURCE_MAP = {"pos": "pos", "web": "web", "shopify_draft_order": "draft"}


def load_or_create_salt(path: Path) -> str:
    """The salt keys the customer hash. It lives in data/raw (gitignored). Lose it and a
    fresh pull hashes customers differently, which only matters if you compare
    customer-level stats across snapshots; the evaluation never keys on it."""
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(32)
    path.write_text(salt + "\n")
    return salt


def hash_customer(customer_gid: str | None, salt: str) -> str | None:
    if not customer_gid:
        return None
    return hmac.new(salt.encode(), customer_gid.encode(), hashlib.sha256).hexdigest()[:16]


def gid_number(gid: str | None) -> int | None:
    """'gid://shopify/ProductVariant/12345' -> 12345."""
    if not gid:
        return None
    return int(gid.rsplit("/", 1)[-1])


def coarse_source(source_name: str | None) -> str:
    s = (source_name or "").strip()
    if s in SOURCE_MAP:
        return SOURCE_MAP[s]
    if s.isdigit():
        # A bare numeric source is a sales-channel app id. On this store it is the
        # store's own mobile app; on another store it could be anything, so it is
        # labelled by what it is structurally rather than by name.
        return "app"
    return "other"


def anonymize_orders(orders: list[dict], salt: str) -> list[dict]:
    rows = []
    for o in sorted(orders, key=lambda o: o["created_at"]):
        rows.append({
            "order_id": len(rows) + 1,
            "date": o["created_at"][:10],
            "source": coarse_source(o.get("source_name")),
            "customer": hash_customer(o.get("customer_id"), salt),
            "items": [{
                "variant_id": gid_number(li["variant_id"]),
                "product_id": gid_number(li.get("product_id")),
                "title": li["title"],
                "quantity": int(li["quantity"]),
                "unit_price": li.get("discounted_unit_price"),
            } for li in o["line_items"]],
        })
    return rows


def flatten_products(products: list[dict]) -> list[dict]:
    """One row per variant, which is the unit the recommender ranks."""
    rows = []
    for p in products:
        for v in p["variants"]:
            rows.append({
                "variant_id": gid_number(v["id"]),
                "product_id": gid_number(p["id"]),
                "title": p["title"] if v["title"] in ("", "Default Title") else f'{p["title"]} - {v["title"]}',
                "tags": sorted(p.get("tags") or []),
                "price": v["price"],
                "created_at": v["created_at"][:10],
                "status": p.get("status"),
                "image_url": p.get("image_url"),
            })
    return rows

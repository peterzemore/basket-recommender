"""Pull orders and the product catalog from the Shopify Admin GraphQL API.

Uses the client-credentials grant (client id + secret -> short-lived token), which is
what this store's custom apps issue; a static admin token is not an option here. The
app only needs read_orders and read_products. Nothing in this module is imported by
the rest of the package - the public snapshot is the boundary.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import requests

DEFAULT_API_VERSION = "2025-07"
_MAX_THROTTLE_RETRIES = 6
_THROTTLE_BACKOFF_SECONDS = 2.0


class ShopifyAdmin:
    def __init__(self, store: str, client_id: str, client_secret: str, api_version: str = DEFAULT_API_VERSION):
        self.store, self.client_id, self.client_secret = store, client_id, client_secret
        self.api_version = api_version
        self._token: str | None = None
        self._expiry = 0.0

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "ShopifyAdmin":
        missing = [k for k in ("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET") if not env.get(k)]
        if missing:
            raise ValueError(f"missing {', '.join(missing)} in env file")
        return cls(env["SHOPIFY_STORE"], env["SHOPIFY_CLIENT_ID"], env["SHOPIFY_CLIENT_SECRET"],
                   env.get("SHOPIFY_ADMIN_API_VERSION") or DEFAULT_API_VERSION)

    def _access_token(self) -> str:
        if self._token and time.time() < self._expiry - 300:
            return self._token
        resp = requests.post(
            f"https://{self.store}/admin/oauth/access_token",
            data={"grant_type": "client_credentials", "client_id": self.client_id,
                  "client_secret": self.client_secret},
            timeout=15,
        )
        body = resp.json()
        if not resp.ok or "access_token" not in body:
            raise RuntimeError(f"token exchange failed ({resp.status_code}): "
                               f"{body.get('error_description') or body.get('error') or resp.text[:120]}")
        self._token = body["access_token"]
        self._expiry = time.time() + float(body.get("expires_in", 86399))
        return self._token

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        url = f"https://{self.store}/admin/api/{self.api_version}/graphql.json"
        for attempt in range(_MAX_THROTTLE_RETRIES):
            resp = requests.post(url, json={"query": query, "variables": variables or {}},
                                 headers={"X-Shopify-Access-Token": self._access_token()}, timeout=60)
            body = resp.json()
            errors = body.get("errors") or []
            if any((e.get("extensions") or {}).get("code") == "THROTTLED" for e in errors):
                time.sleep(_THROTTLE_BACKOFF_SECONDS * (attempt + 1))
                continue
            if errors:
                raise RuntimeError(f"GraphQL error: {errors[0].get('message')}")
            return body["data"]
        raise RuntimeError("throttled by Shopify too many times in a row")


ORDERS_QUERY = """
query($cursor: String, $q: String) {
  orders(first: 100, after: $cursor, query: $q, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      id name createdAt cancelledAt test sourceName email
      customer { id }
      refunds { refundLineItems(first: 50) { edges { node { quantity lineItem { id } } } } }
      lineItems(first: 100) { edges { node {
        id title quantity sku
        variant { id product { id } }
        originalUnitPriceSet { shopMoney { amount } }
        discountedUnitPriceSet { shopMoney { amount } }
      } } }
    } }
  }
}
"""

PRODUCTS_QUERY = """
query($cursor: String) {
  products(first: 100, after: $cursor, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    edges { node {
      id title tags productType status createdAt
      featuredImage { url }
      variants(first: 50) { edges { node { id title price createdAt } } }
    } }
  }
}
"""


def _money(field) -> float | None:
    try:
        return float(field["shopMoney"]["amount"])
    except (KeyError, TypeError, ValueError):
        return None


def fetch_orders(api: ShopifyAdmin, lookback_days: int) -> list[dict]:
    """Raw orders, flattened but otherwise unfiltered. Filtering is clean.py's job so
    the raw snapshot is a faithful record of what the API returned."""
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    out, cursor = [], None
    while True:
        page = api.graphql(ORDERS_QUERY, {"cursor": cursor, "q": f"created_at:>={since}"})["orders"]
        for edge in page["edges"]:
            n = edge["node"]
            refunded: dict[str, int] = {}
            for r in n.get("refunds") or []:
                for e in r["refundLineItems"]["edges"]:
                    li = e["node"]["lineItem"]
                    if li:
                        refunded[li["id"]] = refunded.get(li["id"], 0) + int(e["node"]["quantity"])
            out.append({
                "id": n["id"], "name": n["name"], "created_at": n["createdAt"],
                "cancelled_at": n.get("cancelledAt"), "test": bool(n.get("test")),
                "source_name": n.get("sourceName"), "email": n.get("email"),
                "customer_id": (n.get("customer") or {}).get("id"),
                "line_items": [{
                    "id": li["id"], "title": li["title"], "quantity": int(li["quantity"]),
                    "sku": li.get("sku") or "",
                    "variant_id": (li.get("variant") or {}).get("id"),
                    "product_id": ((li.get("variant") or {}).get("product") or {}).get("id"),
                    "original_unit_price": _money(li.get("originalUnitPriceSet")),
                    "discounted_unit_price": _money(li.get("discountedUnitPriceSet")),
                    "refunded_quantity": refunded.get(li["id"], 0),
                } for li in (e["node"] for e in n["lineItems"]["edges"])],
            })
        if not page["pageInfo"]["hasNextPage"]:
            return out
        cursor = page["pageInfo"]["endCursor"]


def fetch_products(api: ShopifyAdmin) -> list[dict]:
    """Every product (any status) with its variants. Deleted products don't come
    back, which is why orders can reference variants the catalog no longer has."""
    out, cursor = [], None
    while True:
        page = api.graphql(PRODUCTS_QUERY, {"cursor": cursor})["products"]
        for edge in page["edges"]:
            n = edge["node"]
            out.append({
                "id": n["id"], "title": n["title"], "tags": n.get("tags") or [],
                "product_type": n.get("productType") or "", "status": n.get("status"),
                "created_at": n["createdAt"],
                "image_url": (n.get("featuredImage") or {}).get("url"),
                "variants": [{"id": v["id"], "title": v.get("title") or "", "price": float(v["price"]),
                              "created_at": v["createdAt"]} for v in (e["node"] for e in n["variants"]["edges"])],
            })
        if not page["pageInfo"]["hasNextPage"]:
            return out
        cursor = page["pageInfo"]["endCursor"]

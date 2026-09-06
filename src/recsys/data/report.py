"""The data table in the README, computed from the public snapshot so the numbers a
reader sees are the numbers the code sees."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date, timedelta


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


def compute(orders: list[dict], products: list[dict], cold_days: int = 90) -> dict:
    n = len(orders)
    dates = sorted(o["date"] for o in orders)
    by_month = Counter(d[:7] for d in dates)
    src = Counter(o["source"] for o in orders)
    with_cust = [o for o in orders if o["customer"]]
    pos = [o for o in orders if o["source"] == "pos"]
    pos_with_cust = sum(1 for o in pos if o["customer"])
    cust_orders = Counter(o["customer"] for o in with_cust)
    multi = sum(1 for o in orders if len({i["variant_id"] for i in o["items"]}) >= 2)
    units = [sum(i["quantity"] for i in o["items"]) for o in orders]
    variant_units: Counter = Counter()
    variant_orders: Counter = Counter()
    for o in orders:
        for i in o["items"]:
            variant_units[i["variant_id"]] += i["quantity"]
            variant_orders[i["variant_id"]] += 1
    # "sold once" counts orders, not units: one basket containing three of a thing is
    # still one co-occurrence signal, which is what matters for a recommender.
    sold_once = sum(1 for c in variant_orders.values() if c == 1)
    top20 = sum(c for _, c in variant_units.most_common(20))

    first_seen: dict[int, str] = {}
    for o in sorted(orders, key=lambda o: o["date"]):
        for i in o["items"]:
            first_seen.setdefault(i["variant_id"], o["date"])
    cut = (date.fromisoformat(dates[-1]) - timedelta(days=cold_days)).isoformat()
    recent_items = [i for o in orders if o["date"] >= cut for i in o["items"]]
    recent_new = sum(1 for i in recent_items if first_seen[i["variant_id"]] >= cut)

    catalog = {p["variant_id"]: p for p in products}
    sold_in_catalog = sum(1 for v in variant_units if v in catalog)
    tagged = sum(1 for p in products if p["tags"])
    tags = {t for p in products for t in p["tags"]}

    return {
        "orders": n, "first_date": dates[0], "last_date": dates[-1], "months": len(by_month),
        "orders_per_month_median": sorted(by_month.values())[len(by_month) // 2],
        "source_mix": {k: _pct(v, n) for k, v in src.most_common()},
        "orders_with_customer": _pct(len(with_cust), n),
        "pos_orders_with_customer": _pct(pos_with_cust, len(pos)),
        "unique_customers": len(cust_orders),
        "repeat_customers": sum(1 for c in cust_orders.values() if c >= 2),
        "repeat_customer_pct": _pct(sum(1 for c in cust_orders.values() if c >= 2), len(cust_orders)),
        "customers_5plus": sum(1 for c in cust_orders.values() if c >= 5),
        "multi_item_orders": multi, "multi_item_pct": _pct(multi, n),
        "units_per_order_median": sorted(units)[n // 2],
        "distinct_variants_sold": len(variant_units),
        "variants_sold_once_pct": _pct(sold_once, len(variant_units)),
        "top20_share_of_units": _pct(top20, sum(variant_units.values())),
        "cold_days": cold_days,
        "cold_share_of_recent_items": _pct(recent_new, len(recent_items)),
        "sold_variants_still_in_catalog_pct": _pct(sold_in_catalog, len(variant_units)),
        "catalog_variants": len(products),
        "tag_coverage": _pct(tagged, len(products)), "distinct_tags": len(tags),
    }


def to_markdown(s: dict) -> str:
    mix = ", ".join(f"{k} {v}" for k, v in s["source_mix"].items())
    rows = [
        ("Orders", f'{s["orders"]:,} over {s["months"]} months ({s["first_date"]} to {s["last_date"]}), median {s["orders_per_month_median"]}/month'),
        ("Sales channel mix", mix),
        ("Orders with a customer attached", f'{s["orders_with_customer"]} overall; {s["pos_orders_with_customer"]} of in-store'),
        ("Customers", f'{s["unique_customers"]:,} unique; {s["repeat_customers"]} ({s["repeat_customer_pct"]}) ordered twice or more; {s["customers_5plus"]} ordered five or more times'),
        ("Multi-item orders", f'{s["multi_item_orders"]:,} ({s["multi_item_pct"]}); median {s["units_per_order_median"]} units per order'),
        ("Distinct variants sold", f'{s["distinct_variants_sold"]:,}; {s["variants_sold_once_pct"]} appear in only one order'),
        ("Top-20 variants", f'{s["top20_share_of_units"]} of all units'),
        (f"Cold start (last {s['cold_days']} days)", f'{s["cold_share_of_recent_items"]} of line items are variants first sold inside that window'),
        ("Catalog", f'{s["catalog_variants"]:,} variants; {s["sold_variants_still_in_catalog_pct"]} of sold variants still listed; tags on {s["tag_coverage"]} ({s["distinct_tags"]} distinct)'),
    ]
    out = ["| | |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(out)

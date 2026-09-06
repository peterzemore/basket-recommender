"""Cleaning rules for raw orders. Each rule is named, counted, and reported, because
the cleaning decisions are part of the result: dropping the owner's own orders or a
POS "Tip" line changes what the recommender learns, and a reader should see how much.
"""
from __future__ import annotations

from collections import Counter

# Line items that are not products. On this store a POS tip shows up as a line item
# with no variant, and hand-typed custom sales do too; both carry no variant_id, so
# the null-variant rule catches them. TITLE_BLOCKLIST is a belt to that suspender.
TITLE_BLOCKLIST = {"tip"}


def clean_orders(orders: list[dict], exclude_emails: set[str] = frozenset()) -> tuple[list[dict], dict]:
    """Return (kept orders, stats). Orders are not mutated."""
    ex = {e.lower() for e in exclude_emails}
    stats: Counter = Counter()
    kept: list[dict] = []

    for o in orders:
        stats["orders_in"] += 1
        if o.get("test"):
            stats["dropped_test_order"] += 1
            continue
        if o.get("cancelled_at"):
            stats["dropped_cancelled_order"] += 1
            continue
        if (o.get("email") or "").lower() in ex:
            stats["dropped_excluded_email_order"] += 1
            continue

        merged: dict[str, dict] = {}
        for li in o["line_items"]:
            stats["lines_in"] += 1
            if not li.get("variant_id"):
                stats["dropped_line_no_variant"] += 1
                continue
            if li["title"].strip().lower() in TITLE_BLOCKLIST:
                stats["dropped_line_blocklisted_title"] += 1
                continue
            qty = int(li["quantity"]) - int(li.get("refunded_quantity") or 0)
            if qty <= 0:
                stats["dropped_line_fully_refunded"] += 1
                continue
            if qty < int(li["quantity"]):
                stats["lines_partially_refunded"] += 1
            v = li["variant_id"]
            if v in merged:
                stats["lines_merged_duplicate_variant"] += 1
                merged[v]["quantity"] += qty
            else:
                merged[v] = {**li, "quantity": qty}

        if not merged:
            stats["dropped_order_no_lines_left"] += 1
            continue
        kept.append({**o, "line_items": list(merged.values())})
        stats["orders_out"] += 1
        stats["lines_out"] += len(merged)

    return kept, dict(stats)

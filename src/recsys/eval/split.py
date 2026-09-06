"""Time-based split. The dates are fixed in the README; a random split would leak
future baskets into training and flatter every model."""
from __future__ import annotations

TRAIN_END = "2026-03-31"   # inclusive
VAL_END = "2026-05-31"     # inclusive; test is everything after


def split_orders(orders: list[dict], train_end: str = TRAIN_END, val_end: str = VAL_END):
    train = [o for o in orders if o["date"] <= train_end]
    val = [o for o in orders if train_end < o["date"] <= val_end]
    test = [o for o in orders if o["date"] > val_end]
    return train, val, test

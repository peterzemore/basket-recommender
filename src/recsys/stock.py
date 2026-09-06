"""Live stock, refreshed in the background. The evaluation cannot see stock; the
service must, because with sell-through anywhere from a week to never, a
recommendation for something that sold out this morning is worse than none.

With no Shopify credentials in the environment the cache stays empty and the
service says so in /health - every other endpoint keeps working."""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone


class StockCache:
    def __init__(self, refresh_minutes: float = 15.0):
        self.refresh_minutes = refresh_minutes
        self.quantities: dict[int, int] = {}
        self.updated_at: str | None = None
        self.error: str | None = None
        self.enabled = all(os.getenv(k) for k in ("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"))
        self._stop = threading.Event()

    def refresh_once(self) -> None:
        from recsys.data.shopify import ShopifyAdmin, fetch_inventory
        try:
            api = ShopifyAdmin.from_env({k: os.getenv(k, "") for k in
                                         ("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET", "SHOPIFY_ADMIN_API_VERSION")})
            self.quantities = fetch_inventory(api)
            self.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.error = None
        except Exception as e:  # keep serving on a stale cache rather than fall over
            self.error = f"{type(e).__name__}: {e}"[:200]

    def start(self) -> None:
        if not self.enabled:
            return
        self.refresh_once()

        def loop():
            while not self._stop.wait(self.refresh_minutes * 60):
                self.refresh_once()
        threading.Thread(target=loop, daemon=True, name="stock-refresh").start()

    def stop(self) -> None:
        self._stop.set()

    def in_stock(self, variant_id: int) -> bool | None:
        """True/False when stock is known, None when the cache has nothing."""
        if not self.quantities:
            return None
        return self.quantities.get(variant_id, 0) > 0

    def age(self) -> str | None:
        if not self.updated_at:
            return None
        secs = (datetime.now(timezone.utc) - datetime.fromisoformat(self.updated_at)).total_seconds()
        return "just now" if secs < 90 else f"{int(secs // 60)} min ago" if secs < 5400 else f"{secs / 3600:.0f} h ago"

    def status(self) -> dict:
        return {"enabled": self.enabled, "variants_known": len(self.quantities),
                "updated_at": self.updated_at, "age": self.age(), "error": self.error}

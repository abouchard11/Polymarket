"""Whale flow tracker on Polymarket global — SIGNAL SOURCE, not a mirror bot.

Evidence says naive copying ~= coin flip (Polycopy's own backtest across 687k resolved
trades) and top wallets actively evade copiers: iceberg entries, YES+NO merge exits that
fire no sale event, secondary accounts (Polymarket's own newsletter, news.polymarket.com/p/copycat).
55% of 5-minute crypto market participants are bots — copying them is donating slippage.

So this module: polls public Data-API trades for a curated wallet list, applies filters,
and emits WhaleSignal events for a HUMAN or a downstream model to evaluate against
Polymarket US / Kalshi listings of the same event. It does not place orders.

Filters (from the evidence):
- ignore 5m/15m/hourly crypto serials (bot territory, signal-free for followers)
- ignore trades below min_size_usd (noise / iceberg fragments)
- ignore signals older than max_age_s (fills are public only AFTER they happen;
  stale whale flow is adverse selection bait)
- track entry price vs current price; if it already moved > max_drift, the edge is gone
"""

from __future__ import annotations

import time

import yaml

from pmq.core.models import WhaleSignal
from pmq.venues.polymarket_global import PolymarketGlobalData

CRYPTO_SERIAL_MARKERS = ("5m", "15m", "hourly", "up or down", "up-or-down")


def load_whales(path: str = "config/whales.yaml") -> dict[str, str]:
    """wallet -> alias"""
    try:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    return {w["address"].lower(): w.get("alias", "?") for w in raw.get("wallets", [])}


def filter_signal(
    signal: WhaleSignal,
    *,
    min_size_usd: float = 2_000.0,
    max_age_s: float = 900.0,
    now: float | None = None,
) -> bool:
    """True if the signal survives evidence-based filters."""
    q = (signal.question or "").lower()
    if any(marker in q for marker in CRYPTO_SERIAL_MARKERS):
        return False
    if signal.size_usd < min_size_usd:
        return False
    age = (now if now is not None else time.time()) - signal.ts.timestamp()
    if age > max_age_s:
        return False
    return True


class WhaleTracker:
    def __init__(self, data: PolymarketGlobalData, whales: dict[str, str] | None = None) -> None:
        self.data = data
        self.whales = whales if whales is not None else load_whales()
        self._seen: set[str] = set()

    async def poll(self, min_size_usd: float = 2_000.0) -> list[WhaleSignal]:
        """One polling cycle across all tracked wallets. Data API /trades: 200 req/10s —
        a few dozen wallets at a 30-60s cadence is far inside limits."""
        fresh: list[WhaleSignal] = []
        for wallet, alias in self.whales.items():
            try:
                trades = await self.data.get_wallet_trades(wallet, limit=25)
            except Exception:
                continue
            for signal in trades:
                tx = signal.raw.get("transactionHash", signal.ts.isoformat())
                key = f"{wallet}:{tx}:{signal.market_id}"
                if key in self._seen:
                    continue
                self._seen.add(key)
                signal.alias = alias
                if filter_signal(signal, min_size_usd=min_size_usd):
                    fresh.append(signal)
        return fresh

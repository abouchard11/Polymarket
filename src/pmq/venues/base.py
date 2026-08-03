"""Venue interfaces. Data and execution are deliberately separate protocols —
polymarket_global implements only MarketDataSource (US operators cannot trade there)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pmq.core.models import Market, Order, OrderBook


@runtime_checkable
class MarketDataSource(Protocol):
    async def get_markets(self, **filters) -> list[Market]: ...
    async def get_book(self, market: Market, outcome_index: int = 0) -> OrderBook: ...


@runtime_checkable
class ExecutionVenue(MarketDataSource, Protocol):
    async def place_order(self, order: Order) -> Order: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def get_balance(self) -> float: ...

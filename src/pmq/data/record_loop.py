"""Watchlist -> venue adapter -> ParquetRecorder wiring for `pmq record`.

Split out of pmq.cli so the resolve/record cycle is unit-testable against a fake
venue client with zero network (see tests/test_record_loop.py). The CLI owns argument
parsing, the asyncio loop cadence, and SIGINT/SIGTERM shutdown; this module owns one
thing: "given a client and a watchlist, what gets fetched and recorded."

READ-ONLY by construction: this only ever calls get_markets / get_book_by_token on the
venue client — never an order endpoint (see CLAUDE.md invariants: strategies/recorder
never place orders).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from pmq.core.models import Market, OrderBook
from pmq.data.recorder import ParquetRecorder
from pmq.data.watchlist import WatchlistEntry

logger = logging.getLogger(__name__)


class VenueDataClient(Protocol):
    """Structural type for the slice of PolymarketGlobalData the record loop needs."""

    async def get_markets(self, **kwargs: Any) -> list[Market]: ...

    async def get_book_by_token(self, token_id: str) -> OrderBook: ...


async def resolve_market(client: VenueDataClient, entry: WatchlistEntry) -> Market | None:
    """Resolve one watchlist entry's slug to a Market (with CLOB token ids) via Gamma.

    Returns None (never raises) on a bad slug or a transient lookup failure — one
    stale entry in the watchlist must not take down the whole recorder.
    """
    try:
        rows = await client.get_markets(slug=entry.slug, limit=1)
    except Exception:
        logger.exception("failed to resolve watchlist slug %r", entry.slug)
        return None
    if not rows:
        logger.warning("slug %r resolved to no market — is it still active?", entry.slug)
        return None
    return rows[0]


async def resolve_markets(
    client: VenueDataClient, entries: list[WatchlistEntry]
) -> list[tuple[WatchlistEntry, Market]]:
    """Resolve every watchlist entry once at startup. Skips (doesn't crash on) misses."""
    resolved: list[tuple[WatchlistEntry, Market]] = []
    for entry in entries:
        market = await resolve_market(client, entry)
        if market is None:
            continue
        if not market.token_ids:
            logger.warning("slug %r has no CLOB token ids — skipping", entry.slug)
            continue
        resolved.append((entry, market))
    return resolved


async def record_cycle(
    client: VenueDataClient,
    recorder: ParquetRecorder,
    resolved: list[tuple[WatchlistEntry, Market]],
) -> int:
    """One poll of every resolved market's order book(s). Returns snapshots written.

    A single book-fetch failure is logged and skipped, not fatal — a flaky market
    must not stall the rest of the watchlist for a whole cadence cycle.
    """
    count = 0
    for entry, market in resolved:
        for token_id in market.token_ids:
            try:
                book = await client.get_book_by_token(token_id)
            except Exception:
                logger.exception("book fetch failed for %s (token %s)", entry.slug, token_id)
                continue
            recorder.record_book(book)
            count += 1
    return count

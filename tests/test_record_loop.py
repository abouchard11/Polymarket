"""Record-loop invocation paths: watchlist -> venue adapter -> ParquetRecorder.

Zero network — the venue client is a fake. Only local parquet I/O (pandas/pyarrow
writing to tmp_path) is exercised, matching how the rest of the suite treats recorder
output (see ParquetRecorder itself has no dedicated test file; we exercise it here
because `pmq record` is the first real caller of its loop path).
"""

from __future__ import annotations

import pandas as pd
import pytest

from pmq.core.models import Market, OrderBook, Quote, Venue
from pmq.data.record_loop import record_cycle, resolve_market, resolve_markets
from pmq.data.recorder import ParquetRecorder
from pmq.data.watchlist import WatchlistEntry


def _market(slug: str, token_ids: list[str]) -> Market:
    return Market(
        venue=Venue.POLYMARKET_GLOBAL,
        market_id=f"cond-{slug}",
        question=f"Question for {slug}?",
        token_ids=token_ids,
    )


def _book(token_id: str) -> OrderBook:
    return OrderBook(
        venue=Venue.POLYMARKET_GLOBAL,
        market_id="m1",
        token_id=token_id,
        bids=[Quote(price=0.40, size=100)],
        asks=[Quote(price=0.42, size=80)],
    )


class FakeVenueClient:
    """Structural stand-in for PolymarketGlobalData — no network involved."""

    def __init__(self, markets_by_slug=None, books_by_token=None, raise_for_slugs=None):
        self.markets_by_slug = markets_by_slug or {}
        self.books_by_token = books_by_token or {}
        self.raise_for_slugs = raise_for_slugs or set()
        self.raise_for_tokens: set[str] = set()
        self.get_markets_calls: list[dict] = []
        self.get_book_calls: list[str] = []

    async def get_markets(self, **kwargs):
        self.get_markets_calls.append(kwargs)
        slug = kwargs.get("slug")
        if slug in self.raise_for_slugs:
            raise RuntimeError(f"boom resolving {slug}")
        m = self.markets_by_slug.get(slug)
        return [m] if m is not None else []

    async def get_book_by_token(self, token_id: str):
        self.get_book_calls.append(token_id)
        if token_id in self.raise_for_tokens:
            raise RuntimeError(f"boom fetching {token_id}")
        return self.books_by_token[token_id]


@pytest.mark.asyncio
async def test_resolve_market_happy_path():
    client = FakeVenueClient(markets_by_slug={"m1": _market("m1", ["tA", "tB"])})
    entry = WatchlistEntry(slug="m1")
    market = await resolve_market(client, entry)
    assert market is not None
    assert market.token_ids == ["tA", "tB"]
    assert client.get_markets_calls == [{"slug": "m1", "limit": 1}]


@pytest.mark.asyncio
async def test_resolve_market_no_match_returns_none():
    client = FakeVenueClient(markets_by_slug={})
    entry = WatchlistEntry(slug="ghost-slug")
    assert await resolve_market(client, entry) is None


@pytest.mark.asyncio
async def test_resolve_market_swallows_client_exception():
    client = FakeVenueClient(raise_for_slugs={"bad-slug"})
    entry = WatchlistEntry(slug="bad-slug")
    assert await resolve_market(client, entry) is None


@pytest.mark.asyncio
async def test_resolve_markets_skips_unresolved_and_tokenless():
    client = FakeVenueClient(
        markets_by_slug={
            "good": _market("good", ["tA", "tB"]),
            "no-tokens": _market("no-tokens", []),
        },
        raise_for_slugs={"broken"},
    )
    entries = [
        WatchlistEntry(slug="good"),
        WatchlistEntry(slug="missing"),  # not in markets_by_slug -> resolves to []
        WatchlistEntry(slug="no-tokens"),
        WatchlistEntry(slug="broken"),
    ]
    resolved = await resolve_markets(client, entries)
    assert [e.slug for e, _ in resolved] == ["good"]


@pytest.mark.asyncio
async def test_record_cycle_writes_one_snapshot_per_token(tmp_path):
    client = FakeVenueClient(
        books_by_token={"tA": _book("tA"), "tB": _book("tB")},
    )
    recorder = ParquetRecorder(out_dir=str(tmp_path))
    resolved = [(WatchlistEntry(slug="m1"), _market("m1", ["tA", "tB"]))]

    n = await record_cycle(client, recorder, resolved)

    assert n == 2
    assert client.get_book_calls == ["tA", "tB"]
    book_path, opp_path = recorder.flush()
    assert opp_path is None
    assert book_path is not None
    df = pd.read_parquet(book_path)
    assert len(df) == 2
    assert {"ts", "venue", "market_id", "token_id", "bid_p0", "ask_p0"}.issubset(df.columns)
    assert sorted(df["token_id"]) == ["tA", "tB"]


@pytest.mark.asyncio
async def test_record_cycle_continues_after_one_book_fetch_fails(tmp_path):
    client = FakeVenueClient(books_by_token={"tA": _book("tA")})
    client.raise_for_tokens = {"tB"}
    recorder = ParquetRecorder(out_dir=str(tmp_path))
    resolved = [(WatchlistEntry(slug="m1"), _market("m1", ["tA", "tB"]))]

    n = await record_cycle(client, recorder, resolved)

    assert n == 1  # tB failed, tA still recorded
    book_path, _ = recorder.flush()
    df = pd.read_parquet(book_path)
    assert len(df) == 1
    assert df["token_id"].iloc[0] == "tA"


@pytest.mark.asyncio
async def test_record_cycle_multiple_markets(tmp_path):
    client = FakeVenueClient(
        books_by_token={"tA": _book("tA"), "tB": _book("tB"), "tC": _book("tC")},
    )
    recorder = ParquetRecorder(out_dir=str(tmp_path))
    resolved = [
        (WatchlistEntry(slug="m1"), _market("m1", ["tA", "tB"])),
        (WatchlistEntry(slug="m2"), _market("m2", ["tC"])),
    ]

    n = await record_cycle(client, recorder, resolved)
    assert n == 3

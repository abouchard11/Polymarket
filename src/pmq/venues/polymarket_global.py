"""Polymarket global (Polygon CLOB) — READ-ONLY adapter.

US operators are geo-blocked from trading here (help.polymarket.com geographic
restrictions list includes the United States). The public data APIs are the value:

- Gamma  https://gamma-api.polymarket.com   market/event metadata (no auth)
- CLOB   https://clob.polymarket.com        order books, prices (no auth for market data)
- Data   https://data-api.polymarket.com    trades, positions by wallet (no auth)

Rate limits (docs.polymarket.com/api-reference/rate-limits, July 2026):
  Gamma general 4,000/10s (/markets 300/10s, /events 500/10s)
  CLOB /book /price /midpoint 1,500/10s each; batched /books /prices 500/10s
  Data API general 1,000/10s (/trades 200/10s, /positions 150/10s)

NOTE (V2 migration 2026-04-28): the exchange moved to CTF Exchange V2 + pUSD collateral.
Old tutorials and the v1 py-clob-client are dead. This adapter uses plain REST — no
trading auth needed — so it survived the cutover. If trading ever opens to US users
(Polymarket has a pending CFTC request to onshore the on-chain exchange), add an
execution adapter using py-clob-client-v2 or Polymarket/py-sdk (`polymarket-client`).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from pmq.config import settings
from pmq.core.models import Market, OrderBook, Quote, Venue, WhaleSignal

_TIMEOUT = httpx.Timeout(10.0)


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


class PolymarketGlobalData:
    """Async read-only client. Safe to hammer within documented rate limits."""

    def __init__(self) -> None:
        s = settings()
        self.gamma = s.gamma_base
        self.clob = s.clob_base
        self.data_api = s.data_api_base
        self._client = httpx.AsyncClient(timeout=_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    async def _get(self, url: str, params: dict | None = None) -> Any:
        r = await self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def get_markets(
        self, active: bool = True, closed: bool = False, limit: int = 100, offset: int = 0, **extra
    ) -> list[Market]:
        params = {"active": str(active).lower(), "closed": str(closed).lower(),
                  "limit": limit, "offset": offset, **extra}
        rows = await self._get(f"{self.gamma}/markets", params)
        out: list[Market] = []
        for m in rows:
            token_ids: list[str] = []
            raw_tokens = m.get("clobTokenIds")
            if isinstance(raw_tokens, str):
                try:
                    token_ids = json.loads(raw_tokens)
                except json.JSONDecodeError:
                    token_ids = []
            elif isinstance(raw_tokens, list):
                token_ids = raw_tokens
            outcomes = m.get("outcomes")
            if isinstance(outcomes, str):
                try:
                    outcomes = json.loads(outcomes)
                except json.JSONDecodeError:
                    outcomes = ["Yes", "No"]
            out.append(
                Market(
                    venue=Venue.POLYMARKET_GLOBAL,
                    market_id=str(m.get("conditionId") or m.get("id")),
                    question=m.get("question", ""),
                    outcomes=outcomes or ["Yes", "No"],
                    token_ids=[str(t) for t in token_ids],
                    neg_risk=bool(m.get("negRisk")),
                    end_date=_parse_dt(m.get("endDate")),
                    resolution_source=m.get("resolutionSource"),
                    min_order_size=m.get("orderMinSize"),
                    tick_size=m.get("orderPriceMinTickSize"),
                    raw=m,
                )
            )
        return out

    async def get_events(self, limit: int = 50, **extra) -> list[dict]:
        """Events group multi-outcome (negRisk) markets — the unit for basket scans."""
        params = {"active": "true", "closed": "false", "limit": limit, **extra}
        return await self._get(f"{self.gamma}/events", params)

    async def get_book_by_token(self, token_id: str) -> OrderBook:
        data = await self._get(f"{self.clob}/book", {"token_id": token_id})
        return OrderBook(
            venue=Venue.POLYMARKET_GLOBAL,
            market_id=data.get("market", ""),
            token_id=token_id,
            # CLOB returns bids ascending / asks descending in some versions — normalize.
            bids=sorted(
                [Quote(price=float(b["price"]), size=float(b["size"]))
                 for b in data.get("bids", [])],
                key=lambda q: q.price, reverse=True,
            ),
            asks=sorted(
                [Quote(price=float(a["price"]), size=float(a["size"]))
                 for a in data.get("asks", [])],
                key=lambda q: q.price,
            ),
        )

    async def get_book(self, market: Market, outcome_index: int = 0) -> OrderBook:
        if not market.token_ids:
            raise ValueError(f"market {market.market_id} has no CLOB token ids")
        return await self.get_book_by_token(market.token_ids[outcome_index])

    # ---- Whale tracking (Data API — all positions/trades are public) ----

    async def get_wallet_trades(self, wallet: str, limit: int = 100) -> list[WhaleSignal]:
        rows = await self._get(f"{self.data_api}/trades", {"user": wallet, "limit": limit})
        signals: list[WhaleSignal] = []
        for t in rows:
            try:
                signals.append(
                    WhaleSignal(
                        wallet=wallet,
                        market_id=str(t.get("conditionId", "")),
                        question=t.get("title"),
                        outcome=str(t.get("outcome", "")),
                        side=("buy" if str(t.get("side", "")).upper() == "BUY" else "sell"),
                        price=float(t.get("price", 0)),
                        size_usd=float(t.get("size", 0)) * float(t.get("price", 0)),
                        ts=datetime.fromtimestamp(int(t.get("timestamp", 0))),
                        raw=t,
                    )
                )
            except (TypeError, ValueError):
                continue
        return signals

    async def get_wallet_positions(self, wallet: str, limit: int = 100) -> list[dict]:
        return await self._get(f"{self.data_api}/positions", {"user": wallet, "limit": limit})

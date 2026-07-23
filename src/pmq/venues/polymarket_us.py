"""Polymarket US adapter — CFTC-regulated DCM (QCX LLC d/b/a Polymarket US).

Separate stack from polymarket.com: fiat USD, centralized clearing, no on-chain settlement.
REST base: https://api.polymarket.us/v1

Auth (docs.polymarket.us/api-reference/authentication, July 2026):
  Ed25519 signature over timestamp + method + path.
  Headers: X-PM-Access-Key, X-PM-Timestamp (ms, +/-30s tolerance), X-PM-Signature.
  Keys created at polymarket.us/developer AFTER in-app KYC (name/address/SSN/DOB via Socure).

Rate limits: 20 req/s per API key (institutional gateway 100 msg/s; FIX 150 msg/s).
Fees (effective 2026-07-01): taker theta 0.06; MAKER REBATE theta -0.0125. Volume-tiered
taker rebates: 10%/25%/50% at $250k/$1M/$10M prior-month volume. See core/fees.py.

IMPLEMENTATION SEAM: the exact signing message byte-format (separators, path prefix,
casing) must be confirmed against docs.polymarket.us with real keys in hand — this
implementation follows the documented pattern (timestamp+method+path) and isolates it
in `sign_request` so fixing the format is a one-function change. Endpoint paths below
marked TODO(verify) are placeholders to confirm against the OpenAPI reference before
first live call. Everything is gated behind Mode.LIVE anyway.
"""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tenacity import retry, stop_after_attempt, wait_exponential

from pmq.config import settings
from pmq.core.models import Market, Order, OrderBook, Venue


class PolymarketUSAuthError(RuntimeError):
    pass


def load_private_key(b64_seed: str) -> Ed25519PrivateKey:
    raw = base64.b64decode(b64_seed)
    if len(raw) != 32:
        raise PolymarketUSAuthError("PMUS_PRIVATE_KEY_B64 must decode to a 32-byte Ed25519 seed")
    return Ed25519PrivateKey.from_private_bytes(raw)


def sign_request(key: Ed25519PrivateKey, timestamp_ms: str, method: str, path: str) -> str:
    msg = f"{timestamp_ms}{method.upper()}{path}".encode()
    return base64.b64encode(key.sign(msg)).decode()


class PolymarketUSClient:
    def __init__(self) -> None:
        s = settings()
        self.base = s.pmus_base
        self.access_key = s.pmus_access_key
        self._key: Ed25519PrivateKey | None = (
            load_private_key(s.pmus_private_key_b64) if s.pmus_private_key_b64 else None
        )
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, method: str, path: str) -> dict[str, str]:
        if self._key is None:
            return {}
        ts = str(int(time.time() * 1000))
        return {
            "X-PM-Access-Key": self.access_key,
            "X-PM-Timestamp": ts,
            "X-PM-Signature": sign_request(self._key, ts, method, path),
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    async def _request(self, method: str, path: str, **kwargs) -> Any:
        r = await self._client.request(
            method, f"{self.base}{path}", headers=self._headers(method, path), **kwargs
        )
        r.raise_for_status()
        return r.json()

    async def get_markets(self, **filters) -> list[Market]:
        # TODO(verify): confirm path + response shape against docs.polymarket.us OpenAPI.
        data = await self._request("GET", "/markets", params=filters)
        rows = data.get("markets", data if isinstance(data, list) else [])
        return [
            Market(
                venue=Venue.POLYMARKET_US,
                market_id=str(m.get("id") or m.get("ticker", "")),
                question=m.get("title") or m.get("question", ""),
                raw=m,
            )
            for m in rows
        ]

    async def get_book(self, market: Market, outcome_index: int = 0) -> OrderBook:
        # TODO(verify): confirm path + response shape.
        data = await self._request("GET", f"/markets/{market.market_id}/orderbook")
        _ = data
        return OrderBook(venue=Venue.POLYMARKET_US, market_id=market.market_id)

    async def get_balance(self) -> float:
        # TODO(verify): confirm path.
        data = await self._request("GET", "/portfolio/balance")
        return float(data.get("balance", 0))

    async def place_order(self, order: Order) -> Order:
        raise NotImplementedError(
            "Wire after KYC + API keys exist and order schema is confirmed against "
            "docs.polymarket.us. Deliberately unimplemented to make accidental live "
            "trading impossible."
        )

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

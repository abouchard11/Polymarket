"""Kalshi adapter — US-legal execution venue with a DEMO environment (paper trading).

Auth (docs.kalshi.com/getting_started/api_keys, verified July 2026):
  Sign  msg = f"{timestamp_ms}{METHOD}{path}"  (path includes /trade-api/v2 prefix,
  query string stripped) with RSA-PSS SHA256 (salt = digest length), base64 the signature.
  Headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP.

Rate limits: Basic tier 200 read / 100 write tokens per second (most calls cost 10),
token-bucket with ~1-2s burst budget; 429 on exceed. Apply for Advanced when needed.

Fees (fee schedule PDF, effective 2026-02-05): taker = ceil(0.07*C*P*(1-P)) per cent;
maker 0.0175 on designated series only. See core/fees.py.

Env: prod https://external-api.kalshi.com/trade-api/v2
     demo https://external-api.demo.kalshi.co/trade-api/v2   <- paper mode default
"""

from __future__ import annotations

import base64
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from tenacity import retry, stop_after_attempt, wait_exponential

from pmq.config import settings
from pmq.core.models import Market, Order, OrderBook, Quote, Venue


class KalshiAuthError(RuntimeError):
    pass


def _load_private_key(path: str) -> rsa.RSAPrivateKey:
    pem = Path(path).read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise KalshiAuthError("Kalshi private key must be RSA")
    return key


def sign_request(key: rsa.RSAPrivateKey, timestamp_ms: str, method: str, path: str) -> str:
    """RSA-PSS SHA256 over timestamp+METHOD+path. Path keeps the /trade-api/v2 prefix,
    drops the query string."""
    msg = f"{timestamp_ms}{method.upper()}{path}".encode()
    sig = key.sign(
        msg,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode()


class KalshiClient:
    def __init__(self) -> None:
        s = settings()
        self.base = s.kalshi_base
        self.api_key_id = s.kalshi_api_key_id
        self._key: rsa.RSAPrivateKey | None = None
        if self.api_key_id and Path(s.kalshi_private_key_path).exists():
            self._key = _load_private_key(s.kalshi_private_key_path)
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, method: str, url: str) -> dict[str, str]:
        if self._key is None:
            return {}
        ts = str(int(time.time() * 1000))
        path = urlparse(url).path
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sign_request(self._key, ts, method, path),
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base}{path}"
        r = await self._client.request(method, url, headers=self._headers(method, url), **kwargs)
        r.raise_for_status()
        return r.json()

    # ---- market data (public) ----

    async def get_markets(self, limit: int = 100, status: str = "open", **extra) -> list[Market]:
        params = {"limit": limit, "status": status, **extra}
        data = await self._request("GET", "/markets", params=params)
        out: list[Market] = []
        for m in data.get("markets", []):
            close = m.get("close_time")
            out.append(
                Market(
                    venue=Venue.KALSHI,
                    market_id=m.get("ticker", ""),
                    question=m.get("title", ""),
                    outcomes=["Yes", "No"],
                    end_date=(
                        datetime.fromisoformat(close.replace("Z", "+00:00")) if close else None
                    ),
                    resolution_source=m.get("rules_primary"),
                    raw=m,
                )
            )
        return out

    async def get_book(self, market: Market, outcome_index: int = 0) -> OrderBook:
        data = await self._request("GET", f"/markets/{market.market_id}/orderbook")
        ob = data.get("orderbook") or {}
        # Kalshi books are [price_cents, count] on yes/no sides. Normalize to YES-side view:
        # a resting NO bid at price q is liquidity to BUY YES at (100 - q).
        yes_bids = [
            Quote(price=p / 100, size=s) for p, s in (ob.get("yes") or []) if s
        ]
        no_bids = [Quote(price=(100 - p) / 100, size=s) for p, s in (ob.get("no") or []) if s]
        return OrderBook(
            venue=Venue.KALSHI,
            market_id=market.market_id,
            bids=sorted(yes_bids, key=lambda q: q.price, reverse=True),
            asks=sorted(no_bids, key=lambda q: q.price),
            ts=datetime.now(UTC),
        )

    # ---- trading (auth required) ----

    async def get_balance(self) -> float:
        data = await self._request("GET", "/portfolio/balance")
        return float(data.get("balance", 0)) / 100  # cents -> dollars

    async def place_order(self, order: Order) -> Order:
        payload = {
            "ticker": order.market_id,
            "action": order.side.value,               # buy | sell
            "side": order.outcome.value,              # yes | no
            "type": "limit",
            "count": int(order.size),
            f"{order.outcome.value}_price": int(round(order.price * 100)),
            "client_order_id": f"pmq-{int(time.time() * 1000)}",
        }
        data = await self._request("POST", "/portfolio/orders", json=payload)
        o = data.get("order", {})
        order.order_id = o.get("order_id")
        order.status = o.get("status", "submitted")
        return order

    async def cancel_order(self, order_id: str) -> bool:
        await self._request("DELETE", f"/portfolio/orders/{order_id}")
        return True

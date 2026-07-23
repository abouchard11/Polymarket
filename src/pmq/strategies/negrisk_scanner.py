"""NegRisk sum-to-one scanner on Polymarket GLOBAL — measurement only for US operators.

Why keep it if we can't trade it:
1. It is the best free lab for learning where mispricings appear (new chaotic
   multi-outcome listings) — the same dynamics show up on Polymarket US and Kalshi
   multi-outcome events, which we CAN trade.
2. Polymarket has asked the CFTC to onshore the on-chain exchange. If that lands,
   this scanner becomes tradeable with an execution adapter drop-in.

Historical scale: $29.0M of the $39.6M total 2024-25 arb extraction was negRisk
sum-to-one (arXiv:2508.03474). 2026 reality: bot-saturated, scraps only (arXiv:2605.00864).
"""

from __future__ import annotations

import asyncio

from pmq.core.arb import negrisk_basket
from pmq.core.fees import POLYMARKET_GLOBAL_TAKER_RATE
from pmq.core.models import FeeCategory, Opportunity
from pmq.strategies.base import Strategy
from pmq.venues.polymarket_global import PolymarketGlobalData


class NegRiskScanner(Strategy):
    name = "negrisk_scanner"

    def __init__(
        self,
        data: PolymarketGlobalData,
        min_edge_bps: float = 100.0,
        max_events: int = 25,
        fee_category: FeeCategory = FeeCategory.OTHER,
    ) -> None:
        self.data = data
        self.min_edge_bps = min_edge_bps
        self.max_events = max_events
        self.fee_rate = POLYMARKET_GLOBAL_TAKER_RATE[fee_category]

    async def scan(self) -> list[Opportunity]:
        events = await self.data.get_events(limit=self.max_events)
        opportunities: list[Opportunity] = []
        for event in events:
            if not event.get("negRisk"):
                continue
            markets = event.get("markets") or []
            if len(markets) < 2:
                continue
            opp = await self._scan_event(event, markets)
            if opp is not None:
                opportunities.append(opp)
        return opportunities

    async def _scan_event(self, event: dict, markets: list[dict]) -> Opportunity | None:
        import json

        asks: list[tuple[str, float, float]] = []
        bids: list[tuple[str, float, float]] = []

        async def fetch(m: dict) -> None:
            token_ids = m.get("clobTokenIds")
            if isinstance(token_ids, str):
                try:
                    token_ids = json.loads(token_ids)
                except json.JSONDecodeError:
                    return
            if not token_ids:
                return
            try:
                book = await self.data.get_book_by_token(str(token_ids[0]))  # YES token
            except Exception:
                return
            outcome = m.get("groupItemTitle") or m.get("question", "?")
            if book.best_ask:
                asks.append((outcome, book.best_ask.price, book.best_ask.size))
            if book.best_bid:
                bids.append((outcome, book.best_bid.price, book.best_bid.size))

        await asyncio.gather(*(fetch(m) for m in markets[:20]))
        if len(asks) < len(markets[:20]) or len(asks) < 2:
            return None  # incomplete basket — a partial basket is directional, not arb

        result = negrisk_basket(asks, bids, per_leg_fee_rate=self.fee_rate)
        if result.direction == "none" or result.edge_per_basket <= 0:
            return None
        edge_bps = (result.edge_per_basket / max(result.basket_cost, 1e-9)) * 10_000
        if edge_bps < self.min_edge_bps:
            return None
        return Opportunity(
            strategy=self.name,
            description=(
                f"[MEASUREMENT ONLY — US geo-blocked] {event.get('title', '?')}: "
                f"{result.direction} edge {result.edge_per_basket:.4f}/basket "
                f"x {result.max_baskets:.0f} baskets"
            ),
            edge_per_contract=result.edge_per_basket,
            edge_bps=edge_bps,
            max_size=result.max_baskets,
            capital_required=result.basket_cost * result.max_baskets,
            legs=[{"outcome": o, "price": p, "depth": d} for o, p, d in result.legs],
        )

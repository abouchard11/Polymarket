"""Cross-venue arbitrage scanner: Polymarket US <-> Kalshi (both US-legal).

Evidence (RESEARCH.md #2): persistent 2-4% execution-aware deviations on cross-listed
events (TU Munich, arXiv:2601.01706); 8.1pp Kalshi/Polymarket gap at 2024 election peak.
Constraints that eat the edge: hold-to-resolution capital lockup, BOTH venues' fees,
and above all RESOLUTION-SEMANTICS MISMATCH — 'identical' markets often aren't.

Design decisions baked in:
1. Pairs come from a human-curated registry (config/pairs.yaml). resolution_verified=False
   pairs are scanned and logged but NEVER executed. Wording risk is the #1 documented
   loss source; no fuzzy string matching gets to spend money.
2. Fee-aware: Kalshi taker ceil-to-cent + PMUS taker theta 0.06 applied per leg.
3. Sizing respects top-of-book depth only (UCLA paper: depth beyond top-of-book is
   mostly illusory for these markets).
"""

from __future__ import annotations

from datetime import UTC, datetime

import yaml

from pmq.core.arb import two_leg_arb
from pmq.core.fees import kalshi_taker_fee, polymarket_us_fee
from pmq.core.models import EventPair, Market, Opportunity, Venue
from pmq.strategies.base import Strategy
from pmq.venues.kalshi import KalshiClient
from pmq.venues.polymarket_us import PolymarketUSClient


def load_pairs(path: str = "config/pairs.yaml") -> list[EventPair]:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return []
    return [EventPair(**p) for p in raw.get("pairs", [])]


class CrossVenueArb(Strategy):
    name = "cross_venue_arb"

    def __init__(
        self,
        kalshi: KalshiClient,
        pmus: PolymarketUSClient | None = None,
        pairs: list[EventPair] | None = None,
        min_edge_bps: float = 150.0,
    ) -> None:
        self.kalshi = kalshi
        self.pmus = pmus
        self.pairs = pairs if pairs is not None else load_pairs()
        self.min_edge_bps = min_edge_bps

    async def scan(self) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        for pair in self.pairs:
            try:
                opp = await self._scan_pair(pair)
            except Exception:
                continue  # single-pair failure must not kill the scan cycle
            if opp is not None:
                opportunities.append(opp)
        return opportunities

    async def _scan_pair(self, pair: EventPair) -> Opportunity | None:
        if self.pmus is None:
            return None
        # Leg A: buy YES on Polymarket US; Leg B: buy NO on Kalshi (and the reverse).
        pmus_market = Market(venue=Venue.POLYMARKET_US, market_id=pair.market_a, question=pair.name)
        kalshi_market = Market(venue=Venue.KALSHI, market_id=pair.market_b, question=pair.name)

        pmus_book = await self.pmus.get_book(pmus_market)
        kalshi_book = await self.kalshi.get_book(kalshi_market)
        if not (pmus_book.best_ask and kalshi_book.best_bid):
            return None

        days = None
        if pair.resolution_date:
            days = max(
                (pair.resolution_date - datetime.now(UTC)).total_seconds() / 86_400, 0.01
            )

        # Direction 1: YES @ PMUS ask, NO @ Kalshi. Buying NO at price q costs (1 - best_yes_bid).
        p_yes = pmus_book.best_ask.price
        p_no = 1.0 - kalshi_book.best_bid.price
        result = two_leg_arb(
            p_yes_a=p_yes,
            depth_yes_a=pmus_book.best_ask.size,
            fee_yes_a=polymarket_us_fee(1, p_yes, is_taker=True),
            p_no_b=p_no,
            depth_no_b=kalshi_book.best_bid.size,
            fee_no_b=kalshi_taker_fee(1, p_no),
            days_to_resolution=days,
        )
        if result.edge_bps < self.min_edge_bps or result.max_pairs <= 0:
            return None
        return Opportunity(
            strategy=self.name,
            description=(
                f"{pair.name}: YES@PMUS {p_yes:.3f} + NO@Kalshi {p_no:.3f} "
                f"-> edge {result.edge_per_pair:.4f}/pair"
                + ("" if pair.resolution_verified else "  [UNVERIFIED PAIR — no execution]")
            ),
            edge_per_contract=result.edge_per_pair,
            edge_bps=result.edge_bps,
            max_size=result.max_pairs,
            capital_required=result.capital_required,
            annualized_return=result.annualized_return,
            legs=[
                {"venue": "polymarket_us", "market": pair.market_a, "side": "buy_yes",
                 "price": p_yes},
                {"venue": "kalshi", "market": pair.market_b, "side": "buy_no", "price": p_no},
            ],
        )

"""Pure arbitrage math. No I/O — fully unit-testable.

Two documented arb families (see RESEARCH.md for evidence and current viability):

1. Cross-venue two-leg: buy YES on venue A at pA, buy NO on venue B at pB for the SAME
   real-world event. Guaranteed $1 payout per contract pair at resolution iff resolution
   semantics are truly identical (EventPair.resolution_verified gate).
   Profit iff pA + pB + fees < 1.

2. NegRisk basket (Polymarket global, multi-outcome mutually-exclusive events):
   sum of YES asks < $1 -> buy all outcomes, guaranteed $1 basket payout.
   sum of best bids > $1 -> short the basket (requires mint/CTF on the global venue —
   scanner-only for US operators; we measure, we don't trade it).

History: $39.6M extracted Apr'24-Apr'25 (arXiv:2508.03474), but 2026 NBA measurement found
only ~$770/month executable at retail size (arXiv:2605.00864). Treat as opportunistic
scanner output around chaotic new listings and big events, not a business.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TwoLegArb:
    cost_per_pair: float        # pA + pB + fees, per contract pair
    edge_per_pair: float        # 1.0 - cost_per_pair
    edge_bps: float             # edge / cost in basis points
    max_pairs: float            # executable size = min of both legs' depth
    capital_required: float     # cost * pairs (locked until resolution)
    annualized_return: float | None


def two_leg_arb(
    p_yes_a: float,
    depth_yes_a: float,
    fee_yes_a: float,
    p_no_b: float,
    depth_no_b: float,
    fee_no_b: float,
    days_to_resolution: float | None = None,
    slippage_buffer: float = 0.002,
) -> TwoLegArb:
    """Evaluate buy-YES@A + buy-NO@B. Fees are per-contract dollar amounts for ONE contract.

    Returns edge <= 0 when there is no arb — caller filters on edge_bps > min_edge_bps.
    """
    cost = p_yes_a + p_no_b + fee_yes_a + fee_no_b + slippage_buffer
    edge = 1.0 - cost
    pairs = max(0.0, min(depth_yes_a, depth_no_b))
    capital = cost * pairs if pairs else 0.0
    edge_bps = (edge / cost) * 10_000 if cost > 0 else 0.0
    annualized = None
    if days_to_resolution and days_to_resolution > 0 and cost > 0:
        annualized = (edge / cost) * (365.0 / days_to_resolution)
    return TwoLegArb(
        cost_per_pair=cost,
        edge_per_pair=edge,
        edge_bps=edge_bps,
        max_pairs=pairs,
        capital_required=capital,
        annualized_return=annualized,
    )


@dataclass(frozen=True)
class BasketArb:
    direction: str              # "buy_all_yes" | "short_basket" | "none"
    basket_cost: float          # sum of asks (+fees) for buy_all_yes
    edge_per_basket: float
    max_baskets: float          # bounded by thinnest leg
    legs: tuple[tuple[str, float, float], ...]  # (outcome_id, price, depth)


def negrisk_basket(
    asks: list[tuple[str, float, float]],   # (outcome_id, best_ask, ask_depth)
    bids: list[tuple[str, float, float]],   # (outcome_id, best_bid, bid_depth)
    per_leg_fee_rate: float = 0.0,          # geopolitics = 0; others per fees.py
    slippage_buffer: float = 0.002,
) -> BasketArb:
    """Sum-to-one check across all outcomes of a mutually-exclusive event.

    Only top-of-book. A real implementation should walk depth (UCLA methodology:
    executable profit collapses fast beyond top-of-book).
    """
    if not asks:
        return BasketArb("none", 0.0, 0.0, 0.0, ())

    ask_sum = sum(p for _, p, _ in asks)
    ask_fees = sum(per_leg_fee_rate * p * (1 - p) for _, p, _ in asks)
    buy_cost = ask_sum + ask_fees + slippage_buffer
    if buy_cost < 1.0:
        return BasketArb(
            direction="buy_all_yes",
            basket_cost=buy_cost,
            edge_per_basket=1.0 - buy_cost,
            max_baskets=min(d for _, _, d in asks),
            legs=tuple(asks),
        )

    if bids:
        bid_sum = sum(p for _, p, _ in bids)
        bid_fees = sum(per_leg_fee_rate * p * (1 - p) for _, p, _ in bids)
        sell_value = bid_sum - bid_fees - slippage_buffer
        if sell_value > 1.0:
            return BasketArb(
                direction="short_basket",
                basket_cost=sell_value,
                edge_per_basket=sell_value - 1.0,
                max_baskets=min(d for _, _, d in bids),
                legs=tuple(bids),
            )

    return BasketArb("none", buy_cost, 0.0, 0.0, ())

"""Execution engine: the ONLY code path that touches order endpoints.

Mode gating:
  dry_run -> log every intent, send nothing (default)
  paper   -> Kalshi demo env gets real orders; everything else logged
  live    -> real orders, still risk-checked per order

Every order passes RiskManager.check_order first. Fail-closed: any exception in the
risk layer means no order goes out.
"""

from __future__ import annotations

import logging

from pmq.config import Mode, settings
from pmq.core.models import Opportunity, Order, Venue
from pmq.core.risk import RiskManager, RiskViolation
from pmq.venues.base import ExecutionVenue

log = logging.getLogger("pmq.execution")


class ExecutionEngine:
    def __init__(
        self, risk: RiskManager, venues: dict[Venue, ExecutionVenue] | None = None
    ) -> None:
        self.risk = risk
        self.venues = venues or {}
        self.mode = settings().pmq_mode

    async def submit(self, order: Order, edge_bps: float | None = None) -> Order:
        notional = order.price * order.size
        try:
            self.risk.check_order(order.market_id, notional, edge_bps)
        except RiskViolation as e:
            order.status = f"rejected_risk: {e}"
            log.warning("RISK REJECT %s %s: %s", order.venue.value, order.market_id, e)
            return order

        if self.mode == Mode.DRY_RUN:
            order.status = "dry_run"
            log.info(
                "DRY RUN %s %s %s %s %.0f @ %.3f (notional %.2f)",
                order.venue.value, order.market_id, order.side.value,
                order.outcome.value, order.size, order.price, notional,
            )
            return order

        if self.mode == Mode.PAPER and order.venue != Venue.KALSHI:
            order.status = "paper_logged"  # only Kalshi has a demo env
            log.info("PAPER (logged only) %s %s", order.venue.value, order.market_id)
            return order

        venue = self.venues.get(order.venue)
        if venue is None:
            order.status = "rejected_no_venue"
            return order

        placed = await venue.place_order(order)
        self.risk.register_fill(order.market_id, notional)
        log.info("SENT %s %s -> %s", order.venue.value, order.market_id, placed.status)
        return placed

    async def execute_opportunity(self, opp: Opportunity) -> list[Order]:
        """Turn an Opportunity's legs into orders. Both-or-nothing is NOT guaranteed
        across venues — leg risk is real. Start with alert-only; wire execution when
        the pair registry and fill telemetry justify it."""
        log.info(
            "OPPORTUNITY [%s] edge=%.0fbps size=%.0f capital=%.2f :: %s",
            opp.strategy, opp.edge_bps, opp.max_size, opp.capital_required, opp.description,
        )
        return []  # deliberate: alert-only until leg-risk handling is built

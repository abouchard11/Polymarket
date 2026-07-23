"""Risk manager: hard limits every order must pass. Fail-closed by design.

Evidence basis (RESEARCH.md): 68.8% of Polymarket users lose money; a single adverse
30-40% move can erase weeks of MM/reward gains (tezlee postmortem). Limits are not
optional decoration — they are the difference between a drawdown and a blowup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

KILL_SWITCH_FILE = Path("KILL")  # touch this file in repo root -> all trading halts


class RiskViolation(Exception):
    pass


@dataclass
class RiskLimits:
    max_notional_per_market: float = 500.0
    max_total_notional: float = 2_000.0
    max_daily_loss: float = 200.0
    min_edge_bps: float = 150.0
    require_pair_verified: bool = True


@dataclass
class RiskManager:
    limits: RiskLimits = field(default_factory=RiskLimits)
    open_notional: dict[str, float] = field(default_factory=dict)  # market_id -> $
    realized_pnl_today: float = 0.0
    _pnl_date: date = field(default_factory=date.today)

    def _roll_day(self) -> None:
        today = date.today()
        if today != self._pnl_date:
            self._pnl_date = today
            self.realized_pnl_today = 0.0

    @property
    def total_notional(self) -> float:
        return sum(self.open_notional.values())

    def kill_switch_active(self) -> bool:
        return KILL_SWITCH_FILE.exists()

    def check_order(self, market_id: str, notional: float, edge_bps: float | None = None) -> None:
        """Raises RiskViolation if the order must not go out. Call before EVERY order."""
        self._roll_day()
        if self.kill_switch_active():
            raise RiskViolation("kill switch file present — trading halted")
        if self.realized_pnl_today <= -abs(self.limits.max_daily_loss):
            raise RiskViolation(
                f"daily loss limit hit ({self.realized_pnl_today:.2f} <= "
                f"-{self.limits.max_daily_loss:.2f})"
            )
        if notional <= 0:
            raise RiskViolation("non-positive notional")
        market_after = self.open_notional.get(market_id, 0.0) + notional
        if market_after > self.limits.max_notional_per_market:
            raise RiskViolation(
                f"per-market cap exceeded: {market_after:.2f} > "
                f"{self.limits.max_notional_per_market:.2f}"
            )
        if self.total_notional + notional > self.limits.max_total_notional:
            raise RiskViolation(
                f"total notional cap exceeded: {self.total_notional + notional:.2f} > "
                f"{self.limits.max_total_notional:.2f}"
            )
        if edge_bps is not None and edge_bps < self.limits.min_edge_bps:
            raise RiskViolation(
                f"edge {edge_bps:.0f}bps below minimum {self.limits.min_edge_bps:.0f}bps"
            )

    def register_fill(self, market_id: str, notional: float) -> None:
        self.open_notional[market_id] = self.open_notional.get(market_id, 0.0) + notional

    def register_close(self, market_id: str, notional: float, pnl: float) -> None:
        self._roll_day()
        remaining = self.open_notional.get(market_id, 0.0) - notional
        if remaining <= 0:
            self.open_notional.pop(market_id, None)
        else:
            self.open_notional[market_id] = remaining
        self.realized_pnl_today += pnl

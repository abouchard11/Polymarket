"""Strategy interface: pure decision logic in, Opportunities/Signals out.

Strategies NEVER place orders directly. They emit Opportunity objects; the execution
engine applies risk checks and mode gating (dry_run/paper/live). This separation is
what makes every strategy backtestable and testable without a network.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pmq.core.models import Opportunity


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    async def scan(self) -> list[Opportunity]:
        """One scan cycle. Return zero or more opportunities. Must not place orders."""
        raise NotImplementedError

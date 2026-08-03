"""Fee math for all three venues. Verified against official docs, July 2026.

Polymarket global (docs.polymarket.com/trading/fees):
    fee = C * feeRate * p * (1 - p)         [maker fee = 0 all categories]
    taker feeRate: crypto 0.07 | sports/econ/culture/weather/other 0.05
                   finance/politics/mentions/tech 0.04 | geopolitics 0.00

Polymarket US (docs.polymarket.us/fees, effective 2026-07-01):
    fee = theta * C * p * (1 - p)
    taker theta = 0.06 ; maker theta = -0.0125 (a REBATE — makers get paid)
    banker's rounding to $0.01

Kalshi (kalshi.com/docs/kalshi-fee-schedule.pdf, effective 2026-02-05):
    taker fee = ceil_to_cent(0.07 * C * P * (1 - P))   [INX/NASDAQ100 series: 0.035]
    maker fee = 0.0175 * C * P * (1 - P) on designated series only, else 0

The zero-fee Polymarket era ended Jan-Mar 2026. Any arb math that ignores fees is wrong.
"""

from __future__ import annotations

import math

from pmq.core.models import FeeCategory

POLYMARKET_GLOBAL_TAKER_RATE: dict[FeeCategory, float] = {
    FeeCategory.CRYPTO: 0.07,
    FeeCategory.SPORTS: 0.05,
    FeeCategory.ECONOMICS: 0.05,
    FeeCategory.CULTURE: 0.05,
    FeeCategory.WEATHER: 0.05,
    FeeCategory.OTHER: 0.05,
    FeeCategory.FINANCE: 0.04,
    FeeCategory.POLITICS: 0.04,
    FeeCategory.MENTIONS: 0.04,
    FeeCategory.TECH: 0.04,
    FeeCategory.GEOPOLITICS: 0.0,
}

PMUS_TAKER_THETA = 0.06
PMUS_MAKER_THETA = -0.0125  # rebate

KALSHI_TAKER_RATE = 0.07
KALSHI_INDEX_TAKER_RATE = 0.035  # INX / NASDAQ100 series
KALSHI_MAKER_RATE = 0.0175       # designated series only


def _base(contracts: float, price: float, rate: float) -> float:
    if not 0.0 < price < 1.0:
        return 0.0
    return contracts * rate * price * (1.0 - price)


def polymarket_global_taker_fee(
    contracts: float, price: float, category: FeeCategory = FeeCategory.OTHER
) -> float:
    """Global venue taker fee in USD. Maker fee is always 0."""
    return _base(contracts, price, POLYMARKET_GLOBAL_TAKER_RATE[category])


def polymarket_us_fee(contracts: float, price: float, is_taker: bool = True) -> float:
    """Polymarket US fee in USD. Negative return value = maker rebate paid to you."""
    theta = PMUS_TAKER_THETA if is_taker else PMUS_MAKER_THETA
    raw = _base(contracts, price, theta)
    # Docs specify banker's rounding to $0.01
    return round(raw, 2)


def _ceil_cent(raw: float) -> float:
    """Ceil to the next cent, guarding float artifacts (0.07*100*0.25 -> 1.7500000000000002
    must round to 1.75, not 1.76)."""
    return math.ceil(round(raw * 100, 6)) / 100


def kalshi_taker_fee(contracts: float, price: float, index_series: bool = False) -> float:
    """Kalshi taker fee in USD — rounded UP to the next cent per the fee schedule."""
    rate = KALSHI_INDEX_TAKER_RATE if index_series else KALSHI_TAKER_RATE
    return _ceil_cent(_base(contracts, price, rate))


def kalshi_maker_fee(contracts: float, price: float, designated_series: bool = False) -> float:
    """Kalshi maker fee — only on designated series (list at kalshi.com/fee-schedule)."""
    if not designated_series:
        return 0.0
    return _ceil_cent(_base(contracts, price, KALSHI_MAKER_RATE))

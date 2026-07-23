"""Fee math tests — numbers cross-checked against official docs (July 2026).

Known reference points:
- Polymarket global crypto (0.07) at p=0.50, 100 shares: $1.75 max fee.
- Polymarket global 5%-category at p=0.50, 100 shares: $1.25.
- Polymarket global 4%-category at p=0.50, 100 shares: $1.00.
- Geopolitics: fee-free.
- Polymarket US taker (0.06) at p=0.50, 100 lots: $1.50. Maker rebate: -$0.31.
- Kalshi taker at p=0.50, 100 contracts: ceil(0.07*100*0.25) = $1.75.
"""

import math

import pytest

from pmq.core.fees import (
    kalshi_maker_fee,
    kalshi_taker_fee,
    polymarket_global_taker_fee,
    polymarket_us_fee,
)
from pmq.core.models import FeeCategory


def test_global_crypto_max_fee():
    assert polymarket_global_taker_fee(100, 0.50, FeeCategory.CRYPTO) == pytest.approx(1.75)


def test_global_five_percent_categories():
    for cat in (FeeCategory.SPORTS, FeeCategory.ECONOMICS, FeeCategory.CULTURE,
                FeeCategory.WEATHER, FeeCategory.OTHER):
        assert polymarket_global_taker_fee(100, 0.50, cat) == pytest.approx(1.25)


def test_global_four_percent_categories():
    for cat in (FeeCategory.FINANCE, FeeCategory.POLITICS, FeeCategory.MENTIONS,
                FeeCategory.TECH):
        assert polymarket_global_taker_fee(100, 0.50, cat) == pytest.approx(1.00)


def test_global_geopolitics_free():
    assert polymarket_global_taker_fee(100, 0.50, FeeCategory.GEOPOLITICS) == 0.0


def test_fee_symmetry_around_half():
    a = polymarket_global_taker_fee(100, 0.30, FeeCategory.SPORTS)
    b = polymarket_global_taker_fee(100, 0.70, FeeCategory.SPORTS)
    assert a == pytest.approx(b)


def test_fee_near_certainty_is_tiny():
    # Bonding at 0.99 barely gets touched by fees — relevant to resolution plays.
    fee = polymarket_global_taker_fee(100, 0.99, FeeCategory.POLITICS)
    assert fee < 0.05


def test_pmus_taker_max():
    assert polymarket_us_fee(100, 0.50, is_taker=True) == pytest.approx(1.50)


def test_pmus_maker_rebate_negative():
    rebate = polymarket_us_fee(100, 0.50, is_taker=False)
    assert rebate == pytest.approx(-0.31, abs=0.005)
    assert rebate < 0  # makers GET PAID


def test_kalshi_taker_rounds_up():
    assert kalshi_taker_fee(100, 0.50) == pytest.approx(1.75)
    # 1 contract at 0.50: 0.07*1*0.25 = 0.0175 -> ceil to 0.02
    assert kalshi_taker_fee(1, 0.50) == pytest.approx(0.02)
    assert kalshi_taker_fee(1, 0.50) >= 0.07 * 1 * 0.25


def test_kalshi_index_series_half_rate():
    full = kalshi_taker_fee(100, 0.50, index_series=False)
    half = kalshi_taker_fee(100, 0.50, index_series=True)
    assert half == pytest.approx(full / 2, abs=0.01)


def test_kalshi_maker_only_designated():
    assert kalshi_maker_fee(100, 0.50, designated_series=False) == 0.0
    assert kalshi_maker_fee(100, 0.50, designated_series=True) == pytest.approx(
        math.ceil(0.0175 * 100 * 0.25 * 100) / 100
    )


def test_degenerate_prices_no_fee():
    assert polymarket_global_taker_fee(100, 0.0, FeeCategory.CRYPTO) == 0.0
    assert polymarket_global_taker_fee(100, 1.0, FeeCategory.CRYPTO) == 0.0

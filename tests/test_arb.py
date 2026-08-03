"""Arb math tests. The core invariant: fees flip marginal 'arbs' into losses —
any scanner that ignores them is a donation machine."""

import pytest

from pmq.core.arb import negrisk_basket, two_leg_arb
from pmq.core.fees import kalshi_taker_fee, polymarket_us_fee


def test_two_leg_clean_arb():
    # YES at 0.44 + NO at 0.50 = 0.94 gross -> real edge even after fees.
    r = two_leg_arb(
        p_yes_a=0.44, depth_yes_a=200, fee_yes_a=polymarket_us_fee(1, 0.44),
        p_no_b=0.50, depth_no_b=150, fee_no_b=kalshi_taker_fee(1, 0.50),
        days_to_resolution=30,
    )
    assert r.edge_per_pair > 0
    assert r.max_pairs == 150  # min of both depths
    assert r.annualized_return is not None and r.annualized_return > 0


def test_two_leg_fees_kill_marginal_arb():
    # 0.495 + 0.495 = 0.99 gross looks like a 1% arb; fees + slippage buffer eat it.
    fee_a = polymarket_us_fee(1, 0.495)
    fee_b = kalshi_taker_fee(1, 0.495)
    r = two_leg_arb(
        p_yes_a=0.495, depth_yes_a=100, fee_yes_a=fee_a,
        p_no_b=0.495, depth_no_b=100, fee_no_b=fee_b,
    )
    # Kalshi rounds 1-contract fee up to a cent (0.02) — at 1 contract granularity the
    # rounded fees plus buffer exceed the 1c gross edge.
    assert r.edge_per_pair < 0.01
    assert r.edge_bps < 150  # falls below default min_edge_bps -> filtered


def test_two_leg_no_arb_negative_edge():
    r = two_leg_arb(
        p_yes_a=0.60, depth_yes_a=100, fee_yes_a=0.0,
        p_no_b=0.45, depth_no_b=100, fee_no_b=0.0,
    )
    assert r.edge_per_pair < 0


def test_negrisk_buy_all_yes():
    asks = [("A", 0.30, 100), ("B", 0.30, 80), ("C", 0.35, 120)]  # sum 0.95
    r = negrisk_basket(asks, bids=[], per_leg_fee_rate=0.0)
    assert r.direction == "buy_all_yes"
    assert r.edge_per_basket == pytest.approx(1.0 - (0.95 + 0.002))
    assert r.max_baskets == 80  # thinnest leg bounds the basket


def test_negrisk_fees_flip_it():
    asks = [("A", 0.33, 100), ("B", 0.33, 100), ("C", 0.33, 100)]  # sum 0.99
    clean = negrisk_basket(asks, bids=[], per_leg_fee_rate=0.0)
    taxed = negrisk_basket(asks, bids=[], per_leg_fee_rate=0.05)
    assert clean.direction == "buy_all_yes"
    assert taxed.direction == "none"  # 3 legs x 0.05*0.33*0.67 ≈ 0.033 in fees > 1c edge


def test_negrisk_short_basket():
    bids = [("A", 0.40, 50), ("B", 0.40, 60), ("C", 0.25, 40)]  # sum 1.05
    r = negrisk_basket(asks=[("A", 0.45, 50), ("B", 0.45, 60), ("C", 0.30, 40)], bids=bids,
                       per_leg_fee_rate=0.0)
    assert r.direction == "short_basket"
    assert r.max_baskets == 40


def test_negrisk_empty():
    r = negrisk_basket([], [])
    assert r.direction == "none"

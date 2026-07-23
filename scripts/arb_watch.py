#!/usr/bin/env python3
"""arb_watch.py — live arbitrage scanner for Polymarket (global CLOB data).

Watches two documented arb families continuously, fee- and depth-aware:

  1. BINARY REBALANCING: best_ask(YES) + best_ask(NO) < $1  -> buy both, guaranteed $1
     at resolution (or merge). Mirror check: best_bid(YES) + best_bid(NO) > $1 -> short
     the pair (requires inventory/minting — flagged, not actionable from cold start).
  2. NEGRISK BASKETS: sum of YES asks across a mutually-exclusive multi-outcome event
     < $1 -> buy the full basket. (Delegates to pmq.strategies.negrisk_scanner.)

REALITY CHECK (RESEARCH.md §2e): this family extracted $39.6M in the 2024-25 election
era and has since collapsed to scraps — bots with sub-second reactions own what's left.
Expect this scanner to print mostly nothing on a normal day. That silence is data: it
tells you the naked-arb pool is dry and the edge is elsewhere (see RESEARCH.md §5).

MEASUREMENT MODE: the global venue geo-blocks US trading, so this script only observes
and records. Execution seams for when you CAN trade:
  - Polymarket US <-> Kalshi cross-venue: pmq.strategies.cross_venue_arb (needs KYC+keys)
  - Global CLOB directly: only if Polymarket's pending CFTC onshoring lands.

Usage:
  python scripts/arb_watch.py                 # continuous, top 40 markets, 15s cadence
  python scripts/arb_watch.py --once          # single cycle, then exit
  python scripts/arb_watch.py --markets 100 --interval 30 --min-edge-bps 50
  python scripts/arb_watch.py --fee-rate 0.0  # geopolitics-only watchlist (fee-free)

Output: rich console alerts + parquet snapshots in data/raw/ (books + opportunities),
so every claimed opportunity is auditable later.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
from datetime import UTC, datetime

from rich.console import Console

from pmq.core.arb import negrisk_basket, two_leg_arb  # noqa: F401  (two_leg_arb: exec seam)
from pmq.core.models import Market, Opportunity
from pmq.data.recorder import ParquetRecorder
from pmq.strategies.negrisk_scanner import NegRiskScanner
from pmq.venues.polymarket_global import PolymarketGlobalData

logging.basicConfig(level=logging.WARNING)
console = Console()


async def scan_binary_rebalance(
    data: PolymarketGlobalData,
    market: Market,
    fee_rate: float,
    slippage_buffer: float = 0.002,
) -> Opportunity | None:
    """Family 1: YES ask + NO ask < $1 (long both sides of one binary market)."""
    if len(market.token_ids) < 2:
        return None
    try:
        yes_book, no_book = await asyncio.gather(
            data.get_book_by_token(market.token_ids[0]),
            data.get_book_by_token(market.token_ids[1]),
        )
    except Exception:
        return None

    if not (yes_book.best_ask and no_book.best_ask):
        return None

    p_yes, p_no = yes_book.best_ask.price, no_book.best_ask.price
    # Taker fee per contract on each leg: rate * p * (1-p)
    fees = fee_rate * p_yes * (1 - p_yes) + fee_rate * p_no * (1 - p_no)
    cost = p_yes + p_no + fees + slippage_buffer
    edge = 1.0 - cost
    if edge <= 0:
        # Mirror: rich pair on the bid side (needs inventory/mint -> observe only)
        if yes_book.best_bid and no_book.best_bid:
            bid_sum = yes_book.best_bid.price + no_book.best_bid.price
            if bid_sum - fees - slippage_buffer > 1.0:
                depth = min(yes_book.best_bid.size, no_book.best_bid.size)
                rich_edge = bid_sum - fees - slippage_buffer - 1.0
                return Opportunity(
                    strategy="binary_rebalance_short",
                    description=(
                        f"[needs inventory/mint] {market.question[:70]} :: "
                        f"bid_sum {bid_sum:.3f} > $1"
                    ),
                    edge_per_contract=rich_edge,
                    edge_bps=(rich_edge / 1.0) * 10_000,
                    max_size=depth,
                    capital_required=depth * 1.0,
                    legs=[{"side": "sell_yes", "price": yes_book.best_bid.price},
                          {"side": "sell_no", "price": no_book.best_bid.price}],
                )
        return None

    depth = min(yes_book.best_ask.size, no_book.best_ask.size)
    return Opportunity(
        strategy="binary_rebalance_long",
        description=(
            f"{market.question[:70]} :: YES {p_yes:.3f} + NO {p_no:.3f} "
            f"+ fees {fees:.4f} = {cost:.4f} < $1"
        ),
        edge_per_contract=edge,
        edge_bps=(edge / cost) * 10_000,
        max_size=depth,
        capital_required=cost * depth,
        legs=[{"side": "buy_yes", "price": p_yes, "depth": yes_book.best_ask.size},
              {"side": "buy_no", "price": p_no, "depth": no_book.best_ask.size}],
    )


async def one_cycle(
    data: PolymarketGlobalData,
    negrisk: NegRiskScanner,
    recorder: ParquetRecorder,
    n_markets: int,
    fee_rate: float,
    min_edge_bps: float,
    min_depth_usd: float,
) -> list[Opportunity]:
    hits: list[Opportunity] = []

    # Family 1 — binary pairs on the top-volume markets
    markets = await data.get_markets(limit=n_markets, order="volumeNum", ascending="false")
    binary = [m for m in markets if not m.neg_risk and len(m.token_ids) == 2]
    results = await asyncio.gather(
        *(scan_binary_rebalance(data, m, fee_rate) for m in binary)
    )
    hits += [o for o in results if o is not None]

    # Family 2 — negRisk baskets (scanner applies its own fee category)
    with contextlib.suppress(Exception):
        hits += await negrisk.scan()

    # Filter + record
    out: list[Opportunity] = []
    for opp in hits:
        if opp.edge_bps >= min_edge_bps and opp.capital_required >= min_depth_usd:
            recorder.record_opportunity(opp)
            out.append(opp)
    return out


async def main() -> None:
    ap = argparse.ArgumentParser(description="Polymarket live arb scanner (measurement mode)")
    ap.add_argument("--markets", type=int, default=40, help="top-volume markets per cycle")
    ap.add_argument("--interval", type=float, default=15.0, help="seconds between cycles")
    ap.add_argument("--min-edge-bps", type=float, default=50.0)
    ap.add_argument("--min-depth-usd", type=float, default=25.0)
    ap.add_argument("--fee-rate", type=float, default=0.05,
                    help="taker fee rate assumption (0.04-0.07 by category; 0 geopolitics)")
    ap.add_argument("--once", action="store_true", help="single cycle then exit")
    args = ap.parse_args()

    data = PolymarketGlobalData()
    negrisk = NegRiskScanner(data, min_edge_bps=args.min_edge_bps, max_events=25)
    recorder = ParquetRecorder()
    stop = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)

    console.print(
        f"[bold]arb_watch[/bold] — {args.markets} markets / {args.interval}s cadence / "
        f"min {args.min_edge_bps:.0f}bps @ ${args.min_depth_usd:.0f}+ depth / "
        f"fee assumption {args.fee_rate:.2f}  [dim](measurement mode — see header)[/dim]"
    )

    cycles = 0
    total_hits = 0
    try:
        while not stop.is_set():
            t0 = datetime.now(UTC)
            try:
                hits = await one_cycle(
                    data, negrisk, recorder, args.markets,
                    args.fee_rate, args.min_edge_bps, args.min_depth_usd,
                )
            except Exception as e:  # noqa: BLE001 — a bad cycle must not kill the watch
                console.print(f"[red]cycle error: {type(e).__name__}: {e}[/red]")
                hits = []
            cycles += 1
            total_hits += len(hits)
            for opp in hits:
                console.print(
                    f"[green]{t0:%H:%M:%S} {opp.edge_bps:6.0f}bps "
                    f"${opp.capital_required:8.2f} cap[/green]  "
                    f"[{opp.strategy}] {opp.description}"
                )
            if not hits:
                console.print(
                    f"[dim]{t0:%H:%M:%S} cycle {cycles}: nothing past threshold "
                    f"({total_hits} total hits this run)[/dim]"
                )
            if args.once:
                break
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=args.interval)
    finally:
        book_path, opp_path = recorder.flush()
        if opp_path:
            console.print(f"opportunities logged -> {opp_path}")
        await data.aclose()
        console.print(f"done: {cycles} cycles, {total_hits} qualifying opportunities")


if __name__ == "__main__":
    asyncio.run(main())

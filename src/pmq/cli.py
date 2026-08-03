"""pmq CLI — operational entry points.

  pmq doctor            environment + venue reachability check
  pmq markets           list live Polymarket global markets (public data)
  pmq book TOKEN_ID     show an order book
  pmq scan-negrisk      one negRisk sum-to-one scan cycle (measurement only)
  pmq whales            one whale-flow polling cycle
  pmq record            long-running order-book recorder for config/watchlist.yaml
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table

from pmq.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def doctor() -> None:
    """Check environment, credentials presence, and venue reachability."""

    async def _run() -> None:
        import httpx

        s = settings()
        table = Table(title="pmq doctor")
        table.add_column("check")
        table.add_column("status")

        table.add_row("mode", s.pmq_mode.value)
        kalshi_status = "set" if s.kalshi_api_key_id else "MISSING (ok for data-only)"
        table.add_row("kalshi creds", kalshi_status)
        table.add_row("pmus creds", "set" if s.pmus_access_key else "MISSING (ok for data-only)")

        async with httpx.AsyncClient(timeout=8) as client:
            for name, url in [
                ("gamma (global data)", f"{s.gamma_base}/markets?limit=1"),
                ("clob (global data)", f"{s.clob_base}/ok"),
                ("data-api (global data)", f"{s.data_api_base}/trades?limit=1"),
                ("kalshi", f"{s.kalshi_base}/markets?limit=1"),
            ]:
                try:
                    r = await client.get(url)
                    table.add_row(name, f"OK ({r.status_code})")
                except Exception as e:  # noqa: BLE001
                    table.add_row(name, f"FAIL: {type(e).__name__}")
        console.print(table)

    asyncio.run(_run())


@app.command()
def markets(limit: int = 10) -> None:
    """List active Polymarket global markets (public Gamma API)."""

    async def _run() -> None:
        from pmq.venues.polymarket_global import PolymarketGlobalData

        data = PolymarketGlobalData()
        try:
            rows = await data.get_markets(limit=limit, order="volumeNum", ascending="false")
            table = Table(title=f"Polymarket global — {len(rows)} active markets")
            table.add_column("question", max_width=60)
            table.add_column("negRisk")
            table.add_column("end")
            for m in rows:
                table.add_row(
                    m.question, "Y" if m.neg_risk else "",
                    m.end_date.date().isoformat() if m.end_date else "?",
                )
            console.print(table)
        finally:
            await data.aclose()

    asyncio.run(_run())


@app.command()
def book(token_id: str) -> None:
    """Show a Polymarket global order book by CLOB token id."""

    async def _run() -> None:
        from pmq.venues.polymarket_global import PolymarketGlobalData

        data = PolymarketGlobalData()
        try:
            ob = await data.get_book_by_token(token_id)
            table = Table(title=f"book {token_id[:16]}…")
            table.add_column("bid size")
            table.add_column("bid")
            table.add_column("ask")
            table.add_column("ask size")
            for i in range(5):
                table.add_row(
                    f"{ob.bids[i].size:.0f}" if i < len(ob.bids) else "",
                    f"{ob.bids[i].price:.3f}" if i < len(ob.bids) else "",
                    f"{ob.asks[i].price:.3f}" if i < len(ob.asks) else "",
                    f"{ob.asks[i].size:.0f}" if i < len(ob.asks) else "",
                )
            console.print(table)
        finally:
            await data.aclose()

    asyncio.run(_run())


@app.command("scan-negrisk")
def scan_negrisk(max_events: int = 25, min_edge_bps: float = 100.0) -> None:
    """One negRisk basket scan on global data (measurement only for US operators)."""

    async def _run() -> None:
        from pmq.strategies.negrisk_scanner import NegRiskScanner
        from pmq.venues.polymarket_global import PolymarketGlobalData

        data = PolymarketGlobalData()
        try:
            scanner = NegRiskScanner(data, min_edge_bps=min_edge_bps, max_events=max_events)
            opportunities = await scanner.scan()
            if not opportunities:
                console.print("[yellow]no baskets past threshold this cycle (normal in 2026 —"
                              " see RESEARCH.md)[/yellow]")
            for opp in opportunities:
                console.print(f"[green]{opp.edge_bps:.0f}bps[/green] {opp.description}")
        finally:
            await data.aclose()

    asyncio.run(_run())


@app.command()
def whales(min_size_usd: float = 2_000.0) -> None:
    """One whale polling cycle (wallets from config/whales.yaml)."""

    async def _run() -> None:
        from pmq.strategies.whale_signal import WhaleTracker
        from pmq.venues.polymarket_global import PolymarketGlobalData

        data = PolymarketGlobalData()
        try:
            tracker = WhaleTracker(data)
            if not tracker.whales:
                console.print("[red]config/whales.yaml missing or empty — copy "
                              "config/whales.example.yaml[/red]")
                return
            signals = await tracker.poll(min_size_usd=min_size_usd)
            for sig in signals:
                console.print(
                    f"[bold]{sig.alias}[/bold] {sig.side.value} {sig.outcome} "
                    f"@{sig.price:.3f} ${sig.size_usd:,.0f} :: {sig.question}"
                )
            if not signals:
                console.print("no fresh qualifying whale flow this cycle")
        finally:
            await data.aclose()

    asyncio.run(_run())


@app.command()
def record(
    config: str = typer.Option(
        "config/watchlist.yaml", "--config", help="path to watchlist YAML (see .example)"
    ),
    once: bool = typer.Option(
        False, "--once", help="poll every watchlisted market once, flush, then exit"
    ),
) -> None:
    """Long-running order-book recorder for a configured market watchlist -> parquet.

    Reads config/watchlist.yaml (roadmap M1 — see HANDOFF.md seam #2), resolves each
    slug to a market via Gamma, then polls order books on the yaml's cadence_seconds
    (default 30s) through the READ-ONLY polymarket_global adapter. Snapshots go through
    ParquetRecorder; a parquet file is flushed periodically and on shutdown so a crash
    never loses more than one flush interval. Ctrl-C / SIGTERM shuts down cleanly.
    """
    from pmq.data.record_loop import record_cycle, resolve_markets
    from pmq.data.recorder import ParquetRecorder
    from pmq.data.watchlist import WatchlistError, load_watchlist
    from pmq.venues.polymarket_global import PolymarketGlobalData

    try:
        watchlist = load_watchlist(config)
    except WatchlistError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from e

    async def _run() -> int:
        data = PolymarketGlobalData()
        recorder = ParquetRecorder(out_dir=watchlist.out_dir)
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(sig, stop.set)

        cycles = 0
        total_snapshots = 0
        try:
            resolved = await resolve_markets(data, watchlist.entries)
            if not resolved:
                console.print(
                    "[red]no watchlist markets resolved — check the slugs in "
                    f"{config} against `pmq markets` or polymarket.com URLs[/red]"
                )
                return 1

            n_books = sum(len(m.token_ids) for _, m in resolved)
            console.print(
                f"[bold]pmq record[/bold] — watching {len(resolved)} market(s), "
                f"{n_books} order book(s) / {watchlist.cadence_seconds:.0f}s cadence "
                f"-> {watchlist.out_dir}/"
            )
            for entry, market in resolved:
                label = entry.label or entry.slug
                console.print(f"  [dim]watching[/dim] {label} :: {market.question[:70]}")

            while not stop.is_set():
                t0 = datetime.now(UTC)
                n = await record_cycle(data, recorder, resolved)
                cycles += 1
                total_snapshots += n
                console.print(
                    f"[dim]{t0:%H:%M:%S} cycle {cycles}: {n} book snapshot(s) "
                    f"({total_snapshots} total this run)[/dim]"
                )

                if cycles % watchlist.flush_every_cycles == 0:
                    book_path, _ = recorder.flush()
                    if book_path:
                        console.print(f"  flushed -> {book_path}")

                if once:
                    break
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=watchlist.cadence_seconds)
        finally:
            book_path, opp_path = recorder.flush()
            if book_path:
                console.print(f"[bold]final flush[/bold] -> {book_path}")
            await data.aclose()
            console.print(f"done: {cycles} cycle(s), {total_snapshots} snapshot(s) written")
        return 0

    exit_code = asyncio.run(_run())
    if exit_code:
        raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()

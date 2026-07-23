"""Order book / opportunity recorder -> parquet. The backtest data foundation.

You cannot evaluate any of these strategies without recorded books. Run the recorder
for 2+ weeks on your candidate markets BEFORE risking a dollar. Historical depth:
Jon-Becker/prediction-market-analysis (36GiB Polymarket+Kalshi archive) for backfill.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pmq.core.models import Opportunity, OrderBook


class ParquetRecorder:
    def __init__(self, out_dir: str = "data/raw") -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._book_rows: list[dict] = []
        self._opp_rows: list[dict] = []

    def record_book(self, book: OrderBook, depth: int = 5) -> None:
        row: dict = {
            "ts": book.ts,
            "venue": book.venue.value,
            "market_id": book.market_id,
            "token_id": book.token_id,
        }
        for i in range(depth):
            row[f"bid_p{i}"] = book.bids[i].price if i < len(book.bids) else None
            row[f"bid_s{i}"] = book.bids[i].size if i < len(book.bids) else None
            row[f"ask_p{i}"] = book.asks[i].price if i < len(book.asks) else None
            row[f"ask_s{i}"] = book.asks[i].size if i < len(book.asks) else None
        self._book_rows.append(row)

    def record_opportunity(self, opp: Opportunity) -> None:
        self._opp_rows.append(
            {
                "ts": opp.ts,
                "strategy": opp.strategy,
                "edge_bps": opp.edge_bps,
                "edge_per_contract": opp.edge_per_contract,
                "max_size": opp.max_size,
                "capital_required": opp.capital_required,
                "description": opp.description,
            }
        )

    def flush(self) -> tuple[Path | None, Path | None]:
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        book_path = opp_path = None
        if self._book_rows:
            book_path = self.out_dir / f"books_{stamp}.parquet"
            pd.DataFrame(self._book_rows).to_parquet(book_path, index=False)
            self._book_rows.clear()
        if self._opp_rows:
            opp_path = self.out_dir / f"opps_{stamp}.parquet"
            pd.DataFrame(self._opp_rows).to_parquet(opp_path, index=False)
            self._opp_rows.clear()
        return book_path, opp_path

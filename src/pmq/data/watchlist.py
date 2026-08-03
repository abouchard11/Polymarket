"""Market watchlist config for `pmq record` — parses config/watchlist.yaml.

Kept deliberately dumb: this module only ever sees strings and numbers from YAML.
Turning a slug into an actual tradeable Market (with CLOB token ids) requires the
venue adapter and therefore network access — that resolution happens in
`pmq.data.record_loop`, never here, so this module stays unit-testable with zero
network (see tests/test_watchlist.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CADENCE_SECONDS = 30.0
DEFAULT_FLUSH_EVERY_CYCLES = 20
DEFAULT_OUT_DIR = "data/raw"


class WatchlistError(ValueError):
    """Raised for a missing, empty, or malformed watchlist config."""


@dataclass(frozen=True)
class WatchlistEntry:
    slug: str
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.slug or not self.slug.strip():
            raise WatchlistError("watchlist entry has an empty/blank 'slug'")


@dataclass(frozen=True)
class Watchlist:
    entries: list[WatchlistEntry] = field(default_factory=list)
    cadence_seconds: float = DEFAULT_CADENCE_SECONDS
    flush_every_cycles: int = DEFAULT_FLUSH_EVERY_CYCLES
    out_dir: str = DEFAULT_OUT_DIR

    def __post_init__(self) -> None:
        if not self.entries:
            raise WatchlistError(
                "watchlist has no markets — add at least one entry under 'markets:' "
                "(copy config/watchlist.example.yaml to config/watchlist.yaml)"
            )
        if self.cadence_seconds <= 0:
            raise WatchlistError(f"cadence_seconds must be positive, got {self.cadence_seconds!r}")
        if self.flush_every_cycles <= 0:
            raise WatchlistError(
                f"flush_every_cycles must be positive, got {self.flush_every_cycles!r}"
            )


def load_watchlist(path: str | Path) -> Watchlist:
    """Load + validate a watchlist YAML file. Raises WatchlistError on any problem."""
    p = Path(path)
    if not p.exists():
        raise WatchlistError(
            f"watchlist config not found at {p} — copy config/watchlist.example.yaml "
            f"to {p} and edit it with real market slugs"
        )

    raw: Any = yaml.safe_load(p.read_text()) or {}
    if not isinstance(raw, dict):
        raise WatchlistError(f"{p} must be a YAML mapping with a top-level 'markets:' key")

    raw_markets = raw.get("markets")
    if not raw_markets:
        raise WatchlistError(f"{p} has no 'markets:' list — add at least one {{slug: ...}} entry")
    if not isinstance(raw_markets, list):
        raise WatchlistError(f"'markets' in {p} must be a list, got {type(raw_markets).__name__}")

    entries: list[WatchlistEntry] = []
    for i, m in enumerate(raw_markets):
        if not isinstance(m, dict) or "slug" not in m:
            raise WatchlistError(f"markets[{i}] in {p} must be a mapping with a 'slug' key")
        label = m.get("label")
        entries.append(
            WatchlistEntry(slug=str(m["slug"]).strip(), label=str(label).strip() if label else None)
        )

    return Watchlist(
        entries=entries,
        cadence_seconds=float(raw.get("cadence_seconds", DEFAULT_CADENCE_SECONDS)),
        flush_every_cycles=int(raw.get("flush_every_cycles", DEFAULT_FLUSH_EVERY_CYCLES)),
        out_dir=str(raw.get("out_dir", DEFAULT_OUT_DIR)),
    )

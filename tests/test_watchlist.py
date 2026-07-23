"""Watchlist config parsing/validation. Pure logic, zero network — see HANDOFF.md M1."""

from __future__ import annotations

from pathlib import Path

import pytest

from pmq.data.watchlist import (
    DEFAULT_CADENCE_SECONDS,
    DEFAULT_FLUSH_EVERY_CYCLES,
    DEFAULT_OUT_DIR,
    Watchlist,
    WatchlistEntry,
    WatchlistError,
    load_watchlist,
)


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "watchlist.yaml"
    p.write_text(text)
    return p


def test_load_watchlist_parses_valid_config(tmp_path):
    p = _write(
        tmp_path,
        """
        cadence_seconds: 45
        markets:
          - slug: will-jesus-christ-return-before-2027
            label: "Jesus 2027"
          - slug: will-the-us-invade-iran-before-2027
        """,
    )
    wl = load_watchlist(p)
    assert wl.cadence_seconds == 45
    assert len(wl.entries) == 2
    assert wl.entries[0] == WatchlistEntry(
        slug="will-jesus-christ-return-before-2027", label="Jesus 2027"
    )
    assert wl.entries[1] == WatchlistEntry(slug="will-the-us-invade-iran-before-2027", label=None)


def test_load_watchlist_defaults_when_omitted(tmp_path):
    p = _write(tmp_path, "markets:\n  - slug: some-market\n")
    wl = load_watchlist(p)
    assert wl.cadence_seconds == DEFAULT_CADENCE_SECONDS
    assert wl.flush_every_cycles == DEFAULT_FLUSH_EVERY_CYCLES
    assert wl.out_dir == DEFAULT_OUT_DIR


def test_load_watchlist_missing_file_raises(tmp_path):
    with pytest.raises(WatchlistError, match="not found"):
        load_watchlist(tmp_path / "nope.yaml")


def test_load_watchlist_missing_markets_key_raises(tmp_path):
    p = _write(tmp_path, "cadence_seconds: 30\n")
    with pytest.raises(WatchlistError, match="markets"):
        load_watchlist(p)


def test_load_watchlist_empty_markets_list_raises(tmp_path):
    p = _write(tmp_path, "markets: []\n")
    with pytest.raises(WatchlistError, match="markets"):
        load_watchlist(p)


def test_load_watchlist_markets_not_a_list_raises(tmp_path):
    p = _write(tmp_path, "markets: not-a-list\n")
    with pytest.raises(WatchlistError, match="list"):
        load_watchlist(p)


def test_load_watchlist_entry_without_slug_raises(tmp_path):
    p = _write(tmp_path, "markets:\n  - label: no slug here\n")
    with pytest.raises(WatchlistError, match="slug"):
        load_watchlist(p)


def test_load_watchlist_entry_blank_slug_raises(tmp_path):
    p = _write(tmp_path, 'markets:\n  - slug: "   "\n')
    with pytest.raises(WatchlistError, match="slug"):
        load_watchlist(p)


def test_load_watchlist_rejects_nonpositive_cadence(tmp_path):
    p = _write(tmp_path, "cadence_seconds: 0\nmarkets:\n  - slug: some-market\n")
    with pytest.raises(WatchlistError, match="cadence"):
        load_watchlist(p)


def test_load_watchlist_rejects_negative_cadence(tmp_path):
    p = _write(tmp_path, "cadence_seconds: -5\nmarkets:\n  - slug: some-market\n")
    with pytest.raises(WatchlistError, match="cadence"):
        load_watchlist(p)


def test_load_watchlist_rejects_nonpositive_flush_every(tmp_path):
    p = _write(tmp_path, "flush_every_cycles: 0\nmarkets:\n  - slug: some-market\n")
    with pytest.raises(WatchlistError, match="flush_every_cycles"):
        load_watchlist(p)


def test_load_watchlist_custom_out_dir(tmp_path):
    p = _write(tmp_path, "out_dir: data/custom\nmarkets:\n  - slug: some-market\n")
    wl = load_watchlist(p)
    assert wl.out_dir == "data/custom"


def test_watchlist_direct_construction_validates_too():
    # Watchlist() is also called directly by load_watchlist; make sure its own
    # invariants hold even if a caller builds it without going through YAML.
    with pytest.raises(WatchlistError):
        Watchlist(entries=[])

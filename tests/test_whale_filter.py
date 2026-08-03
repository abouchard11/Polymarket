from datetime import UTC, datetime

from pmq.core.models import Side, WhaleSignal
from pmq.strategies.whale_signal import filter_signal


def _sig(question: str, size_usd: float, age_s: float, now: float = 1_800_000_000.0) -> WhaleSignal:
    return WhaleSignal(
        wallet="0xabc",
        market_id="m1",
        question=question,
        outcome="Yes",
        side=Side.BUY,
        price=0.42,
        size_usd=size_usd,
        ts=datetime.fromtimestamp(now - age_s, tz=UTC),
    )


NOW = 1_800_000_000.0


def test_passes_good_signal():
    assert filter_signal(_sig("Will X win the election?", 5_000, age_s=60), now=NOW)


def test_rejects_crypto_serials():
    # 55% of 5-minute market participants are bots — no signal value for followers.
    assert not filter_signal(_sig("Bitcoin Up or Down — 5m", 50_000, age_s=10), now=NOW)
    assert not filter_signal(_sig("ETH hourly close above?", 50_000, age_s=10), now=NOW)


def test_rejects_small_size():
    assert not filter_signal(_sig("Will X win?", 500, age_s=60), now=NOW)


def test_rejects_stale():
    assert not filter_signal(_sig("Will X win?", 5_000, age_s=3_600), now=NOW)

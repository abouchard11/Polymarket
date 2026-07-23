import pytest

from pmq.core.risk import RiskLimits, RiskManager, RiskViolation


@pytest.fixture
def rm() -> RiskManager:
    return RiskManager(
        limits=RiskLimits(
            max_notional_per_market=500,
            max_total_notional=1_000,
            max_daily_loss=100,
            min_edge_bps=150,
        )
    )


def test_ok_order_passes(rm):
    rm.check_order("m1", 400, edge_bps=200)


def test_per_market_cap(rm):
    rm.register_fill("m1", 400)
    with pytest.raises(RiskViolation, match="per-market"):
        rm.check_order("m1", 200)


def test_total_cap(rm):
    rm.register_fill("m1", 500)
    rm.register_fill("m2", 400)
    with pytest.raises(RiskViolation, match="total notional"):
        rm.check_order("m3", 200)


def test_daily_loss_halts(rm):
    rm.register_close("m1", 100, pnl=-150)
    with pytest.raises(RiskViolation, match="daily loss"):
        rm.check_order("m2", 10)


def test_min_edge_enforced(rm):
    with pytest.raises(RiskViolation, match="edge"):
        rm.check_order("m1", 100, edge_bps=100)


def test_edge_none_skips_edge_check(rm):
    rm.check_order("m1", 100, edge_bps=None)


def test_nonpositive_notional(rm):
    with pytest.raises(RiskViolation):
        rm.check_order("m1", 0)


def test_kill_switch(tmp_path, monkeypatch, rm):
    import pmq.core.risk as risk_mod

    kill = tmp_path / "KILL"
    kill.touch()
    monkeypatch.setattr(risk_mod, "KILL_SWITCH_FILE", kill)
    with pytest.raises(RiskViolation, match="kill switch"):
        rm.check_order("m1", 10)


def test_close_frees_capacity(rm):
    rm.register_fill("m1", 500)
    rm.register_close("m1", 500, pnl=25)
    rm.check_order("m1", 500)  # should not raise
    assert rm.realized_pnl_today == 25

import pandas as pd
import pytest

from polyrea.analysis.ledger import build_ledger, capital_and_roc
from polyrea.analysis.pnl import daily_frame, monthly_blocks, weekly_sums

DAY = 86400


def trade(ts, side, size, price, asset="A", cid="c1", oi=0):
    return {"timestamp": ts, "type": "TRADE", "side": side, "size": size, "price": price, "usdcSize": size * price, "asset": asset, "conditionId": cid, "outcomeIndex": oi, "transactionHash": f"0x{ts}{side}"}


def test_round_trip_realized_pnl_and_exposure():
    led = build_ledger("w", [trade(0, "BUY", 100, 0.40), trade(10, "BUY", 100, 0.60), trade(20, "SELL", 200, 0.70)])
    p = led.positions["A"]
    assert p.realized == pytest.approx(200 * 0.70 - 100)
    assert p.shares == pytest.approx(0) and p.close_kind == "sold"
    exp = led.exposure_series()
    assert exp.max() == pytest.approx(100.0)
    assert exp.iloc[-1] == pytest.approx(0.0)


def test_resolution_releases_capital_without_redeem():
    led = build_ledger("w", [trade(0, "BUY", 100, 0.5), trade(5 * DAY, "BUY", 10, 0.5, asset="B", cid="c2")], resolution_ts={"c1": DAY})
    exp = led.exposure_series()
    assert exp.loc[pd.Timestamp(DAY, unit="s", tz="UTC")] == pytest.approx(0.0)
    assert led.positions["A"].close_kind == "resolved"
    assert exp.iloc[-1] == pytest.approx(5.0)


def test_redeem_and_merge():
    rows = [
        trade(0, "BUY", 10, 0.45, asset="Y"),
        trade(1, "BUY", 10, 0.50, asset="N", oi=1),
        {"timestamp": 2, "type": "MERGE", "size": 10, "usdcSize": 10, "conditionId": "c1", "asset": ""},
        trade(3, "BUY", 5, 0.9, asset="Z", cid="c3"),
        {"timestamp": 4, "type": "REDEEM", "size": 5, "usdcSize": 5, "conditionId": "c3", "asset": "Z"},
    ]
    led = build_ledger("w", rows)
    assert led.exposure_series().iloc[-1] == pytest.approx(0.0, abs=1e-9)
    assert led.positions["Y"].close_kind == "merged"
    assert led.positions["Z"].close_kind == "redeemed"


def test_sell_without_buy_is_recorded_as_anomaly():
    led = build_ledger("w", [trade(0, "SELL", 5, 0.5)])
    assert led.anomalies


def test_income_tracked():
    led = build_ledger("w", [{"timestamp": 1, "type": "MAKER_REBATE", "usdcSize": 3.5}])
    assert led.income == 3.5


def test_daily_frame_drops_partial_day_and_differences():
    pts = [
        {"timestamp": 0, "economic_pnl": 0, "trade_pnl": 0},
        {"timestamp": DAY, "economic_pnl": 10, "trade_pnl": 9},
        {"timestamp": 3 * DAY, "economic_pnl": 25, "trade_pnl": 20},  # day 2 missing -> forward fill
        {"timestamp": 3 * DAY + 500, "economic_pnl": 999, "trade_pnl": 999},  # partial "now" point
    ]
    df = daily_frame(pts)
    assert list(df["d_economic_pnl"].iloc[1:]) == [10, 0, 15]
    assert df["economic_pnl"].iloc[-1] == 25


def test_blocks_and_weeks():
    s = pd.Series(range(65), dtype=float)
    blocks = monthly_blocks(s)
    assert blocks[0] == sum(range(35, 65)) and len(blocks) == 2
    assert len(weekly_sums(s)) == 9


def test_capital_and_roc():
    led = build_ledger("w", [trade(0, "BUY", 1000, 0.5), trade(2 * DAY, "SELL", 1000, 0.6)])
    idx = pd.date_range(pd.Timestamp(0, unit="s", tz="UTC"), periods=3, freq="D")
    daily = pd.Series([0.0, 0.0, 100.0], index=idx)
    r = capital_and_roc(led, daily, window_days=30)
    assert r["peak_capital"] == pytest.approx(500.0)
    assert r["monthly_roc"] == pytest.approx(0.2)

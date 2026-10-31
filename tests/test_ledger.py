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


def test_complete_sets_are_not_capital_at_risk():
    rows = [
        {"timestamp": 0, "type": "SPLIT", "size": 4000, "usdcSize": 4000, "conditionId": "park", "asset": ""},
        trade(1, "BUY", 100, 0.5),
        {"timestamp": 2, "type": "MERGE", "size": 4000, "usdcSize": 4000, "conditionId": "park", "asset": ""},
    ]
    led = build_ledger("w", rows)
    assert led.exposure_series().max() == pytest.approx(50.0)
    assert led.exposure_series(include_complete_sets=True).max() == pytest.approx(4050.0)
    assert led.exposure_series(include_complete_sets=True).iloc[-1] == pytest.approx(50.0)


def _decomp(trades_rows, payout_yes):
    from polyrea.analysis.profile import per_market_decomposition

    led = build_ledger("w", trades_rows)
    t = pd.DataFrame(led.trades)
    t["slug"] = "m"
    market = {"clobTokenIds": '["Y", "N"]', "outcomePrices": f'["{payout_yes}", "{1 - payout_yes}"]', "umaResolutionStatus": "resolved"}
    return per_market_decomposition(t, {"c1": market}).iloc[0]


def test_decomposition_treats_sells_as_sales_not_purchases():
    rows = [trade(0, "BUY", 100, 0.40, asset="Y"), trade(1, "SELL", 100, 0.60, asset="Y")]
    for payout in (0.0, 1.0):  # nothing is held, so the outcome must not matter
        r = _decomp(rows, payout)
        assert r["pnl"] == pytest.approx(20.0)
        assert r["realized_pnl"] == pytest.approx(20.0)
        assert r["q0"] == pytest.approx(0.0) and r["cost"] == pytest.approx(40.0) and r["sold_usdc"] == pytest.approx(60.0)


def test_decomposition_two_sided_with_partial_exit_reconciles():
    rows = [
        trade(0, "BUY", 100, 0.45, asset="Y"),
        trade(1, "BUY", 100, 0.50, asset="N", oi=1),
        trade(2, "BUY", 50, 0.55, asset="Y"),
        trade(3, "SELL", 30, 0.70, asset="Y"),
    ]
    r = _decomp(rows, 1.0)
    avg_y = (100 * 0.45 + 50 * 0.55) / 150
    assert r["realized_pnl"] == pytest.approx(30 * (0.70 - avg_y))
    assert r["q0"] == pytest.approx(120) and r["pairs"] == pytest.approx(100)
    cash = -(100 * 0.45 + 100 * 0.50 + 50 * 0.55) + 30 * 0.70 + 120 * 1.0  # every cash flow incl. payout
    assert r["pnl"] == pytest.approx(cash)
    assert r["pnl"] == pytest.approx(r["realized_pnl"] + r["locked_pnl"] + r["residual_pnl"])


def test_rebate_dependence_tier_and_level_up_bonus():
    from polyrea.analysis.rebates import rebate_dependence

    pts, cum = [], {"position_pnl": 0.0, "fees_paid": 0.0, "taker_rebate": 0.0, "maker_rebate": 0.0}
    for d in range(40):
        fee = 1000.0
        cum["fees_paid"] -= fee
        cum["position_pnl"] += 100.0  # after fees
        if d > 0:
            cum["taker_rebate"] += 0.44 * 1000.0 + (25_000.0 if d == 35 else 0.0)  # Diamond rate + Obsidian bonus once
        cum["maker_rebate"] += 10.0
        econ = cum["position_pnl"] + cum["taker_rebate"] + cum["maker_rebate"]
        pts.append({"timestamp": d * DAY, **cum, "economic_pnl": econ, "reward_income": 0.0, "yield_income": 0.0, "referral_income": 0.0})
    r = rebate_dependence(pts, as_of=39 * DAY, days=30)
    assert r["observed_tier"] == "Diamond"
    assert r["level_up_bonus_total"] == pytest.approx(25_000.0)
    assert r["pnl_at_tier"]["None 0%"] == pytest.approx(30 * 110.0)
    assert r["economic_pnl_recurring"] == pytest.approx(30 * (110.0 + 440.0))


def test_merge_takes_complete_sets_before_bought_legs():
    rows = [
        {"timestamp": 0, "type": "SPLIT", "size": 100, "usdcSize": 100, "conditionId": "c1", "asset": ""},
        trade(1, "BUY", 50, 0.6, asset="Y"),
        trade(2, "BUY", 50, 0.4, asset="N", oi=1),
        {"timestamp": 3, "type": "MERGE", "size": 100, "usdcSize": 100, "conditionId": "c1", "asset": ""},
    ]
    led = build_ledger("w", rows)
    assert led.positions["Y"].shares == pytest.approx(50) and led.positions["N"].shares == pytest.approx(50)
    assert led.exposure_series().iloc[-1] == pytest.approx(50.0)  # the bought legs are still held
    assert led.exposure_series(include_complete_sets=True).iloc[-1] == pytest.approx(50.0)


def test_rebate_bonus_outside_the_window_is_ignored():
    from polyrea.analysis.rebates import rebate_dependence

    pts, cum = [], {"position_pnl": 0.0, "fees_paid": 0.0, "taker_rebate": 0.0, "maker_rebate": 0.0}
    for d in range(80):
        fee = 1000.0 if d % 4 == 0 else 0.0
        cum["fees_paid"] -= fee
        cum["position_pnl"] += 10.0
        if d > 0:
            cum["taker_rebate"] += 0.32 * (1000.0 if (d - 1) % 4 == 0 else 0.0) + (7500.0 if d == 37 else 0.0)
        pts.append({"timestamp": d * DAY, **cum, "economic_pnl": cum["position_pnl"] + cum["taker_rebate"], "reward_income": 0.0, "yield_income": 0.0, "referral_income": 0.0})
    r = rebate_dependence(pts, as_of=79 * DAY, days=30)
    assert r["level_up_bonus_total"] == 0.0  # the bonus was paid 42 days before as_of
    assert r["economic_pnl_recurring"] == pytest.approx(r["window"]["economic_pnl"])

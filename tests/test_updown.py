import numpy as np
import pandas as pd
import pytest

from polyrea.analysis.updown import (
    SpotIndex,
    Window,
    audit_vectorized_fair_value,
    backtest,
    fair_up_vectorized,
    match_test,
    score_prints,
    taker_fee_per_share,
    wallet_replay,
)
from polyrea.pit import PITStore, TimeSeries

T0 = 1_700_000_000


def _spot(n=4 * 3600, seed=0, vol=2e-4):
    rng = np.random.default_rng(seed)
    px = 60000 * np.exp(np.cumsum(rng.standard_normal(n) * vol))
    return TimeSeries.build("spot", zip(range(T0, T0 + n), px.tolist()), availability_lag=1)


def _windows(n, first=T0 + 3600, dur=300):
    return [Window(f"c{i}", "btc", "5m", first + i * dur, first + (i + 1) * dur, f"u{i}", f"d{i}") for i in range(n)]


def test_vectorized_matches_pit_reference_and_ignores_future():
    store = PITStore()
    store.add_series(_spot())
    ws = _windows(20)
    rng = np.random.default_rng(1)
    probes = [(w, int(rng.integers(w.start_ts - 30, w.end_ts + 5))) for w in ws for _ in range(4)]
    rep = audit_vectorized_fair_value(store, "spot", ws, probes, latency=1)
    assert rep["passed"], rep
    assert rep["probes"] >= 60


def test_scores_unchanged_when_future_spot_is_corrupted():
    s = _spot(seed=2)
    ws = _windows(10)
    prints = pd.DataFrame(
        [
            {"condition_id": w.condition_id, "ts": w.start_ts + k, "wallet": "x", "is_up": bool(k % 2), "price": 0.5, "size": 10,
             "start_ts": w.start_ts, "end_ts": w.end_ts, "twap": 60, "fee_rate": 0.07, "up_payout": 1.0}
            for w in ws for k in (10, 100, 250, 280)
        ]
    )
    base = score_prints(prints, SpotIndex(s), latency=2)
    for i, row in prints.iterrows():
        cut = row["ts"] - 2  # decision time
        vals = s.values.copy()
        vals[s.available_ts > cut] *= 1.5  # wreck everything not yet available
        corrupted = TimeSeries(s.name, s.event_ts, s.available_ts, vals)
        assert score_prints(prints.iloc[[i]], SpotIndex(corrupted), latency=2)[0] == pytest.approx(base[i], abs=1e-12)


def _synthetic_market(seed, n_windows=120, informed="w_inf"):
    s = _spot(n=3600 + n_windows * 300 + 600, seed=seed)
    spot = SpotIndex(s)
    ws = _windows(n_windows)
    rng = np.random.default_rng(seed)
    rows = []
    for w in ws:
        # settle like the real markets: closing 60 s TWAP vs. the 60 s TWAP before the start
        twap_end = spot.mean_between(np.array([w.end_ts - 60]), np.array([w.end_ts]), np.array([w.end_ts + 1]))[0]
        twap_start = spot.mean_between(np.array([w.start_ts - 60]), np.array([w.start_ts]), np.array([w.start_ts + 1]))[0]
        final = twap_end >= twap_start
        for _ in range(40):
            ts = int(rng.integers(w.start_ts + 5, w.end_ts - 5))
            fu = fair_up_vectorized(spot, np.array([w.start_ts]), np.array([w.end_ts]), np.array([ts - 1]))[0]
            is_up = bool(rng.random() < 0.5)
            fair = fu if is_up else 1 - fu
            price = float(np.clip(fair + rng.normal(0, 0.06), 0.02, 0.98))
            edge = fair - price
            wallet = informed if edge > 0.04 and rng.random() < 0.8 else f"r{rng.integers(50)}"
            rows.append({"condition_id": w.condition_id, "ts": ts, "wallet": wallet, "is_up": is_up, "price": price, "size": 20.0,
                         "start_ts": w.start_ts, "end_ts": w.end_ts, "twap": 60, "fee_rate": 0.07, "up_payout": float(final)})
    return pd.DataFrame(rows).sort_values("ts").reset_index(drop=True), spot


BLOCKS = [(T0 + 3600 + b * 7200, T0 + 3600 + (b + 1) * 7200) for b in range(5)]


def test_match_test_detects_informed_wallet_and_rejects_random():
    prints, spot = _synthetic_market(3)
    half = prints["ts"].median()
    fit, test = prints[prints["ts"] < half], prints[prints["ts"] >= half]
    res = match_test(fit, test, "w_inf", spot, BLOCKS, 300, lags=[0, 1, 2], n_perm=60)
    assert res["test"]["auc"] > 0.8
    assert res["test"]["auc_perm_p"] < 0.05
    assert res["test"]["decision"]["mcc"] > 0.4
    assert res["test"]["null_finite_share_min"] == 1.0
    rnd = match_test(fit, test, "r7", spot, BLOCKS, 300, lags=[0, 1, 2], n_perm=60)
    assert rnd["test"]["auc_perm_p"] > 0.05


def _gapped(seed, n_blocks=8, gap=6 * 3600):
    """Spot loaded only around sampled 2 h blocks, as in a real study."""
    rng = np.random.default_rng(seed)
    blocks, ev, px, level = [], [], [], 60000.0
    for b in range(n_blocks):
        a = T0 + 3600 + b * (7200 + gap)
        blocks.append((a, a + 7200))
        secs = np.arange(a - 1920, a + 7200 + 120)
        path = level * np.exp(np.cumsum(rng.standard_normal(len(secs)) * 2e-4))
        level = float(path[-1]) * float(np.exp(rng.normal(0, 0.01)))
        ev.extend(secs.tolist())
        px.extend(path.tolist())
    spot = SpotIndex(TimeSeries.build("spot", zip(ev, px), availability_lag=1))
    rows = []
    for a, e in blocks:
        for ws in range(a, e, 300):
            for _ in range(60):
                ts = int(rng.integers(ws + 3, ws + 297))
                fu = fair_up_vectorized(spot, np.array([ws]), np.array([ws + 300]), np.array([ts - 1]))[0]
                is_up = bool(rng.random() < 0.5)
                price = float(np.clip((fu if is_up else 1 - fu) + rng.normal(0, 0.05), 0.02, 0.98))
                rows.append({"condition_id": f"c{ws}", "ts": ts, "is_up": is_up, "price": price, "size": 10.0, "start_ts": ws, "end_ts": ws + 300,
                             "twap": 60, "fee_rate": 0.07, "up_payout": 1.0})
    df = pd.DataFrame(rows)
    return df, spot, blocks


@pytest.mark.parametrize("pref", ["expensive", "late"])
def test_match_null_is_not_fooled_by_spot_blind_preferences(pref):
    """A wallet that picks prints by price or timing alone, ignoring spot, must not
    'match' a spot hypothesis (the earlier clock-shift null passed such a wallet)."""
    df, spot, blocks = _gapped(11)
    rng = np.random.default_rng(12)
    wgt = df["price"].to_numpy() ** 3 if pref == "expensive" else ((df["ts"] - df["start_ts"]).to_numpy() / 300.0) ** 3
    pick = rng.random(len(df)) < np.clip(0.06 * wgt / wgt.mean(), 0, 1)
    df["wallet"] = np.where(pick, "blind", "other")
    fit = df[df["start_ts"] < blocks[4][0]]
    test = df[df["start_ts"] >= blocks[4][0]]
    res = match_test(fit, test, "blind", spot, blocks[4:], 300, lags=[0, 2], n_perm=100)
    assert res["test"]["null_finite_share_min"] == 1.0
    assert res["test"]["auc_perm_p"] > 0.05
    assert not res["criterion_6"]["pass"]


def test_spot_return_score_detects_a_spot_reactive_maker():
    from functools import partial

    from polyrea.analysis.updown import score_spot_return

    df, spot, blocks = _gapped(21)
    r = score_spot_return(df, spot, latency=1, horizon=2)
    rng = np.random.default_rng(22)
    wgt = np.exp(4000 * np.nan_to_num(r))  # fills follow spot moves toward the bought side
    pick = rng.random(len(df)) < np.clip(0.05 * wgt / wgt.mean(), 0, 1)
    df["wallet"] = np.where(pick, "maker", "other")
    fit = df[df["start_ts"] < blocks[4][0]]
    test = df[df["start_ts"] >= blocks[4][0]]
    fns = {"spot_return_2s": partial(score_spot_return, horizon=2), "fair_minus_price": score_prints}
    res = match_test(fit, test, "maker", spot, blocks[4:], 300, score_fns=fns, lags=[0, 1, 2, 5], n_perm=100)
    assert res["chosen_score"] == "spot_return_2s" and res["chosen_latency_s"] == 1
    assert res["test"]["auc_perm_p"] < 0.02


def test_backtest_profits_only_with_real_edge():
    prints, spot = _synthetic_market(4)
    good = backtest(prints, spot, theta=0.03, latency=1)
    assert good["pnl"] > 0 and good["per_window_p"] < 0.01
    replay = wallet_replay(prints, "w_inf")
    assert replay["pnl"] > 0


def test_fee_formula():
    assert taker_fee_per_share(0.5, 0.07) == pytest.approx(0.0175)
    assert taker_fee_per_share(0.9, 0.07) == pytest.approx(0.0063)


def test_backtest_settlement_arithmetic():
    spot = SpotIndex(_spot(seed=5))
    w = _windows(1)[0]
    prints = pd.DataFrame([{"condition_id": "c0", "ts": w.end_ts - 1, "wallet": "z", "is_up": True, "price": 0.4, "size": 10.0,
                            "start_ts": w.start_ts, "end_ts": w.end_ts, "twap": 60, "fee_rate": 0.07, "up_payout": 1.0}])
    res = backtest(prints, spot, theta=-1.0, latency=0)  # buy everything
    expected = 10 * 1.0 - 4.0 - 0.07 * 0.4 * 0.6 * 10
    assert res["pnl"] == pytest.approx(expected)


def test_maker_backtest_trade_through_rules():
    from polyrea.analysis.updown import maker_backtest

    s = TimeSeries.build("spot", [(T0 + i, 60000.0) for i in range(4 * 3600)], availability_lag=1)
    spot = SpotIndex(s)
    # flat spot => fair_up ~ 0.5 (z = 0) ; delta 0.05 -> bid 0.45 on both sides
    w = Window("c0", "btc", "5m", T0 + 3600, T0 + 3900, "u", "d", up_payout=1.0)
    t = w.start_ts + 2  # inside the first 5 s requote interval
    flow = pd.DataFrame(
        [
            {"condition_id": "c0", "ts": t, "is_up": True, "side": "SELL", "price": 0.45, "size": 100.0},  # at the bid: no fill
            {"condition_id": "c0", "ts": t + 1, "is_up": True, "side": "SELL", "price": 0.44, "size": 7.0},  # through: fills 7
            {"condition_id": "c0", "ts": t + 1, "is_up": True, "side": "BUY", "price": 0.60, "size": 5.0},  # mint vs Down bid (0.60 > 1-0.45)
        ]
    )
    res = maker_backtest(flow, [w], spot, delta=0.05, latency=1, requote_s=5, size_shares=20)
    assert res["fills"] == 2
    # Up: 7 shares at 0.45 pay 1 -> +3.85 ; Down: 5 shares at 0.45 pay 0 -> -2.25
    assert res["pnl"] == pytest.approx(7 * 0.55 - 5 * 0.45)


def test_maker_backtest_respects_size_cap_and_queue_share():
    from polyrea.analysis.updown import maker_backtest

    s = TimeSeries.build("spot", [(T0 + i, 60000.0) for i in range(4 * 3600)], availability_lag=1)
    w = Window("c0", "btc", "5m", T0 + 3600, T0 + 3900, "u", "d", up_payout=0.0)
    flow = pd.DataFrame([{"condition_id": "c0", "ts": w.start_ts + 2, "is_up": True, "side": "SELL", "price": 0.40, "size": 100.0}])
    full = maker_backtest(flow, [w], SpotIndex(s), 0.05, 1, size_shares=20)
    half = maker_backtest(flow, [w], SpotIndex(s), 0.05, 1, size_shares=20, queue_share=0.1)
    assert full["pnl"] == pytest.approx(-20 * 0.45)
    assert half["pnl"] == pytest.approx(-10 * 0.45)


def test_tape_maker_backtest_uses_only_stale_tape_price():
    from polyrea.analysis.tape_maker import tape_maker_backtest

    flow = pd.DataFrame(
        [
            {"condition_id": "m", "ts": 100, "outcome": 0, "side": "BUY", "price": 0.50, "size": 10.0},
            {"condition_id": "m", "ts": 115, "outcome": 0, "side": "SELL", "price": 0.30, "size": 50.0},  # crash print
            {"condition_id": "m", "ts": 116, "outcome": 0, "side": "SELL", "price": 0.29, "size": 50.0},
        ]
    )
    # latency 0: at t0=110 the last print is 0.50 -> bid 0.48 on outcome 0 is traded through at 115 -> picked off
    r = tape_maker_backtest(flow, {"m": 0.0}, delta=0.02, latency=0, requote_s=10, active={"m": (110, 120)})
    assert r["fills"] == 1 and r["pnl"] == pytest.approx(-20 * 0.48)
    # the 0.30 print at 115 must not inform the 110 quote (no look-ahead)
    r2 = tape_maker_backtest(flow, {"m": 0.0}, delta=0.02, latency=0, requote_s=10, active={"m": (110, 120)}, size_shares=5)
    assert r2["pnl"] == pytest.approx(-5 * 0.48)


def test_vectorized_maker_backtest_equals_reference():
    from polyrea.analysis.updown import _maker_backtest_reference, maker_backtest

    rng = np.random.default_rng(9)
    s = _spot(n=3600 + 30 * 300 + 600, seed=9)
    spot = SpotIndex(s)
    ws = [Window(w.condition_id, "btc", "5m", w.start_ts, w.end_ts, w.up_token, w.down_token, up_payout=float(rng.random() < 0.5)) for w in _windows(30)]
    rows = []
    for w in ws:
        for _ in range(200):
            rows.append({"condition_id": w.condition_id, "ts": int(rng.integers(w.start_ts - 20, w.end_ts + 20)), "is_up": bool(rng.random() < 0.5),
                         "side": "SELL" if rng.random() < 0.5 else "BUY", "price": float(np.round(rng.uniform(0.02, 0.98), 2)), "size": float(rng.integers(1, 40))})
    flow = pd.DataFrame(rows)
    for delta, lat, q in ((0.0, 1, 1.0), (0.03, 2, 0.5), (0.08, 5, 1.0)):
        a = maker_backtest(flow, ws, spot, delta, lat, queue_share=q)
        b = _maker_backtest_reference(flow, ws, spot, delta, lat, queue_share=q)
        assert a["fills"] == b["fills"]
        assert a["pnl"] == pytest.approx(b["pnl"], rel=1e-9, abs=1e-9)


def test_spot_reactive_maker_quotes_only_after_spot_moves_toward_the_side():
    from polyrea.analysis.updown import spot_reactive_maker_backtest

    w = Window("c0", "btc", "5m", T0 + 3600, T0 + 3900, "u", "d", up_payout=1.0)
    secs = list(range(T0, T0 + 4 * 3600))
    px = [60000.0 if t < w.start_ts + 10 else 60060.0 for t in secs]  # +10 bp jump at start+10
    spot = SpotIndex(TimeSeries.build("spot", zip(secs, px), availability_lag=1))
    flow = pd.DataFrame(
        [
            {"condition_id": "c0", "ts": w.start_ts + 1, "is_up": True, "side": "BUY", "price": 0.50, "size": 1.0},  # sets the anchor
            {"condition_id": "c0", "ts": w.start_ts + 5, "is_up": True, "side": "SELL", "price": 0.49, "size": 50.0},  # before the move: no bid; anchor -> 0.49
            {"condition_id": "c0", "ts": w.start_ts + 13, "is_up": True, "side": "SELL", "price": 0.45, "size": 50.0},  # after: fills
        ]
    )
    # the jump is visible at start+11 (availability lag) and decided with latency 1 at tick start+12
    res = spot_reactive_maker_backtest(flow, [w], spot, theta=5e-4, delta=0.03, latency=1, horizon=2, requote_s=1)
    assert res["fills"] == 1  # only the post-move sell trades through the 0.46 bid
    assert res["pnl"] == pytest.approx(20 * (1.0 - 0.46))
    none = spot_reactive_maker_backtest(flow, [w], spot, theta=5e-3, delta=0.03, latency=1, horizon=2, requote_s=1)
    assert none.get("fills", 0) == 0  # move below theta: never quotes


def test_match_slack_never_credits_a_fill_before_the_order_existed():
    from polyrea.analysis.updown import spot_reactive_maker_backtest

    w = Window("c0", "btc", "5m", T0 + 3600, T0 + 3900, "u", "d", up_payout=1.0)
    secs = list(range(T0, T0 + 4 * 3600))
    px = [60000.0 if t < w.start_ts + 10 else 60060.0 for t in secs]
    spot = SpotIndex(TimeSeries.build("spot", zip(secs, px), availability_lag=1))
    flow = pd.DataFrame([
        {"condition_id": "c0", "ts": w.start_ts + 5, "is_up": True, "side": "SELL", "price": 0.49, "size": 50.0},
        {"condition_id": "c0", "ts": w.start_ts + 13, "is_up": True, "side": "SELL", "price": 0.45, "size": 50.0},  # stamped 1 s after the order rests
    ])
    kw = dict(theta=5e-4, delta=0.03, latency=1, horizon=2, requote_s=1)
    assert spot_reactive_maker_backtest(flow, [w], spot, **kw)["fills"] == 1
    # the print may have matched up to 2 s before its block time, i.e. before the bid existed
    assert spot_reactive_maker_backtest(flow, [w], spot, match_slack=2, **kw).get("fills", 0) == 0

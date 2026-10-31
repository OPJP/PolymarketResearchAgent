"""Reverse-engineering study for wallets trading crypto Up/Down windows.

Design (walk-forward, no look-ahead):

* Two disjoint periods ending at ``as_of``: FIT = [as_of-14d, as_of-7d),
  TEST = [as_of-7d, as_of). A deterministic random sample of 2-hour blocks is
  drawn from each; every window of the asset/duration inside a block is used,
  whether or not the wallet traded it.
* For each window: the taker tape (every aggressive order, any wallet) and
  Kraken spot trades reduced to per-second prices (available 1 s later).
* FIT chooses latency (lag scan) and threshold; TEST measures, untouched:
  decision-level agreement with the wallet (stratified AUC vs. a within-block
  window-rotation null, plus recall and lift of the fitted rule), backtest PnL
  of the rule, the wallet's own outcome on the same windows, and how the edge
  decays when our information is slower.
* Spot is Kraken trades or Binance 1-second klines (``spot_source``), reduced
  to per-second prices available one second later.
* A sample of fair values is recomputed through the guarded PIT view and on
  stores truncated at the decision time; the study fails closed if they differ.
"""

from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from polyrea.adapters.http import shared_client
from polyrea.adapters.polymarket import GAMMA_API, PolymarketData
from functools import partial

from polyrea.adapters.spot import binance_seconds, kraken_trades, per_second_series
from polyrea.analysis.updown import (
    SpotIndex,
    Window,
    audit_vectorized_fair_value,
    backtest,
    fair_up_vectorized,
    match_test,
    score_prints,
    score_spot_return,
    taker_buy_prints,
    wallet_replay,
    windows_from_markets,
)
from polyrea.evidence import Coverage, Evidence, to_jsonable
from polyrea.pit import PITStore

DAY = 86400
DURATION_S = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


def sample_blocks(period_start: int, period_end: int, n_blocks: int, block_s: int, seed: int) -> list[tuple[int, int]]:
    """Non-overlapping, aligned blocks drawn deterministically from a period."""
    slots = list(range(period_start - period_start % block_s + block_s, period_end - block_s + 1, block_s))
    rng = random.Random(seed)
    pick = sorted(rng.sample(slots, min(n_blocks, len(slots))))
    return [(s, s + block_s) for s in pick]


def window_slugs(asset: str, duration: str, start: int, end: int) -> list[str]:
    step = DURATION_S[duration]
    first = start - start % step
    return [f"{asset}-updown-{duration}-{t}" for t in range(first, end, step) if t >= start and t + step <= end]


def fetch_windows(slugs: list[str], chunk: int = 20) -> dict[str, dict[str, Any]]:
    http = shared_client()
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(slugs), chunk):
        part = slugs[i : i + chunk]
        data, _ = http.get_json(f"{GAMMA_API}/markets", [("slug", s) for s in part] + [("closed", "true"), ("limit", len(part) * 2)], adapter="gamma.markets", max_age=None)
        for m in data or []:
            out[m["conditionId"]] = m
    return out


_PERIOD_MEMO: dict[tuple, dict[str, Any]] = {}


def load_period(
    asset: str,
    duration: str,
    blocks: list[tuple[int, int]],
    pm: PolymarketData,
    workers: int = 6,
    with_full_tape: bool = False,
    spot_source: str = "kraken",
) -> dict[str, Any]:
    """Windows, tapes and spot of sampled blocks (memoized per process: every
    wallet studied on the same blocks reuses one load)."""
    key = (asset, duration, tuple(blocks), with_full_tape, spot_source)
    if key in _PERIOD_MEMO:
        return _PERIOD_MEMO[key]
    _PERIOD_MEMO[key] = out = _load_period(asset, duration, blocks, pm, workers, with_full_tape, spot_source)
    return out


def _load_period(asset: str, duration: str, blocks: list[tuple[int, int]], pm: PolymarketData, workers: int, with_full_tape: bool, spot_source: str) -> dict[str, Any]:
    slugs = [s for a, b in blocks for s in window_slugs(asset, duration, a, b)]
    markets = fetch_windows(slugs)
    windows = [w for w in windows_from_markets(markets) if w.up_payout is not None]

    def tape(w: Window):
        rows, _, cov = pm.market_trades(w.condition_id, start=w.start_ts - 3600, end=w.end_ts + 120, taker_only=True)
        return w.condition_id, rows, cov.status

    with ThreadPoolExecutor(workers) as ex:
        tapes_list = list(ex.map(tape, windows))
    tapes = {cid: rows for cid, rows, _ in tapes_list}
    full_tapes: dict[str, list[dict[str, Any]]] = {}
    if with_full_tape:

        def full(w: Window):
            rows, _, _ = pm.market_trades(w.condition_id, start=w.start_ts - 3600, end=w.end_ts + 120, taker_only=False)
            return w.condition_id, rows

        with ThreadPoolExecutor(workers) as ex:
            full_tapes = dict(ex.map(full, windows))
    partial = [cid for cid, _, st in tapes_list if st == "partial"]
    spot_series = []
    fetch = kraken_trades if spot_source == "kraken" else binance_seconds
    name = f"spot.{spot_source}.{asset}"
    for a, b in blocks:
        tr, _ = fetch(asset, a - 1800 - 120, b + 120)
        spot_series.append(per_second_series(name, tr, a - 1800 - 120, b + 120))
    # stitch blocks into one series (blocks do not overlap)
    ev = np.concatenate([s.event_ts for s in spot_series]) if spot_series else np.array([], dtype=np.int64)
    vals = np.concatenate([s.values for s in spot_series]) if spot_series else np.array([])
    from polyrea.pit import TimeSeries

    spot = TimeSeries.build(name, zip(ev.tolist(), vals.tolist()), availability_lag=1)
    return {
        "slugs": len(slugs),
        "windows": windows,
        "tapes": tapes,
        "full_tapes": full_tapes,
        "partial_tapes": partial,
        "spot": spot,
        "prints": taker_buy_prints(tapes, windows),
    }


def _combined_spot(fit: dict[str, Any], test: dict[str, Any]):
    from polyrea.pit import TimeSeries

    ev = np.concatenate([fit["spot"].event_ts, test["spot"].event_ts])
    vals = np.concatenate([fit["spot"].values, test["spot"].values])
    order = np.argsort(ev, kind="stable")
    keep = np.r_[True, np.diff(ev[order]) > 0]  # FIT and TEST lookback pads may touch
    return TimeSeries.build(fit["spot"].name, zip(ev[order][keep].tolist(), vals[order][keep].tolist()), availability_lag=1)


def calibration(windows: list[Window], tapes: dict[str, list[dict[str, Any]]], spot: SpotIndex, latency: int = 1, step: int = 30) -> dict[str, Any]:
    """Brier score of the spot model vs. the market's own last price at fixed times.

    At every ``step`` seconds inside each resolved window, the model's P(Up)
    (spot ``latency`` s old) and the last implied Up price on the taker tape
    are scored against the outcome. Shows how much the public spot model knows
    beyond the market price.
    """
    rows = []
    for w in windows:
        if w.up_payout is None:
            continue
        tape = [r for r in tapes.get(w.condition_id, []) if str(r.get("asset")) in (w.up_token, w.down_token)]
        if not tape:
            continue
        ts = np.array([int(r["timestamp"]) for r in tape])
        order = np.argsort(ts, kind="stable")
        ts = ts[order]
        up = np.array([float(r["price"]) if str(r["asset"]) == w.up_token else 1 - float(r["price"]) for r in tape])[order]
        times = np.arange(w.start_ts + step, w.end_ts, step)
        k = np.searchsorted(ts, times - latency, side="right") - 1
        mkt = np.where(k >= 0, up[np.clip(k, 0, None)], np.nan)
        mod = fair_up_vectorized(spot, np.full(len(times), w.start_ts), np.full(len(times), w.end_ts), times - latency, w.twap_seconds)
        for t, a, b in zip(times, mkt, mod):
            rows.append((w.condition_id, t - w.start_ts, a, b, w.up_payout))
    if not rows:
        return {}
    df = pd.DataFrame(rows, columns=["cid", "rel", "market", "model", "y"]).dropna()
    last = df.sort_values("rel").groupby("cid").last()
    sq = df.assign(market=(df["market"] - df["y"]) ** 2, model=(df["model"] - df["y"]) ** 2)
    by = sq.groupby("rel")[["market", "model"]].mean()
    return {
        "points": int(len(df)),
        "brier_market": float(((df["market"] - df["y"]) ** 2).mean()),
        "brier_model": float(((df["model"] - df["y"]) ** 2).mean()),
        "model_wrong_side_at_last_step": float(((last["model"] >= 0.5) != (last["y"] >= 0.5)).mean()),
        "market_wrong_side_at_last_step": float(((last["market"] >= 0.5) != (last["y"] >= 0.5)).mean()),
        "by_seconds_into_window": {str(int(k)): {"market": float(v["market"]), "model": float(v["model"])} for k, v in by.iterrows()},
        "latency_s": latency,
        "step_s": step,
    }


def run_updown_study(
    wallet: str,
    asset: str = "btc",
    duration: str = "5m",
    as_of: int | None = None,
    blocks_per_period: int = 12,
    block_hours: int = 2,
    seed: int = 7,
    out_dir: Path | None = None,
    n_perm: int = 200,
    spot_source: str = "kraken",
) -> Evidence:
    from polyrea.workflows.investigate import default_as_of

    pm = PolymarketData()
    as_of = as_of or default_as_of()
    fit_period = (as_of - 14 * DAY, as_of - 7 * DAY)
    test_period = (as_of - 7 * DAY, as_of)
    bs = block_hours * 3600
    fit_blocks = sample_blocks(*fit_period, blocks_per_period, bs, seed)
    test_blocks = sample_blocks(*test_period, blocks_per_period, bs, seed + 1)
    fit = load_period(asset, duration, fit_blocks, pm, spot_source=spot_source)
    test = load_period(asset, duration, test_blocks, pm, spot_source=spot_source)
    w = wallet.lower()
    spot_ts = _combined_spot(fit, test)
    spot = SpotIndex(spot_ts)

    # --- no-look-ahead audit of the fast path
    store = PITStore()
    store.add_series(spot_ts)
    rng = random.Random(seed)
    probe_windows = rng.sample(test["windows"], min(15, len(test["windows"])))
    probes = [(win, rng.randint(win.start_ts, win.end_ts)) for win in probe_windows for _ in range(2)]

    mt = match_test(fit["prints"], test["prints"], w, spot, test_blocks, DURATION_S[duration], n_perm=n_perm, seed=seed)
    lat = mt["chosen_latency_s"]
    theta = mt["theta"]
    audit = audit_vectorized_fair_value(store, spot_ts.name, test["windows"], probes, latency=lat)
    if not audit["passed"]:
        raise RuntimeError(f"PIT audit failed: {audit}")
    bt = backtest(test["prints"], spot, theta=theta, latency=lat)
    bt_ex = backtest(test["prints"], spot, theta=theta, latency=lat, exclude_wallet=w)
    degraded = {}
    for extra in (1, 2, 3, 5, 10):
        r = backtest(test["prints"], spot, theta=theta, latency=lat + extra)
        degraded[str(lat + extra)] = {k: r.get(k) for k in ("trades", "pnl", "return_on_traded", "per_window_p")}
    replay = wallet_replay(test["prints"], w)
    replay_fit = wallet_replay(fit["prints"], w)
    share_wallet = float((test["prints"]["wallet"] == w).mean()) if len(test["prints"]) else None
    windows_with_wallet = int(test["prints"][test["prints"]["wallet"] == w]["condition_id"].nunique()) if len(test["prints"]) else 0
    ev_out = Evidence(
        tool="updown_study",
        subject={"kind": "wallet", "wallet": w, "asset": asset, "duration": duration, "as_of": as_of, "spot_source": spot_source},
        observed={
            "fit_blocks": fit_blocks,
            "test_blocks": test_blocks,
            "fit_windows": len(fit["windows"]),
            "test_windows": len(test["windows"]),
            "fit_taker_buy_prints": int(len(fit["prints"])),
            "test_taker_buy_prints": int(len(test["prints"])),
            "test_wallet_taker_buys": int((test["prints"]["wallet"] == w).sum()) if len(test["prints"]) else 0,
            "test_windows_with_wallet": windows_with_wallet,
            "wallet_share_of_taker_buys": share_wallet,
            "spot_seconds": int(len(spot_ts)),
        },
        derived={
            "match_test": mt,
            "pit_audit": audit,
            "calibration_test_period": calibration(test["windows"], test["tapes"], spot),
            "backtest_test_period": bt,
            "backtest_excluding_wallet_prints": bt_ex,
            "latency_degradation": degraded,
            "wallet_replay_test_period": replay,
            "wallet_replay_fit_period": replay_fit,
        },
        coverage=Coverage(
            "partial" if fit["partial_tapes"] or test["partial_tapes"] else "complete",
            f"{len(fit['partial_tapes']) + len(test['partial_tapes'])} truncated tapes",
        ),
        limitations=[
            f"Spot is {spot_source} per-second prices; markets resolve on Chainlink's aggregated feed, so the strike TWAP and the closing TWAP are proxies.",
            "Backtest fills assume the observed taker liquidity at each print was available to us; contested liquidity is reported via the excluding-wallet run and latency degradation, not modeled queue competition.",
            "Polymarket tape timestamps are block times (~2 s), bounding the resolution of the latency estimate; a replicator needs >= 2 s.",
            "Only the wallet's taker buys are modeled; its maker fills are analysed in the maker study.",
        ],
    )
    if out_dir is not None:
        d = out_dir / w
        d.mkdir(parents=True, exist_ok=True)
        tag = "" if spot_source == "kraken" else f"_{spot_source}"
        (d / f"updown_study_{asset}_{duration}{tag}.json").write_text(json.dumps(ev_out.to_dict(), indent=1), encoding="utf-8")
    return ev_out


SR_HORIZONS = (1, 2, 3, 5)


def sr_score_fns() -> dict[str, Any]:
    return {f"spot_return_{h}s": partial(score_spot_return, horizon=h) for h in SR_HORIZONS}


def fit_sr_maker(fit_flow: pd.DataFrame, fit_windows: list[Window], spot: SpotIndex, latencies: tuple[int, ...] = (2, 3), min_fills: int = 100, match_slack: int = 0) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Choose (theta, delta, horizon, requote, latency) of the SR maker on FIT by per-window t (zero-fill windows included)."""
    import itertools

    from polyrea.analysis.updown import spot_reactive_maker_backtest

    scan = []
    for theta, delta, h, R, L in itertools.product((0.0, 2e-5, 5e-5, 1e-4), (0.0, 0.01, 0.02, 0.04), (2, 3), (1, 2), latencies):
        r = spot_reactive_maker_backtest(fit_flow, fit_windows, spot, theta, delta, L, horizon=h, requote_s=R, match_slack=match_slack)
        if r.get("fills", 0) >= min_fills:
            scan.append({"theta": theta, "delta": delta, "horizon": h, "requote_s": R, "latency": L, **{k: r.get(k) for k in ("fills", "pnl", "return_on_bought", "per_window_t_incl_zero")}})
    if not scan:
        return {}, scan
    best = max(scan, key=lambda r: r["per_window_t_incl_zero"] if r["per_window_t_incl_zero"] is not None and np.isfinite(r["per_window_t_incl_zero"]) else -1e9)
    return best, scan


def run_updown_maker_study(
    wallet: str,
    asset: str = "btc",
    duration: str = "5m",
    as_of: int | None = None,
    blocks_per_period: int = 12,
    block_hours: int = 2,
    seed: int = 7,
    out_dir: Path | None = None,
    n_perm: int = 200,
    spot_source: str = "kraken",
) -> Evidence:
    """Maker hypotheses for an Up/Down wallet, on passive BUY fills.

    DM(delta, latency), directional maker: match = does spot-model edge
    (fair - price) rank the wallet's passive fills above other makers'?
    Backtest = bids at fair - delta, strict trade-through fills, with the
    at-touch bound.

    SR(theta, delta, horizon, latency), spot-reactive maker: match = does the
    spot return toward the bought side just before the fill rank the wallet's
    fills? Backtest = bid on a side only after spot moved toward it, at the
    last tape price minus delta, with latency >= 2 s (block-time resolution).

    Both are fitted on FIT windows and evaluated once on TEST, with the
    wallet's own maker-fill outcome on the same TEST windows.
    """
    from polyrea.analysis.updown import maker_backtest, maker_buy_prints, spot_reactive_maker_backtest, taker_flow
    from polyrea.stats.significance import hac_t_test
    from polyrea.workflows.investigate import default_as_of

    pm = PolymarketData()
    as_of = as_of or default_as_of()
    bs = block_hours * 3600
    fit_blocks = sample_blocks(as_of - 14 * DAY, as_of - 7 * DAY, blocks_per_period, bs, seed)
    test_blocks = sample_blocks(as_of - 7 * DAY, as_of, blocks_per_period, bs, seed + 1)
    fit = load_period(asset, duration, fit_blocks, pm, with_full_tape=True, spot_source=spot_source)
    test = load_period(asset, duration, test_blocks, pm, with_full_tape=True, spot_source=spot_source)
    spot = SpotIndex(_combined_spot(fit, test))
    w = wallet.lower()
    mkey = ("maker_prints", id(fit), id(test))
    if mkey not in _PERIOD_MEMO:
        _PERIOD_MEMO[mkey] = {
            "fit_m": maker_buy_prints(fit["full_tapes"], fit["tapes"], fit["windows"]),
            "test_m": maker_buy_prints(test["full_tapes"], test["tapes"], test["windows"]),
            "fit_flow": taker_flow(fit["tapes"], fit["windows"]),
            "test_flow": taker_flow(test["tapes"], test["windows"]),
        }
    pre = _PERIOD_MEMO[mkey]
    fit_m, test_m, fit_flow, test_flow = pre["fit_m"], pre["test_m"], pre["fit_flow"], pre["test_flow"]
    dur = DURATION_S[duration]
    have = len(fit_m) and len(test_m)
    mt_dm = match_test(fit_m, test_m, w, spot, test_blocks, dur, score_fns={"fair_minus_price": score_prints}, n_perm=n_perm, seed=seed) if have else {}
    mt_sr = match_test(fit_m, test_m, w, spot, test_blocks, dur, score_fns=sr_score_fns(), lags=[0, 1, 2, 3, 5], n_perm=n_perm, seed=seed) if have else {}

    # --- DM backtest (unchanged design, dynamic tick) + at-touch bound
    lat = max(int(mt_dm.get("chosen_latency_s", 1)) if mt_dm else 1, 1)
    grid = [0.0, 0.01, 0.02, 0.03, 0.05, 0.08]
    dkey = ("dm_scan", id(fit), lat)
    if dkey not in _PERIOD_MEMO:
        _PERIOD_MEMO[dkey] = {d: maker_backtest(fit_flow, fit["windows"], spot, d, lat) for d in grid}
    fit_scan = _PERIOD_MEMO[dkey]
    best_delta = max(grid, key=lambda d: (fit_scan[d].get("per_window_t") or -1e9) if fit_scan[d].get("fills", 0) >= 30 else -1e9)
    bt = maker_backtest(test_flow, test["windows"], spot, best_delta, lat)
    bt_touch = maker_backtest(test_flow, test["windows"], spot, best_delta, lat, at_touch=True)
    degraded = {str(lat + x): {k: v for k, v in maker_backtest(test_flow, test["windows"], spot, best_delta, lat + x).items() if k in ("fills", "pnl", "return_on_bought", "per_window_p")} for x in (1, 2, 5, 10)}
    queue = {str(q): {k: v for k, v in maker_backtest(test_flow, test["windows"], spot, best_delta, lat, queue_share=q).items() if k in ("fills", "pnl", "per_window_p")} for q in (0.5, 0.25)}

    # --- SR executable rule (parameters from FIT only; the same for every wallet)
    skey = ("sr_fit", id(fit))
    if skey not in _PERIOD_MEMO:
        _PERIOD_MEMO[skey] = fit_sr_maker(fit_flow, fit["windows"], spot)
    sr_best, sr_scan = _PERIOD_MEMO[skey]
    sr = {}
    if sr_best:
        kw = {"theta": sr_best["theta"], "delta": sr_best["delta"], "horizon": sr_best["horizon"], "requote_s": sr_best["requote_s"]}
        L = sr_best["latency"]
        trim = lambda r: {k: v for k, v in r.items() if k != "daily_pnl"}  # noqa: E731
        sr = {
            "fit_best": sr_best,
            "fit_configs": len(sr_scan),
            "fit_share_positive": float(np.mean([r["pnl"] > 0 for r in sr_scan])) if sr_scan else None,
            "test_strict": trim(spot_reactive_maker_backtest(test_flow, test["windows"], spot, latency=L, **kw)),
            "test_at_touch": trim(spot_reactive_maker_backtest(test_flow, test["windows"], spot, latency=L, at_touch=True, **kw)),
            "test_latency_degradation_at_touch": {str(L + x): {k: v for k, v in spot_reactive_maker_backtest(test_flow, test["windows"], spot, latency=L + x, at_touch=True, **kw).items() if k in ("fills", "pnl", "return_on_bought", "per_window_p_incl_zero")} for x in (1, 3)},
            "test_latency_1s_reference_at_touch": {k: v for k, v in spot_reactive_maker_backtest(test_flow, test["windows"], spot, latency=1, at_touch=True, **kw).items() if k in ("fills", "pnl", "return_on_bought", "per_window_p_incl_zero")},
        }

    mine = test_m[test_m["wallet"] == w]
    replay = {}
    if len(mine):
        payout = np.where(mine["is_up"], mine["up_payout"], 1 - mine["up_payout"])
        pnl = mine["size"] * (payout - mine["price"])
        per_w = pd.Series(pnl.to_numpy(), index=mine["condition_id"]).groupby(level=0).sum()
        tt = hac_t_test(per_w.to_numpy())
        replay = {"fills": int(len(mine)), "usd": float((mine["size"] * mine["price"]).sum()), "pnl": float(pnl.sum()), "return": float(pnl.sum() / (mine["size"] * mine["price"]).sum()), "per_window_p": tt.p_value}
    ev_out = Evidence(
        tool="updown_maker_study",
        subject={"kind": "wallet", "wallet": w, "asset": asset, "duration": duration, "as_of": as_of, "spot_source": spot_source},
        observed={
            "fit_windows": len(fit["windows"]),
            "test_windows": len(test["windows"]),
            "fit_passive_buys": int(len(fit_m)),
            "test_passive_buys": int(len(test_m)),
            "test_wallet_passive_buys": int(len(mine)),
            "wallet_share_of_passive_buys": float(len(mine) / len(test_m)) if len(test_m) else None,
        },
        derived={
            "match_test": mt_dm,
            "match_test_spot_reactive": mt_sr,
            "fit_delta_scan": {str(k): {kk: vv for kk, vv in v.items() if kk in ("fills", "pnl", "per_window_t", "per_window_p")} for k, v in fit_scan.items()},
            "chosen_delta": best_delta,
            "chosen_latency_s": lat,
            "backtest_test_period": {k: v for k, v in bt.items() if k != "daily_pnl"},
            "backtest_test_period_at_touch": {k: v for k, v in bt_touch.items() if k != "daily_pnl"},
            "latency_degradation": degraded,
            "queue_share_sensitivity": queue,
            "spot_reactive_maker": sr,
            "wallet_maker_replay_test_period": replay,
        },
        coverage=Coverage("partial" if fit["partial_tapes"] or test["partial_tapes"] else "complete"),
        limitations=[
            "Trade-through fills ignore queue position at the touch (conservative) but assume our bid sat at the front among bids below the touch; queue-share sensitivity reports thinner fills; at-touch is the first-in-queue bound.",
            "Taker tape rows of multi-level sweeps carry the sweep's average price, so trade-through is judged on that price (it misses some fills at levels the sweep reached).",
            f"Spot is {spot_source} per-second prices; resolution uses Chainlink's aggregated feed.",
            "Maker rebates are excluded from backtest PnL (conservative).",
        ],
    )
    if out_dir is not None:
        d = out_dir / w
        d.mkdir(parents=True, exist_ok=True)
        tag = "" if spot_source == "kraken" else f"_{spot_source}"
        (d / f"updown_maker_study_{asset}_{duration}{tag}.json").write_text(json.dumps(ev_out.to_dict(), indent=1), encoding="utf-8")
    return ev_out


def all_blocks(period_start: int, period_end: int, block_s: int) -> list[tuple[int, int]]:
    slots = range(period_start - period_start % block_s + (block_s if period_start % block_s else 0), period_end - block_s + 1, block_s)
    return [(s, s + block_s) for s in slots]


def run_frozen_rule_extension(
    wallets: list[str],
    asset: str = "btc",
    duration: str = "5m",
    as_of: int | None = None,
    forward_days: int = 1,
    spot_source: str = "binance",
    seed: int = 7,
    blocks_per_period: int = 12,
    block_hours: int = 2,
    others_sample: float = 0.25,
    n_perm: int = 100,
    out_path: Path | None = None,
) -> Evidence:
    """Out-of-sample extension of the FIT-chosen rules on every unseen block.

    FIT is the standard FIT sample (seed ``seed``). Rules and parameters are
    chosen there exactly as in the studies (match score, latency and theta per
    wallet; the SR maker's parameters). They are then evaluated, frozen, on
    (a) every 2-hour block of the TEST week that the standard TEST sample did
    not use, and (b) ``forward_days`` days after ``as_of`` (data that did not
    exist when the study was designed). Non-wallet passive and taker prints
    are subsampled at ``others_sample`` for the match statistic (AUC is
    unbiased under random subsampling of the other class); backtests use the
    full tape.
    """
    from polyrea.analysis.updown import maker_buy_prints, spot_reactive_maker_backtest, taker_flow
    from polyrea.pit import TimeSeries
    from polyrea.workflows.investigate import default_as_of

    pm = PolymarketData()
    as_of = as_of or default_as_of()
    bs = block_hours * 3600
    dur = DURATION_S[duration]
    ws = [w.lower() for w in wallets]
    fit_blocks = sample_blocks(as_of - 14 * DAY, as_of - 7 * DAY, blocks_per_period, bs, seed)
    used_test = set(sample_blocks(as_of - 7 * DAY, as_of, blocks_per_period, bs, seed + 1))
    unseen = [b for b in all_blocks(as_of - 7 * DAY, as_of, bs) if b not in used_test]
    forward = all_blocks(as_of, as_of + forward_days * DAY, bs)
    fit = load_period(asset, duration, fit_blocks, pm, with_full_tape=True, spot_source=spot_source)
    fit_m = maker_buy_prints(fit["full_tapes"], fit["tapes"], fit["windows"])
    fit_flow = taker_flow(fit["tapes"], fit["windows"])
    fit_p = fit["prints"]
    fit_windows = fit["windows"]
    fit_spot = fit["spot"]
    _PERIOD_MEMO.clear()  # free the FIT tapes; only compact frames are kept

    rng = np.random.default_rng(seed)
    parts: dict[str, list[pd.DataFrame]] = {"m": [], "p": [], "p_full": [], "flow": []}
    windows: list[Window] = []
    spot_ev, spot_vals = [fit_spot.event_ts], [fit_spot.values]
    origin: dict[str, str] = {}
    for kind, blocks in (("unseen_test_week", unseen), ("forward", forward)):
        for b in blocks:
            per = _load_period(asset, duration, [b], pm, 6, True, spot_source)
            m = maker_buy_prints(per["full_tapes"], per["tapes"], per["windows"])
            p = per["prints"]
            for key, df in (("m", m), ("p", p)):
                if len(df):
                    keep = df["wallet"].isin(ws).to_numpy() | (rng.random(len(df)) < others_sample)
                    parts[key].append(df[keep])
            parts["flow"].append(taker_flow(per["tapes"], per["windows"]))
            if len(p):
                parts["p_full"].append(p[["condition_id", "ts", "wallet", "is_up", "price", "size", "start_ts", "end_ts", "twap", "fee_rate", "up_payout"]])
            windows.extend(per["windows"])
            for w in per["windows"]:
                origin[w.condition_id] = kind
            spot_ev.append(per["spot"].event_ts)
            spot_vals.append(per["spot"].values)
    ev = np.concatenate(spot_ev)
    vals = np.concatenate(spot_vals)
    order = np.argsort(ev, kind="stable")
    keep = np.r_[True, np.diff(ev[order]) > 0]
    spot = SpotIndex(TimeSeries.build(f"spot.{spot_source}.{asset}", zip(ev[order][keep].tolist(), vals[order][keep].tolist()), availability_lag=1))
    ext_m = pd.concat(parts["m"], ignore_index=True)
    ext_p = pd.concat(parts["p"], ignore_index=True)
    ext_flow = pd.concat(parts["flow"], ignore_index=True)
    ext_p_full = pd.concat(parts["p_full"], ignore_index=True)
    ext_blocks = unseen + forward

    trim = lambda r: {k: v for k, v in r.items() if k != "daily_pnl"}  # noqa: E731
    sr: dict[str, Any] = {}
    # primary: parameters chosen and evaluated with match_slack=2 (block-time slack); slack 0 is the optimistic reference
    for slack in (2, 0):
        sr_best, sr_scan = fit_sr_maker(fit_flow, fit_windows, spot, match_slack=slack)
        res: dict[str, Any] = {"fit_best": sr_best, "fit_configs": len(sr_scan), "fit_share_positive": float(np.mean([r["pnl"] > 0 for r in sr_scan])) if sr_scan else None}
        if sr_best:
            kw = {"theta": sr_best["theta"], "delta": sr_best["delta"], "horizon": sr_best["horizon"], "requote_s": sr_best["requote_s"], "match_slack": slack}
            L = sr_best["latency"]
            for kind in ("unseen_test_week", "forward"):
                fl = ext_flow[ext_flow["condition_id"].map(origin) == kind]
                wn = [w for w in windows if origin[w.condition_id] == kind]
                res[kind] = {
                    "windows": len(wn),
                    "strict": trim(spot_reactive_maker_backtest(fl, wn, spot, latency=L, **kw)),
                    "at_touch": trim(spot_reactive_maker_backtest(fl, wn, spot, latency=L, at_touch=True, **kw)),
                    "at_touch_latency_plus_1": trim(spot_reactive_maker_backtest(fl, wn, spot, latency=L + 1, at_touch=True, **kw)),
                }
            res["all"] = {"strict": trim(spot_reactive_maker_backtest(ext_flow, windows, spot, latency=L, **kw)), "at_touch": trim(spot_reactive_maker_backtest(ext_flow, windows, spot, latency=L, at_touch=True, **kw))}
        sr[f"match_slack_{slack}"] = res
    per_wallet = {}
    for w in ws:
        mt_sr = match_test(fit_m, ext_m, w, spot, ext_blocks, dur, score_fns=sr_score_fns(), lags=[0, 1, 2, 3, 5], n_perm=n_perm, seed=seed)
        mt_la = match_test(fit_p, ext_p, w, spot, ext_blocks, dur, n_perm=n_perm, seed=seed)
        bt_la = {k: v for k, v in backtest(ext_p_full, spot, theta=mt_la["theta"], latency=max(2, mt_la["chosen_latency_s"])).items() if k != "daily_pnl"}
        mine = ext_m[ext_m["wallet"] == w]
        replay = {}
        if len(mine):
            payout = np.where(mine["is_up"], mine["up_payout"], 1 - mine["up_payout"])
            pnl = mine["size"] * (payout - mine["price"])
            replay = {"fills": int(len(mine)), "usd": float((mine["size"] * mine["price"]).sum()), "pnl": float(pnl.sum()), "return": float(pnl.sum() / (mine["size"] * mine["price"]).sum())}
        per_wallet[w] = {"match_spot_reactive": mt_sr, "match_latency_taker": mt_la, "latency_taker_backtest_L_ge_2": bt_la, "wallet_maker_replay": replay}
    ev_out = Evidence(
        tool="frozen_rule_extension",
        subject={"kind": "wallets", "wallets": ws, "asset": asset, "duration": duration, "as_of": as_of, "spot_source": spot_source, "forward_days": forward_days},
        observed={
            "fit_blocks": fit_blocks,
            "unseen_test_week_blocks": len(unseen),
            "forward_blocks": len(forward),
            "windows": len(windows),
            "passive_buys_kept": int(len(ext_m)),
            "taker_buys_kept": int(len(ext_p)),
            "taker_flow_rows": int(len(ext_flow)),
            "others_sample": others_sample,
        },
        derived={"spot_reactive_maker": sr, "per_wallet": per_wallet},
        coverage=Coverage("complete"),
        limitations=[
            "Parameters come from the standard FIT sample only; nothing measured on these blocks fed back.",
            "Other wallets' prints are subsampled for the match statistic; wallet prints are kept in full.",
            f"Spot is {spot_source} per-second prices; markets settle on Chainlink.",
        ],
    )
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(ev_out.to_dict(), indent=1), encoding="utf-8")
    return ev_out

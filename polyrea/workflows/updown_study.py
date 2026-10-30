"""Reverse-engineering study for wallets trading crypto Up/Down windows.

Design (walk-forward, no look-ahead):

* Two disjoint periods ending at ``as_of``: FIT = [as_of-14d, as_of-7d),
  TEST = [as_of-7d, as_of). A deterministic random sample of 2-hour blocks is
  drawn from each; every window of the asset/duration inside a block is used,
  whether or not the wallet traded it.
* For each window: the taker tape (every aggressive order, any wallet) and
  Kraken spot trades reduced to per-second prices (available 1 s later).
* FIT chooses latency (lag scan) and threshold; TEST measures, untouched:
  decision-level agreement with the wallet (AUC / MCC vs. a spot-clock-shift
  permutation null), backtest PnL of the rule, the wallet's own outcome on the
  same windows, and how the edge decays when our information is slower.
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
from polyrea.adapters.spot import kraken_trades, per_second_series
from polyrea.analysis.updown import (
    SpotIndex,
    Window,
    audit_vectorized_fair_value,
    backtest,
    match_test,
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


def load_period(asset: str, duration: str, blocks: list[tuple[int, int]], pm: PolymarketData, workers: int = 6, with_full_tape: bool = False) -> dict[str, Any]:
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
    for a, b in blocks:
        tr, _ = kraken_trades(asset, a - 1800 - 120, b + 120)
        spot_series.append(per_second_series(f"spot.kraken.{asset}", tr, a - 1800 - 120, b + 120))
    # stitch blocks into one series (blocks do not overlap)
    ev = np.concatenate([s.event_ts for s in spot_series]) if spot_series else np.array([], dtype=np.int64)
    vals = np.concatenate([s.values for s in spot_series]) if spot_series else np.array([])
    from polyrea.pit import TimeSeries

    spot = TimeSeries.build(f"spot.kraken.{asset}", zip(ev.tolist(), vals.tolist()), availability_lag=1)
    return {
        "slugs": len(slugs),
        "windows": windows,
        "tapes": tapes,
        "full_tapes": full_tapes,
        "partial_tapes": partial,
        "spot": spot,
        "prints": taker_buy_prints(tapes, windows),
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
) -> Evidence:
    from polyrea.workflows.investigate import default_as_of

    pm = PolymarketData()
    as_of = as_of or default_as_of()
    fit_period = (as_of - 14 * DAY, as_of - 7 * DAY)
    test_period = (as_of - 7 * DAY, as_of)
    bs = block_hours * 3600
    fit_blocks = sample_blocks(*fit_period, blocks_per_period, bs, seed)
    test_blocks = sample_blocks(*test_period, blocks_per_period, bs, seed + 1)
    fit = load_period(asset, duration, fit_blocks, pm)
    test = load_period(asset, duration, test_blocks, pm)
    w = wallet.lower()
    # one spot index spanning both periods (disjoint blocks)
    from polyrea.pit import TimeSeries

    ev = np.concatenate([fit["spot"].event_ts, test["spot"].event_ts])
    vals = np.concatenate([fit["spot"].values, test["spot"].values])
    order = np.argsort(ev, kind="stable")
    spot_ts = TimeSeries.build(fit["spot"].name, zip(ev[order].tolist(), vals[order].tolist()), availability_lag=1)
    spot = SpotIndex(spot_ts)

    # --- no-look-ahead audit of the fast path
    store = PITStore()
    store.add_series(spot_ts)
    rng = random.Random(seed)
    probe_windows = rng.sample(test["windows"], min(15, len(test["windows"])))
    probes = [(win, rng.randint(win.start_ts, win.end_ts)) for win in probe_windows for _ in range(2)]

    mt = match_test(fit["prints"], test["prints"], w, spot, n_perm=n_perm, seed=seed)
    lat = mt["chosen_latency_s"]
    theta = mt["theta"]
    audit = audit_vectorized_fair_value(store, spot_ts.name, test["windows"], probes, latency=lat)
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
        subject={"kind": "wallet", "wallet": w, "asset": asset, "duration": duration, "as_of": as_of},
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
            "Spot is Kraken trades; markets resolve on Chainlink's aggregated TWAP, so S0 and the TWAP are proxies.",
            "Backtest fills assume the observed taker liquidity at each print was available to us; contested liquidity is reported via the excluding-wallet run and latency degradation, not modeled queue competition.",
            "Polymarket tape timestamps are block times (~2 s), bounding the resolution of the latency estimate.",
            "Only the wallet's taker buys are modeled; its maker fills are analysed separately in the profile.",
        ],
    )
    if out_dir is not None:
        d = out_dir / w
        d.mkdir(parents=True, exist_ok=True)
        (d / f"updown_study_{asset}_{duration}.json").write_text(json.dumps(ev_out.to_dict(), indent=1))
    return ev_out


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
) -> Evidence:
    """Directional-maker hypothesis DM(delta, latency) for an Up/Down wallet.

    Match: does spot-model edge (fair - price) predict which passive BUY fills
    belong to the wallet (AUC on TEST vs. spot-clock-shift null)?
    Backtest: a slow maker resting bids at fair - delta, filled only by later
    taker prints that trade through the bid, on TEST windows with delta fitted
    on FIT windows; latency degradation; the wallet's own maker-fill outcome.
    """
    from polyrea.analysis.updown import maker_backtest, maker_buy_prints, taker_flow
    from polyrea.workflows.investigate import default_as_of

    pm = PolymarketData()
    as_of = as_of or default_as_of()
    bs = block_hours * 3600
    fit_blocks = sample_blocks(as_of - 14 * DAY, as_of - 7 * DAY, blocks_per_period, bs, seed)
    test_blocks = sample_blocks(as_of - 7 * DAY, as_of, blocks_per_period, bs, seed + 1)
    fit = load_period(asset, duration, fit_blocks, pm, with_full_tape=True)
    test = load_period(asset, duration, test_blocks, pm, with_full_tape=True)
    from polyrea.pit import TimeSeries

    ev = np.concatenate([fit["spot"].event_ts, test["spot"].event_ts])
    vals = np.concatenate([fit["spot"].values, test["spot"].values])
    order = np.argsort(ev, kind="stable")
    spot_ts = TimeSeries.build(fit["spot"].name, zip(ev[order].tolist(), vals[order].tolist()), availability_lag=1)
    spot = SpotIndex(spot_ts)
    w = wallet.lower()
    fit_m = maker_buy_prints(fit["full_tapes"], fit["tapes"], fit["windows"])
    test_m = maker_buy_prints(test["full_tapes"], test["tapes"], test["windows"])
    mt = match_test(fit_m, test_m, w, spot, n_perm=n_perm, seed=seed) if len(fit_m) and len(test_m) else {}
    lat = int(mt.get("chosen_latency_s", 1)) if mt else 1
    fit_flow = taker_flow(fit["tapes"], fit["windows"])
    test_flow = taker_flow(test["tapes"], test["windows"])
    grid = [0.0, 0.01, 0.02, 0.03, 0.05, 0.08]
    fit_scan = {d: maker_backtest(fit_flow, fit["windows"], spot, d, lat) for d in grid}
    best_delta = max(grid, key=lambda d: (fit_scan[d].get("per_window_t") or -1e9) if fit_scan[d].get("fills", 0) >= 30 else -1e9)
    bt = maker_backtest(test_flow, test["windows"], spot, best_delta, lat)
    degraded = {str(lat + x): {k: v for k, v in maker_backtest(test_flow, test["windows"], spot, best_delta, lat + x).items() if k in ("fills", "pnl", "return_on_bought", "per_window_p")} for x in (1, 2, 5, 10)}
    queue = {str(q): {k: v for k, v in maker_backtest(test_flow, test["windows"], spot, best_delta, lat, queue_share=q).items() if k in ("fills", "pnl", "per_window_p")} for q in (0.5, 0.25)}
    mine = test_m[test_m["wallet"] == w]
    replay = {}
    if len(mine):
        payout = np.where(mine["is_up"], mine["up_payout"], 1 - mine["up_payout"])
        pnl = mine["size"] * (payout - mine["price"])
        per_w = pd.Series(pnl.to_numpy(), index=mine["condition_id"]).groupby(level=0).sum()
        from polyrea.stats.significance import hac_t_test

        tt = hac_t_test(per_w.to_numpy())
        replay = {"fills": int(len(mine)), "usd": float((mine["size"] * mine["price"]).sum()), "pnl": float(pnl.sum()), "return": float(pnl.sum() / (mine["size"] * mine["price"]).sum()), "per_window_p": tt.p_value}
    ev_out = Evidence(
        tool="updown_maker_study",
        subject={"kind": "wallet", "wallet": w, "asset": asset, "duration": duration, "as_of": as_of},
        observed={
            "fit_windows": len(fit["windows"]),
            "test_windows": len(test["windows"]),
            "fit_passive_buys": int(len(fit_m)),
            "test_passive_buys": int(len(test_m)),
            "test_wallet_passive_buys": int(len(mine)),
            "wallet_share_of_passive_buys": float(len(mine) / len(test_m)) if len(test_m) else None,
        },
        derived={
            "match_test": mt,
            "fit_delta_scan": {str(k): {kk: vv for kk, vv in v.items() if kk in ("fills", "pnl", "per_window_t", "per_window_p")} for k, v in fit_scan.items()},
            "chosen_delta": best_delta,
            "chosen_latency_s": lat,
            "backtest_test_period": {k: v for k, v in bt.items() if k != "daily_pnl"},
            "latency_degradation": degraded,
            "queue_share_sensitivity": queue,
            "wallet_maker_replay_test_period": replay,
        },
        coverage=Coverage("partial" if fit["partial_tapes"] or test["partial_tapes"] else "complete"),
        limitations=[
            "Trade-through fills ignore queue position at the touch (conservative) but assume our bid sat at the front among bids below the touch; queue-share sensitivity reports thinner fills.",
            "Spot is Kraken per-second trades; resolution uses Chainlink's aggregate TWAP.",
            "Maker rebates are excluded from backtest PnL (conservative).",
        ],
    )
    if out_dir is not None:
        d = out_dir / w
        d.mkdir(parents=True, exist_ok=True)
        (d / f"updown_maker_study_{asset}_{duration}.json").write_text(json.dumps(ev_out.to_dict(), indent=1))
    return ev_out

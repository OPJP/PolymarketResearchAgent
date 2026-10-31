"""Replicability study for in-play two-sided makers (no external event data needed).

Samples the wallet's markets in the window, splits them by start time into FIT
and TEST, chooses the quote offset on FIT, and backtests a slow public-data
maker on TEST at several information delays. Also scores the wallet's own
passive fills on the same TEST markets ("original strategy" outcome), so the
gap between the wallet and a slow imitator is measured on identical markets.
"""

from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info
from polyrea.analysis.tape_maker import tape_maker_backtest
from polyrea.analysis.updown import snap_price
from polyrea.evidence import Coverage, Evidence
from polyrea.stats.significance import hac_t_test
from polyrea.workflows.investigate import load_window


def _flow_and_passive(cid: str, m: dict[str, Any], wallet: str, start: int, end: int, pm: PolymarketData) -> tuple[pd.DataFrame, pd.DataFrame]:
    tokens = json.loads(m.get("clobTokenIds") or "[]")
    taker, _, _ = pm.market_trades(cid, start=start, end=end, taker_only=True)
    full, _, _ = pm.market_trades(cid, start=start, end=end, taker_only=False)
    keys: dict[tuple, int] = {}
    rows = []
    for r in taker:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        keys[k] = keys.get(k, 0) + 1
        if str(r.get("asset")) in tokens:
            rows.append({"condition_id": cid, "ts": int(r["timestamp"]), "outcome": tokens.index(str(r["asset"])), "side": r.get("side"), "price": snap_price(float(r["price"])), "size": float(r["size"])})
    passive = []
    for r in full:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        if keys.get(k, 0) > 0:
            keys[k] -= 1
            continue
        if (r.get("proxyWallet") or "").lower() == wallet and r.get("side") == "BUY" and str(r.get("asset")) in tokens:
            passive.append({"condition_id": cid, "ts": int(r["timestamp"]), "outcome": tokens.index(str(r["asset"])), "price": snap_price(float(r["price"])), "size": float(r["size"])})
    return pd.DataFrame(rows), pd.DataFrame(passive)


def run_maker_replicability_study(
    wallet: str,
    days: int = 30,
    as_of: int | None = None,
    max_markets: int = 160,
    seed: int = 5,
    out_dir: Path | None = None,
    family_prefixes: tuple[str, ...] | None = None,
) -> Evidence:
    pm = PolymarketData()
    win = load_window(wallet, days=days, as_of=as_of, pm=pm)
    t, markets = win["trades"], win["markets"]
    w = wallet.lower()
    if family_prefixes:
        t = t[t["slug"].str.startswith(family_prefixes)]
    agg = t.groupby("condition_id").agg(first=("ts", "min"), last=("ts", "max"), n=("ts", "size"), usd=("usdc", "sum"))
    agg = agg[agg["n"] >= 5]
    rng = random.Random(seed)
    cids = list(agg.index)
    if len(cids) > max_markets:
        cids = rng.sample(cids, max_markets)
    payouts, active = {}, {}
    for cid in cids:
        r = resolution_info(markets.get(cid) or {})
        tokens = json.loads((markets.get(cid) or {}).get("clobTokenIds") or "[]")
        if r["resolved"] and len(tokens) == 2:
            payouts[cid] = r["payout"].get(str(tokens[0]), 0.0)
            active[cid] = (int(agg.at[cid, "first"]), int(agg.at[cid, "last"]))
    cids = [c for c in cids if c in payouts]

    def load(cid):
        a, b = active[cid]
        return _flow_and_passive(cid, markets[cid], w, a - 1800, b + 600, pm)

    with ThreadPoolExecutor(6) as ex:
        parts = list(ex.map(load, cids))
    flow = pd.concat([p[0] for p in parts], ignore_index=True) if parts else pd.DataFrame()
    passive = pd.concat([p[1] for p in parts], ignore_index=True) if parts else pd.DataFrame()
    split = int(np.median([active[c][0] for c in cids])) if cids else 0
    fit_c = {c for c in cids if active[c][0] < split}
    test_c = {c for c in cids if active[c][0] >= split}
    fit_flow, test_flow = flow[flow["condition_id"].isin(fit_c)], flow[flow["condition_id"].isin(test_c)]
    grid = [0.005, 0.01, 0.02, 0.03, 0.05]
    fit_scan = {d: tape_maker_backtest(fit_flow, payouts, d, latency=2, active=active) for d in grid}
    best = max(grid, key=lambda d: fit_scan[d].get("per_market_t") or -1e9)
    test_res = {str(L): tape_maker_backtest(test_flow, payouts, best, latency=L, active=active) for L in (0, 2, 5, 10, 30)}
    test_touch = {str(L): tape_maker_backtest(test_flow, payouts, best, latency=L, active=active, at_touch=True) for L in (0, 2, 5)}
    mine = passive[passive["condition_id"].isin(test_c)]
    replay = {}
    if len(mine):
        pay = np.where(mine["outcome"] == 0, mine["condition_id"].map(payouts), 1 - mine["condition_id"].map(payouts))
        pnl = mine["size"] * (pay - mine["price"])
        per_m = pd.Series(pnl.to_numpy(), index=mine["condition_id"]).groupby(level=0).sum()
        tt = hac_t_test(per_m.to_numpy())
        usd = float((mine["size"] * mine["price"]).sum())
        replay = {"fills": int(len(mine)), "usd": usd, "pnl": float(pnl.sum()), "return": float(pnl.sum() / usd) if usd else None, "per_market_p": tt.p_value}
    ev = Evidence(
        tool="maker_replicability_study",
        subject={"kind": "wallet", "wallet": w, "days": days, "families": family_prefixes},
        observed={"markets_sampled": len(cids), "fit_markets": len(fit_c), "test_markets": len(test_c), "taker_prints": int(len(flow)), "wallet_passive_buys": int(len(passive))},
        derived={
            "fit_delta_scan": {str(k): {kk: vv for kk, vv in v.items() if kk in ("fills", "pnl", "return_on_bought", "per_market_t", "per_market_p")} for k, v in fit_scan.items()},
            "chosen_delta": best,
            "test_by_latency_s": test_res,
            "test_at_touch_by_latency_s": test_touch,
            "wallet_passive_replay_test": replay,
        },
        coverage=Coverage("partial", f"{len(cids)} sampled markets"),
        limitations=[
            "Fair value is the last public print (no external event data); a real maker would also use game state.",
            "Trade-through fills: conservative at the touch, optimistic about queue position below it; at-touch results are the first-in-queue bound.",
            "Maker rebates and liquidity rewards are excluded from backtest PnL.",
        ],
    )
    if out_dir is not None:
        d = out_dir / w
        d.mkdir(parents=True, exist_ok=True)
        (d / "maker_replicability_study.json").write_text(json.dumps(ev.to_dict(), indent=1), encoding="utf-8")
    return ev

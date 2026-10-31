"""Per-window / per-game / per-market PnL series are built with groupby(condition_id | event_slug),
which orders them by hash / slug, not by time. HAC and the stationary block bootstrap then see a
shuffled series. Compare p-values with the series in hash order (as run) vs time order, on the cached
BTC 5m TEST period (repo's backtest + wallet_replay), and in a simulation with clustered windows.
Run with POLYREA_OFFLINE=1 POLYREA_CACHE_DIR=<scratch copy>."""
import os
import sys

import numpy as np
import pandas as pd

import common  # noqa: F401
from polyrea.stats import significance as S

AS_OF = 1793318400


def compare(label, df, value_col, key_col, time_col):
    by_key = df.groupby(key_col)[value_col].sum()  # what the repo does
    t_order = df.groupby(key_col).agg(v=(value_col, "sum"), t=(time_col, "min")).sort_values("t")["v"]
    a, b = by_key.to_numpy(), t_order.to_numpy()
    print(f"  {label}: n={len(a)} mean={a.mean():.2f} | hash order: HAC p={S.hac_t_test(a).p_value:.3g} boot p={S.stationary_bootstrap_pvalue(a, 3000).p_value:.3g} "
          f"rho1={np.corrcoef(a[1:], a[:-1])[0,1]:+.2f} | time order: HAC p={S.hac_t_test(b).p_value:.3g} boot p={S.stationary_bootstrap_pvalue(b, 3000).p_value:.3g} rho1={np.corrcoef(b[1:], b[:-1])[0,1]:+.2f}")


print("== simulation: 12 blocks x 24 windows, PnL = block effect (sd 1) + window noise (sd 1), true mean 0")
rng = np.random.default_rng(3)
rej_h = rej_t = 0
R = 2000
for r in range(R):
    blk = np.repeat(rng.standard_normal(12), 24)
    x = blk + rng.standard_normal(288)
    perm = rng.permutation(288)  # hash order is a fixed pseudo-random permutation of time order
    rej_h += S.hac_t_test(x[perm]).p_value < 0.05
    rej_t += S.hac_t_test(x).p_value < 0.05
print(f"  rejection rate at 0.05: hash-ordered {rej_h/R:.3f}, time-ordered {rej_t/R:.3f}")

if os.environ.get("POLYREA_OFFLINE") != "1":
    sys.exit("set POLYREA_OFFLINE=1 and POLYREA_CACHE_DIR to the scratch cache copy")
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.updown import SpotIndex, backtest
from polyrea.workflows.updown_study import DAY, load_period, sample_blocks

test = sample_blocks(AS_OF - 7 * DAY, AS_OF, 12, 7200, 8)
per = load_period("btc", "5m", test, PolymarketData(), with_full_tape=False)
prints = per["prints"]
spot = SpotIndex(per["spot"]) if "SpotIndex" in dir() else None
print("== real data: BTC 5m TEST period,", len(prints), "taker-buy prints,", prints["condition_id"].nunique(), "windows")
for w, name in [("0xc53375ff94e96100f2b30a4b5775db35218d69a9", "dangerously-skip-permissions"), ("0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "GoodFallen"),
                ("0x3048d65321be3497164cdfc2996f94f98a2e7537", "x-MoneyForWhiskas")]:
    p = prints[(prints["wallet"] == w) & prints["up_payout"].notna()].copy()
    if p.empty:
        continue
    payout = np.where(p["is_up"], p["up_payout"], 1 - p["up_payout"])
    p["pnl"] = p["size"] * payout - p["size"] * p["price"]  # gross of fees: enough to show the ordering effect
    compare(f"{name} own taker buys (wallet_replay-style)", p, "pnl", "condition_id", "end_ts")
try:
    from polyrea.analysis.updown import SpotIndex
    sp = SpotIndex(per["spot"])
    p = prints[prints["up_payout"].notna()].copy()
    from polyrea.analysis.updown import score_prints, taker_fee_per_share
    p["edge"] = score_prints(p, sp, 20)
    sel = p[np.isfinite(p["edge"]) & (p["edge"] > 0.065)].copy()
    usd = np.minimum(sel["size"] * sel["price"], 25.0)
    shares = usd / sel["price"]
    payout = np.where(sel["is_up"], sel["up_payout"], 1 - sel["up_payout"])
    sel["pnl"] = shares * payout - usd - taker_fee_per_share(sel["price"].to_numpy(), 1.0) * sel["fee_rate"].to_numpy() * shares
    compare("LA rule backtest (theta=0.065, latency=20 s)", sel, "pnl", "condition_id", "end_ts")
except Exception as exc:  # noqa: BLE001
    print("  backtest replication skipped:", repr(exc))

"""Iteration 2: order-level view of the cluster's resting BUY orders (on-chain OrderFilled grouped by orderHash),
VALIDATE BTC 5m. How long does an order rest while it is being filled, and how far does the Binance fair value
move while it rests (staleness = how it cancels / requotes)?"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT  # noqa: E402

f = pd.read_parquet(OUT / "chain_fills_1792108800_1792713600.parquet")
w = pd.read_parquet(OUT / "windows_5m.parquet")
tu = dict(zip(w["up_token"], w["cid"]))
td = dict(zip(w["down_token"], w["cid"]))
f["token_id"] = f["token_id"].astype(str)
f = f[(f["role"] == "maker") & (f["side"].astype(str).isin(["BUY", "0"])) & f["token_id"].isin(tu.keys() | td.keys())].copy()
f["cid"] = [tu.get(t) or td.get(t) for t in f["token_id"]]
f["is_up"] = f["token_id"].isin(tu.keys())
f = f.merge(w[["cid", "start_ts", "end_ts"]], on="cid")
f["ts"] = np.round(f["block_ts_interp"]).astype(np.int64)
f["price"] = f["usdc"] / f["shares"]
o = f.groupby("order_hash").agg(n=("ts", "size"), t0=("ts", "min"), t1=("ts", "max"), sh=("shares", "sum"), px=("price", "mean"),
                                 pxsd=("price", "std"), wallet=("maker", "first"), is_up=("is_up", "first"), start=("start_ts", "first"),
                                 end=("end_ts", "first"), cid=("cid", "first"))
o["life"] = o["t1"] - o["t0"]
spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
res = {"fills": int(len(f)), "orders": int(len(o)), "fills_per_order_median": float(o["n"].median()),
       "single_fill_share": float((o["n"] == 1).mean()), "price_constant_share": float((o["pxsd"].fillna(0) < 1e-4).mean()),
       "filled_shares_quantiles": [float(x) for x in o["sh"].quantile([0.1, 0.25, 0.5, 0.75, 0.9])],
       "filled_shares_top": {str(k): int(v) for k, v in o["sh"].round(0).value_counts().head(8).items()},
       "orders_per_window_median": float(o.groupby("cid").size().median())}
m = o[o["n"] >= 2].copy()
res["multi_fill_orders"] = int(len(m))
res["life_quantiles_multi"] = [float(x) for x in m["life"].quantile([0.25, 0.5, 0.75, 0.9, 0.99])]
# fair-value drift while the order rests (between its first and last fill), vs the same-length drift at random times
f0, _ = fair_up(sp, m["start"].to_numpy(), m["end"].to_numpy(), m["t0"].to_numpy() - 1)
f1, _ = fair_up(sp, m["start"].to_numpy(), m["end"].to_numpy(), m["t1"].to_numpy() - 1)
d = np.where(m["is_up"], f1 - f0, f0 - f1)
m["dfair"] = d
lv = m[m["life"] >= 5]
res["dfair_abs_quantiles_life>=5s"] = [float(x) for x in np.quantile(np.abs(lv["dfair"]), [0.5, 0.75, 0.9, 0.99])]
res["dfair_signed_mean_life>=5s"] = float(lv["dfair"].mean())
res["n_life>=5s"] = int(len(lv))
rng = np.random.default_rng(3)
sh = rng.integers(-1800, 1800, len(lv)) // 300 * 300  # same window position and life, other windows
g0, _ = fair_up(sp, lv["start"].to_numpy() + sh, lv["end"].to_numpy() + sh, lv["t0"].to_numpy() - 1 + sh)
g1, _ = fair_up(sp, lv["start"].to_numpy() + sh, lv["end"].to_numpy() + sh, lv["t1"].to_numpy() - 1 + sh)
res["dfair_abs_quantiles_random_same_life"] = [float(x) for x in np.quantile(np.abs(g1 - g0), [0.5, 0.75, 0.9, 0.99])]
# price vs fair at the last fill of long-resting orders (does it let the quote go stale?)
res["last_fill_fair_minus_price_median_life>=5s"] = float(np.median(np.where(lv["is_up"], f1[m["life"].to_numpy() >= 5], 1 - f1[m["life"].to_numpy() >= 5]) - lv["px"]))
res["first_fill_fair_minus_price_median_life>=5s"] = float(np.median(np.where(lv["is_up"], f0[m["life"].to_numpy() >= 5], 1 - f0[m["life"].to_numpy() >= 5]) - lv["px"]))
print(json.dumps(res, indent=1))
(HERE.parent / "results_iter2_orders.json").write_text(json.dumps(res, indent=1))

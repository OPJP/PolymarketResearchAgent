"""Iteration 12, X123 / X120 light: when did the deep-bid module step up? Lot calldata of the cluster's filled maker BUY
orders (b1_cluster_orders_*: limit, salt, block second, wallet). Deep = limit <= 0.10. STUDY (10-23..26) per hour and per
wallet, with each wallet's salt-counter resets (salt drops by > 50% between consecutive orders) as the restart log;
VALIDATE days only as daily aggregates. Also: the share of deep orders among orders placed in decided windows (|mid - 0.5| >
0.4 at the fill), from it12/typed_fills.parquet, per STUDY hour.
    python code12/deep_step.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"


def main():
    o = pd.concat([pd.read_parquet(C / f"b1_cluster_orders_{s}.parquet", columns=["salt", "w", "lim", "bts", "taker_amount"]).assign(sp=s)
                   for s in ("study", "valid")])
    o["salt_i"] = pd.to_numeric(o.salt, errors="coerce")
    o = o.drop_duplicates(["w", "salt"]).sort_values("bts")
    o["deep"] = o.lim <= 0.10 + 1e-9
    o["hour"] = (o.bts // 3600 * 3600).astype(int)
    res = {}
    S = o[o.sp == "study"]
    hourly = S.groupby("hour").agg(n=("deep", "size"), deep=("deep", "mean")).reset_index()
    hourly["t"] = pd.to_datetime(hourly.hour, unit="s").dt.strftime("%m-%d %H")
    res["study_hourly"] = {r.t: [int(r.n), round(float(r.deep), 3)] for r in hourly.itertuples()}
    resets = {}
    for w, g in o.groupby("w"):
        s_ = g.salt_i.to_numpy()
        t_ = g.bts.to_numpy()
        drop = np.nonzero(s_[1:] < 0.5 * s_[:-1])[0] + 1
        resets[w] = [str(pd.to_datetime(int(t_[i]), unit="s")) for i in drop if t_[i] < 1793059200]
    res["salt_resets_study"] = resets
    # first hour of STUDY with deep share >= 0.10 and n >= 20, per wallet
    first = {}
    for w, g in S.groupby("w"):
        h = g.groupby("hour").agg(n=("deep", "size"), deep=("deep", "mean"))
        hh = h[(h.n >= 20) & (h.deep >= 0.10)]
        first[w] = str(pd.to_datetime(int(hh.index.min()), unit="s")) if len(hh) else None
    res["first_hour_deep_ge_0.10_by_wallet"] = first
    daily = o.groupby(o.bts // 86400 * 86400).agg(n=("deep", "size"), deep=("deep", "mean"))
    res["daily_deep_share_orders"] = {str(pd.to_datetime(int(d), unit="s").date()): [int(r.n), round(float(r.deep), 4)] for d, r in daily.iterrows()}
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet", columns=["b", "sp", "mid_up", "lim", "oid", "first_b"])
    V = V[(V.b == V.first_b)].drop_duplicates("oid")
    V["dec"] = np.abs(V.mid_up - 0.5) > 0.4
    V["deep"] = V.lim <= 0.10 + 1e-9
    Vd = V[V.dec]
    dd = Vd.groupby(Vd.b // 86400 * 86400).agg(n=("deep", "size"), deep=("deep", "mean"))
    res["decided_window_orders_deep_share_daily"] = {str(pd.to_datetime(int(d), unit="s").date()): [int(r.n), round(float(r.deep), 4)] for d, r in dd.iterrows()}
    (HERE.parent / "results" / "iter12_deep_step.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "study_hourly"}, indent=1))
    hh = hourly[(hourly.hour >= 1793318400 - 4 * 86400 + 2 * 86400)]
    print(hh[["t", "n", "deep"]].to_string(index=False))


if __name__ == "__main__":
    main()

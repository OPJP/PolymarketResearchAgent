"""Iteration 16 (X160 step 2 / X159, a fills-based proxy of the hidden-occupancy census): if a GF- or XM-led first leg is the 2nd / 3rd
slot of a fan-out whose earlier legs lost their races (E1), the lost DS (GF) leg rests as a BUY at its own limit on the same outcome and
is sometimes hit as maker right away. Count, per first leg (rank 0) with a calldata limit L, maker-FIRST order hashes (maker fills only,
no taker fill) of each other wallet on the same (window, outcome) at price L - c (c = 0, 1, 2 cents) whose first maker fill block ts is
in [m0/1000 - 1, m0/1000 + 4]; compare by lead wallet. Placebo: the same count 30 s earlier. Usage: python hidden16.py DAYS"""
import os, sys, json
import numpy as np, pandas as pd
S = os.environ["RE16_SCRATCH"]
DAYS = sys.argv[1].split(",")
cols = ["tx", "role", "maker_amt", "taker_amt", "oside"]
cd = pd.concat([pd.read_parquet(f"{S}/it16/cdfull_{d}.parquet", columns=cols) for d in DAYS if os.path.exists(f"{S}/it16/cdfull_{d}.parquet")] +
               [pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=cols), pd.read_parquet(S + "/it15/cl_orders.parquet", columns=cols)])
cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
cd["L"] = np.round(100 * cd.maker_amt / cd.taker_amt).astype(int)
mp = pd.concat([pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m"]) for d in DAYS]); mp["tx"] = mp.tx.str.lower()
mp = mp.merge(cd[["tx", "L"]], on="tx")
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "m0", "rank", "start_ts"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
p = p[p.dd.isin(DAYS) & (p["rank"] == 0)].merge(mp[["cid", "wallet", "m", "L"]], on=["cid", "wallet", "m"], how="inner")
f = pd.read_parquet(".cache/re/btc5m-bot/fills.parquet", columns=["ts", "oh", "wallet", "role", "cid", "is_up", "price", "start_ts"])
f = f[f.start_ts.isin(p.start_ts.unique())]
th = set(f.oh[f.role == "T"])
mf = f[(f.role == "M") & ~f.oh.isin(th)].groupby("oh").agg(t1=("ts", "min"), cid=("cid", "first"), up=("is_up", "first"), w=("wallet", "first"), px=("price", "first")).reset_index()
mf["c"] = np.round(100 * mf.px).astype(int)
idx = {k: np.sort(g.t1.to_numpy()) for k, g in mf.groupby(["cid", "up", "w", "c"])}
res = {"first_legs": int(len(p)), "maker_first_hashes": int(len(mf)), "by_lead": {}}
for shift, tag in ((0.0, "at_m0"), (-30.0, "placebo_m0-30s")):
    out = {}
    for lead, g in p.groupby("wallet"):
        rec = {"n": int(len(g))}
        for w in ("DS", "GF", "XM"):
            if w == lead:
                continue
            for c in (0, 1, 2):
                hit = 0
                for r in g.itertuples():
                    a = idx.get((r.cid, bool(r.up), w, int(r.L) - c))
                    if a is None:
                        continue
                    t = r.m0 / 1000.0 + shift
                    i = np.searchsorted(a, t - 1.0); hit += int(i < len(a) and a[i] <= t + 4.0)
                rec[f"{w}@L-{c}"] = round(hit / len(g), 4)
        out[lead] = rec
    res["by_lead"][tag] = out
print(json.dumps(res, indent=0))
json.dump(res, open(f"research/reverse_engineering/btc5m-bot/results/hidden16_{'_'.join(DAYS)}.json", "w"), indent=1)

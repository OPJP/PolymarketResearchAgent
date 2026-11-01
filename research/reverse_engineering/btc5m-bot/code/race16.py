"""Iteration 16 (X161 step 2 input, X160): would the HIGHER-PRIORITY wallet's leg have lost its race? For every first leg (rank 0) of
10-20 with a calldata limit L, the depth of o's asks at or below the limit the higher-priority wallet would have used (DS pays +0 c,
GF / XM +1 c: DS's limit = L - 1 for a GF / XM leg priced on the same view) at m - x on the book clock (x = 50, 35: the post-hold book
the earlier slot met ~16-26 ms before), by lead wallet and visible occupancy. Under the priority dispatcher (E1) GF-led first legs with
DS visibly free have D(<= L - 1) == 0 (DS's leg lost) far more often than DS-led legs have D(<= L) == 0. Usage: python race16.py"""
import os, json
import numpy as np, pandas as pd
S = os.environ["RE16_SCRATCH"]
od = pd.read_parquet(S + "/it15/l2ordb_2026-10-20.parquet"); ov = np.load(S + "/it15/l2ordb_2026-10-20.npy", mmap_mode="r")
q = json.load(open(S + "/it15/l2ordb_2026-10-20_qoff.json")); ix = {x: i for i, x in enumerate(q)}
cd = pd.concat([pd.read_parquet(S + "/it16/cdfull_10-20.parquet", columns=["tx", "role", "maker_amt", "taker_amt", "oside"]),
                pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=["tx", "role", "maker_amt", "taker_amt", "oside"]),
                pd.read_parquet(S + "/it15/cl_orders.parquet", columns=["tx", "role", "maker_amt", "taker_amt", "oside"])])
cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
cd["L"] = np.round(100 * cd.maker_amt / cd.taker_amt).astype(int)
od["row"] = np.arange(len(od)); od["tx"] = od.tx.str.lower()
j = od.merge(cd[["tx", "L"]], on="tx")
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "m", "rank"])
j = j.merge(p, on=["cid", "wallet", "m"], how="inner")
# visible occupancy (matches in (m - 300, m)) from all operator taker orders
al = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["wallet", "m"])
for w in ("DS", "GF"):
    a = np.sort(al.m[al.wallet == w].to_numpy()); mv = j.m.to_numpy()
    j[f"busy_{w}"] = (np.searchsorted(a, mv, "left") - np.searchsorted(a, mv - 300, "right")) > 0
fl = j[j["rank"] == 0].copy(); r = fl.row.to_numpy()
def dle(v, L):
    cs = np.cumsum(v, 1); L = np.clip(L, 0, 100).astype(int); return cs[np.arange(len(L)), L]
res = {}
for x in (50, 35, 75, 100):
    v = np.asarray(ov[r, ix[x], :])
    fl[f"Dm1_{x}"] = dle(v, fl.L.to_numpy() - 1); fl[f"D0_{x}"] = dle(v, fl.L.to_numpy())
out = {}
for lead, g in fl.groupby("wallet"):
    for occ, gg in (("DS_free", g[~g.busy_DS]), ("DS_busy", g[g.busy_DS])):
        if not len(gg):
            continue
        out[f"{lead}|{occ}"] = {"n": int(len(gg))}
        for x in (100, 75, 50, 35):
            out[f"{lead}|{occ}"][f"P(D<=L-1 ==0)@m-{x}"] = round(float((gg[f"Dm1_{x}"] <= 0).mean()), 4)
            out[f"{lead}|{occ}"][f"P(D<=L ==0)@m-{x}"] = round(float((gg[f"D0_{x}"] <= 0).mean()), 4)
res["first_legs_10_20"] = out
print(json.dumps(res, indent=0))
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/race16.json", "w"), indent=1)

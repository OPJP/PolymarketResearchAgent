"""Iteration 16 (X156 step 1 on the complete record): the realized taker fill as an execution on the post-hold book, for EVERY operator
taker order of 10-20 (complete calldata: original size and limit L): r and within-10% share of fill vs min(orig, D(<= L) at m - x) for
the 16 offsets, per wallet and size class. Usage: python posthold16.py"""
import os, json
import numpy as np, pandas as pd
S = os.environ["RE16_SCRATCH"]
od = pd.read_parquet(S + "/it15/l2ordb_2026-10-20.parquet"); ov = np.load(S + "/it15/l2ordb_2026-10-20.npy", mmap_mode="r")
q = json.load(open(S + "/it15/l2ordb_2026-10-20_qoff.json")); ix = {x: i for i, x in enumerate(q)}
cd = pd.read_parquet(S + "/it16/cdfull_10-20.parquet", columns=["tx", "role", "maker_amt", "taker_amt", "oside", "fill_amt"])
for f in [".cache/re/btc5m-bot/calldata_sample.parquet", S + "/it15/cl_orders.parquet"]:
    cd = pd.concat([cd, pd.read_parquet(f, columns=["tx", "role", "maker_amt", "taker_amt", "oside", "fill_amt"])])
cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
cd["L"] = np.round(100 * cd.maker_amt / cd.taker_amt).astype(int); cd["orig"] = cd.taker_amt
od["row"] = np.arange(len(od)); od["tx"] = od.tx.str.lower()
j = od.merge(cd[["tx", "L", "orig"]], on="tx")
r = j.row.to_numpy()
def dle(v, L):
    cs = np.cumsum(v, 1); L = np.clip(L, 0, 100).astype(int); return cs[np.arange(len(L)), L]
res = {"n": int(len(j))}
for x in (180, 150, 100, 75, 50, 35, 20):
    j[f"D{x}"] = dle(np.asarray(ov[r, ix[x], :]), j.L.to_numpy())
    pr = np.minimum(j.orig, j[f"D{x}"])
    rec = {"r": round(float(np.corrcoef(pr, j.shares)[0, 1]), 4), "within10": round(float((np.abs(pr - j.shares) <= 0.1 * j.shares + 1e-9).mean()), 4)}
    for w in ("DS", "GF", "XM"):
        m = (j.wallet == w).to_numpy(); rec[w] = round(float(np.corrcoef(pr[m], j.shares[m])[0, 1]), 4)
    for cl, m in (("large", (j.orig >= 90).to_numpy()), ("small", (j.orig < 90).to_numpy())):
        rec[cl] = round(float(np.corrcoef(pr[m], j.shares[m])[0, 1]), 4)
    res[f"m-{x}"] = rec
res["orig_only_r"] = round(float(np.corrcoef(j.orig, j.shares)[0, 1]), 4)
res["share_filled_below_orig"] = round(float((j.shares < j.orig - 0.5).mean()), 4)
print(json.dumps(res, indent=0))
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/posthold16.json", "w"), indent=1)

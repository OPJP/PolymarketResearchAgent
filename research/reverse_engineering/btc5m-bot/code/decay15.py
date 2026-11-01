"""Iteration 15 (X143 / X144 'if false'): WHEN does the visible ask depth at or below the limit disappear? 10-20 operator taker orders,
ask vectors at m - x for x = 1..500 ms (l2ingest15b). Median and mean D<=L(m - x) for calldata depth-bound orders (filled < original),
fully filled calldata orders, and all orders (L = best ask at m - 180 + k_w); plus the share of the D(m - 180) - filled gap that is
gone by m - x. Usage: python -I decay15.py IT15_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd
D15, OUT = sys.argv[1], sys.argv[2]
day = "2026-10-20"
od = pd.read_parquet(f"{D15}/l2ordb_{day}.parquet"); ov = np.load(f"{D15}/l2ordb_{day}.npy"); qo = json.load(open(f"{D15}/l2ordb_{day}_qoff.json"))
o = pd.read_parquet(f"{D15}/depth15_orders.parquet")
o = o[(o.start_ts >= 1792454400) & (o.start_ts < 1792540800)]
od = od.reset_index().rename(columns={"index": "ri"}).merge(o[["cid", "wallet", "m", "orig", "Lcd", "Lpub", "b180"]], on=["cid", "wallet", "m"], how="inner")
L = np.where(od.Lcd.notna(), od.Lcd, od.Lpub).astype(int)
cs = np.cumsum(ov[od.ri.to_numpy()], 2)  # (n, nq, 101)
Dx = cs[np.arange(len(od))[:, None], np.arange(len(qo))[None, :], np.clip(L, 0, 100)[:, None]]
rep = {"offsets_ms": qo, "n": int(len(od))}
groups = {"calldata_depth_bound": (od.orig.notna() & (od.shares < od.orig - 1e-6)).to_numpy(),
          "calldata_full": (od.orig.notna() & (od.shares >= od.orig - 1e-6)).to_numpy(), "all": np.ones(len(od), bool)}
j180 = qo.index(180)
for g, sel in groups.items():
    d = Dx[sel]; fl = od.shares.to_numpy()[sel]
    gap = np.maximum(d[:, j180] - fl, 1e-9)
    gone = np.clip((d[:, j180][:, None] - d) / gap[:, None], -5, 5)
    rep[g] = {"n": int(sel.sum()), "median_filled": float(np.median(fl)),
              "median_D": {int(x): float(np.median(d[:, k])) for k, x in enumerate(qo)},
              "mean_D": {int(x): round(float(d[:, k].mean()), 1) for k, x in enumerate(qo)},
              "median_share_of_gap_gone": {int(x): round(float(np.median(gone[:, k])), 3) for k, x in enumerate(qo)}}
json.dump(rep, open(OUT, "w"), indent=1)
for g in groups:
    print(g, rep[g]["n"], "filled", rep[g]["median_filled"])
    print("  median D", rep[g]["median_D"])
    print("  gap gone", rep[g]["median_share_of_gap_gone"])

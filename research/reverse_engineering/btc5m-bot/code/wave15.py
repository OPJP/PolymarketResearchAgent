"""Iteration 15 (finding 4 follow-up): is there a maker cancellation wave on the bought outcome's asks around the operator's decisions, and
when does it start? First legs of 10-20..22 (dcfit14_pred rank 0). From the l2ingest15 50-ms grid: o's ask depth at best + 0..4 c (c4)
and o's best ask at server times m0 - x, x = 0, 50, ..., 1500 ms, against a placebo anchor m0 - 5000 - x, and the other outcome's.
Reported: median of c4(t) / c4(m0 - 1500) by x (operator vs placebo), and the share of first legs with a depth drop >= 30% over
[m0 - x - 100, m0 - x]. Usage: python -I wave15.py IT15_DIR IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd
D15, D14, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DAYS = ["2026-10-20", "2026-10-21", "2026-10-22"]
p = pd.read_parquet(f"{D14}/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m0", "rank", "start_ts"])
p = p[(p.start_ts >= 1792454400) & (p["rank"] == 0)].reset_index(drop=True)
GR = {}
for day in DAYS:
    tk = pd.read_parquet(f"{D15}/l2tok_{day}.parquet"); gd = pd.read_parquet(f"{D15}/l2grid_{day}.parquet", columns=["c4", "best"])
    n = len(tk); ng = len(gd) // n
    c4 = gd.c4.to_numpy().reshape(n, ng); bb = gd.best.to_numpy().reshape(n, ng)
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
    for i, r in enumerate(tk.itertuples()):
        if d0 <= int(r.start_ts) < d0 + 86400:
            GR[(r.cid, int(r.is_up))] = (int(r.start_ts), c4[i], bb[i])
    del gd
XS = list(range(0, 1550, 50))
rep = {"n_first_legs": int(len(p))}
for side, flip in (("o", False), ("x", True)):
    for anc, off in (("op", 0), ("placebo", 5000)):
        M = np.full((len(p), len(XS)), np.nan); Bk = np.full((len(p), len(XS)), np.nan)
        for cid, g in p.groupby("cid"):
            for upv in (0, 1):
                gg = g[g.up.astype(int) == upv]
                if not len(gg):
                    continue
                key = (cid, (1 - upv) if flip else upv)
                if key not in GR:
                    continue
                st, c4, bb = GR[key]
                for j, x in enumerate(XS):
                    t = gg.m0.to_numpy() - off - x
                    k = (t - (st * 1000 - 60000)) // 50
                    ok = (k >= 0) & (k < len(c4)); kk = np.clip(k, 0, len(c4) - 1)
                    v = c4[kk].astype(float); v[~ok] = np.nan; M[gg.index.to_numpy(), j] = v
                    b = bb[kk].astype(float); b[~ok] = np.nan; Bk[gg.index.to_numpy(), j] = b
        ref = M[:, -1]
        rel = M / np.where(ref > 0, ref, np.nan)[:, None]
        drop = (M[:, :-2] - M[:, 2:]) / np.where(M[:, 2:] > 0, M[:, 2:], np.nan)  # change over 100 ms ending at m0 - x
        rep[f"{side}_{anc}"] = {"median_rel_depth": {int(x): round(float(np.nanmedian(rel[:, j])), 3) for j, x in enumerate(XS) if x % 100 == 0},
                                "share_drop30_100ms": {int(XS[j]): round(float(np.nanmean(drop[:, j] <= -0.3)), 4) for j in range(len(XS) - 2) if XS[j] % 100 == 0},
                                "mean_best_change_vs_1500": {int(x): round(float(np.nanmean(Bk[:, j] - Bk[:, -1])), 3) for j, x in enumerate(XS) if x % 250 == 0}}
json.dump(rep, open(OUT, "w"), indent=1)
for k, v in rep.items():
    if isinstance(v, dict):
        print(k, "rel", v["median_rel_depth"]); print("   drop30", v["share_drop30_100ms"]); print("   best", v["mean_best_change_vs_1500"])

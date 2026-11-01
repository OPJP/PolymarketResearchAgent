"""P2(a) (panel X12): is the cluster filled when a bid hit clears the level? STUDY (2026-10-23..26) case by case.

Population: data-api taker prints in BTC 5m windows [start, end) that hit a bid on side s (taker SELL s at p -> level p;
taker BUY of the complement at p' -> level 1 - p'), excluding the cluster's own taker prints. Label: the print's
transaction holds a cluster maker BUY fill on s. "Cleared" (descriptive, uses the next print): the next bid hit on s
in the same window (within 30 s) is at a lower level (by >= 0.005); "held": at the same or a higher level.
Stratified by level bucket (0.1) x time bucket (60 s) x size bucket; compared with the same statistic for the
prints in transactions with any other maker... (all prints are maker fills, so the contrast is cluster vs base).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache" / "re" / "directional-maker"
OUT = ROOT / "research" / "reverse_engineering" / "directional-maker" / "results"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
DAYS = [1792713600, 1792800000, 1792886400, 1792972800]

f = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh", "token_id", "ts", "side", "role", "price", "shares"])
f = f[(f.role == "maker") & (f.side == "BUY") & (f.ts < 1793059200)]
mk = set(zip(f.txh.str.lower(), f.token_id.astype(str)))
w = pd.read_parquet(C / "exam" / "windows_5m.parquet")
w = w[(w.start_ts >= DAYS[0]) & (w.start_ts < DAYS[-1] + 86400)]
active = set(pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["cid", "ts", "role"]).query("role=='maker' and ts<1793059200").cid)
wd = w.set_index("cid")
rows = []
for d in DAYS:
    t = pd.read_parquet(C / "exam" / f"taker5m_day_{d}.parquet")
    t = t[t.cid.isin(active) & ~t.wallet.isin(CL)]
    t["k"] = np.arange(len(t))
    for cid, g in t.groupby("cid", sort=False):
        wi = wd.loc[cid]
        g = g[(g.ts >= wi.start_ts) & (g.ts < wi.end_ts)].sort_values(["ts", "k"], kind="stable")
        if len(g) < 3:
            continue
        is_up = g.asset.to_numpy() == wi.up_token
        buy = g.side.astype(str).to_numpy() == "BUY"
        pr = g.price.to_numpy().astype(float)
        # side whose bid is hit, and the level on that side
        s_up = (is_up & ~buy) | (~is_up & buy)
        lvl = np.where(is_up & ~buy, pr, np.where(~is_up & buy, 1 - pr, np.where(is_up & buy, 1 - pr, pr)))
        tok_s = np.where(s_up, wi.up_token, wi.down_token)
        txs = g.tx.str.lower().to_numpy()
        lab = np.array([(x, y) in mk for x, y in zip(txs, tok_s)])
        ts = g.ts.to_numpy()
        sz = g["size"].to_numpy().astype(float)
        for side in (True, False):
            idx = np.where(s_up == side)[0]
            if len(idx) < 2:
                continue
            nxt_l = np.r_[lvl[idx[1:]], np.nan]
            nxt_t = np.r_[ts[idx[1:]], np.nan]
            ok = (nxt_t - ts[idx]) <= 30
            cleared = np.where(ok, nxt_l < lvl[idx] - 0.005, np.nan)
            # point-in-time: hits on the same level so far, volume absorbed at this level so far
            same = np.zeros(len(idx))
            vol_lvl = np.zeros(len(idx))
            for j in range(1, len(idx)):
                if abs(lvl[idx[j]] - lvl[idx[j - 1]]) < 0.005:
                    same[j] = same[j - 1] + 1
                    vol_lvl[j] = vol_lvl[j - 1] + sz[idx[j - 1]]
            for j, i in enumerate(idx):
                rows.append((cid, ts[i] - wi.start_ts, lvl[i], sz[i], lab[i], cleared[j], same[j], vol_lvl[j]))
df = pd.DataFrame(rows, columns=["cid", "rel", "lvl", "size", "lab", "cleared", "same", "vol_lvl"])
df = df[df.cleared.notna()]
df["cleared"] = df.cleared.astype(bool)
df["pb"] = (df.lvl * 10).clip(0, 9.99).astype(int)
df["tb"] = (df.rel // 60).clip(0, 4).astype(int)
df["zb"] = pd.cut(df["size"], [0, 10, 50, 200, 1e9], labels=False)
res = {"n": int(len(df)), "base_rate": float(df.lab.mean()), "cleared_share": float(df.cleared.mean())}
res["p_lab_cleared"] = float(df[df.cleared].lab.mean())
res["p_lab_held"] = float(df[~df.cleared].lab.mean())
res["share_of_cluster_prints_cleared"] = float(df[df.lab].cleared.mean())
# stratified ratio (Mantel-Haenszel style): sum over strata of expected vs observed
g = df.groupby(["pb", "tb", "zb", "cleared"]).lab.agg(["sum", "size"]).unstack("cleared").fillna(0)
g.columns = [f"{a}_{b}" for a, b in g.columns]
num = (g["sum_True"] * g["size_False"] / (g["size_True"] + g["size_False"])).sum()
den = (g["sum_False"] * g["size_True"] / (g["size_True"] + g["size_False"])).sum()
res["mh_rate_ratio_cleared_vs_held"] = float(num / den)
by_z = df.groupby(["zb", "cleared"]).lab.mean().unstack().round(4)
res["by_size_bucket"] = {str(k): v for k, v in by_z.to_dict("index").items()}
# point-in-time proxy: does volume already absorbed at the level predict the cluster (and clearing)?
df["vb"] = pd.cut(df.vol_lvl, [-1, 0, 50, 200, 1000, 1e9], labels=False)
res["by_vol_absorbed_at_level"] = {str(k): {"p_lab": float(v.lab.mean()), "p_cleared": float(v.cleared.mean()), "n": int(len(v))}
                                   for k, v in df.groupby("vb")}
print(json.dumps(res, indent=1))
(OUT / "iter5_clear.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

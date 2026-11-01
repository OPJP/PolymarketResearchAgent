"""Iteration 18 prep: build and cache the operator taker frame of 10-20..22 with the true size state S/E and the SIBLING public
large-print state Spub/Epub/Tpub (W4/W5, filled>=60, usable block_ts+2s, shared txs excluded). Split-independent; cached to it18/.
Usage: python -I sib18_prep.py"""
import os, time
import numpy as np, pandas as pd

S = os.environ["RE16_SCRATCH"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = ROOT + "/.cache/re/btc5m-bot"
OUT = S + r"/it18"; os.makedirs(OUT, exist_ok=True)
DAYS = ["10-20", "10-21", "10-22"]
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
t0 = time.time()

cols = ["tx", "role", "taker_amt", "oside"]
cds = [pd.read_parquet(C + "/calldata_sample.parquet", columns=cols), pd.read_parquet(S + r"/it15/cl_orders.parquet", columns=cols)]
for d in DAYS:
    cds.append(pd.read_parquet(f"{S}/it16/cdfull_{d}.parquet", columns=cols))
cd = pd.concat(cds); cd = cd[(cd.role == "T") & (cd.oside == 0)].copy(); cd["tx"] = cd.tx.str.lower(); cd = cd.drop_duplicates("tx")
mp = pd.concat([pd.read_parquet(f"{S}/it15/l2ord_2026-{d}.parquet", columns=["tx", "cid", "wallet", "m"]) for d in DAYS])
mp["tx"] = mp.tx.str.lower(); mp = mp.merge(cd[["tx", "taker_amt"]], on="tx", how="left").drop_duplicates(["cid", "wallet", "m"])
p = pd.read_parquet(S + r"/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "osz", "start_ts", "p_dc14_spot_own"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
p = p[p.dd.isin(DAYS)].merge(mp[["cid", "wallet", "m", "taker_amt"]], on=["cid", "wallet", "m"], how="left")
p = p[p.taker_amt.notna()].copy(); p["orig"] = p.taker_amt
p["L"] = (p.orig >= 90).astype(int)
p["sg"] = np.where(p.up == 1, 1, -1); p["sh"] = np.where(p.p_dc14_spot_own > 0.5, 1, -1)
p = p.sort_values(["start_ts", "m"]).reset_index(drop=True)
q = p.sort_values(["cid", "up", "m"]); gap = q.m - q.groupby(["cid", "up"]).m.shift(); p.loc[q.index, "gap"] = gap
p["slot"] = np.where(p.gap < 150, 2, np.where(p.gap < 400, 1, 0))
p["tb"] = np.digitize(p.m / 1000.0 - p.start_ts, [30, 60, 120])
print("operator orders", len(p), p.groupby("dd").size().to_dict(), "t", round(time.time() - t0, 1), flush=True)

def true_state(g):
    mm = g.m.to_numpy(); L = g.L.to_numpy(); sg = g.sg.to_numpy(); oz = g.orig.to_numpy()
    Sv = np.zeros(len(g), int); Ev = np.zeros(len(g)); s_cur, e_cur = 0, 0.0; j = 0
    for k in range(len(g)):
        while j < k and mm[j] < mm[k]:
            if L[j]:
                if sg[j] != s_cur:
                    s_cur, e_cur = sg[j], 0.0
                e_cur += oz[j]
            j += 1
        Sv[k], Ev[k] = s_cur, e_cur
    return Sv, Ev
p["S"] = 0; p["E"] = 0.0
for st, g in p.groupby("start_ts", sort=False):
    Sv, Ev = true_state(g); p.loc[g.index, "S"] = Sv; p.loc[g.index, "E"] = Ev

# W4/W5 public large prints (lean tape loop)
clus_tx = set(pd.read_parquet(C + "/fills.parquet", columns=["tx"]).tx.str.lower())
cid2st = p.drop_duplicates("cid").set_index("cid").start_ts.to_dict()
pub = {}; nfiles = 0; npr = 0
for i, cc in enumerate(p.cid.unique()):
    fn = f"{S}/it16/tapes/{cc}.parquet"
    if not os.path.exists(fn):
        continue
    nfiles += 1
    t = pd.read_parquet(fn, columns=["proxyWallet", "side", "size", "timestamp", "outcome", "transactionHash"])
    w = t.proxyWallet.str.lower()
    m = (t.side.to_numpy() == "BUY") & (t["size"].to_numpy() >= 60) & w.isin(W45).to_numpy()
    if not m.any():
        continue
    t = t[m]
    keep = np.array([h.lower() not in clus_tx for h in t.transactionHash.to_numpy()], bool)  # set membership O(1); subset is tiny
    t = t[keep]
    if not len(t):
        continue
    sgn = np.where(t.outcome.to_numpy() == "Up", 1, -1)
    tu = (t.timestamp.to_numpy().astype(np.int64) + 2) * 1000
    o = np.argsort(tu, kind="stable")
    pub[cid2st[cc]] = (tu[o], sgn[o], t["size"].to_numpy()[o].astype(float)); npr += len(t)
    if nfiles % 300 == 0:
        print("  tapes", nfiles, "prints", npr, "t", round(time.time() - t0, 1), flush=True)
print("tapes read", nfiles, "W4/W5 large prints", npr, "t", round(time.time() - t0, 1), flush=True)

Spub = np.zeros(len(p), int); Epub = np.zeros(len(p)); Tpub = np.full(len(p), -1, np.int64)
for st, g in p.groupby("start_ts", sort=False):
    arr = pub.get(st)
    if arr is None:
        continue
    tu, sgn, sz = arr
    runS = np.zeros(len(tu), int); runE = np.zeros(len(tu)); s_c, e_c = 0, 0.0
    for i in range(len(tu)):
        if sgn[i] != s_c:
            s_c, e_c = sgn[i], 0.0
        e_c += sz[i]; runS[i] = s_c; runE[i] = e_c
    mm = g.m.to_numpy(np.int64); j = np.searchsorted(tu, mm, "left") - 1; ok = j >= 0; idx = g.index.to_numpy()
    Spub[idx[ok]] = runS[j[ok]]; Epub[idx[ok]] = runE[j[ok]]; Tpub[idx[ok]] = tu[j[ok]]
p["Spub"] = Spub; p["Epub"] = Epub; p["Tpub"] = Tpub
p.to_parquet(OUT + "/sib_frame.parquet")
cov = float((p.Tpub >= 0).mean())
print("saved frame", len(p), "pub coverage(all)", round(cov, 3), "t", round(time.time() - t0, 1), flush=True)

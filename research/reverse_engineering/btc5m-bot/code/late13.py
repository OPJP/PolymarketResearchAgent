"""Iteration 13 (B3b / A1 lead; X124 counterpart for the window END): what drives the side of the LATE decisions (rel >= 180 s),
where the decision-clock tick model falls to 62-72%? On the dcside13 frame (10-20 / 10-21 operator taker orders with archive
match ms; a = m - 180 ms): agreement of the order's outcome with (i) the favourite by spot (archive spot mid at a vs the Gamma
priceToBeat), (ii) the favourite by Chainlink RTDS (server clock <= a), (iii) the partial settlement TWAP (mean RTDS price from
the window's 240th second to a, for rel >= 240), (iv) the underdog by ask, (v) the complement of the operator's realized net
(own state, block ts <= a - 2 s), (vi) the tick model. Usage: python late13.py FRAME_TAG ARCHIVE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
tag, A = sys.argv[1], sys.argv[2]
X = pd.read_parquet(f"{C}/it13/dcside13_frame{tag}.parquet")
win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
ptb = pd.read_parquet(f"{C}/ptb.parquet").set_index("start").priceToBeat.astype(float)
st = win.loc[X.cid, "start_ts"].to_numpy(np.int64)
a = ((X.rel.to_numpy() + st) * 1000).astype(np.int64)
k = ptb.reindex(st).to_numpy(float)
def at(T, V, tt):
    i = np.searchsorted(T, tt, "right") - 1
    o = V[np.clip(i, 0, len(V) - 1)].astype(float); o[i < 0] = np.nan
    return o
sp = np.full(len(X), np.nan); clp = np.full(len(X), np.nan); tw = np.full(len(X), np.nan)
for day in sorted(X.day.unique()):
    m = (X.day == day).to_numpy()
    b = pd.read_parquet(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "askPrice"])
    b = b[b.type == "book"].sort_values("receivedTimestampMs", kind="stable")
    sp[m] = at(b.receivedTimestampMs.to_numpy(np.int64), ((b.bidPrice + b.askPrice) / 2).to_numpy(float), a[m]); del b
    r = pd.read_parquet(f"{A}/btcrtds_{day}.parquet", columns=["timestampMs", "serverTimestampMs", "fullAccuracyValue"]).sort_values("serverTimestampMs")
    T = r.serverTimestampMs.to_numpy(np.int64); V = r.fullAccuracyValue.astype(float).to_numpy() / 1e18; ts = r.timestampMs.to_numpy(np.int64)
    clp[m] = at(T, V, a[m])
    cs = np.r_[0, np.cumsum(V)]
    idx = np.where(m)[0]
    for i in idx:
        if X.rel.iat[i] >= 240:
            lo = np.searchsorted(ts, (st[i] + 240) * 1000, "left"); hi = np.searchsorted(T, a[i], "right")  # observed by a (server clock)
            if hi > lo:
                tw[i] = (cs[hi] - cs[lo]) / (hi - lo)
fl = pd.read_parquet(f"{C}/fills.parquet", columns=["cid", "rel", "is_up", "shares"])
fl = fl[fl.cid.isin(set(X.cid))]; fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
g = {c: (d.sort_values("rel").rel.to_numpy(float), np.cumsum(d.sort_values("rel").sg.to_numpy(float))) for c, d in fl.groupby("cid")}
net = np.zeros(len(X))
for i, (c, rl) in enumerate(zip(X.cid.to_numpy(), X.rel.to_numpy())):
    if c in g:
        T_, cs_ = g[c]; j = np.searchsorted(T_, rl - 2, "right") - 1
        net[i] = cs_[j] if j >= 0 else 0.0
y = X.up.to_numpy() == 1
sig = {"fav_spot": np.sign(sp - k), "fav_chainlink": np.sign(clp - k), "twap_part_fav": np.sign(tw - k), "underdog": np.where(X.askU_0 < 0.5, 1, -1) * np.isfinite(X.askU_0),
       "complement_of_net": -np.sign(net), "bs_mic_250": np.sign(X.bs_mic_250.to_numpy())}
res = {}
rel = X.rel.to_numpy()
for nm, v in sig.items():
    o = {}
    for a0, b0 in ((0, 60), (60, 180), (180, 240), (240, 270), (270, 300)):
        mm = (rel >= a0) & (rel < b0) & np.isfinite(v) & (v != 0)
        o[f"{a0}-{b0}"] = [round(float(((v[mm] > 0) == y[mm]).mean()), 4) if mm.any() else None, int(mm.sum())]
    res[nm] = o
# strike distance late: is the late side the favourite when the TWAP is far from the strike?
for a0, b0 in ((240, 300),):
    mm = (rel >= a0) & (rel < b0) & np.isfinite(tw)
    d = np.abs(tw - k)[mm]; q = np.nanquantile(d, [0.5])
    for nm, s2 in (("near", d <= q[0]), ("far", d > q[0])):
        v = np.sign(tw - k)[mm][s2]
        res[f"twap_part_fav_{nm}_strike_240_300"] = round(float(((v > 0) == y[mm][s2]).mean()), 4)
json.dump(res, open(f"{R}/late13{tag}.json", "w"), indent=1)
print(json.dumps(res))

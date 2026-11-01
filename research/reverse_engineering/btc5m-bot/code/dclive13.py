"""Iteration 13: OUT-OF-TIME check of the frozen exam-route decision-clock side model (model_it13_dcside_spot.txt, fitted on VALIDATE
10-17..19) on the 2,155 live operator decisions of the 10-31 12-18 development block (it11/large_dec.parquet: arrival a = match
- 150 ms, side, wallet). Binance spot BTCUSDT bookTicker from rec_exam7's btc5m_xven ('bs', laptop receive clock t) put on the
capture's European receive clock: t - median(t - E) of the USD-M 'bf' records + the capture's spot transit (131 ms). Features at
a - 30 ms (= match - 180) exactly as dc_exam13. Read through tools/live.py iter_live (development blocks only)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
import live_lab as L
import dc_exam13 as de
C = L.C
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
d = pd.read_parquet(f"{C}/it11/large_dec.parquet")
a0, a1 = int(d.a.min() // 1000) - 10, int(d.a.max() // 1000) + 5
bs, off = [], []
for r in L.recs("btc5m_xven", a0, a1):
    if r.get("y") != "BTC" or not r.get("b") or not r.get("a"):
        continue
    if r.get("v") == "bs":
        bs.append((r["t"], r["b"], r.get("B") or 0.0, r["a"], r.get("A") or 0.0))
    elif r.get("v") == "bf" and r.get("E"):
        off.append(r["t"] - r["E"])
x = np.array(bs, float); x = x[np.argsort(x[:, 0], kind="stable")]
lag = float(np.median(off)) if off else 0.0
T = (x[:, 0] - lag + 131.0).astype(np.int64)
mic = (x[:, 1] * x[:, 4] + x[:, 3] * x[:, 2]) / np.maximum(x[:, 2] + x[:, 4], 1e-12)
mid = (x[:, 1] + x[:, 3]) / 2
a = (d.a.to_numpy(np.int64) - 30)
X = pd.DataFrame({"rel": a / 1000.0 - d.st.to_numpy(float)})
for nm, S in (("mic", mic), ("mid", mid)):
    x0 = de._at(T, S, a)
    for K in de.KS:
        X[f"bs_{nm}_{K}"] = ((x0 / de._at(T, S, a - K) - 1) * 1e4).astype(np.float32)
m = lgb.Booster(model_file=de.MODEL)
p = m.predict(X[m.feature_name()])
y = d.up.to_numpy(bool); ok = (p > 0.5) == y
res = {"decisions": int(len(d)), "bs_records": int(len(x)), "laptop_lag_bf_ms": round(lag, 1), "accuracy": round(float(ok.mean()), 4),
       "by_wallet": {w: [round(float(ok[d.w.to_numpy() == w].mean()), 4), int((d.w == w).sum())] for w in ("DS", "GF", "XM")},
       "large": round(float(ok[d.large.to_numpy(bool)].mean()), 4), "small": round(float(ok[~d.large.to_numpy(bool)].mean()), 4)}
rel = X.rel.to_numpy()
res["by_rel"] = {f"{lo}-{hi}": [round(float(ok[(rel >= lo) & (rel < hi)].mean()), 4), int(((rel >= lo) & (rel < hi)).sum())] for lo, hi in ((0, 120), (120, 180), (180, 300))}
g = pd.DataFrame({"st": d.st, "w": d.w, "up": y.astype(int), "p": p})
xm = g[g.w == "XM"].groupby("st").agg(up=("up", "mean"), p=("p", "mean"))
o = xm[(xm.up == 0) | (xm.up == 1)]
res["XM_windows"] = int(len(xm)); res["XM_one_sided"] = int(len(o))
res["XM_one_sided_window_acc"] = round(float(((o.p > 0.5).astype(int) == o.up.astype(int)).mean()), 4) if len(o) else None
json.dump(res, open(os.path.join(R, "dclive13.json"), "w"), indent=1)
print(json.dumps(res))

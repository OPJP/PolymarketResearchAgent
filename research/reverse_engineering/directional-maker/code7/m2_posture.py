"""Iteration 7 (mechanics M2, X50 pilot, on the publish clock): after each Chainlink publish, does the cluster put an
exact-500 bid at the Up touch or at the Down touch within 200 ms, and does the Chainlink edge (Chainlink fair - mid)
decide which? BTC 15m windows of 10-31 17:29-18:00 UTC (development; the cluster was off BTC 5m then).

Per publish P_S and current 15m window: Chainlink fair_up = Phi(ln(CL_S / K) / (sigma sqrt(tau))) with K = Gamma
priceToBeat, sigma = 1.4 x the realised 1-s futures vol of the last 300 s, tau = time left (+ 20 s); mid = Up touch mid
at P; labels: an exact-500 add at the Up best bid (side 1, p == bb) / at the Down best bid (side 0, p == ba) within
[P, P + 200 ms].
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(ROOT))
from rawread import iter_dm  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
a, b = int(sys.argv[1]), int(sys.argv[2])
MKT = sys.argv[3] if len(sys.argv) > 3 else "15m"
DUR = 900 if MKT == "15m" else 300
STAMP_MODE = len(sys.argv) > 4 and sys.argv[4] == "stamp"  # no publish ms: label window [S+700, S+1500] ms
if not STAMP_MODE:
    rt = pd.DataFrame([(int(r["ts"]) // 1000, int(r["P"]), float(r["v"])) for r in iter_dm("dy_rtds", a - 30, b + 5)
                       if r.get("k") == "u" and r.get("sy") == "btc" and r.get("tp") == "cl" and r.get("P")],
                      columns=["S", "P", "v"]).drop_duplicates("S").sort_values("S")
else:
    cl = {}
    for r in iter_dm("dm_rtds", a - 60, b + 60):
        if r.get("q") != "crypto_prices_chainlink":
            continue
        try:
            jj = json.loads(r["m"])
        except ValueError:
            continue
        for x in (jj.get("payload") or {}).get("data", []) or []:
            cl[int(x["timestamp"]) // 1000] = float(x["value"])
    rt = pd.DataFrame([(S, S * 1000 + 700, v) for S, v in sorted(cl.items())], columns=["S", "P", "v"])
FROM = int(sys.argv[5]) if len(sys.argv) > 5 else a
rt = rt[(rt.P >= FROM * 1000) & (rt.P < b * 1000 - 500)]
fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 400, b) if r["r"][0] == "b" and r["r"][2]]
fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s")
fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
msec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
r1 = np.diff(np.log(msec), prepend=np.log(msec[0]))
ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d", "bb", "ba"])
ev = ev[ev.w.str.startswith(f"btc-updown-{MKT}")]
tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
tch = tch[tch.w.str.startswith(f"btc-updown-{MKT}")].sort_values("s")
starts = sorted({int(w.rsplit("-", 1)[1]) for w in ev.w.unique()})
raw = fetch_windows([f"btc-updown-{MKT}-{s}" for s in starts])
K = {}
for m in raw.values():
    st = int(str(m.get("slug")).rsplit("-", 1)[1])
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None:
            K[st] = float(v)
e5 = ev[ev.d == 500]
at_up = e5[(e5.side == 1) & ((e5.p - e5.bb).abs() < 1e-6)]
at_dn = e5[(e5.side == 0) & ((e5.p - e5.ba).abs() < 1e-6)]
A_up = {w: np.sort(g.s.to_numpy(np.int64)) for w, g in at_up.groupby("w")}
A_dn = {w: np.sort(g.s.to_numpy(np.int64)) for w, g in at_dn.groupby("w")}
T = {w: (g.s.to_numpy(np.int64), g.bb.to_numpy(), g.ba.to_numpy()) for w, g in tch.groupby("w")}
xx = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
xx = xx[xx.w.str.startswith(f"btc-updown-{MKT}")].sort_values("s").drop_duplicates("h")
dd = xx.d.astype(str).str.upper().str[0]
xx["s_up"] = (((xx.ai == 0) & (dd == "S")) | ((xx.ai == 1) & (dd == "B"))).astype(int)
X = {w: (g.s.to_numpy(np.int64), g.s_up.to_numpy()) for w, g in xx.groupby("w")}
rows = []
for S, P, v in zip(rt.S, rt.P, rt.v):
    st = (P // 1000) // DUR * DUR
    w = f"btc-updown-{MKT}-{st}"
    if st not in K or w not in T:
        continue
    ts_, bb_, ba_ = T[w]
    i = np.searchsorted(ts_, P, side="right") - 1
    if i < 0:
        continue
    bb, ba = bb_[i], ba_[i]
    if not (0.03 < bb < ba < 0.97):
        continue
    j = np.searchsorted(sec, P // 1000)
    sig = np.std(r1[max(j - 300, 0):j]) * 1.4 if j > 30 else np.nan
    tau = max(st + DUR - P / 1000, 1.0) + 20
    fair = norm.cdf(np.log(v / K[st]) / (sig * np.sqrt(tau))) if sig == sig and sig > 0 else np.nan
    mid = (bb + ba) / 2

    def lab(D):
        arr = D.get(w)
        if arr is None:
            return 0
        k = np.searchsorted(arr, P, side="left")
        return int(k < len(arr) and arr[k] <= P + (800 if STAMP_MODE else 200))
    i2 = np.searchsorted(ts_, P - 2000, side="right") - 1
    dmid = mid - ((bb_[i2] + ba_[i2]) / 2 if i2 >= 0 else mid)
    xs = X.get(w)
    last_sold_up = np.nan
    if xs is not None:
        k2 = np.searchsorted(xs[0], P, side="left") - 1
        if k2 >= 0 and P - xs[0][k2] < 5000:
            last_sold_up = xs[1][k2]
    k0, k1 = np.searchsorted(sec, st - 60), np.searchsorted(sec, st)
    Kf = msec[k0:k1].mean() if k1 > k0 else np.nan
    fP = fm[np.clip(np.searchsorted(fs, P, side="right") - 1, 0, None)]
    ffair = norm.cdf(np.log(fP / Kf) / (sig * np.sqrt(tau))) if (Kf == Kf and sig == sig and sig > 0) else np.nan
    rows.append({"P": P, "w": w, "left": st + DUR - P / 1000, "e": fair - mid, "up": lab(A_up), "dn": lab(A_dn), "mid": mid,
                 "dmid": dmid, "last_sold_up": last_sold_up, "ef": ffair - mid})
D = pd.DataFrame(rows).dropna(subset=["e"])
D["de"] = D.groupby("w").e.diff()
out = {"publishes": int(len(D)), "p_up_post": float(D.up.mean()), "p_dn_post": float(D.dn.mean()),
       "auc_up_by_e": float(roc_auc_score(D.up, D.e)) if 0 < D.up.sum() < len(D) else None,
       "auc_dn_by_minus_e": float(roc_auc_score(D.dn, -D.e)) if 0 < D.dn.sum() < len(D) else None}
Dd = D.dropna(subset=["de"])
out["auc_up_by_de"] = float(roc_auc_score(Dd.up, Dd.de)) if 0 < Dd.up.sum() < len(Dd) else None
out["auc_dn_by_minus_de"] = float(roc_auc_score(Dd.dn, -Dd.de)) if 0 < Dd.dn.sum() < len(Dd) else None
D["q"] = pd.qcut(D.e, 5, labels=False, duplicates="drop")
out["by_e_quintile"] = {str(int(k)): {"e_med": round(float(g.e.median()), 3), "p_up": round(float(g.up.mean()), 3),
                                      "p_dn": round(float(g.dn.mean()), 3), "n": int(len(g))} for k, g in D.groupby("q")}
one = D[(D.up + D.dn) == 1]
out["side_when_one"] = {"n": int(len(one)), "acc_sign_e": float(((one.e > 0) == (one.up == 1)).mean()) if len(one) else None,
                        "always_up": float(one.up.mean()) if len(one) else None,
                        "acc_sign_futures_edge": float(((one.ef > 0) == (one.up == 1)).mean()) if len(one) else None,
                        "acc_sign_mid_move_2s": float(((one.dmid > 0) == (one.up == 1))[one.dmid != 0].mean()) if (one.dmid != 0).any() else None,
                        "n_mid_moved": int((one.dmid != 0).sum()),
                        "acc_last_sold_token": float((one.last_sold_up == one.up)[one.last_sold_up.notna()].mean()) if one.last_sold_up.notna().any() else None,
                        "n_last_sold": int(one.last_sold_up.notna().sum()),
                        "acc_mid_below_half_up": float(((one.mid < 0.5) == (one.up == 1)).mean()) if len(one) else None}
(ROOT / "research/reverse_engineering/directional-maker/results" / f"iter7_m2_posture_{MKT}{'_stamp' if STAMP_MODE else ''}_{FROM}_{b}.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

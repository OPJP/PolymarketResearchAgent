"""H1 backtests on TEST (all parameters from FIT only).

A) matched rule: buy every taker print whose FIT-fitted wallet-likeness score exceeds the FIT max-MCC threshold.
B) profit-tuned contrarian taker: buy side X at an observed taker print when X's implied price fell by >= x over the
   last k seconds (tape up to t-2 s), within a price band; (k, x, band) chosen on FIT by per-window HAC t.
Fills: min(print size, $25) at the print price; taker fee = rate*p*(1-p) per share; resolution only for settlement.
"""
import sys, json, itertools
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from common import *
from polyrea.analysis.updown import decision_metrics, auc

d, G = load()
Pf, Pt = base_frame(d, "fit"), base_frame(d, "test")
Df, Dt = dyn_frame(G, "fit", Pf), dyn_frame(G, "test", Pt)
for P, D in ((Pf, Df), (Pt, Dt)):
    for c in D.columns:
        P[c] = D[c].to_numpy()
Sf, St = static_frame(Pf), static_frame(Pt)
okf = Df[DYN].notna().all(axis=1).to_numpy(); okt = Dt[DYN].notna().all(axis=1).to_numpy()
out = {"A_matched_rule": {}, "B_contrarian": {}}
for name, wal in W.items():
    yf = (Pf.wallet == wal).to_numpy().astype(int)
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(pd.concat([Sf, Df[DYN]], axis=1)[okf], yf[okf])
    sf = np.full(len(Pf), np.nan); sf[okf] = m.predict_proba(pd.concat([Sf, Df[DYN]], axis=1)[okf])[:, 1]
    st = np.full(len(Pt), np.nan); st[okt] = m.predict_proba(pd.concat([St, Dt[DYN]], axis=1)[okt])[:, 1]
    grid = np.nanquantile(sf, np.linspace(0.5, 0.995, 60))
    th = max(grid, key=lambda x: (lambda v: v if np.isfinite(v) else -1)(decision_metrics(np.nan_to_num(sf, nan=-1), yf, x)["mcc"]))
    out["A_matched_rule"][name] = {"theta": float(th), "fit": taker_bt(Pf, pd.Series(sf > th, index=Pf.index)), "test": taker_bt(Pt, pd.Series(st > th, index=Pt.index)),
                                    "test_excluding_cluster_prints": taker_bt(Pt, pd.Series(st > th, index=Pt.index), exclude_cluster=True)}
    print("A", name, json.dumps(out["A_matched_rule"][name], default=float), flush=True)

# B: contrarian grid on FIT
best, scan = None, []
for k, x, band in itertools.product((5, 20, 60), (0.03, 0.05, 0.08, 0.12, 0.2), ((0.05, 0.95), (0.2, 0.8), (0.3, 0.7), (0.5, 0.95), (0.05, 0.5))):
    sel = (Pf[f"dside_{k}"] <= -x) & (Pf.price >= band[0]) & (Pf.price <= band[1])
    r = taker_bt(Pf, sel)
    if r["trades"] < 500:
        continue
    scan.append({"k": k, "x": x, "band": band, **{kk: r[kk] for kk in ("trades", "windows", "pnl", "ret", "per_window_t")}})
    if best is None or r["per_window_t"] > best[1]["per_window_t"]:
        best = ((k, x, band), r)
(k, x, band), rfit = best
sel_t = (Pt[f"dside_{k}"] <= -x) & (Pt.price >= band[0]) & (Pt.price <= band[1])
out["B_contrarian"] = {"chosen": {"k": k, "x": x, "band": band}, "fit": rfit, "test": taker_bt(Pt, sel_t), "test_excluding_cluster_prints": taker_bt(Pt, sel_t, exclude_cluster=True),
                       "fit_scan_top10": sorted(scan, key=lambda r: -r["per_window_t"])[:10], "fit_scan_n": len(scan),
                       "fit_scan_share_positive": float(np.mean([r["pnl"] > 0 for r in scan]))}
# latency degradation of B on TEST: decide with tape up to t-gap-L (feature recomputed at larger gap)
deg = {}
for L in (1, 3, 5, 10):
    cols = {f"dside_{k}": np.full(len(Pt), np.nan)}
    for cid, idx in Pt.groupby("condition_id").indices.items():
        f = G["test"].feats(cid, Pt.ts.to_numpy()[idx], Pt.is_up.to_numpy()[idx], gap=2 + L)
        cols[f"dside_{k}"][idx] = f[f"dside_{k}"]
    s = (pd.Series(cols[f"dside_{k}"]) <= -x) & (Pt.price >= band[0]) & (Pt.price <= band[1])
    r = taker_bt(Pt, s)
    deg[str(2 + L)] = {kk: r.get(kk) for kk in ("trades", "pnl", "ret", "per_window_p")}
out["B_contrarian"]["latency_degradation_gap_s"] = deg
print("B", json.dumps({kk: v for kk, v in out["B_contrarian"].items() if kk != "fit_scan_top10"}, default=float), flush=True)
json.dump(out, open("h1_backtest.json", "w"), indent=1, default=float)

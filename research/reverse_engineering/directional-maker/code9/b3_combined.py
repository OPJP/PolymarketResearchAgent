"""Iteration 9 (X85 B3): a posture with own-history inertia on the taker-event unit (10-31 12-18 side_D, events = same-window
same-side fills within 100 ms collapsed): predict the previous event's side when |edge| <= theta (and a previous event
exists), else the posture sign. theta chosen on 12:00-15:00, scored on 15:00-18:00, frozen and slow sigma. Own state
(previous own fill side): reported separately from the public posture. Development, descriptive."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker/it9"
D = pd.read_parquet(C / "side_D_1793448000_1793469600.parquet")
sp = pd.read_parquet(C / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
b0 = int(sp.sec.iloc[0]); px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan); px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
px = pd.Series(px).ffill().to_numpy(); rr = np.r_[0.0, np.diff(np.log(px))]; cs = np.r_[0.0, np.cumsum(rr * rr)]
D = D.sort_values(["T", "wallet"]).reset_index(drop=True)
i = D["T"].to_numpy() // 1000 - 1 - b0
tau = np.maximum(D.en.to_numpy() - D["T"].to_numpy() / 1000, 1.0); x = np.log(D.cl.to_numpy(float) / D.K.to_numpy(float)); m = D.mid_up.to_numpy()
E6 = norm.cdf(x / (1.4 * np.sqrt((cs[i + 1] - cs[i + 1 - 300]) / 300) * np.sqrt(tau))) - m
ES = norm.cdf(x / (np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600) * np.sqrt(tau))) - m
y = D.is_up.to_numpy() == 1; Ts = D["T"].to_numpy(); key = (D.st.astype(str) + "_" + D.en.astype(str)).to_numpy()
ev, last, prev = [], {}, {}
for j in range(len(D)):
    k = key[j]
    if k in last and Ts[j] - last[k][0] <= 100 and y[j] == last[k][1]:
        continue
    ev.append((j, prev.get(k)))
    last[k] = (Ts[j], y[j]); prev[k] = y[j]
idx = np.array([e[0] for e in ev]); pv = np.array([np.nan if e[1] is None else float(e[1]) for e in ev])
yy = y[idx]; fit = Ts[idx] < 1793458800 * 1000
out = {"events": int(len(idx)), "prev_baseline_all_events_with_prev": float(np.mean((pv[np.isfinite(pv)] == 1) == yy[np.isfinite(pv)]))}
for nm, E in (("frozen", E6[idx]), ("slow", ES[idx])):
    res = {}
    for th in (0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2):
        pred = np.where(np.isfinite(pv) & (np.abs(E) <= th), pv == 1, E > 0)
        res[th] = (float(np.mean((pred == yy)[fit])), float(np.mean((pred == yy)[~fit])))
    th_best = max(res, key=lambda t: res[t][0])
    prevb = np.where(np.isfinite(pv), pv == 1, E > 0)
    out[nm] = {"grid_fit_test": {str(k): [round(a, 3), round(b, 3)] for k, (a, b) in res.items()}, "theta_chosen_on_fit": th_best,
               "test_acc_chosen": round(res[th_best][1], 3), "test_posture_only": round(res[0.0][1], 3),
               "test_prev_baseline_(posture_if_first)": round(float(np.mean((prevb == yy)[~fit])), 3)}
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_b3_combined.json").write_text(json.dumps(out, indent=1))

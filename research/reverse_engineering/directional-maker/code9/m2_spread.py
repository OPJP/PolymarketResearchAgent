"""Iteration 9 (mechanics M2 = X80): is the ladder's half-spread a spread on the digital's risk? Per second of 10-31
14:06-16:30 with cluster-class top rungs on both outcomes of the current BTC 5m and 15m windows (iteration 8
it6/m1inv: center F = (top Up 500 bid + lowest Up-ask 500)/2, half-spread h = (ask - bid)/2, market mid). Regress h on
the risk terms of the digital: phi(z)/sqrt(tau) (the fair's sensitivity per unit move) and p(1-p), with z from the
Chainlink report stamped t - 1.432 s and sigma frozen (1.4 x v300 futures, the table's sig) or slow (v3600 spot), plus
tau and the market spread proxy |F - mid|. OLS fitted on t < 15:00, R^2 and within-a-tick accuracy of the predicted top
Up rung (mid_5m + 0.2 (fair - mid) - h_hat) scored on t >= 15:00, against the 21% anchor of iteration 6 and touch - 1."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
SPLIT = 1793458800


def main():
    D = pd.read_parquet(C / "it6" / "m1inv_1793455600_1793464202.parquet")
    sp = pd.read_parquet(C / "it9" / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    k = D.t.to_numpy() - 1 - b0
    v3600 = np.sqrt((cs[k + 1] - cs[k + 1 - 3600]) / 3600)
    out = {"seconds": int(len(D))}
    for fam in ("5", "15"):
        tau = D[f"tau{fam}"].to_numpy().astype(float)
        x = np.log(D.cl1432.to_numpy() / D[f"K{fam}"].to_numpy())
        mid = D[f"mid{fam}"].to_numpy()
        h = D[f"h{fam}"].to_numpy()
        F = D[f"F{fam}"].to_numpy()
        res = {}
        for nm, sg in (("frozen", D.sig.to_numpy()), ("slow", v3600)):
            z = x / (sg * np.sqrt(tau))
            p = norm.cdf(z)
            X = np.column_stack([np.ones(len(D)), norm.pdf(z) / np.sqrt(tau) * 100, p * (1 - p), mid * (1 - mid), tau / 300, np.abs(F - mid)])
            tr = D.t.to_numpy() < SPLIT
            ok = np.all(np.isfinite(X), axis=1) & np.isfinite(h)
            beta = np.linalg.lstsq(X[tr & ok], h[tr & ok], rcond=None)[0]
            pred = X @ beta
            te = ~tr & ok
            r2 = 1 - np.var(h[te] - pred[te]) / np.var(h[te])
            r2_tr = 1 - np.var(h[tr & ok] - pred[tr & ok]) / np.var(h[tr & ok])
            q_obs = F - h  # top Up 500 bid
            q_hat = mid + 0.2 * (p - mid) - pred
            within = np.abs(np.round(q_hat, 2) - np.round(q_obs, 2)) <= 0.0101
            within_anchor = np.abs(np.round(mid - np.median(mid[tr] - q_obs[tr]), 2) - np.round(q_obs, 2)) <= 0.0101
            res[nm] = {"r2_train": round(float(r2_tr), 3), "r2_test": round(float(r2), 3), "beta": [round(float(b_), 4) for b_ in beta],
                       "top_rung_within_tick_test": round(float(within[te].mean()), 3),
                       "anchor_mid_minus_median_offset_within_tick_test": round(float(within_anchor[te].mean()), 3),
                       "corr_h_p1p": round(float(np.corrcoef(h[ok], (p * (1 - p))[ok])[0, 1]), 3),
                       "corr_h_phi": round(float(np.corrcoef(h[ok], (norm.pdf(z) / np.sqrt(tau))[ok])[0, 1]), 3)}
        res["h_sd"] = round(float(np.nanstd(h)), 4)
        out[f"btc{fam}m"] = res
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_m2_spread.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

"""X138 / X76: per-wallet Chainlink stamp lag from the tracer re-signs (within-order Spearman of the re-sign price with
the Chainlink digital at stamp floor((s - L) / 1000), k 1.4), L = 0..3000 ms; bootstrap over orders for the peak."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm, spearmanr
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
import cl_source
from tracer_laws import spot
R = pd.read_parquet(ROOT / ".cache/re/directional-maker/it13/tracer_features.parquet")
R = R[R.side_ok & R.K.notna()].copy()
lags = list(range(0, 3001, 250))
clv = cl_source.cl_values(sorted(set(int(x) for L in lags for x in ((R.s - L) // 1000))), allow_sealed=False, fetch=False)
sp = spot(int(R.s.min() // 1000) - 7200, int(R.s.max() // 1000) + 5)
s300 = sp.sigma((R.s // 1000).to_numpy(), look=300)
up = (R.is_up == 1).to_numpy()
for L in lags:
    cl = ((R.s - L) // 1000).map(clv).to_numpy(float)
    fu = norm.cdf(np.log(cl / R.K.to_numpy(float)) / (1.4 * s300 * np.sqrt(R.tau.to_numpy())))
    R[f"F{L}"] = np.where(up, fu, 1 - fu)
def rho(g, L):
    yy = g.p_own - g.groupby("order").p_own.transform("mean"); ff = g[f"F{L}"] - g.groupby("order")[f"F{L}"].transform("mean")
    ok = np.isfinite(ff)
    return spearmanr(yy[ok], ff[ok]).correlation if ok.sum() > 10 else np.nan
out = {}
rng = np.random.default_rng(1)
for wname, g in list(R.groupby("wallet")) + [("pooled", R)]:
    prof = {L: round(float(rho(g, L)), 3) for L in lags}
    peaks = []
    ords = g.order.unique()
    for _ in range(200):
        pick = rng.choice(ords, len(ords), replace=True)
        gb = pd.concat([g[g.order == o].assign(order=f"{o}_{i}") for i, o in enumerate(pick)])
        pr = {L: rho(gb, L) for L in lags}
        peaks.append(max(pr, key=lambda k: -1 if not np.isfinite(pr[k]) else pr[k]))
    out[wname] = {"n_events": int(len(g)), "orders": int(len(ords)), "profile": prof, "peak": max(prof, key=prof.get),
                  "peak_boot_q": np.percentile(peaks, [10, 50, 90]).tolist()}
print(json.dumps(out, indent=1))
(HERE.parent / "results/iter13_tracer_lag_wallet.json").write_text(json.dumps(out, indent=1))

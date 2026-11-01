"""X135 step 2: scan the engine's Chainlink stamp lag L and vol multiplier k on the tracer re-sign prices (FIT half
chooses; TEST half scores). Law (a): min(F_own(L, k) - h, ask - 0.01). Also the Spearman correlation of the re-sign
price with F_own(L, k) inside each order (de-meaned per order), which does not depend on h."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm, spearmanr
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
import cl_source
from tracer_laws import spot, snap, score, cap
OUT = ROOT / ".cache/re/directional-maker/it13"
R = pd.read_parquet(OUT / "tracer_features.parquet")
R = R[R.side_ok & R.bid_ex.notna() & R.ask.notna() & R.K.notna()].copy()
orders = R.groupby("order").fill_ms.first().sort_values()
R["fit"] = R.order.isin(set(orders.index[: len(orders) // 2]))
lags = list(range(-1000, 4001, 250))
stamps = sorted(set(int(x) for L in lags for x in ((R.s - L) // 1000)))
clv = cl_source.cl_values(stamps, allow_sealed=False, fetch=True, max_requests=600)
sp = spot(int(R.s.min() // 1000) - 7200, int(R.s.max() // 1000) + 5)
tsec = (R.s // 1000).to_numpy()
s300 = sp.sigma(tsec, look=300)
up = (R.is_up == 1).to_numpy()
tau = R.tau.to_numpy(); K = R.K.to_numpy(float)
y = R.p_own.to_numpy(); fit = R.fit.to_numpy()
res = []
for L in lags:
    cl = ((R.s - L) // 1000).map(clv).to_numpy(float)
    for k in (0.7, 1.0, 1.4, 2.0, 3.0, 5.0, 8.0):
        fu = norm.cdf(np.log(cl / K) / (k * s300 * np.sqrt(tau)))
        fo = np.where(up, fu, 1 - fu)
        X = R.assign(F_own=fo)
        best = None
        for h in np.arange(-0.10, 0.40, 0.005):
            sc = score(cap(X.F_own[fit] - h, X.ask[fit]), y[fit])["within_tick"]
            if best is None or sc > best[1]:
                best = (h, sc)
        te = score(cap(X.F_own[~fit] - best[0], X.ask[~fit]), y[~fit])
        dm = X.assign(py=y).groupby("order")
        yy = (X.p_own - dm.p_own.transform("mean")).to_numpy(); ff = (X.F_own - dm.F_own.transform("mean")).to_numpy()
        ok = np.isfinite(ff)
        rho = spearmanr(yy[ok], ff[ok]).correlation if ok.sum() > 10 else np.nan
        res.append(dict(L=L, k=k, h=round(float(best[0]), 3), fit_wt=round(best[1], 3), test_wt=round(te["within_tick"], 3), test_mae=round(te["mae"], 4), rho_within_order=round(float(rho), 3), cov=round(float(ok.mean()), 3)))
D = pd.DataFrame(res)
print(D.sort_values("rho_within_order", ascending=False).head(12).to_string(index=False))
print(D[D.k == 1.4].to_string(index=False))
(HERE.parent / "results/iter13_tracer_lag_scan.json").write_text(D.to_json(orient="records"))

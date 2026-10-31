"""Decision metrics of the maker-side spot-timing score (static + sside) at the FIT max-MCC threshold, plus coefficients."""
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from common import *
from polyrea.analysis.updown import auc, decision_metrics
SP = ["sside_2", "sside_10", "sside_30"]
d, G = load()
def mframe(per):
    P = d[per]["maker_prints"]; P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True).copy(); P["rel"] = P.ts - P.start_ts; return P
Pf, Pt = mframe("fit"), mframe("test")
Df, Dt = dyn_frame(G, "fit", Pf), dyn_frame(G, "test", Pt)
okf = Df[SP].notna().all(axis=1).to_numpy(); okt = Dt[SP].notna().all(axis=1).to_numpy()
Xf = pd.concat([static_frame(Pf), Df[SP]], axis=1)[okf]; Xt = pd.concat([static_frame(Pt), Dt[SP]], axis=1)[okt]
out = {}
for n, w in W.items():
    yf = (Pf.wallet == w).to_numpy().astype(int)[okf]; yt = (Pt.wallet == w).to_numpy().astype(int)[okt]
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)).fit(Xf, yf)
    sf, st = m.predict_proba(Xf)[:, 1], m.predict_proba(Xt)[:, 1]
    grid = np.quantile(sf, np.linspace(0.5, 0.995, 60))
    th = max(grid, key=lambda x: (lambda v: v if np.isfinite(v) else -1)(decision_metrics(sf, yf, x)["mcc"]))
    out[n] = {"coef_std": dict(zip(Xf.columns, np.round(m[-1].coef_[0], 3).tolist())), "test_auc": auc(st, yt), "decision": decision_metrics(st, yt, th),
              "univariate_test_auc": {c: auc(Dt[c].to_numpy()[okt], yt) for c in SP}}
    print(n, json.dumps(out[n], default=float), flush=True)
json.dump(out, open("h2_spot_decision.json", "w"), indent=1, default=float)

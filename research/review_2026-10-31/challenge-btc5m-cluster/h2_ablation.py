"""Which features carry the passive-fill (maker) association? TEST AUC gain over static-only, per feature group."""
import numpy as np, pandas as pd, json
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from common import *
from polyrea.analysis.updown import auc
d, G = load()
def mframe(per):
    P = d[per]["maker_prints"]; P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True).copy(); P["rel"] = P.ts - P.start_ts; return P
Pf, Pt = mframe("fit"), mframe("test")
Df, Dt = dyn_frame(G, "fit", Pf), dyn_frame(G, "test", Pt)
Df["dev"] = Df.up_last_side - Pf.price.to_numpy(); Dt["dev"] = Dt.up_last_side - Pt.price.to_numpy()
Sf, St = static_frame(Pf), static_frame(Pt)
okf = Df.notna().all(axis=1).to_numpy(); okt = Dt.notna().all(axis=1).to_numpy()
groups = {"static": [], "spot_only": ["sside_2", "sside_10", "sside_30"], "tape_only": ["dside_5", "dside_20", "dside_60", "fx_5", "fx_20", "fx_60"], "dev_only": ["dev"], "all_but_dev": DYN, "all": DYN + ["dev"]}
out = {}
for n, w in W.items():
    yf = (Pf.wallet == w).to_numpy().astype(int)[okf]; yt = (Pt.wallet == w).to_numpy().astype(int)[okt]
    r = {}
    for g, cols in groups.items():
        Xf = pd.concat([Sf, Df[cols]], axis=1)[okf] if cols else Sf[okf]; Xt = pd.concat([St, Dt[cols]], axis=1)[okt] if cols else St[okt]
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)).fit(Xf, yf)
        r[g] = round(auc(m.predict_proba(Xt)[:, 1], yt), 4)
    out[n] = r; print(n, r, flush=True)
json.dump(out, open("h2_ablation.json", "w"), indent=1)

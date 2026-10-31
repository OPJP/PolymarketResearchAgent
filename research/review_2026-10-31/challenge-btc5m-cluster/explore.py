import pickle, json, sys
import pandas as pd, numpy as np
d = pickle.load(open('data.pkl', 'rb'))
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
CL = set(W.values())
for per in ("fit", "test"):
    t = d[per]
    p = t["prints"]; m = t["maker_prints"]
    print("=====", per, "taker buys", len(p), "passive buys", len(m))
    for k, w in W.items():
        pw = p[p.wallet == w]; mw = m[m.wallet == w]
        rel = pw.ts - pw.start_ts
        relm = mw.ts - mw.start_ts
        print(k, "taker", len(pw), "maker", len(mw), "taker usd", round((pw.size*pw.price).sum()), "maker usd", round((mw.size*mw.price).sum()),
              "| taker rel-start q", np.percentile(rel, [1, 10, 50, 90, 99]).round(0) if len(pw) else None,
              "| maker rel q", np.percentile(relm, [1, 10, 50, 90, 99]).round(0) if len(mw) else None,
              "| share pre-window taker", round(float((rel < 0).mean()), 3), "maker", round(float((relm < 0).mean()), 3))
    # cluster total share
    print("cluster share taker buys", round(float(p.wallet.isin(CL).mean()), 4), "passive", round(float(m.wallet.isin(CL).mean()), 4))
    # top wallets by taker buys
    top = p.groupby("wallet").agg(n=("ts", "size"), usd=("size", lambda s: 0)).sort_values("n", ascending=False).head(12)
    print(top.n.to_dict())
    topm = m.groupby("wallet").size().sort_values(ascending=False).head(12)
    print("top passive", topm.to_dict())

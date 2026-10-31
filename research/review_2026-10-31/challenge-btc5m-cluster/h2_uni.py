import numpy as np, pandas as pd, json
from common import *
from polyrea.analysis.updown import auc
d, G = load()
P = d["test"]["maker_prints"]; P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True)
D = dyn_frame(G, "test", P); D["dev"] = D.up_last_side - P.price.to_numpy()
out = {}
for n, w in W.items():
    y = (P.wallet == w).to_numpy().astype(int)
    r = {c: round(auc(D[c].to_numpy(), y), 3) for c in ["dev"] + DYN}
    dv_w = D.dev[y == 1]; dv_o = D.dev[y == 0]
    r["dev_quantiles_wallet"] = np.nanpercentile(dv_w, [10, 25, 50, 75, 90]).round(3).tolist()
    r["dev_quantiles_others"] = np.nanpercentile(dv_o, [10, 25, 50, 75, 90]).round(3).tolist()
    r["share_dev_within_1c_wallet"] = round(float((dv_w.abs() <= 0.01).mean()), 3); r["share_dev_within_1c_others"] = round(float((dv_o.abs() <= 0.01).mean()), 3)
    out[n] = r
print(json.dumps(out, indent=1))
json.dump(out, open("h2_uni.json", "w"), indent=1)

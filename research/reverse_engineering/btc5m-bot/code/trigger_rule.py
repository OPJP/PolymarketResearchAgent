"""Iteration 3 (late): distil the side / presence models into one explicit trigger rule and measure it on VALIDATE.
Rule T(x): at second s, BUY outcome o (at its ask) when the largest 2-s move among the six reference series
(Binance futures, OKX swap, Bybit perp, Binance spot, Bybit spot, OKX spot; trades with T < (s-1)*1000 ms) is
>= x bp toward o (C6_mx2000 oriented to o) and o's last implied ask is in [0.12, 0.88].
Side: on one-sided seconds with |C6_mx2000| >= x, side = sign(C6_mx2000). Presence: cells flagged by T(x)."""
import os, sys, glob, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
from scipy import stats
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
parts = []
for d0 in range(V0, V1, 86400):
    c = pd.read_parquet(f"{C}/cells/{d0}.parquet", columns=["cid", "rel", "is_up", "y", "yT", "ask_o"])
    v = pd.read_parquet(f"{C}/cells_ven2/{d0}.parquet", columns=["C6_mx2000"])
    c["mx"] = v.C6_mx2000.to_numpy(); parts.append(c)
D = pd.concat(parts, ignore_index=True)
res = {"cells": int(len(D)), "base_rate_y": round(float(D.y.mean()), 4)}
ok_ask = D.ask_o.between(0.12, 0.88).to_numpy()
pres = {}
for x in (0.3, 0.5, 1.0, 2.0):
    f = (D.mx.to_numpy() >= x) & ok_ask; y = D.y.to_numpy() == 1
    k, n = int(y[f].sum()), int(f.sum())
    pres[str(x)] = {"flag_share": round(float(f.mean()), 4), "recall": round(float(f[y].mean()), 4), "precision": round(float(y[f].mean()), 4),
                    "lift": round(float(y[f].mean() / y.mean()), 3), "p_value": float(stats.binomtest(k, n, y.mean(), alternative="greater").pvalue)}
res["presence_trigger"] = pres
# side on one-sided seconds (pair Up / Down rows: Up rows first in every day file)
side = {}
ups, dns = [], []
for d0 in range(V0, V1, 86400):
    c = D[D.cid.isin(set())]  # placeholder to keep memory flat
n_all = []
for d0 in range(V0, V1, 86400):
    c = pd.read_parquet(f"{C}/cells/{d0}.parquet", columns=["y", "yT"]); v = pd.read_parquet(f"{C}/cells_ven2/{d0}.parquet", columns=["C6_mx2000"])
    n = len(c) // 2
    one = (c.y.to_numpy()[:n] + c.y.to_numpy()[n:]) == 1
    n_all.append(pd.DataFrame({"truth_up": c.y.to_numpy()[:n][one] == 1, "mx": v.C6_mx2000.to_numpy()[:n][one]}))
S = pd.concat(n_all, ignore_index=True)
for x in (0.0, 0.1, 0.3, 0.5, 1.0, 2.0):
    m = np.abs(S.mx.to_numpy()) >= max(x, 1e-9)
    side[str(x)] = {"coverage": round(float(m.mean()), 4), "accuracy": round(float(((S.mx.to_numpy()[m] > 0) == S.truth_up.to_numpy()[m]).mean()), 4)}
res["side_trigger_sign_C6_mx2000"] = side
res["n_one_sided_seconds"] = int(len(S))
json.dump(res, open(f"{R}/results_trigger_rule_iter3.json", "w"), indent=1)
print(json.dumps(res))

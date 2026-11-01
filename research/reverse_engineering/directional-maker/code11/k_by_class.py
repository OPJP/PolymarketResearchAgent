"""Iteration 11 (side of the off-session ladder vs the weekly k cycle; exploratory): per rung class (calldata original size:
500 x 2^k / 62 / 250 / other) and per half-week regime (low-k days: Thu-Sun of weeks 1-2 = 10-22..25; high-k days:
10-26..30), the per-fill posture accuracy over the k grid with the real Chainlink value (T_hat - 1,432 ms) and the region-D
accuracy (sigma-free). VALIDATE days only as aggregates.
    python code11/k_by_class.py
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE))
import cl_source  # noqa: E402
from side_inblock import that  # noqa: E402
C = ROOT / ".cache/re/directional-maker"
NAME = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
        "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
KS = (0.35, 0.5, 0.7, 0.85, 1.0, 1.4, 2.0, 2.5)
ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
clv = cl_source._cache()
rows = []
for sp, fn, on in (("study", "b1_takers_study", "b1_cluster_orders_study"), ("validate", "b1_takers_valid", "b1_cluster_orders_valid")):
    v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "token", "b", "st", "en", "is_up", "mid_up", "v300"])
    t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
    t["tx"] = t.tx.str.lower()
    t = t.drop_duplicates("tx").set_index("tx")
    v["txh"] = v.txh.str.lower()
    v["T_hat"] = that(v.txh.map(t.sign_ms), v.b.astype(float) * 1000)
    v["cl"] = ((v.T_hat - 1432) // 1000).astype(np.int64).map(lambda s: clv.get(int(s), np.nan))
    v["K"] = v.st.map(K)
    v["tau"] = np.maximum(v.en - v.T_hat / 1000.0, 1.0)
    ob = pd.read_parquet(C / f"{on}.parquet", columns=["tx", "w", "token_id", "taker_amount", "oside", "role"])
    ob = ob[(ob.role == "maker") & (ob.oside == 0)].copy()
    ob["key"] = ob.tx.str.lower() + "|" + ob.w.astype(str) + "|" + ob.token_id.astype(str)
    om = ob.drop_duplicates("key").set_index("key").taker_amount / 1e6
    v["key"] = v.txh + "|" + v.wallet.astype(str).str.lower().map(lambda a: NAME.get(a, a)) + "|" + v.token.astype(str)
    v["orig"] = v.key.map(om).round(2)
    rows.append(v.dropna(subset=["cl", "K", "mid_up", "orig"]))
D = pd.concat(rows)
D["cls"] = np.where(D.orig.isin([500, 1000, 2000]), "500", np.where(D.orig == 62, "62", np.where(D.orig == 250, "250", "other")))
D["date"] = pd.to_datetime(D.b, unit="s").dt.strftime("%m-%d")
D["regime"] = np.where(D.date <= "10-25", "low_k_10-23..25", np.where(D.date == "10-26", "monday_10-26", "high_k_10-27..30"))
x = np.log(D.cl / D.K).to_numpy()
y = D.is_up.to_numpy() == 1
m = D.mid_up.to_numpy()
for k in KS:
    f = norm.cdf(x / (k * D.v300.to_numpy() * np.sqrt(D.tau.to_numpy())))
    D[f"a{k}"] = ((f > m) == y).astype(float)
Dm = (x != 0) & (np.abs(m - 0.5) > 0) & ((x > 0) != (m > 0.5))
D["regD"] = Dm
D["accD"] = ((x > 0) == y).astype(float)
out = {}
for (rg, c), g in D.groupby(["regime", "cls"]):
    acc = {k: round(float(g[f"a{k}"].mean()), 3) for k in KS}
    kb = max(acc, key=acc.get)
    gd = g[g.regD]
    out[f"{rg}|{c}"] = {"n": int(len(g)), "best_k": kb, "acc_best": acc[kb], "acc_k0.5": acc[0.5], "acc_k1.4": acc[1.4], "acc_k2.0": acc[2.0],
                        "regionD_n": int(len(gd)), "regionD_acc": round(float(gd.accD.mean()), 3) if len(gd) else None}
    print(rg, c, out[f"{rg}|{c}"])
(HERE.parent / "results" / "iter11_k_by_class.json").write_text(json.dumps(out, indent=1))

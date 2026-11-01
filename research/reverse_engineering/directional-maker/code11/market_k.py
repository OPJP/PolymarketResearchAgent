"""Iteration 11 (X111 / X75): does the engine's sigma step follow the MARKET's implied volatility? Per 6-h block of the lot,
the market-implied multiplier k_m = median over clean BTC 5m prints of sigma_imp / v300, with sigma_imp from the print's
Up price as a digital (Binance S at t - 1, Binance TWAP-60 strike, tau = end - t; prints with 0.15 < p < 0.85, |z| > 0.3,
|ln S/K| > 1e-4 and matching signs), next to the cluster's best posture k per block (code11/k_by_day.py). Aggregates only.
    python code11/market_k.py
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as RP  # noqa: E402
C = RP.C
base, px = RP.load_spot()
v3 = RP.rv(px, 300)
W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
F = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh"])
cl_tx = set(F.txh.str.lower())
for n in ("bosona", "almach", "momoney"):
    cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
rows = []
for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
    T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "asset", "price", "tx"])
    T = T[~T.tx.str.lower().isin(cl_tx) & T.cid.isin(W.index)]
    st = T.cid.map(W.start_ts).to_numpy().astype(np.int64)
    en = T.cid.map(W.end_ts).to_numpy().astype(np.int64)
    up = T.cid.map(W.up_token.astype(str)).to_numpy()
    ts = T.ts.to_numpy().astype(np.int64)
    pu = np.where(T.asset.astype(str).to_numpy() == up, T.price.to_numpy(float), 1 - T.price.to_numpy(float))
    ok = (ts > st) & (ts < en - 5) & (pu > 0.15) & (pu < 0.85)
    st, en, ts, pu = st[ok], en[ok], ts[ok], pu[ok]
    K = np.array([px[s - 60 - base:s - base].mean() for s in st])
    S = px[ts - 1 - base]
    lr = np.log(S / K)
    z = norm.ppf(pu)
    good = (np.abs(z) > 0.3) & (np.abs(lr) > 1e-4) & (np.sign(lr) == np.sign(z))
    sig = lr[good] / (z[good] * np.sqrt(en[good] - ts[good]))
    km = sig / v3[ts[good] - 1 - base]
    rows.append(pd.DataFrame({"blk": ts[good] // 21600 * 21600, "km": km, "sig": sig}))
D = pd.concat(rows)
D = D[np.isfinite(D.km) & (D.km > 0)]
kb = json.loads((HERE.parent / "results" / "iter11_k_by_day.json").read_text())["by_block"]
out = {}
for b, g in D.groupby("blk"):
    lab = pd.to_datetime(b, unit="s").strftime("%m-%d %H")
    out[lab] = {"n": int(len(g)), "market_k_median": round(float(g.km.median()), 3), "market_sigma_median_e5": round(float(g.sig.median() * 1e5), 3),
                "cluster_best_k": kb.get(lab, {}).get("best_k")}
xs = [(v["market_k_median"], v["cluster_best_k"]) for v in out.values() if v["cluster_best_k"] is not None]
a = np.array(xs, float)
res = {"by_block": out, "spearman_market_k_vs_cluster_k": round(float(pd.Series(a[:, 0]).corr(pd.Series(a[:, 1]), method="spearman")), 3), "blocks": int(len(a))}
for k, v in out.items():
    print(k, v)
print("spearman", res["spearman_market_k_vs_cluster_k"], res["blocks"])
(HERE.parent / "results" / "iter11_market_k.json").write_text(json.dumps(res, indent=1))

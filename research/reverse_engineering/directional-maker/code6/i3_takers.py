"""Iteration 6, panel iter5 information I3 (X28) first look: what the takers who fill the cluster act on.
All-match calldata of 10-31 15:20-15:40 UTC (code6/q2_identity.py): each taker order's signing ms (client clock) vs
the Binance futures bookTicker mid (server ms): 'futures-triggered' if the mid moved >= $5 over the 300 ms before the
signature (and >= $3 over 300 ms as a looser class); also the Chainlink fair-futures fair gap at the match for the
cluster's fills. Shares for cluster-filled matches vs other matches; cluster fill PnL by class (RTDS TWAP settlement).
    python code6/i3_takers.py <x_a> <x_b> <s0> <s1>"""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm
C = ROOT / ".cache/re/directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
a, b, s0, s1 = map(int, sys.argv[1:5])
cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / f"allmatch{s0}_*.parquet"))])
cd["maker"] = cd.maker.str.lower(); cd["tx"] = cd.tx.str.lower()
cl_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(CL), "tx"])
tk = cd[cd.role == "taker"].drop_duplicates("tx")
tk = tk[~tk.maker.isin(CL)]
fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", s0 - 60, s1 + 60) if r["r"][0] == "b" and r["r"][2]]
fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
def mid(t):
    i = np.searchsorted(fs, t, side="right") - 1
    return fm[i] if i >= 0 else np.nan
x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
ms = x.groupby("h").s.min()
tk = tk.assign(sign=pd.to_numeric(tk.sign_ms, errors="coerce"), match=tk.tx.map(ms))
tk = tk.dropna(subset=["sign", "match"])
tk = tk[(tk.sign > 0)]
tk["lag_ms"] = tk.match - tk.sign
mv = np.array([mid(t) - mid(t - 300) for t in tk.sign.to_numpy(np.int64)])
tk["fut5"] = np.abs(mv) >= 5
tk["fut3"] = np.abs(mv) >= 3
tk["cl"] = tk.tx.isin(cl_tx)
out = {"taker_orders": int(len(tk)), "cluster_matches": int(tk.cl.sum()),
       "sign_to_match_ms_q": tk.lag_ms.quantile([.1, .5, .9]).round(0).to_dict(),
       "P_fut5_cluster": round(float(tk[tk.cl].fut5.mean()), 3), "P_fut5_other": round(float(tk[~tk.cl].fut5.mean()), 3),
       "P_fut3_cluster": round(float(tk[tk.cl].fut3.mean()), 3), "P_fut3_other": round(float(tk[~tk.cl].fut3.mean()), 3),
       "base_P_fut5_random": round(float(np.mean(np.abs(np.array([mid(t) - mid(t - 300) for t in np.random.default_rng(1).uniform(s0 * 1000, s1 * 1000, 3000).astype(np.int64)])) >= 5)), 3)}
(HERE.parent / "results" / f"iter6_i3_takers_{s0}_{s1}.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))

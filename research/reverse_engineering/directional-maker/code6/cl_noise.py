"""Iteration 6: does the center skew track the Chainlink stream's own 1-s noise? Skew (code6/m1_center.py construction)
regressed on the Chainlink 'noise' n(t) = CL(t-2) - mean(CL(t-6..t-3)) (USD) and on the futures change over the same span
f(t) = F(t) - mean(F(t-4..t-1)); live BTC 5m, fit < 15:00 UTC, held out after. python code6/cl_noise.py <a> <b>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm
C = ROOT / ".cache/re/directional-maker"; SPLIT = 1793458800
a, b = int(sys.argv[1]), int(sys.argv[2])
ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet"); ev = ev[ev.w.str.contains("btc-updown-5m") & (ev.d == 500.0)]
tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 400, b) if r["r"][0] == "b" and r["r"][2]]
fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s").drop_duplicates("s", keep="last")
sec = np.arange(a - 400, b + 60)
F = pd.Series(fu.m.to_numpy()[np.clip(np.searchsorted(fu.s.to_numpy(), (sec + 1) * 1000, side="left") - 1, 0, None)], index=sec)
cl = {}
for r in iter_dm("dm_rtds", a - 400, b + 60):
    if r["q"] != "crypto_prices_chainlink": continue
    try: j = json.loads(r["m"])
    except ValueError: continue
    for x in (j.get("payload") or {}).get("data", []) or []: cl[int(x["timestamp"]) // 1000] = float(x["value"])
CLs = pd.Series(cl).sort_index().reindex(sec).ffill()
rows = []
for w, g in ev.groupby("w"):
    st = int(w.split("-")[-1])
    if st < a or st + 300 > b: continue
    tw_ = tch[tch.w == w].sort_values("s"); ts_, bb_, ba_ = tw_.s.to_numpy(), tw_.bb.to_numpy(), tw_.ba.to_numpy()
    gb, ga = g[g.side == 1], g[g.side == 0]
    for t in range(st + 10, st + 270):
        T = t * 1000
        mb = gb[(gb.s > T - 1500) & (gb.s <= T)]; ma = ga[(ga.s > T - 1500) & (ga.s <= T)]
        if not len(mb) or not len(ma): continue
        qu, au = float(mb.p.max()), float(ma.p.min()); i = np.searchsorted(ts_, T, side="right") - 1
        if au <= qu or i < 0: continue
        sk = (qu + au) / 2 - (bb_[i] + ba_[i]) / 2
        n_cl = CLs.get(t - 2) - CLs.loc[t - 6:t - 3].mean()
        n_f = F.get(t) - F.loc[t - 4:t - 1].mean()
        n_cl1 = CLs.get(t - 1) - CLs.loc[t - 5:t - 2].mean()
        rows.append((t, sk, n_cl, n_f, n_cl1))
D = pd.DataFrame(rows, columns=["t", "sk", "n_cl", "n_f", "n_cl1"]).dropna()
out = {"seconds": int(len(D))}
for nm, cols in (("chainlink_noise", ["n_cl"]), ("futures_change", ["n_f"]), ("both", ["n_cl", "n_f"]), ("chainlink_noise_t-1", ["n_cl1"])):
    tr, te = D[D.t < SPLIT], D[D.t >= SPLIT]
    X = np.c_[np.ones(len(tr)), tr[cols].to_numpy()]; beta = np.linalg.lstsq(X, tr.sk.to_numpy(), rcond=None)[0]
    Xt = np.c_[np.ones(len(te)), te[cols].to_numpy()]; pr = Xt @ beta
    r2 = 1 - np.sum((te.sk - pr) ** 2) / np.sum((te.sk - te.sk.mean()) ** 2)
    out[nm] = {"coef_per_100usd": [round(float(c) * 100, 4) for c in beta[1:]], "heldout_r2": round(float(r2), 4),
               "corr_test": [round(float(np.corrcoef(te[c], te.sk)[0, 1]), 3) for c in cols]}
(HERE.parent / "results" / f"iter6_cl_noise_{a}_{b}.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

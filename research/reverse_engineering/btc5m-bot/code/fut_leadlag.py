"""Iteration 3: order-level lead-lag of the bot's side vs Binance USD-M futures at sub-second resolution, and the
residual-anticipation test: when futures were flat up to the bot's information horizon, does its side still predict
the NEXT futures move? (VALIDATE orders, orders.parquet; s = block second of the order's first fill.)"""
import os, sys, glob, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600

o = pd.read_parquet(f"{C}/orders.parquet")
o = o[(o.ts >= V0) & (o.ts < V1) & (o.rel >= 0) & (o.rel < 300)].copy()
o["first"] = o.roles.str[0]
sp = pd.read_parquet(f"{C}/binance_1s.parquet"); sp_sec = sp.sec.to_numpy(np.int64); sp_lp = np.log(sp.close.to_numpy())
def spot_move(a, b):  # kline closes: price at the end of second a-1 .. end of second b-1 (= close of b-1 minus close of a-1)
    ia = np.searchsorted(sp_sec, a - 1); ib = np.searchsorted(sp_sec, b - 1)
    return (sp_lp[np.clip(ib, 0, len(sp_lp) - 1)] - sp_lp[np.clip(ia, 0, len(sp_lp) - 1)]) * 1e4
res = {"n_orders": int(len(o))}
WIN = [(-6, -4), (-4, -3), (-3, -2), (-2, -1.5), (-1.5, -1), (-1, -0.5), (-0.5, 0), (0, 0.5), (0.5, 1), (1, 2), (2, 5), (5, 15)]
rows = []
for d0 in range(V0, V1, 86400):
    f = pd.read_parquet(f"{C}/fut/{d0}.parquet").sort_values("T", kind="stable")
    T = f["T"].to_numpy(np.int64); lp = np.log(f.p.to_numpy())
    g = o[(o.ts >= d0 + 20) & (o.ts < d0 + 86400 - 20)]
    s = g.ts.to_numpy(np.int64) * 1000
    def px(t):
        i = np.searchsorted(T, t, side="left") - 1
        return lp[np.clip(i, 0, None)]
    d = {"first": g["first"].to_numpy(), "sg": np.where(g.is_up.to_numpy(), 1.0, -1.0)}
    for a, b in WIN:
        d[f"f[{a},{b})"] = (px(s + int(b * 1000)) - px(s + int(a * 1000))) * 1e4
    d["f_past3"] = (px(s - 1000) - px(s - 4000)) * 1e4      # PIT horizon (T < (s-1)*1000)
    d["f_past3_to_s-0.5"] = (px(s - 500) - px(s - 4000)) * 1e4
    d["spot_r3"] = spot_move(g.ts.to_numpy(np.int64) - 4, g.ts.to_numpy(np.int64) - 1)
    rows.append(pd.DataFrame(d))
D = pd.concat(rows, ignore_index=True)
def agree(mask, col):
    m = D[col].to_numpy(); sg = D.sg.to_numpy(); k = mask & (np.abs(m) > 1e-9)
    return {"agree": round(float((np.sign(m[k]) == sg[k]).mean()), 4) if k.any() else None, "nonzero": round(float(k.sum() / max(mask.sum(), 1)), 3), "n": int(mask.sum())}
for first in ("T", "M"):
    base = D["first"].to_numpy() == first
    r = {c: agree(base, c) for c in [f"f[{a},{b})" for a, b in WIN]}
    flat = base & (np.abs(D.f_past3.to_numpy()) < 0.3) & (np.abs(D.spot_r3.to_numpy()) < 0.01)
    flat_s05 = base & (np.abs(D["f_past3_to_s-0.5"].to_numpy()) < 0.3) & (np.abs(D.spot_r3.to_numpy()) < 0.01)
    r["FLAT_futures_to_s-1_and_spot"] = {c: agree(flat, c) for c in ["f[-1,-0.5)", "f[-0.5,0)", "f[0,0.5)", "f[0.5,1)", "f[1,2)", "f[2,5)", "f[5,15)"]}
    r["FLAT_futures_to_s-0.5_and_spot"] = {c: agree(flat_s05, c) for c in ["f[-0.5,0)", "f[0,0.5)", "f[0.5,1)", "f[1,2)", "f[2,5)", "f[5,15)"]}
    res[f"first_{first}"] = r
# placebo: side shuffled within day
rng = np.random.default_rng(0); sgp = rng.permutation(D.sg.to_numpy())
m = D["f[2,5)"].to_numpy(); k = np.abs(m) > 1e-9
res["placebo_f[2,5)"] = round(float((np.sign(m[k]) == sgp[k]).mean()), 4)
json.dump(res, open(f"{R}/results_fut_leadlag_iter3.json", "w"), indent=1)
print(json.dumps(res, indent=0)[:3500])

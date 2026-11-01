"""Iteration 17 (X177 step 2): are XM's 60-share maker-first orders LOST RACES (taker attempts priced at the ask the bot saw ~180 ms
before arrival, resting because the ask moved) or DELIBERATE bids? For every posting found by post60_17.py (server ms t_post of the
+60 size change at L), the bought outcome's best ask from the unthrottled near-touch channel at t_post - lag for lag = 0, 50, 100,
150, 180, 250, 500, 1000, 3000 ms: P(ask == L) (a lost race: L was the ask at the bot's view) and P(ask < L) (L was marketable then).
Control: DS / GF 30-share maker-first orders (known lost-race remainders). Usage: python post60b_17.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live
S = os.environ["RE16_SCRATCH"] + "/it17"
R = pd.read_parquet(S + "/post60_17.parquet"); o = pd.read_parquet(S + "/mkx17_orders.parquet")
R["start_ts"] = o.start_ts.to_numpy(); R["t_post"] = (R.post_rel + R.start_ts) * 1000.0
win = pd.read_parquet(S + "/post17_windows.parquet")
a0, b0 = int(win.start_ts.min()) - 120, int(win.end_ts.max()) + 10
P = {}
for r in live.iter_live("btc5m_clob_raw2", a0, b0):
    if r.get("k") == "p" and r.get("bb") is not None and r.get("ba") is not None:
        P.setdefault(int(r["m"]), []).append((r["s"], float(r["bb"]), float(r["ba"])))
P = {k: np.array(v, float) for k, v in P.items()}
for k in P:
    P[k] = P[k][np.argsort(P[k][:, 0], kind="stable")]
LAGS = (0, 50, 100, 150, 180, 250, 500, 1000, 3000)
res = {}
for nm, g in (("XM60", R[(R.wallet == "XM") & (R.orig.round() == 60)]), ("DS30", R[(R.wallet == "DS") & (R.orig.round() == 30)]), ("GF30", R[(R.wallet == "GF") & (R.orig.round() == 30)]), ("XM30", R[(R.wallet == "XM") & (R.orig.round() == 30)])):
    g = g[g.t_post.notna()]
    eq = {l: [] for l in LAGS}; lt = {l: [] for l in LAGS}
    for x in g.itertuples():
        a = P.get(int(x.start_ts))
        if a is None:
            continue
        for l in LAGS:
            i = np.searchsorted(a[:, 0], x.t_post - l, "left") - 1     # state strictly before t_post - l
            if i < 0:
                continue
            ask = a[i, 2] if x.is_up else round(1 - a[i, 1], 2)
            eq[l].append(abs(ask - x.L) < 1e-6); lt[l].append(ask < x.L - 1e-6)
    res[nm] = {"n": int(len(g)), "P_ask_eq_L_by_lag_ms": {str(l): round(float(np.mean(eq[l])), 4) for l in LAGS if eq[l]},
               "P_ask_below_L_by_lag_ms": {str(l): round(float(np.mean(lt[l])), 4) for l in LAGS if lt[l]}}
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/post60b_17.json", "w"), indent=1)
print(json.dumps(res, indent=1))

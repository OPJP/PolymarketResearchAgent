"""Iteration 4: why is the per-window PnL / net-position correlation stuck at ~0.44 although the side model improved?
Diagnostic decomposition on VALIDATE (val_outcome_it4b.parquet from val_outcome4.py; ORACLE variants use the cluster's
own fills and are diagnostics only, never part of the rule). Per window: actual Up / Down / net shares vs predictions
built from (model or oracle) per-second volume x (model or oracle) per-second side."""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
D = pd.read_parquet(f"{C}/val_outcome_it4b.parquet")
f = pd.read_parquet(f"{C}/fills.parquet", columns=["cid", "rel", "is_up", "shares", "price", "fee_usd", "up_payout"])
f = f[f.cid.isin(set(D.cid))].copy(); f["r"] = f.rel.astype(int)
g = f.assign(u=np.where(f.is_up, f.shares, 0.0), d=np.where(f.is_up, 0.0, f.shares)).groupby(["cid", "r"])[["u", "d"]].sum()
D = D.join(g, on=["cid", "rel"]).fillna({"u": 0.0, "d": 0.0})
vol_m = 30 * (D.pu + D.pd); side_m = D.ps
vol_o = D.u + D.d; side_o = np.where(vol_o > 0, D.u / np.maximum(vol_o, 1e-9), D.ps)
W = lambda x: pd.Series(np.asarray(x, float)).groupby(D.cid.to_numpy()).sum()
act_u, act_d = W(D.u), W(D.d); act_net = act_u - act_d
res = {"windows": int(D.cid.nunique()),
       "corr_window_up_shares_model": round(float(np.corrcoef(W(30 * D.pu), act_u)[0, 1]), 4),
       "corr_window_down_shares_model": round(float(np.corrcoef(W(30 * D.pd), act_d)[0, 1]), 4),
       "corr_window_total_shares_model": round(float(np.corrcoef(W(vol_m), act_u + act_d)[0, 1]), 4),
       "net_share_of_gross_median": round(float(np.median(np.abs(act_net) / np.maximum(act_u + act_d, 1))), 4)}
for nm, vol, side in [("model_vol_x_model_side", vol_m, side_m), ("oracle_vol_x_model_side", vol_o, side_m),
                      ("model_vol_x_oracle_side", vol_m, side_o), ("model_vol_x_sharp_model_side", vol_m, (side_m >= 0.5).astype(float)),
                      ("oracle_vol_x_sharp_model_side", vol_o, (side_m >= 0.5).astype(float))]:
    net = W(vol * (2 * np.asarray(side, float) - 1))
    res[nm] = round(float(np.corrcoef(net, act_net)[0, 1]), 4)
# netflow regression prediction per window
res["netflow_model"] = round(float(np.corrcoef(W(D.nf), act_net)[0, 1]), 4)
# how much of the net comes from two-sided seconds (both outcomes bought in the same second)?
two = (D.u > 0) & (D.d > 0)
res["share_of_abs_net_from_two_sided_seconds"] = round(float(np.abs(W(np.where(two, D.u - D.d, 0))).sum() / np.abs(act_net).sum()), 4)
res["share_of_gross_in_two_sided_seconds"] = round(float((D.u + D.d)[two].sum() / (D.u + D.d).sum()), 4)
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_net_diag_iter4.json", "w"), indent=1)

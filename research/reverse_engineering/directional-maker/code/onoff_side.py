"""Iteration 2 descriptive checks from activity + spot only (no tapes):
A1 on/off structure across all markets; A2 first-fill second; A3 first-fill side vs public window-open state."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa
from panel2 import cluster_trades, OUT, H  # noqa
VAL0 = 1792108800; B0 = 1791504000
ct = cluster_trades()
ct = ct[(ct["ts"] >= B0) & (ct["ts"] < H)]
w = pd.read_parquet(OUT / "windows_5m.parquet"); w = w[w["end_ts"] <= H].sort_values("start_ts")
tok_up = dict(zip(w["up_token"], w["cid"])); tok_dn = dict(zip(w["down_token"], w["cid"]))
ct["btc5"] = ct["token_id"].isin(tok_up.keys() | tok_dn.keys())
res = {}
# A1: per 5-min slot activity anywhere vs in BTC 5m
ct["slot"] = ct["ts"] // 300 * 300
slots = pd.DataFrame({"slot": np.arange(B0, H, 300)})
any_ = ct.groupby("slot").size().rename("n_any"); b5 = ct[ct["btc5"]].groupby("slot").size().rename("n_b5")
nb5 = ct[~ct["btc5"]].groupby("slot").size().rename("n_other")
s = slots.set_index("slot").join(any_).join(b5).join(nb5).fillna(0)
s["val"] = s.index >= VAL0
for nm, g in s.groupby("val"):
    k = "validate" if nm else "build"
    on5 = g["n_b5"] > 0; onO = g["n_other"] > 0
    res[f"A1_{k}"] = {"slots": len(g), "btc5_on": float(on5.mean()), "other_on": float(onO.mean()),
                      "other_on_given_btc5_off": float(onO[~on5].mean()), "other_on_given_btc5_on": float(onO[on5].mean()),
                      "hour_btc5_on": {int(h): round(float(x), 2) for h, x in on5.groupby((g.index // 3600) % 24).mean().items()}}
# per-wallet on/off agreement in BTC 5m
for nm, g in ct[ct["btc5"]].groupby("wallet"):
    pass
wb = ct[ct["btc5"]].groupby(["slot", "wallet"]).size().unstack(fill_value=0).reindex(slots["slot"], fill_value=0) > 0
res["A1_wallet_on_share"] = {k[:8]: float(v) for k, v in wb.mean().items()}
res["A1_wallet_on_corr"] = wb.astype(int).corr().round(2).values.tolist()
# A2/A3: first BUY fill per active BTC 5m window
b = ct[ct["btc5"] & (ct["side"] == "BUY")].copy()
b["cid"] = [tok_up.get(t) or tok_dn.get(t) for t in b["token_id"]]
b["is_up"] = b["token_id"].isin(tok_up.keys())
b = b.merge(w[["cid", "start_ts", "end_ts", "up_payout"]], on="cid")
b["rel"] = b["ts"] - b["start_ts"]
spd = pd.read_parquet(OUT / "spot_btc_1s.parquet"); sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
first = b.sort_values(["cid", "ts"]).groupby("cid").first().reset_index()
sh = b.assign(sh_up=b["shares"] * b["is_up"]).groupby("cid").agg(sh=("shares", "sum"), sh_up=("sh_up", "sum"))
first = first.merge(sh, left_on="cid", right_index=True)
first["dom_up"] = first["sh_up"] / first["sh"] > 0.5
first["val"] = first["start_ts"] >= VAL0
res["A2_first_rel_quantiles"] = {k: [int(x) for x in np.quantile(g["rel"], [0.05, 0.1, 0.25, 0.5, 0.75])] for k, g in first.groupby("val")}
res["A2_first_rel_hist_0_10"] = {k: np.bincount(np.clip(g["rel"], -1, 11) + 1, minlength=13).tolist() for k, g in first.groupby("val")}
# public state at the first fill second T (published by T): z, fair, previous window proxy, strike move
T = first["ts"].to_numpy(); st0 = first["start_ts"].to_numpy(); en = first["end_ts"].to_numpy()
fu, z = fair_up(sp, st0, en, T)
s_cur = sp.mean(st0 - 60, st0); s_prev = sp.mean(st0 - 360, st0 - 300)
first["fair_up_T"] = fu; first["prev_up"] = s_cur >= s_prev
first["r_open"] = np.log(sp.last(T) / sp.last(st0))  # spot move since the start
first["r10"] = np.log(sp.last(T) / sp.last(T - 10))
first["r_pre60"] = np.log(sp.last(st0) / sp.last(st0 - 60))
out = {}
for k, g in first.groupby("val"):
    kk = "validate" if k else "build"
    fu_ = g["is_up"]
    out[kk] = {"n": len(g), "first_up_share": float(fu_.mean()), "first_wins": float((g["is_up"] == (g["up_payout"] > 0.5)).mean()),
               "first==binance_fav": float((fu_ == (g["fair_up_T"] > 0.5)).mean()),
               "first==prev_outcome(momentum)": float((fu_ == g["prev_up"]).mean()),
               "first==sign(spot move since start)": float((fu_ == (g["r_open"] > 0)).mean()),
               "first==sign(r10)": float((fu_ == (g["r10"] > 0)).mean()),
               "first==sign(pre-window 60s move)": float((fu_ == (g["r_pre60"] > 0)).mean()),
               "first==dominant": float((fu_ == g["dom_up"]).mean())}
res["A3_first_side"] = out
print(json.dumps(res, indent=1, default=str))

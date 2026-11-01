"""Iteration 12 (pivot: condition 5 as an exposure-path target). Per-window cluster net exposure and PnL on BUILD /
VALIDATE (pre-H fills), the identity PnL ~ net x outcome, and how well the frozen per-second netflow model (it4b, PIT)
predicts the window net on VALIDATE."""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"
VAL0, H = 1792108800, 1792713600
f = pd.read_parquet(f"{C}/fills.parquet", columns=["wallet", "role", "side", "shares", "price", "fee_usd", "usdc", "cid", "start_ts", "rel", "is_up", "up_payout"])
print(f.side.value_counts().to_dict(), f.role.value_counts().to_dict(), f.wallet.value_counts().to_dict())
f = f[f.side == "BUY"] if f.side.dtype == object else f
f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
f["sgn"] = np.where(f.is_up, 1.0, -1.0)
win = pd.read_parquet(f"{C}/windows.parquet")
win = win[win.up_payout.notna()]
out = {}
for wl in ("pool", "GF", "XM", "DS"):
    x = f if wl == "pool" else f[f.wallet == wl]
    g = x.groupby("cid").agg(net=("shares", lambda s: 0), pnl=("pnl", "sum"))
    g["net"] = (x.shares * x.sgn).groupby(x.cid).sum()
    g["gross"] = x.groupby("cid").shares.sum()
    g = win.set_index("cid")[["start_ts", "up_payout"]].join(g, how="left").fillna({"net": 0, "pnl": 0, "gross": 0})
    g["o"] = 2 * g.up_payout - 1
    g["val"] = g.start_ts >= VAL0
    r = {}
    for nm, m in (("BUILD", ~g.val), ("VALIDATE", g.val)):
        gg = g[m]
        r[nm] = {"windows": int(len(gg)), "corr_pnl_net_x_outcome": round(float(gg.pnl.corr(gg.net * gg.o)), 4),
                 "share_net_sign_agrees_outcome": round(float(((np.sign(gg.net) == np.sign(gg.o)) & (gg.net != 0)).sum() / max((gg.net != 0).sum(), 1)), 4),
                 "mean_abs_net": round(float(gg.net.abs().mean()), 1), "mean_gross": round(float(gg.gross.mean()), 1), "pnl_sum": round(float(gg.pnl.sum()), 1)}
    out[wl] = r
    if wl == "pool":
        G = g
print(json.dumps(out, indent=1))
# frozen per-second netflow model (it4b) on VALIDATE: cumulative predicted net vs the realized net
vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet")
nfw = vo.groupby("cid").nf.sum().rename("nf_sum")
pres = (vo.pu - vo.pd).groupby(vo.cid).sum().rename("pu_minus_pd")
V = G[G.val].join(nfw).join(pres)
res = {"corr_net_nf_sum": round(float(V.net.corr(V.nf_sum)), 4), "spearman_net_nf_sum": round(float(V.net.corr(V.nf_sum, method="spearman")), 4),
       "corr_net_pu_minus_pd": round(float(V.net.corr(V.pu_minus_pd)), 4),
       "corr_pnl_nf_sum_x_outcome": round(float(V.pnl.corr(V.nf_sum * V.o)), 4)}
# by time in window: net after 60 / 120 / 180 s vs final
for cut in (60, 120, 180, 240):
    x = f[(f.start_ts >= VAL0) & (f.rel < cut)]
    n_c = (x.shares * x.sgn).groupby(x.cid).sum().reindex(V.index).fillna(0)
    res[f"corr_final_net_net_before_{cut}"] = round(float(V.net.corr(n_c)), 4)
    p_c = vo[vo.rel < cut].groupby("cid").nf.sum().reindex(V.index).fillna(0)
    res[f"corr_nf_sum_before_{cut}_vs_net_before_{cut}"] = round(float(n_c.corr(p_c)), 4)
print(json.dumps(res, indent=1))
os.makedirs(_ROOT + "/research/reverse_engineering/btc5m-bot/results", exist_ok=True)
json.dump({"by_wallet": out, "netflow_model_validate": res}, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/net12.json", "w"), indent=1)
G.to_parquet(f"{C}/it12_win_net.parquet")

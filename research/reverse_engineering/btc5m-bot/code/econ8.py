"""Iteration 8, X50 step 4 (panel-mechanics iter7 P2): PnL split into LOCKED SETS and the UNPAIRED remainder, VALIDATE and
BUILD (fills.parquet), per cluster window and per wallet-window. Paired shares q = min(Up shares, Down shares); locked gross =
q x (1 - avgcost_Up - avgcost_Down); unpaired = (net shares on the long leg) x (payout - its avg cost); fees separately; the
taker rebate = 0.5 x taker fees (B6). Large orders (>= 90 filled shares) share of the unpaired net. Writes results/econ8.json."""
import os, json
import numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
f = pd.read_parquet(os.path.join(ROOT, ".cache/re/btc5m-bot/fills.parquet"), columns=["wallet", "role", "oh", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
VAL0 = 1792108800
res = {}
for per, k in (("VALIDATE", f.start_ts >= VAL0), ("BUILD", f.start_ts < VAL0)):
    x = f[k].copy(); x["usd"] = x.shares * x.price
    for unit, keys in (("cluster_window", ["cid"]), ("wallet_window", ["cid", "wallet"])):
        g = x.groupby(keys + ["is_up"]).agg(sh=("shares", "sum"), usd=("usd", "sum")).unstack("is_up", fill_value=0.0)
        g.columns = [f"{a}_{'U' if b else 'D'}" for a, b in g.columns]
        pay = x.groupby(keys).up_payout.first()
        fee = x.groupby(keys).fee_usd.sum(); tfee = x[x.role == "T"].groupby(keys).fee_usd.sum().reindex(fee.index).fillna(0)
        g = g.join(pay).join(fee.rename("fee")).join(tfee.rename("tfee"))
        aU = g.usd_U / g.sh_U.where(g.sh_U > 0); aD = g.usd_D / g.sh_D.where(g.sh_D > 0)
        q = np.minimum(g.sh_U, g.sh_D)
        locked = (q * (1 - aU.fillna(0) - aD.fillna(0))).where(q > 0, 0.0)
        net = g.sh_U - g.sh_D
        un = np.where(net > 0, net * (g.up_payout - aU.fillna(0)), (-net) * ((1 - g.up_payout) - aD.fillna(0)))
        tot = g.sh_U * g.up_payout + g.sh_D * (1 - g.up_payout) - g.usd_U - g.usd_D
        r = {"units": int(len(g)), "paired_share_of_shares": round(float((2 * q).sum() / (g.sh_U + g.sh_D).sum()), 4),
             "share_weighted_pair_cost": round(float(((aU + aD) * q).sum() / q[q > 0].sum()), 4),
             "locked_gross_usd": round(float(locked.sum()), 1), "unpaired_pnl_usd": round(float(np.sum(un)), 1), "gross_trading_pnl_usd": round(float(tot.sum()), 1),
             "fees_usd": round(float(g.fee.sum()), 1), "taker_rebate_usd_0.5": round(float(0.5 * g.tfee.sum()), 1),
             "corr_unpaired_vs_total": round(float(np.corrcoef(un, tot - 0)[0, 1]), 4), "corr_locked_vs_total": round(float(np.corrcoef(locked, tot)[0, 1]), 4)}
        res[f"{per}_{unit}"] = r
        print(per, unit, json.dumps(r))
json.dump(res, open(os.path.join(ROOT, "research/reverse_engineering/btc5m-bot/results/econ8.json"), "w"), indent=1)

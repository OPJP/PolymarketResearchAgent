"""Iteration 15 (X144 / X143 'if false' branch): where does the depth the bot saw go? For every operator taker order of the ingested
days, the visible ask depth at or below its limit at the bot's view, D(m - 180), is split into
  filled            its own taker-step fill,
  crowd_take        non-operator taker BUYs of o at <= L plus taker SELLs of the other outcome at >= 1 - L matched in (m - 180, m)
                    (capture trade rows, server ms; operator txs excluded),
  own_prior         the operator's other taker legs on o matched in (m - 180, m) (its fan-out and follower legs),
  residual          D(m - 180) - filled - crowd_take - own_prior (maker cancels minus new asks, plus same-ms ordering).
Limit L: calldata limit where known, else best ask at m - 180 + k_w. Reported for depth-bound orders (calldata: filled < original;
all orders: filled < E[menu]) and by wallet, plus the share of orders whose fill would have been min(orig, D(m-180)) without the crowd.
Usage: python -I race15.py IT15_DIR HF_DIR OUT.json DAY [DAY ...]"""
import sys, json
import numpy as np, pandas as pd

D15, HF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DAYS = sys.argv[4:]
C = ".cache/re/btc5m-bot"
o = pd.read_parquet(f"{D15}/depth15_orders.parquet")
win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "up_token", "down_token"]).set_index("cid")
o["tok"] = np.where(o.is_up, win.loc[o.cid, "up_token"].astype(str).to_numpy(), win.loc[o.cid, "down_token"].astype(str).to_numpy())
o["otok"] = np.where(o.is_up, win.loc[o.cid, "down_token"].astype(str).to_numpy(), win.loc[o.cid, "up_token"].astype(str).to_numpy())
o["L"] = np.where(o.Lcd.notna(), o.Lcd, o.Lpub).astype(float)
fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx"])
optx = set(fl.tx.str.lower())
res = {"days": DAYS}
parts = []
for day in DAYS:
    tr = pd.read_parquet(f"{HF}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSize", "tradeSide"])
    tr["tokenId"] = tr.tokenId.astype(str); tr["op"] = tr.transactionHash.str.lower().isin(optx)
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
    od = o[(o.start_ts >= d0) & (o.start_ts < d0 + 86400)].copy()
    byt = {k: g.sort_values("exchangeTimestampMs") for k, g in tr.groupby("tokenId")}
    ct, ow = np.zeros(len(od)), np.zeros(len(od))
    for i, r in enumerate(od.itertuples()):
        a, b = r.m - 180, r.m
        g = byt.get(r.tok)
        if g is not None:
            t = g.exchangeTimestampMs.to_numpy()
            j0, j1 = np.searchsorted(t, a, "right"), np.searchsorted(t, b, "left")
            x = g.iloc[j0:j1]
            sel = (x.tradeSide == "BUY") & (x.tradePrice * 100 <= r.L + 1e-6)
            ct[i] += x.tradeSize[sel & ~x.op].sum(); ow[i] += x.tradeSize[sel & x.op].sum()
        g = byt.get(r.otok)
        if g is not None:
            t = g.exchangeTimestampMs.to_numpy()
            j0, j1 = np.searchsorted(t, a, "right"), np.searchsorted(t, b, "left")
            x = g.iloc[j0:j1]
            sel = (x.tradeSide == "SELL") & ((1 - x.tradePrice) * 100 <= r.L + 1e-6)
            ct[i] += x.tradeSize[sel & ~x.op].sum(); ow[i] += x.tradeSize[sel & x.op].sum()
    od["crowd_take"] = ct; od["own_prior"] = ow
    parts.append(od)
o = pd.concat(parts, ignore_index=True)
o["resid"] = o.D_m180 - o.shares - o.crowd_take - o.own_prior
o["missing"] = (o.D_m180 - o.shares).clip(lower=0)


def summ(x):
    miss = x.missing.sum()
    return {"n": int(len(x)), "median_D180": float(x.D_m180.median()), "median_filled": float(x.shares.median()),
            "sum_D180": round(float(x.D_m180.sum())), "sum_filled": round(float(x.shares.sum())),
            "share_missing_crowd": round(float(np.minimum(x.crowd_take, x.missing).sum() / max(miss, 1)), 4),
            "share_missing_own_prior": round(float(np.minimum(x.own_prior, (x.missing - np.minimum(x.crowd_take, x.missing))).sum() / max(miss, 1)), 4),
            "share_orders_crowd_took_any": round(float((x.crowd_take > 0).mean()), 4),
            "share_orders_own_prior_any": round(float((x.own_prior > 0).mean()), 4),
            "median_crowd_take": float(x.crowd_take.median()), "mean_crowd_take": round(float(x.crowd_take.mean()), 2),
            "corr_filled_vs_D180_minus_crowd_minus_own": round(float(np.corrcoef(x.shares, (x.D_m180 - x.crowd_take - x.own_prior).clip(lower=0))[0, 1]), 4) if len(x) > 10 else None,
            "corr_filled_vs_D180": round(float(np.corrcoef(x.shares, x.D_m180)[0, 1]), 4) if len(x) > 10 else None}


cd = o[o.orig.notna()]
res["calldata_depth_bound"] = summ(cd[cd.shares < cd.orig - 1e-6])
res["calldata_full"] = summ(cd[cd.shares >= cd.orig - 1e-6])
cdb = cd[cd.shares < cd.orig - 1e-6]
pred = np.minimum(cdb.orig, (cdb.D_m180 - cdb.crowd_take - cdb.own_prior).clip(lower=0))
res["calldata_depth_bound_within10_after_crowd"] = round(float((np.abs(cdb.shares - pred) <= 0.1 * np.maximum(pred, 1)).mean()), 4)
res["calldata_depth_bound_r_after_crowd"] = round(float(np.corrcoef(cdb.shares, pred)[0, 1]), 4)
res["all_orders"] = summ(o)
res["all_by_wallet"] = {w: summ(o[o.wallet == w]) for w in ("DS", "GF", "XM")}
o.to_parquet(f"{D15}/race15_orders.parquet", index=False)
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1)[:5000])

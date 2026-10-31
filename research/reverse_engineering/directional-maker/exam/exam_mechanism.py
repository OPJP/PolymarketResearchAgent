"""Examiner: mechanism on the holdout (descriptive; outcomes and later spot used only to describe). Cluster maker
BUY fills in BTC 5m: Binance fair of the bought side at the fill (seconds published by the fill), discount to it,
dollar-weighted return by fill size quartile, by time in window and by fair bucket, and the fair move 60 s later.
python exam_mechanism.py -> results/exam_mechanism.json"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up
from exam_panel import EX
w = pd.read_parquet(EX / "windows_5m.parquet")
spd = pd.read_parquet(EX / "spot_btc_1s.parquet"); sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
f = pd.read_parquet(EX / "fills_holdout.parquet"); f = f[f["role"] == "maker"].copy()
up = dict(zip(w.up_token, w.cid)); dn = dict(zip(w.down_token, w.cid))
f["wcid"] = [up.get(t, dn.get(t)) for t in f.token_id]; f["is_up"] = f.token_id.isin(set(w.up_token))
wi = w.set_index("cid")
f["start"] = wi.loc[f.wcid, "start_ts"].to_numpy(); f["end"] = wi.loc[f.wcid, "end_ts"].to_numpy()
pay = wi.loc[f.wcid, "up_payout"].to_numpy(); f["payout"] = np.where(f.is_up, pay, 1 - pay)
fu, _ = fair_up(sp, f.start.to_numpy(), f.end.to_numpy(), f.ts.to_numpy())
f["fair"] = np.where(f.is_up, fu, 1 - fu)
t60 = np.minimum(f.ts.to_numpy() + 60, f.end.to_numpy())
fu60, _ = fair_up(sp, f.start.to_numpy(), f.end.to_numpy(), t60)
f["fair60"] = np.where(f.is_up, fu60, 1 - fu60)
f["usd"] = f.price * f.shares; f["pnl"] = (f.payout - f.price) * f.shares
f["rel"] = f.ts - f.start
def ret(g): return round(float(g.pnl.sum() / g.usd.sum()), 4)
out = {"fills": int(len(f)), "mean_fair_minus_price": float((f.fair - f.price).mean()),
       "share_at_or_above_fair": float((f.price >= f.fair).mean()), "mean_fair_move_60s": float((f.fair60 - f.fair).mean()),
       "mean_payout_minus_price": float((f.payout - f.price).mean()), "usd_return": ret(f)}
f["szq"] = pd.qcut(f.shares, 4, labels=False, duplicates="drop")
out["by_fill_size_quartile"] = {int(k): {"ret": ret(g), "pnl": round(float(g.pnl.sum())), "max_shares": float(g.shares.max())} for k, g in f.groupby("szq")}
f["tb"] = pd.cut(f.rel, [0, 10, 30, 120, 240, 300], right=False)
out["by_time_in_window"] = {str(k): {"ret": ret(g), "usd": round(float(g.usd.sum()))} for k, g in f.groupby("tb", observed=True)}
f["fb"] = pd.cut(f.fair, [0, .2, .4, .6, .8, 1.0001])
out["by_binance_fair"] = {str(k): {"ret": ret(g), "usd": round(float(g.usd.sum()))} for k, g in f.groupby("fb", observed=True)}
f["half"] = np.where(f.ts < 1793059200, "10-23..10-26", "10-27..10-30")
out["by_half"] = {k: {"ret": ret(g), "fair_minus_price": round(float((g.fair - g.price).mean()), 4), "fair_move_60s": round(float((g.fair60 - g.fair).mean()), 4), "usd": round(float(g.usd.sum()))} for k, g in f.groupby("half")}
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "exam_mechanism.json").write_text(json.dumps(out, indent=1))

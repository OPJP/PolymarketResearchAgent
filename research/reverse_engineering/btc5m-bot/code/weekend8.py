"""Iteration 8, X57 step 1 on HISTORICAL data (panel-assumptions iter7 P4): is there a weekend regime? Per day of VALIDATE (10-16
Fri .. 10-22 Thu; 10-17 / 10-18 = Saturday / Sunday) and BUILD (10-09 .. 10-15; 10-10 / 10-11 weekend): side accuracy of the
frozen side model psb on VALIDATE one-sided seconds and the share of quiet seconds (no six-series move); per wallet the large
share of orders (>= 90 filled shares) and the cluster's taker orders per window. Writes results/weekend8.json."""
import os, json
import numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
v = pd.read_parquet(os.path.join(C, "val_side_it5book.parquet"), columns=["cid", "rel", "start_ts", "truth_up", "psb"])
w = pd.read_parquet(os.path.join(C, "val_side_book_it5.parquet"), columns=["cid", "rel", "nomove"])
v = v.merge(w.drop_duplicates(["cid", "rel"]), on=["cid", "rel"], how="left")
v["day"] = pd.to_datetime(v.start_ts, unit="s").dt.strftime("%m-%d %a")
v["ok"] = (v.psb > 0.5) == (v.truth_up == 1)
res = {"side_by_day": v.groupby("day").agg(n=("ok", "size"), acc=("ok", "mean"), quiet=("nomove", "mean")).round(4).to_dict(orient="index")}
f = pd.read_parquet(os.path.join(C, "fills.parquet"), columns=["wallet", "oh", "shares", "start_ts", "role"])
o = f.groupby(["wallet", "oh"]).agg(sh=("shares", "sum"), st=("start_ts", "first"), roles=("role", lambda x: "".join(sorted(set(x))))).reset_index()
o["day"] = pd.to_datetime(o.st, unit="s").dt.strftime("%m-%d %a")
o["big"] = o.sh >= 90
res["large_share_by_day"] = o.pivot_table(index="day", columns="wallet", values="big", aggfunc="mean").round(4).to_dict(orient="index")
res["orders_per_day"] = o.groupby("day").size().to_dict()
we = v.day.str.contains("Sat|Sun")
res["side_weekend_vs_weekday"] = {"weekend": round(float(v.ok[we].mean()), 4), "weekday": round(float(v.ok[~we].mean()), 4),
                                  "quiet_weekend": round(float(v.nomove[we].mean()), 4), "quiet_weekday": round(float(v.nomove[~we].mean()), 4)}
owe = o.day.str.contains("Sat|Sun")
res["large_weekend_vs_weekday"] = {w_: {"weekend": round(float(o.big[owe & (o.wallet == w_)].mean()), 4), "weekday": round(float(o.big[~owe & (o.wallet == w_)].mean()), 4)} for w_ in ("DS", "GF", "XM")}
print(json.dumps({k: res[k] for k in ("side_weekend_vs_weekday", "large_weekend_vs_weekday")}))
print(json.dumps(res["side_by_day"]))
print(json.dumps(res["large_share_by_day"]))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "weekend8.json"), "w"), indent=1)

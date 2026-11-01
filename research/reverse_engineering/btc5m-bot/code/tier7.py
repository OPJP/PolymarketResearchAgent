"""Iteration 7 (catalog X33 = panel-assumptions iter6 P6, step 1): taker-rebate tier path and one-off bonuses per wallet.
data-api activity rows TAKER_REBATE (cached adapter), development period only (rows before H). Per wallet: daily rebate
amounts from the first row; rows that are round bonus amounts; the ratio of each day's rebate to the median of its
neighbours (a step path through tiers shows as a rising ratio). Usage: python tier7.py"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
import pandas as pd, numpy as np
from polyrea.adapters.polymarket import PolymarketData
H = 1792713600
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9",
     "W4": "0xd84403efd50b49a1d8a7181627e00307e6ea5908"}
pm = PolymarketData()
res = {}
for nm, w in W.items():
    rows, _, cov = pm.activity(w, start=1780272000, end=H - 1, types=("TAKER_REBATE",))
    d = pd.DataFrame(rows)
    if not len(d):
        res[nm] = None; continue
    d = d[d.timestamp < H].sort_values("timestamp")
    d["day"] = pd.to_datetime(d.timestamp, unit="s").dt.strftime("%m-%d")
    amt = pd.to_numeric(d.get("usdcSize", d.get("size")), errors="coerce")
    d["amt"] = amt
    first = d.head(12)[["day", "amt"]].round(2).values.tolist()
    rnd = d[(d.amt.round(2) % 5 == 0) & (d.amt >= 10)][["day", "amt"]].round(2).values.tolist()
    res[nm] = {"rows": int(len(d)), "first_day": d.day.iloc[0], "first_rows": first, "round_amount_rows": rnd[:20],
               "per_day_rows_max": int(d.groupby("day").size().max())}
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "tier7.json"), "w"), indent=1)
print(json.dumps(res)[:3500])

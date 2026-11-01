"""Iteration 7 (catalog X32 = panel-assumptions iter6 P5, step 1): ladder lifecycle around the signing bursts. VALIDATE
taker first fills per wallet by block rel second; 3-s rolling counts normalised by the pre-burst mean; is the dip at each
wallet's own signing offset (XM +172.7 s, DS +173.8 s, GF +174.9 s: the signer blocks that wallet) or common (the process
blocks)? Same around +42 s and the next window's -89.5 s burst (rel 210.5 s). Usage: python burst7.py"""
import os, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/burst7.json"
VAL = (1792108800, 1792713600)
f = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "li", "ts", "oh", "wallet", "role", "start_ts"])
f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])].sort_values(["block", "li"])
o = f.groupby(["wallet", "oh"], sort=False).agg(ts=("ts", "first"), role0=("role", "first"), st=("start_ts", "first")).reset_index()
o = o[o.role0 == "T"]; o["rel"] = (o.ts - o.st).astype(int)
res = {}
for burst, (pre_lo, pre_hi, lo, hi) in {"+172.7": (150, 168, 166, 196), "+42.0": (22, 38, 36, 60), "next -89.5 (rel 210.5)": (192, 206, 204, 226)}.items():
    r = {}
    for w in ["XM", "DS", "GF"]:
        c = o[o.wallet == w].rel.value_counts().reindex(range(0, 300), fill_value=0).astype(float)
        roll = c.rolling(3, center=True).sum()
        base = roll.loc[pre_lo:pre_hi].mean()
        seg = (roll.loc[lo:hi] / base).round(3)
        r[w] = {"min_rel": int(seg.idxmin()), "min": float(seg.min()), "max_rel_after_min": int(seg.loc[seg.idxmin():].idxmax()), "max_after": float(seg.loc[seg.idxmin():].max()),
                "profile": {int(k): float(v) for k, v in seg.items()}}
    res[burst] = r
json.dump(res, open(OUT, "w"), indent=1)
for b, r in res.items():
    print(b, {w: (v["min_rel"], v["min"], v["max_rel_after_min"], v["max_after"]) for w, v in r.items()})

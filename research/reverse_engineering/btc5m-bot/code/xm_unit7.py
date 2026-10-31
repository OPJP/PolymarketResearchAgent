"""Iteration 7 (panel-assumptions iter6 critique 5; X14): XM's side condition in the pre-registered DECISION units.
Units: (1) per XM taker order (first fill as taker; the block second of that fill), (2) per XM one-sided window (the outcome
XM bought; decision = its first taker order in the window). Prediction = the frozen side model (model_it5_side_book,
stored VALIDATE predictions psb) at that block second where the pooled cluster was one-sided (the stored rows); coverage
reported. VALIDATE, development only. Usage: python xm_unit7.py"""
import os, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/xm_unit7.json"
VAL = (1792108800, 1792713600)
f = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "li", "ts", "oh", "wallet", "role", "cid", "start_ts", "is_up"])
f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])].sort_values(["block", "li"])
o = f.groupby(["wallet", "oh"], sort=False).agg(cid=("cid", "first"), ts=("ts", "first"), role0=("role", "first"), st=("start_ts", "first"), is_up=("is_up", "first")).reset_index()
o["rel"] = (o.ts - o.st).astype(int)
sd = pd.read_parquet(f"{C}/val_side_it5book.parquet", columns=["cid", "rel", "psb"]).set_index(["cid", "rel"]).psb
res = {}
for w in ["XM", "GF", "DS"]:
    x = o[(o.wallet == w) & (o.role0 == "T")].copy()
    x["psb"] = sd.reindex(pd.MultiIndex.from_arrays([x.cid, x.rel])).to_numpy()
    cov = x.psb.notna()
    acc = ((x.psb[cov] >= 0.5) == x.is_up[cov]).mean()
    # one-sided windows of this wallet (all its fills, taker and maker)
    ws = f[f.wallet == w].groupby("cid").is_up.agg(["min", "max"])
    one = ws.index[ws["min"] == ws["max"]]
    xf = x[x.cid.isin(one)].sort_values("ts").drop_duplicates("cid")
    covw = xf.psb.notna()
    accw = ((xf.psb[covw] >= 0.5) == xf.is_up[covw]).mean() if covw.any() else None
    res[w] = {"taker_orders": int(len(x)), "per_order_coverage": round(float(cov.mean()), 4), "per_order_accuracy": round(float(acc), 4),
              "one_sided_windows": int(len(one)), "one_sided_windows_with_taker_order": int(len(xf)), "per_window_coverage": round(float(covw.mean()), 4) if len(xf) else None,
              "per_window_accuracy_first_decision": round(float(accw), 4) if accw is not None else None}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))

"""Examiner r1: wallets' own persistence (polyrea.tools.assess_persistence, one-off bonuses removed) as of the latest full day
(as_of = 2026-11-01 00:00 UTC, so 10-31 is the last day), plus the daily user-pnl series of the last 21 days (economic, trading,
rebates), through the exam HTTP cache only. Usage: python persist.py OUT_JSON"""
import os, sys, json
ARGS = sys.argv[1:]
assert os.environ.get("POLYREA_CACHE_DIR", "").replace("\\", "/").rstrip("/").endswith(".cache/exam/btc5m-bot")
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
from polyrea.tools import assess_persistence
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.pnl import daily_frame

AS_OF = 1793491200
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
out = {"as_of": AS_OF}
pm = PolymarketData()
for k, w in W.items():
    r = assess_persistence(w, recent_days=30, as_of=AS_OF)
    out[k] = {"derived": r.get("derived"), "observed": r.get("observed"), "coverage": r.get("coverage")}
    body, _ = pm.user_pnl(w, max_age=6 * 3600)
    df = daily_frame(body.get("points") or [], as_of=AS_OF)
    cols = [c for c in df.columns if c.startswith("d_")]
    tail = df.tail(22)
    out[k]["daily_tail"] = {str(i): {c: (round(float(tail.loc[i, c]), 1) if pd.notna(tail.loc[i, c]) else None) for c in cols} for i in tail.index}
    out[k]["columns"] = list(df.columns)
    print(k, "done", flush=True)
json.dump(out, open(ARGS[0], "w"), indent=1, default=str)
for k in W:
    d = out[k]["derived"] or {}
    for s in ("d_economic_pnl", "d_economic_pnl_recurring", "d_trade_pnl"):
        if s in d:
            x = d[s]
            print(k, s, {kk: x[kk] for kk in list(x)[:12]})

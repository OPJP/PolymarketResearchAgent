"""Iteration 7 (assumptions P4, X56, historical form): PnL of the cluster's maker BUY fills in the Chainlink sample windows
by the gap between the Chainlink and the Binance fair of the token at the fill's bin start (STUDY case by case allowed;
VALIDATE aggregate only)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import i1_cl_hist as h  # noqa: E402
from polyrea.analysis.updown import windows_from_markets  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

C = h.C
cl = h.cl_series()
pt = pd.read_parquet(C / "cl/ptb_lot.parquet")
ptb = dict(zip(pt["start_ts"].astype(np.int64), pt["ptb"]))
pay = dict(zip(pt["start_ts"].astype(np.int64), (pt["final"] >= pt["ptb"]).astype(float)))
p = pd.concat([pd.read_parquet(C / f"exam/panel_day_{d}.parquet", columns=["cid", "start_ts", "rel", "side_up", "sig", "fair_s", "last_s"])
               for d in range(h.S0, h.V1, 86400)], ignore_index=True)
p = p[p.start_ts.isin(h.sample_windows())].copy()
p = h.add_cl(p, cl, ptb)
p = p[p.cl_ok]
ws = windows_from_markets(fetch_windows(sorted({f"btc-updown-5m-{int(s)}" for s in p.start_ts.unique()})))
tok = {}
for x in ws:
    tok[str(x.up_token)] = (x.start_ts, 1)
    tok[str(x.down_token)] = (x.start_ts, 0)
f = pd.read_parquet(C / "exam/fills_holdout.parquet")
f = f[(f.role == "maker") & (f.side == "BUY")].copy()
f["k"] = [tok.get(str(t)) for t in f.token_id]
f = f[f.k.notna()].copy()
f["start_ts"] = [k[0] for k in f.k]
f["side_up"] = [k[1] for k in f.k]
f["rel"] = ((f.ts - f.start_ts) // 10 * 10).astype(int)
m = f.merge(p[["start_ts", "rel", "side_up", "fair_cl_s", "fair_s", "gap_s"]], on=["start_ts", "rel", "side_up"], how="inner")
m["won"] = [pay[s] if u == 1 else 1 - pay[s] for s, u in zip(m.start_ts, m.side_up)]
m["pnl"] = (m.won - m.price) * m.shares
m["usd"] = m.price * m.shares
bins = [-1, -0.03, -0.01, 0.01, 0.03, 1]
out = {}
for nm, g in (("study", m[m.start_ts < h.V0]), ("validate", m[m.start_ts >= h.V0])):
    g = g.assign(b=pd.cut(g.gap_s, bins, labels=["< -3c", "-3..-1c", "-1..+1c", "+1..+3c", "> +3c"]))
    t = g.groupby("b", observed=True).agg(fills=("pnl", "size"), pnl=("pnl", "sum"), usd=("usd", "sum"))
    t["ret"] = t.pnl / t.usd
    t["share"] = t.fills / t.fills.sum()
    out[nm] = {str(k): {kk: round(float(vv), 4) for kk, vv in r.items()} for k, r in t.iterrows()}
    out[nm]["total_ret"] = round(float(g.pnl.sum() / g.usd.sum()), 4)
(ROOT / "research/reverse_engineering/directional-maker/results/iter7_p4_gap_hist.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

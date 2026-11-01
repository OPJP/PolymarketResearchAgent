"""Censoring check for the R reading (iteration 16): on BUILD-live (10-31 12-18, the uncensored add bursts of
own_bursts_dev, server clock), which of its value changes (burst top moving >= 1c on a token) are visible on the filled
record (a filled wallet order of that token signed within [s - 80, s + 10] ms at a price inside the burst)? Compare
filled vs unfilled value changes: |dV|, a >= 2c clean-print jump within +-10 s (round-result-like moments), and a
wallet-free taker print within 3 s after (a sweep). If fills over-represent jump moments, filled-record counts follow
round results by construction. Output: results/censoring_check.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
A, B = 1793448000, 1793469600
b = pd.read_parquet(OUT / "own_bursts_dev.parquet")
b = b[(b.side == "BUY") & (b.s / 1000 >= A) & (b.s / 1000 < B)].sort_values(["a", "s"])
b["dV"] = b.groupby("a").pmax.diff()
vc = b[b.dV.abs() >= 0.01 - 1e-9].copy()
c = pd.read_parquet(OUT / "calldata_dev.parquet")
c = c[(c.maker.str.lower() == W) & (c.idx >= 0) & (c.sign_ms / 1000 >= A - 60) & (c.sign_ms / 1000 < B)].drop_duplicates(["salt", "sign_ms"])
fil = {a: g for a, g in c.groupby(c.token_id.astype(str))}
vis = []
for r in vc.itertuples():
    g = fil.get(str(r.a))
    if g is None:
        vis.append(False)
        continue
    k = (g.sign_ms >= r.s - 80) & (g.sign_ms <= r.s + 10) & (g.price >= r.pmin - 1e-9) & (g.price <= r.pmax + 1e-9)
    vis.append(bool(k.any()))
vc["filled"] = vis
act = pd.read_parquet(OUT / "activity_devblocks.parquet")
cids = act.conditionId.unique().tolist()
pm = PolymarketData()
rows = []
for cid in cids:
    rws, _, _ = pm.market_trades(cid, start=A - 3600, end=B - 1, taker_only=True)
    for x in rws:
        x = dict(x)
        x["cid"] = cid
        rows.append(x)
T = pd.DataFrame(rows)
T["proxyWallet"] = T.proxyWallet.str.lower()
wtx = set(c.tx) | set(T.loc[T.proxyWallet == W, "transactionHash"])
T = T[(T.timestamp < B) & ~T.transactionHash.isin(wtx)].sort_values("timestamp")
tok_cid = dict(zip(T.asset.astype(str), T.cid))
jump_t, any_t = {}, {}
for cid, g in T.groupby("cid"):
    pA = np.where(g.outcomeIndex.astype(int) == 0, g.price.astype(float), 1 - g.price.astype(float))
    ts = g.timestamp.to_numpy(float)
    dp = np.diff(pA, prepend=np.nan)
    jump_t[cid] = ts[np.abs(dp) >= 0.02 - 1e-9]
    any_t[cid] = ts
f_jump, f_sweep = [], []
for r in vc.itertuples():
    cid = tok_cid.get(str(r.a))
    t0 = r.s / 1000.0
    jt = jump_t.get(cid, np.array([]))
    at = any_t.get(cid, np.array([]))
    f_jump.append(bool(len(jt)) and bool((np.abs(jt - t0) <= 10).any()))
    f_sweep.append(bool(len(at)) and bool(((at - t0 >= 0) & (at - t0 <= 3)).any()))
vc["near_jump"] = f_jump
vc["print_after_3s"] = f_sweep
vc["absdV"] = vc.dV.abs() * 100
out = {"value_changes_uncensored": int(len(vc)), "filled_share": round(float(vc.filled.mean()), 3), "tokens": int(vc.a.nunique())}
for nm, g in (("filled", vc[vc.filled]), ("unfilled", vc[~vc.filled])):
    out[nm] = {"n": int(len(g)), "near_2c_jump_10s": round(float(g.near_jump.mean()), 3), "print_within_3s_after": round(float(g.print_after_3s.mean()), 3),
               "absdV_c_median": round(float(g.absdV.median()), 2), "absdV_ge4c_share": round(float((g.absdV >= 4).mean()), 3)}
out["fill_rate_near_jump"] = round(float(vc[vc.near_jump].filled.mean()), 3) if vc.near_jump.any() else None
out["fill_rate_not_near_jump"] = round(float(vc[~vc.near_jump].filled.mean()), 3) if (~vc.near_jump).any() else None
(RES / "censoring_check.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

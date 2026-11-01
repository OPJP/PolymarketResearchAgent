"""Exam-risk check for X230 (iteration 16): the frozen v5 selection on VALIDATE (build constants, as for state.json) with
gp72 recomputed WITHOUT P4e among the group-P members (coefficients and threshold unchanged), i.e. what the frozen rule
scores if P4e had already left the fan-out. Same code path as evaluate(). Output: results/selection_without_p4e.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
import final_rule as fr  # noqa: E402

fr.CONSTANTS = "build"
VAL0, H = 1792540800, 1792713600
C = dict(fr.CALL["build"])
C["league_sum"] = {**C["league_sum"], **fr.DOTA["build"]["league_sum"]}
C["league_n"] = {**C["league_n"], **fr.DOTA["build"]["league_n"]}
iv = [(VAL0, H)]
u = fr._universe(VAL0, H, iv)
fills = fr._wallet_fills(u, H)
traded = set(fills["cid"]) if len(fills) else set()
bad = set(fills["tx"]) if len(fills) else set()
pre, tapes = {}, {}
for r in u.itertuples():
    d = fr._tape(r.cid, int(r.gs_ts), H)
    if d is None or len(d) == 0:
        pre[r.cid] = (0, 0.0, 0)
        continue
    d = d[~d["transactionHash"].isin(bad)].sort_values("timestamp")
    tapes[r.cid] = d
    ts = d["timestamp"].to_numpy(np.int64)
    m = (ts >= r.gs_ts - 3600) & (ts < r.gs_ts)
    pre[r.cid] = (int(m.sum()), float((d["price"].astype(float) * d["size"].astype(float))[m].sum()), int(d["proxyWallet"][m].nunique()))
u[["n", "v", "w"]] = pd.DataFrame([pre.get(c, (0, 0.0, 0)) for c in u["cid"]], index=u.index)
u["y"] = u["cid"].isin(traded).astype(int)
u["grid"] = u["grid_series_id"].notna() if "grid_series_id" in u else False
ev = u.groupby("event_slug").agg(y=("y", "max"), n=("n", "sum"), v=("v", "sum"), w=("w", "sum"), league=("league", "first"),
                                 tier=("league_tier", "first"), grid=("grid", "max"), gs=("gs_ts", "min")).reset_index()
y = ev["y"].to_numpy()
out = {}
for nm, mem in (("all_members", set(fr.V5["members"])), ("without_P4e", {m for m in fr.V5["members"] if not m.startswith("0x4ebc2722")})):
    fr.V5_MEMBERS = mem
    gp = fr._gp72(ev, u, tapes, VAL0, H, iv)
    sc = fr.selection_score_v5(ev, C, gp)
    sel = sc >= fr.V5["build"]["thr"]
    out[nm] = {"auc": round(fr._auc(sc, y), 4), "recall": round(float(y[sel].sum() / max(y.sum(), 1)), 3),
               "lift": round(float(y[sel].mean() / max(y.mean(), 1e-9)), 3) if sel.sum() else None,
               "gp72_mean": round(float(np.mean(gp)), 3), "gp72_gt0": int((gp > 0).sum()), "selected": int(sel.sum())}
out["events"] = int(len(ev))
out["traded"] = int(y.sum())
(Path(fr.__file__).resolve().parents[1] / "results" / "selection_without_p4e.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

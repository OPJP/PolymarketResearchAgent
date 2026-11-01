"""Iteration 12: replication of the state-machine side on BUILD 10-09..22 (development, case by case) without calldata
sizes: decided window -> cheaper; no cluster position -> Binance stand-in posture (volhist S, K, 1.4 x v300); after entry
-> the cluster's held outcome (all after-entry fills, pairing bids included, so this is the no-size variant). Cluster
inventory from activity_<w>.parquet (10-08..22). Reports the after-entry branch by itself (the iteration-12 finding).
    python code12/sm_build.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"


def main():
    acts = []
    for n in ("bosona", "almach", "momoney"):
        a = pd.read_parquet(C / f"activity_{n}.parquet", columns=["timestamp", "type", "side", "outcome", "size", "slug"])
        acts.append(a)
    A = pd.concat(acts)
    A = A[(A.type == "TRADE") & (A.side == "BUY") & A.slug.str.startswith("btc-updown-5m-", na=False)].copy()
    A["st"] = A.slug.str.split("-").str[-1].astype(int)
    A["sgn"] = np.where(A.outcome == "Up", 1.0, -1.0) * A["size"]
    A = A.sort_values("timestamp")
    G = {k: (g.timestamp.to_numpy(), np.cumsum(g.sgn.to_numpy())) for k, g in A.groupby("st")}
    v = pd.read_parquet(C / "it9" / "volhist_build.parquet", columns=["wallet", "st", "en", "b", "is_up", "price", "mid_up", "S", "K", "tau", "v300"])
    v = v[v.b < 1792713600]
    inv = []
    for st, b in zip(v.st.astype(int), v.b.astype(int)):
        g = G.get(st)
        if g is None:
            inv.append(0.0)
            continue
        i = np.searchsorted(g[0], b, side="left") - 1
        inv.append(float(g[1][i]) if i >= 0 else 0.0)
    inv = np.array(inv)
    y = v.is_up.to_numpy() == 1
    mid = v.mid_up.to_numpy().astype(float)
    fb = norm.cdf(np.log(v.S.to_numpy(float) / v.K.to_numpy(float)) / (1.4 * v.v300.to_numpy(float) * np.sqrt(np.maximum(v.tau.to_numpy(float), 1.0))))
    post = fb > mid
    dec = np.abs(mid - 0.5) > 0.4
    cheap = mid < 0.5
    comp = np.where(dec, cheap, np.where(inv == 0, post, inv > 0))
    noown = np.where(dec, cheap, post)
    ok = np.isfinite(mid)
    aft = ok & ~dec & (inv != 0)
    day = (v.b // 86400 * 86400).to_numpy()
    out = {"n": int(ok.sum()), "composite_no_size": round(float((comp == y)[ok].mean()), 4), "no_own_state": round(float((noown == y)[ok].mean()), 4),
           "posture_bn": round(float((post == y)[ok].mean()), 4), "cheaper": round(float((cheap == y)[ok].mean()), 4),
           "after_entry_share": round(float(aft.sum() / ok.sum()), 4), "after_entry_held": round(float(((inv > 0) == y)[aft].mean()), 4),
           "after_entry_posture": round(float((post == y)[aft].mean()), 4), "entry_posture": round(float((post == y)[ok & ~dec & (inv == 0)].mean()), 4),
           "decided_cheaper": round(float((cheap == y)[ok & dec].mean()), 4),
           "after_entry_held_by_day": {str(pd.to_datetime(int(d), unit="s").date()): round(float(((inv > 0) == y)[aft & (day == d)].mean()), 3)
                                       for d in sorted(set(day[aft]))}}
    (HERE.parent / "results" / "iter12_sm_build.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

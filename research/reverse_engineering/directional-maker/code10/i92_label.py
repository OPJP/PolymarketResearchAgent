"""Iteration 10 (I9-2 = X88, step 1): can the quote-unit label be computed from the SHARED recorder (clob_crypto `q`
top-10 snapshots, at most every 200 ms) instead of the own raw recorder? Development block 10-31 14:06-16:30, BTC 5m.
Raw label (code8/a4_ceiling.py, it6/a4_secs_*): an exact-500 add on s at/above the touch in (t-1 s, t] whose price is
still >= the touch. Shared-recorder labels per (window, side, second t):
  L1: in a snapshot of s stamped in (t-1, t], the best bid size rose by exactly 500 (same price) or a new best bid price
      appeared with size exactly 500 (or 500 + the old size at that price);
  L2: L1 at any of the top-3 bid levels (size delta exactly +500 at that price);
  L3: L2 with any multiple of 500 (500, 1000, 1500).
Reports precision / recall / base rates, and the univariate AUC of the Chainlink edge e_cl under each label."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def main():
    lab = pd.read_parquet(C / "it6/a4_secs_1793455600_1793464202.parquet")
    a, b = int(lab.st.min()) - 60, int(lab.st.max()) + 360
    w = F._windows(a, b)
    w = w[w.start_ts.isin(set(lab.st))]
    tok = {}
    for r in w.itertuples(index=False):
        tok[str(r.up_token)] = (int(r.start_ts), 1)
        tok[str(r.down_token)] = (int(r.start_ts), 0)
    snaps = {}
    for r in F._iter_live_xq(a, b, set(tok)):
        if r.get("k") != "q":
            continue
        t_ = str(r.get("a"))
        if t_ not in tok:
            continue
        bids = r.get("b") or []
        if not bids:
            continue
        lv = sorted(((float(p), float(z)) for p, z in bids), reverse=True)[:3]
        snaps.setdefault(t_, []).append((int(r.get("s") or r.get("t")), lv))
    L = {1: set(), 2: set(), 3: set()}
    nsnap = 0
    for t_, v in snaps.items():
        st, sup = tok[t_]
        v.sort(key=lambda x: x[0])
        nsnap += len(v)
        prev = None
        for ms, lv in v:
            if prev is not None:
                pd_ = dict(prev)
                sec = int(np.ceil(ms / 1000.0)) - st  # the second t whose interval (t-1, t] holds ms
                key = (st, sec, sup)
                bp, bz = lv[0]
                d0 = bz - pd_.get(bp, 0.0)
                if abs(d0 - 500) < 0.01 and bp >= prev[0][0]:
                    L[1].add(key)
                for p, z in lv:
                    dz = z - pd_.get(p, 0.0)
                    if abs(dz - 500) < 0.01:
                        L[2].add(key)
                    if dz > 1 and abs(dz / 500 - round(dz / 500)) < 1e-4 and round(dz / 500) >= 1:
                        L[3].add(key)
            prev = lv
    lab["key"] = list(zip(lab.st.astype(int), lab.rel.astype(int), lab.s_up.astype(int)))
    out = {"cells": int(len(lab)), "raw_base_rate": float(lab.y.mean()), "snapshots": nsnap, "tokens": len(snaps)}
    y = lab.y.to_numpy()
    for k in (1, 2, 3):
        yy = lab.key.map(lambda x: x in L[k]).to_numpy().astype(int)
        tp = int(((yy == 1) & (y == 1)).sum())
        out[f"L{k}"] = {"base_rate": float(yy.mean()), "precision": float(tp / max(yy.sum(), 1)), "recall": float(tp / max(y.sum(), 1)),
                        "auc_e_cl_shared_label": auc(yy, lab.e_cl.to_numpy()), "auc_e_cl_raw_label": auc(y, lab.e_cl.to_numpy())}
        # tolerance: the shared label within +-1 s of the raw label
        near = lab.key.map(lambda x: any((x[0], x[1] + d, x[2]) in L[k] for d in (-1, 0, 1))).to_numpy().astype(int)
        out[f"L{k}"]["recall_pm1s"] = float(((near == 1) & (y == 1)).sum() / max(y.sum(), 1))
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_i92_label.json", "w"), indent=1)


if __name__ == "__main__":
    main()

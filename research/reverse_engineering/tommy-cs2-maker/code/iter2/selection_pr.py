"""PR curve + pre-registered precision threshold (BUILD precision >= 0.85) for event-level selection scores."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, SPLIT, auc  # noqa: E402
from selection_event import league_score  # noqa: E402
from sklearn.linear_model import LogisticRegression

def prec_thr(sb, yb, pmin=0.85):
    best = None
    for t in np.unique(sb)[::-1]:
        sel = sb >= t
        if sel.sum() >= 5 and yb[sel].mean() >= pmin: best = t
    return best

def main():
    ev = pd.read_parquet(OUT / "events_sel.parquet")
    b, v = ev[ev.gs < SPLIT].copy(), ev[ev.gs >= SPLIT].copy()
    b["s_lg"] = league_score(b, b); v["s_lg"] = league_score(b, v)
    act = ["e_pre_n", "e_pre_v", "e_pre_w"]
    X = lambda d, cols: np.column_stack([np.log1p(d[c].fillna(0).to_numpy()) if c in act else d[c].to_numpy() for c in cols])
    out = {}
    for name, cols in (("S_lg", None), ("B_act", act), ("S_lg_act", act + ["s_lg"])):
        if cols is None: sb, sv = b.s_lg.to_numpy(), v.s_lg.to_numpy()
        else:
            m = LogisticRegression(max_iter=5000).fit(X(b, cols), b.y); sb = m.predict_proba(X(b, cols))[:, 1]; sv = m.predict_proba(X(v, cols))[:, 1]
        yb, yv = b.y.to_numpy(), v.y.to_numpy(); t = prec_thr(sb, yb)
        r = {"val_auc": round(auc(sv, yv), 4), "thr_prec85": None if t is None else round(float(t), 4)}
        if t is not None:
            sel = sv >= t; prec = yv[sel].mean() if sel.sum() else np.nan
            r |= {"val_selected": int(sel.sum()), "val_recall": round(float(yv[sel].sum() / yv.sum()), 3), "val_precision": round(float(prec), 3), "val_lift": round(float(prec / yv.mean()), 2),
                  "build_recall": round(float(yb[sb >= t].sum() / yb.sum()), 3)}
        # PR curve on VALIDATE (descriptive)
        o = np.argsort(-sv); cy = np.cumsum(yv[o]); k = np.arange(1, len(yv) + 1)
        r["val_pr"] = {f"rec{int(rr*100)}": round(float((cy / k)[np.searchsorted(cy, rr * yv.sum())]), 3) for rr in (0.5, 0.6, 0.7, 0.8)}
        out[name] = r
    json.dump(out, open(RES / "results/selection_pr.json", "w"), indent=1)
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()

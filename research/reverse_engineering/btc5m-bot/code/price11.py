"""Iteration 11 (X92 / X96 follow-up): taken vs skipped among Binance USD-M PRICE-level events only (the strongest event class,
~29-30% taken). Rebuilds onset11's event tables for A and C (saved to .cache/re/btc5m-bot/it11/onset_{A,C}.parquet for the
next iterations) and reports univariate AUCs on C (and A) of every event feature, including the operator's recent decisions
(own state, reported apart), time in window, o's ask level, the spread, venue agreement, activity and the normalizer terms.
Usage: python price11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, onset11
from sklearn.metrics import roc_auc_score

C = L.C


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    res = {}
    for nm in ("A", "C"):
        a, b = stale9.IV[nm]
        ev, dec, Tm, allev = onset11.build11(a, b, lost)
        ev.to_parquet(C + f"/it11/onset_{nm}.parquet")
        pe = ev[ev.cls == "PRICE"].copy()
        pe["absask"] = (pe.ask - 0.5).abs(); pe["absbp"] = pe.bp.abs()
        feats = ["absbp", "absask", "ask", "rel", "act", "agree", "spread_bp", "unch150", "pct_win", "rec30", "rec60"] + \
                [f"z_rv_{h}" for h in onset11.HS] + [f"n_{h}" for h in onset11.HS] + [f"np_{h}" for h in onset11.HS] + \
                [f"mv_{D}" for D in onset11.DS_] + [f"cf_ok_{D}" for D in onset11.DS_] + [f"cf_by_{D}" for D in onset11.DS_]
        row = {"n": int(len(pe)), "P": round(float(pe.y.mean()), 4)}
        for f in feats:
            v = pe[f].astype(float).fillna(pe[f].astype(float).median())
            if pe.y.nunique() == 2 and v.nunique() > 1:
                row[f] = round(float(roc_auc_score(pe.y, v)), 4)
        # P(take) by time in window and by ask level
        row["P_by_rel"] = {lab: [round(float(pe.y[s].mean()), 4), int(s.sum())] for lab, s in
                           (("5-60", pe.rel < 60), ("60-180", (pe.rel >= 60) & (pe.rel < 180)), ("180-240", (pe.rel >= 180) & (pe.rel < 240)), ("240-285", pe.rel >= 240)) if s.any()}
        row["P_by_ask"] = {lab: [round(float(pe.y[s].mean()), 4), int(s.sum())] for lab, s in
                           (("<0.3", pe.ask < 0.3), ("0.3-0.5", (pe.ask >= 0.3) & (pe.ask < 0.5)), ("0.5-0.7", (pe.ask >= 0.5) & (pe.ask < 0.7)), (">=0.7", pe.ask >= 0.7)) if s.any()}
        row["P_by_rec30(own)"] = {lab: [round(float(pe.y[s].mean()), 4), int(s.sum())] for lab, s in
                                  (("0", pe.rec30 == 0), ("1-5", (pe.rec30 >= 1) & (pe.rec30 <= 5)), ("6+", pe.rec30 >= 6)) if s.any()}
        res[nm] = row
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:6000])


if __name__ == "__main__":
    main(sys.argv[1])

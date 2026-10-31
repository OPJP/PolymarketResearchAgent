"""Iteration 8: freeze the decision-level hazard of final_rule (_live_hazard) on development interval B = 10-31
16:04:30-16:33:00 UTC (exam-input feeds btc5m_xclob / btc5m_xven), then score the frozen constants on the later development
interval C = 16:33-17:55 (never used for fitting). Prints the constants pasted into final_rule.HAZ_*_COEF and the C metrics.
Usage: python fit_hazard8.py fit | test"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn.linear_model import LogisticRegression
import final_rule as FR
from live8 import fills_for, OWN

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "fit":
        own, a, b = OWN["B"]
        f, _, _ = fills_for(own, a, b)
        y, F, B, U = FR._live_hazard_data(f, a + 30, b)
        out = {"n": int(len(y)), "pos": int(y.sum())}
        for nm, X in (("full", F), ("base", B)):
            lr = LogisticRegression(C=1.0, max_iter=5000).fit(X, y)
            out[nm] = [round(float(lr.intercept_[0]), 6)] + [round(float(c), 6) for c in lr.coef_[0]]
        print(json.dumps(out))
    else:
        own, a, b = OWN["C"]
        f, _, _ = fills_for(own, a, b)
        r = FR._live_hazard(f, a, b)
        print(json.dumps(r))
        json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "hazard8_frozen_C.json"), "w"), indent=1)

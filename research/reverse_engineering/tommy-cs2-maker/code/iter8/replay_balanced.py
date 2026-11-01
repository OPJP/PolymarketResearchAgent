"""Iteration 8 (outcome item): one pre-specified executable variant of the maker replay, scored on VALIDATE through
final_rule.evaluate() with only _replay swapped. "Balanced pair ladder" (the wallet's economics: buy both outcomes,
keep the pair cost below a cap, quote the side it is short of): every 10 s, fair = last public print (2-s latency);
bid on outcome o at floor(fair_o x 100) / 100 - 0.01 only if (a) its inventory in o does not exceed the other outcome's
by >= one order size and (b) bid + average cost of the other outcome <= 0.98 when it holds the other outcome; strict
trade-through fills on the public taker tape, at most one order size per 10-s step. Settlement PnL per market.
Output: results/replay_balanced_validate.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
import final_rule as F  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
CAP = 0.98


def replay_balanced(d, gs, pay0, delta=0.0, levels=1, req=10, lat=2, size=100.0):
    if d is None or len(d) < 5:
        return 0.0
    ts = d["timestamp"].to_numpy(float)
    oi = d["outcomeIndex"].astype(int).to_numpy()
    side = d["side"].to_numpy()
    pr = d["price"].astype(float).to_numpy()
    sz = d["size"].astype(float).to_numpy()
    p0 = np.where(oi == 0, pr, 1 - pr)
    sh, cs = np.zeros(2), np.zeros(2)
    for t0 in np.arange(max(gs, ts[0]), ts[-1], req):
        k = np.searchsorted(ts, t0 - lat, side="right") - 1
        lo, hi = np.searchsorted(ts, t0, side="right"), np.searchsorted(ts, t0 + req, side="right")
        if k < 0 or hi <= lo:
            continue
        for o, fair in ((0, p0[k]), (1, 1 - p0[k])):
            q = round(np.floor(fair * 100 + 1e-9) / 100 - 0.01, 2)
            if q < 0.01 or q > 0.98:
                continue
            if sh[o] - sh[1 - o] >= size:
                continue
            if sh[1 - o] > 0 and q + cs[1 - o] / sh[1 - o] > CAP + 1e-9:
                continue
            m = slice(lo, hi)
            thr = ((oi[m] == o) & (side[m] == "SELL") & (pr[m] < q - 1e-9)) | ((oi[m] != o) & (side[m] == "BUY") & (pr[m] > 1 - q + 1e-9))
            f = min(size, float(sz[m][thr].sum()))
            if f > 0:
                sh[o] += f
                cs[o] += f * q
    return float(sh[0] * pay0 + sh[1] * (1 - pay0) - cs.sum())


def main():
    F.CONSTANTS = "build"
    F._replay = replay_balanced
    r = F.evaluate(1792540800, 1792713600)
    keep = {k: r.get(k) for k in ("pnl_corr_pearson", "pnl_corr_spearman", "pnl_markets", "pnl_baseline_prints_pearson",
                                  "pnl_baseline_prints_spearman", "pnl_corr_partial_given_prints", "selection_auc")}
    print(json.dumps(keep, indent=1))
    json.dump(keep, open(RES / "replay_balanced_validate.json", "w"), indent=1)


if __name__ == "__main__":
    main()

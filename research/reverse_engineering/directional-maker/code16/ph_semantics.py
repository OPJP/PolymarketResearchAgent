"""iteration 16, X185 step 1 (information panel I15-1): what is a CLOB prices-history point? One development unit with a
recorded book: the BTC 4h window starting 10-31 12:00 UTC (shared recorder clob_crypto 'q' top-10 books and 'x' trades,
server ms). For each fidelity-1 point (t, p) of the Up token: |p - X| for X = the book mid at t - 60 / t - 30 / t /
t + 30 / t + 60 s, the mean mid over [t - 60, t) and [t, t + 60), and the last trade at or before t. The smallest median
error names the point's meaning and its point-in-time lag.
    python ph_semantics.py"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

SLUG, A, B = "btc-updown-4h-1793448000", 1793448000, 1793462400
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
m = fetch_windows([SLUG])[SLUG] if SLUG in fetch_windows([SLUG]) else list(fetch_windows([SLUG]).values())[0]
toks = json.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m["clobTokenIds"]
outs = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else m["outcomes"]
up = str(toks[outs.index("Up")])
pts, _ = PolymarketData().price_history(up, A, B, fidelity_minutes=1)
bk, tr = [], []
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as fr  # noqa: E402  (tolerant gzip-member reader, development blocks only)
for r in fr._iter_live_xq(A, B, {up}):
    if not r.get("s"):
        continue
    if r.get("k") == "q" and str(r.get("a")) == up:
        b_, o_ = r.get("b") or [], r.get("o") or []
        if b_ and o_:
            bk.append((int(r["s"]) / 1000.0, (max(float(x[0]) for x in b_) + min(float(x[0]) for x in o_)) / 2))
    elif r.get("k") == "x" and str(r.get("a")) == up:
        tr.append((int(r["s"]) / 1000.0, float(r["p"])))
bk.sort(); tr.sort()
bt = np.array([x[0] for x in bk]); bm = np.array([x[1] for x in bk])
tt = np.array([x[0] for x in tr]); tp = np.array([x[1] for x in tr])


def at(ts, vs, t):
    i = np.searchsorted(ts, t, side="right") - 1
    return vs[i] if i >= 0 and t - ts[i] < 120 else np.nan


def mean_over(t0, t1):
    i0, i1 = np.searchsorted(bt, t0), np.searchsorted(bt, t1)
    return float(np.mean(bm[i0:i1])) if i1 > i0 else np.nan


rows = {k: [] for k in ("mid_t-60", "mid_t-30", "mid_t", "mid_t+30", "mid_t+60", "mean_mid_prev_60", "mean_mid_next_60", "last_trade_t", "last_trade_t+60")}
for t, p in pts:
    if not (A + 60 <= t <= B - 60):
        continue
    for k, v in (("mid_t-60", at(bt, bm, t - 60)), ("mid_t-30", at(bt, bm, t - 30)), ("mid_t", at(bt, bm, t)), ("mid_t+30", at(bt, bm, t + 30)),
                 ("mid_t+60", at(bt, bm, t + 60)), ("mean_mid_prev_60", mean_over(t - 60, t)), ("mean_mid_next_60", mean_over(t, t + 60)),
                 ("last_trade_t", at(tt, tp, t)), ("last_trade_t+60", at(tt, tp, t + 60))):
        if np.isfinite(v):
            rows[k].append(abs(p - v))
out = {"slug": SLUG, "points": len(pts), "book_records": len(bk), "trades": len(tr),
       "median_abs_err": {k: (round(float(np.median(v)), 4) if v else None) for k, v in rows.items()},
       "share_within_0.005": {k: (round(float(np.mean(np.array(v) <= 0.005)), 3) if v else None) for k, v in rows.items()},
       "n": {k: len(v) for k, v in rows.items()}}
print(json.dumps(out, indent=1))
(HERE.parent / "results/iter16_ph_semantics.json").write_text(json.dumps(out, indent=1))

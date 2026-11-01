"""Examiner round 2: run the frozen final_rule.evaluate() unchanged on lot f1.

Mechanical settings only (no file in code/ is edited):
  * final_rule.ALLOW_SEALED = True (the examiner's switch);
  * POLYREA_CACHE_DIR = .cache/exam/directional-maker (r2_common), so the shared HTTP cache never holds the lot;
  * cl_source.CLDIR and r9_nonbtc.CACHE point into .cache/exam/directional-maker, so the Chainlink endpoint values and
    the Binance 1-s klines of the sealed lot are not written into the reverse engineer's cache before the release;
  * capture wrappers around build_panel (5m and 15m), features2.Spot and sel2.day_prints save the rule's own
    intermediate frames to .cache/exam/directional-maker/ev/ for the examiner's independent metrics (they call the
    original functions and return their results unchanged).
python exam/r2_run_evaluate.py
"""
from __future__ import annotations

import json
import pickle
import time

import numpy as np
import pandas as pd

from r2_common import EXC, LOT, LOT_START, LOT_END, RES

import final_rule as fr  # noqa: E402
import cl_source  # noqa: E402
import r9_nonbtc  # noqa: E402
import features2  # noqa: E402
import features15  # noqa: E402
import sel2  # noqa: E402

EV = EXC / "ev"
EV.mkdir(parents=True, exist_ok=True)
fr.ALLOW_SEALED = True
cl_source.CLDIR = EXC / "cl"
r9_nonbtc.CACHE = EXC / "bn1s_eval"

_orig_bp, _orig_bp15, _orig_dp = fr.build_panel, features15.build_panel, sel2.day_prints
_OrigSpot = fr.Spot


class SpotCap(_OrigSpot):
    def __init__(self, sec, px):
        super().__init__(sec, px)
        pd.DataFrame({"sec": np.asarray(sec, dtype=np.int64), "px": np.asarray(px, dtype=float)}).to_parquet(EV / "spot_btc.parquet", index=False)


def bp5(w, sp, tk, mk):
    p = _orig_bp(w, sp, tk, mk)
    w.to_parquet(EV / "w5.parquet", index=False)
    t = tk.copy()
    for c in ("cid", "asset", "wallet", "side"):
        t[c] = t[c].astype(str)
    t.to_parquet(EV / "clean5.parquet", index=False)
    m = mk.copy()
    m.to_parquet(EV / "mk5.parquet", index=False)
    p.to_parquet(EV / "panel5.parquet", index=False)
    return p


def bp15(w, sp, tk, mk):
    p = _orig_bp15(w, sp, tk, mk)
    w.to_parquet(EV / "w15.parquet", index=False)
    t = tk.copy()
    for c in ("cid", "asset", "wallet", "side"):
        t[c] = t[c].astype(str)
    t.to_parquet(EV / "clean15.parquet", index=False)
    mk.to_parquet(EV / "mk15.parquet", index=False)
    p.to_parquet(EV / "panel15.parquet", index=False)
    return p


def dp(d, w, sp, mk_tx, cw, neg_frac, rng, tk=None, pan=None):
    te, pan_d, wd = _orig_dp(d, w, sp, mk_tx, cw, neg_frac, rng, tk=tk, pan=pan)
    te.to_parquet(EV / f"sel_te_{d}.parquet", index=False)
    wd.to_parquet(EV / f"sel_wd_{d}.parquet", index=False)
    if tk is not None:
        t = tk.copy()
        for c in ("cid", "asset", "wallet", "side"):
            t[c] = t[c].astype(str)
        t.to_parquet(EV / f"sel_tk_{d}.parquet", index=False)
    with open(EV / "sel_mk_tx.pkl", "wb") as f:
        pickle.dump(set(mk_tx), f)
    return te, pan_d, wd


fr.build_panel = bp5
features15.build_panel = bp15
fr.Spot = SpotCap
sel2.day_prints = dp


def main():
    t0 = time.time()
    res = fr.evaluate(LOT_START, LOT_END, intervals=[list(x) for x in LOT])
    res["_examiner"] = {"secs": round(time.time() - t0, 1), "intervals": LOT, "allow_sealed": True,
                        "cache_dir": str(EXC), "note": "frozen evaluate() run unchanged; capture wrappers only"}
    (RES / "exam_r2_evaluate.json").write_text(json.dumps(res, indent=1, default=str))
    print("done", round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    main()

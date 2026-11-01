"""iteration 17, T16 (pre-registered in NOTES.md 11:33 UTC): G3 = R8c + a trailing 2-h realised-vol gate to the cheaper
token for non-decided BTC 5m fills (threshold = BUILD fills' 75th percentile); STUDY / VALIDATE per fill vs R8c."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code"))
import inform_gate as ig  # noqa: E402
import side_sm  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def spot():
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).dropna().drop_duplicates("sec").sort_values("sec")
    sec = s.sec.to_numpy(np.int64)
    lp = np.log(s.px.to_numpy(float))
    r2 = np.r_[0.0, np.diff(lp) ** 2]
    r2[np.r_[False, np.diff(sec) > 5]] = 0.0  # no returns across gaps
    return sec, np.cumsum(r2)


def trv(sec, cs, t):
    t = np.asarray(t, np.int64)
    j1 = np.searchsorted(sec, t - 2, side="right") - 1
    j0 = np.searchsorted(sec, t - 7202, side="right") - 1
    ok = (j1 >= 0) & (j0 >= 0) & (sec[np.clip(j1, 0, None)] >= t - 60)
    return np.where(ok, np.sqrt(np.maximum(cs[np.clip(j1, 0, None)] - cs[np.clip(j0, 0, None)], 0)), np.nan)


def main():
    sec, cs = spot()
    Fb = ig.build_fills()
    rvb = trv(sec, cs, Fb.ts.to_numpy())
    thr = float(np.nanquantile(rvb, 0.75))
    V = ig.lot_fills()
    rv = trv(sec, cs, V.ts.to_numpy())
    y = V.y.to_numpy()
    mid = V.mid_up.to_numpy()
    dec = np.abs(mid - 0.5) > 0.4
    cheap = mid < 0.5
    post = V.post_up.to_numpy()
    op = side_sm.nyse_open_window(V.st.to_numpy(), V.en.to_numpy())
    r8c = np.where(op, cheap, np.where(dec, cheap, post))
    hi = np.isfinite(rv) & (rv > thr)
    g3 = np.where(op | dec, cheap, np.where(hi, cheap, post))
    out = {"threshold_rv2h": thr, "build_rv_coverage": float(np.isfinite(rvb).mean())}
    for sp in ("study", "validate"):
        m = (V.sp == sp).to_numpy()
        out[sp] = {"n": int(m.sum()), "rv_coverage": round(float(np.isfinite(rv[m]).mean()), 3), "share_hi": round(float(hi[m].mean()), 3),
                   "r8c": round(float((r8c == y)[m].mean()), 4), "g3": round(float((g3 == y)[m].mean()), 4),
                   "in_hi_nondecided": {"n": int((m & hi & ~dec & ~op).sum()),
                                        "posture": round(float((post == y)[m & hi & ~dec & ~op].mean()), 3) if (m & hi & ~dec & ~op).any() else None,
                                        "cheaper": round(float((cheap == y)[m & hi & ~dec & ~op].mean()), 3) if (m & hi & ~dec & ~op).any() else None}}
    out["adopt"] = bool(out["validate"]["g3"] - out["validate"]["r8c"] >= 0.01 and out["study"]["g3"] - out["study"]["r8c"] >= -0.01)
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter17_vol_gate.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

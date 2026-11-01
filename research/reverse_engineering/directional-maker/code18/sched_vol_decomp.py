"""iteration 18, T1 follow-up (post hoc, descriptive; not a selection): separates the profile's effect from the k change
in T1 (S1 uses k 1.0, R8 k 1.4): trailing posture at k 1.0 vs the profile posture at k 1.0 on the lot (STUDY case by
case, VALIDATE aggregate and halves); and the sigma needed in the open window (share of open fills where the posture
picks the cheap token as a function of the multiplier on the profile)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code"))
import sched_vol as sv  # noqa: E402
import side_sm  # noqa: E402

C = sv.C


def main():
    T = pd.read_parquet(C / "it18" / "slot_rv.parquet")
    PV = sv.profiles(T)
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet", columns=["st", "en", "b", "is_up", "mid_up", "cl", "Kg", "tau_cl", "S", "K", "tau",
                                                                   "v300", "sp"])
    V = V[((V.en - V.st) == 300) & np.isfinite(V.mid_up)].reset_index(drop=True)
    y = (V.is_up == 1).to_numpy()
    mid = V.mid_up.to_numpy(float)
    dec = np.abs(mid - 0.5) > 0.4
    cheap = mid < 0.5
    hascl = np.isfinite(V.cl.to_numpy(float))
    x = np.where(hascl, np.log(V.cl / V.Kg), np.log(V.S / V.K))
    tl = np.where(hascl, V.tau_cl, V.tau).astype(float)
    v = V.v300.to_numpy(float)
    P = sv.prof_col(PV["utc_N28"], V.st.to_numpy())
    op = side_sm.nyse_open_window(V.st.to_numpy(), V.en.to_numpy())
    out = {}
    mt = None
    for spn in ("study", "validate"):
        m = (V.sp == spn).to_numpy()
        rec = {}
        for nm, sig in (("trail_k1.0", 1.0 * v), ("trail_k1.4", 1.4 * v), ("prof_max_k1.0", 1.0 * np.maximum(v, P)),
                        ("prof_max_k1.4", 1.4 * np.maximum(v, P))):
            s_, _ = sv.side(x, tl, sig, mid, dec, cheap)
            rec[nm] = {"all": sv.acc(s_, y, m), "outside_open": sv.acc(s_, y, m & ~op)}
            if spn == "validate":
                bb = V.b.to_numpy()
                mt = (int(bb[m].min()) + int(bb[m].max())) // 2
                rec[nm]["half1"] = sv.acc(s_, y, m & (bb < mt))
                rec[nm]["half2"] = sv.acc(s_, y, m & (bb >= mt))
        # open window: share of fills where the posture says cheap, by multiplier c on max(v300, P)
        rec["open_cheap_pick_by_mult"] = {}
        for c in (1, 2, 3, 5, 8):
            s_, _ = sv.side(x, tl, c * np.maximum(v, P), mid, dec, cheap)
            mm = m & op & ~dec
            rec["open_cheap_pick_by_mult"][str(c)] = {"n": int(mm.sum()), "picks_cheap": round(float((s_ == cheap)[mm].mean()), 3) if mm.any() else None}
        rec["open_ratio_P_over_v300_median"] = round(float(np.median((P / v)[m & op])), 2) if (m & op).any() else None
        out[spn] = rec
    (HERE.parent / "results" / "iter18_sched_vol_decomp.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

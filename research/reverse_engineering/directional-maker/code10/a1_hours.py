"""Iteration 10 (A1 = X97, follow-up): region D (Chainlink and the last clean print disagree on the favourite) by UTC hour and
by hours since the daily ~01:00 UTC restart, on the lot (STUDY case by case, VALIDATE aggregate by hour) and per window
on 10-31 00-06 (development). Same pre-registered proxies as a1_score.py / a1_0006.py. Descriptive."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(ROOT))
import a1_score as A  # noqa: E402
import cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def region(h):
    x = np.log(h.cl.to_numpy(float) / h.K.to_numpy(float))
    m = h.mid_up.to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(m) & (x != 0)
    D = ok & ((x > 0) != (m > 0.5))
    hit = (x > 0) == (h.is_up.to_numpy() == 1)
    return D, hit


def main():
    ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
    K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
    clv = cl_source._cache()
    out = {}
    for sp, fn in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
        v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "wallet", "b", "st", "en", "is_up", "mid_up"])
        t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
        t["tx"] = t.tx.str.lower()
        t = t.drop_duplicates("tx").set_index("tx")
        v["txh"] = v.txh.str.lower()
        v["T_hat"] = A.that(v.txh.map(t.sign_ms), v.b.astype(float) * 1000)
        v["cl"] = ((v.T_hat - 1432) // 1000).astype(np.int64).map(lambda s: clv.get(int(s), np.nan))
        v["K"] = v.st.map(K)
        h = v.dropna(subset=["cl", "K"]).copy()
        D, hit = region(h)
        hr = (h.b.to_numpy() // 3600) % 24
        out[sp] = {"by_utc_hour": {int(k): [int((D & (hr == k)).sum()), float(np.mean(hit[D & (hr == k)])) if (D & (hr == k)).any() else None] for k in range(24)},
                   "hour_00_utc": [int((D & (hr == 0)).sum()), float(np.mean(hit[D & (hr == 0)])) if (D & (hr == 0)).any() else None],
                   "hours_01_06": [int((D & (hr >= 1) & (hr < 6)).sum()), float(np.mean(hit[D & (hr >= 1) & (hr < 6)])) if (D & (hr >= 1) & (hr < 6)).any() else None],
                   "n_windows_D": int(h[D].st.nunique())}
        if sp == "study":
            g = pd.DataFrame({"st": h.st.to_numpy()[D], "hit": hit[D]})
            out[sp]["per_window_D"] = g.groupby("st").hit.agg(["size", "mean"]).sort_values("size", ascending=False).head(12).reset_index().values.tolist()
            # window-clustered accuracy: mean of per-window means
            out[sp]["window_mean_D"] = float(g.groupby("st").hit.mean().mean())
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_a1_hours.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

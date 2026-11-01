"""iteration 18, T3 robustness (descriptive): law E2 vs the posture per hour on the two 11-01 full-depth blocks, with the
same frozen beta and branches as code18/event_law.py (no new choice)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import event_law as el  # noqa: E402
import e7_e2  # noqa: E402


def main():
    E0, M0 = el.fut_mid(el.FIT[0] - 120, el.FIT[1] + 60)
    secs, cl, P = el.publishes(*el.FIT)
    X = el.design(E0, M0, secs)
    y = np.array([cl[s] - cl[s - 1] for s in secs])
    ok = np.all(np.isfinite(X), axis=1)
    beta, *_ = np.linalg.lstsq(np.c_[np.ones(ok.sum()), X[ok]], y[ok], rcond=None)
    out = {}
    for name in ("freeze_1101_0700_0915", "confirm_1101_0915_1200"):
        tms, hit, ph = e7_e2.e2_labels(name, beta, need_posture=True)
        hr = tms // 3600000
        rec = {}
        for h in np.unique(hr):
            m = hr == h
            rec[pd.Timestamp(int(h) * 3600, unit="s").strftime("%H:00")] = {"n": int(m.sum()), "E2": round(float(hit[m].mean()), 3), "posture": round(float(ph[m].mean()), 3)}
        out[name] = rec
    (HERE.parent / "results" / "iter18_e2_hours.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

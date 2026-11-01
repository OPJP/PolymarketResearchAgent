"""Iteration 10 (A1 / X46 follow-up): the Chainlink 1-s noise regime by day and hour, from every run of >= 10 consecutive
cached Chainlink seconds (endpoint cache + the 10-31 00-06 noise runs; development and released lot days only).
Per run: sd of 1-s changes and lag-1 autocorrelation of the changes; reported per UTC day and, for 10-31 00-06, per hour."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source  # noqa: E402


def main():
    c = pd.Series(cl_source._cache()).sort_index()
    c = c[(c.index >= 1791504000) & (c.index < 1793426400)]
    idx = c.index.to_numpy()
    brk = np.r_[0, np.where(np.diff(idx) != 1)[0] + 1, len(idx)]
    runs = []
    for a, b in zip(brk[:-1], brk[1:]):
        if b - a >= 10:
            v = c.iloc[a:b].to_numpy()
            d = np.diff(v)
            ac = float(np.corrcoef(d[:-1], d[1:])[0, 1]) if len(d) > 4 and d.std() > 0 else np.nan
            runs.append((int(idx[a]), int(b - a), float(d.std()), ac))
    R = pd.DataFrame(runs, columns=["start", "n", "sd", "ac1"])
    R["day"] = pd.to_datetime(R.start, unit="s").dt.strftime("%m-%d")
    R["hour"] = (R.start // 3600) % 24
    out = {"runs": int(len(R)),
           "by_day": {d: {"runs": int(len(g)), "sd_median": float(g.sd.median()), "ac1_median": float(g.ac1.median())} for d, g in R.groupby("day")},
           "1031_by_hour": {int(h): {"runs": int(len(g)), "sd": [round(x, 2) for x in g.sd], "ac1": [round(x, 2) for x in g.ac1]}
                            for h, g in R[R.start >= 1793404800].groupby("hour")}}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_cl_noise.json", "w"), indent=1)


if __name__ == "__main__":
    main()

"""Iteration 10 (I9-3 = X89, step 3), pre-registered 23:08 UTC before any value is read: does a public data-quality
excursion (Chainlink 1-s noise, Chainlink - Binance divergence) precede the BTC 5m switch-offs?
Switches (BTC 5m off-runs >= 1 h starting in development data since 10-16, plus the 10-31 16:53:54 switch-off; 10-29 is
VALIDATE and excluded): 10-17 20:35, 10-17 22:30, 10-18 22:15, 10-23 20:40, 10-24 22:30, 10-31 16:53 UTC.
For each switch S: six 30-s runs of consecutive Chainlink seconds starting at S - 120 + 20 k minutes (k = 0..5); controls:
the same clock times 3 and 4 days earlier (both Mon-Thu for every switch above except 10-31's -3 d = Wed 10-28, kept as a
market-only aggregate). Measures per run: sd of 1-s changes, lag-1 autocorrelation, mean |CL - Binance spot| (basis
change). Signature: switch hours show a noise or divergence excursion vs their controls; calendar switches do not.
This script only appends the stamps to the fetch queue (priority 1.5, after the BUILD BTC 5m stamps)."""
import calendar
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
SW = ["2026-10-17 20:35", "2026-10-17 22:30", "2026-10-18 22:15", "2026-10-23 20:40", "2026-10-24 22:30", "2026-10-31 16:53"]


def ts(s):
    return calendar.timegm(pd.Timestamp(s).timetuple())


rows = []
for s in SW:
    S = ts(s)
    for lab, off in (("switch", 0), ("ctrl3", 3 * 86400), ("ctrl4", 4 * 86400)):
        for k in range(6):
            a = S - off - 7200 + 1200 * k
            for i in range(30):
                rows.append((a + i, f"i93_{s}_{lab}"))
st = pd.DataFrame(rows, columns=["stamp", "split"])
st["pri"] = 1.5
st["ord"] = np.arange(len(st))
q = pd.read_parquet(C / "a1_queue10.parquet")
q = pd.concat([q, st]).drop_duplicates("stamp")
q["pri"] = q.pri.astype(float)
q = q.sort_values(["pri", "ord"], kind="stable")
q.to_parquet(C / "a1_queue10.parquet", index=False)
st.to_parquet(C / "i93_switch_stamps.parquet", index=False)
print("added", len(st), "queue", len(q))

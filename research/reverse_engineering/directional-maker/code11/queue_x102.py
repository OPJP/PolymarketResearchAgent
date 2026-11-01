"""Iteration 11 (information panel I10-2 = X102): queue of Chainlink stamps for print-level selection on the lot with
the settlement-grade reference. Pre-registered sample: on every lot day (10-23..30) the consecutive window pairs (i, i+1)
with i = 0, 16, 32, ..., 272 (18 pairs a day, 288 windows in all); every even second tau in [S_i - 65, S_i + 300); one
crypto-price request returns the values at tau and tau + 300, so window i+1's [S_{i+1} - 65, E_{i+1}) is covered too.
Writes .cache/re/directional-maker/a1_queue11.parquet (stamp).
    python code11/queue_x102.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
C = Path(__file__).resolve().parents[4] / ".cache" / "re" / "directional-maker"
days = [1792713600 + 86400 * k for k in range(8)]
st = []
for d in days:
    for i in range(0, 288, 16):
        S = d + 300 * i
        st += list(range(S - 65, S + 300, 2))
q = pd.DataFrame({"stamp": np.array(st, dtype=np.int64)})
q.to_parquet(C / "a1_queue11.parquet")
print(len(q), "requests (each also returns tau + 300)")

"""Iteration 17 (X167 = information panel P4, steps 1-2 in part): is the capture collector's Binance clock stable? Per UTC hour of the
capture days 10-17..22 (local copies it13/hf_dl/btc_<day>.parquet), the median and q10 / q90 of receivedTimestampMs - exchangeTimestampMs
of spot TRADE rows (the transit the frozen exam route fixes at 131 ms). Usage: python transit17.py"""
import os, json
import numpy as np, pandas as pd, pyarrow.parquet as pq
A = os.environ["RE16_SCRATCH"] + "/it13/hf_dl"
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
res = {}
for day in ("2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"):
    fn = f"{A}/btc_{day}.parquet"
    if not os.path.exists(fn):
        res[day] = "missing"; continue
    t = pq.read_table(fn, columns=["type", "receivedTimestampMs", "exchangeTimestampMs"], filters=[("type", "==", "trade")])
    r = t.column("receivedTimestampMs").to_numpy().astype(np.int64); e = t.column("exchangeTimestampMs").to_numpy().astype(np.int64)
    lag = r - e; hh = (e // 3600000) % 24
    d = {}
    for h in range(24):
        x = lag[hh == h]
        if len(x):
            d[h] = [int(np.median(x)), int(np.quantile(x, 0.1)), int(np.quantile(x, 0.9)), int(len(x))]
    res[day] = d
    med = [v[0] for v in d.values()]
    print(day, "hourly median transit min/med/max", min(med), int(np.median(med)), max(med), flush=True)
    del t, r, e, lag
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/transit17.json", "w"), indent=1)

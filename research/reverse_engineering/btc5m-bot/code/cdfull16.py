"""Iteration 16 (panel iter15 mechanics P2 = X157, information P2 = X152 input): the COMPLETE decision record of the capture
days: V2 matchOrders calldata of EVERY operator taker tx of 10-20..22 (fills.parquet role T), decoded fields only (calldata.py),
one parquet per day in the session scratchpad it16/ (not .cache: the strategy cache is at its 1.5 GB cap). Txs already decoded in
calldata_sample.parquet / it15 cl_orders are skipped. Polite: calldata.fetch_txs (25 calls per POST, <= 3 POST/s, 2 threads).
Usage: python cdfull16.py [days comma-separated]"""
import os, sys, time
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calldata

S = os.environ.get("RE16_SCRATCH")
days = (sys.argv[1] if len(sys.argv) > 1 else "10-20,10-21,10-22").split(",")
f = pd.read_parquet(".cache/re/btc5m-bot/fills.parquet", columns=["tx", "role", "start_ts"])
f = f[f.role == "T"].copy()
f["day"] = pd.to_datetime(f.start_ts, unit="s").dt.strftime("%m-%d")
have = set(pd.read_parquet(".cache/re/btc5m-bot/calldata_sample.parquet", columns=["tx"]).tx.str.lower())
have |= set(pd.read_parquet(S + "/it15/cl_orders.parquet", columns=["tx"]).tx.str.lower())
for d in days:
    out = f"{S}/it16/cdfull_{d}.parquet"
    if os.path.exists(out):
        print("exists", out, flush=True); continue
    need = sorted(set(f[f.day == d].tx.str.lower()) - have)
    print(d, "need", len(need), flush=True)
    t0 = time.time()
    rows = calldata.fetch_txs(need, threads=2, log_every=200)
    df = calldata.to_frame(rows)
    df.to_parquet(out, index=False)
    print(d, "saved", len(df), "rows", df.tx.nunique(), "txs", round(time.time() - t0), "s", flush=True)
print("DONE", flush=True)

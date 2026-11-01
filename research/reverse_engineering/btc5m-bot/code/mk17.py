"""Iteration 17: calldata of the operator's MAKER fills in the new-regime block (11-01 06:00-09:30 development windows): the txs in which
an operator wallet's resting order was hit (the takers are other traders). Decoded fields only -> it17/post17_mk_cd.parquet.
Usage: python mk17.py"""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calldata
S = os.environ["RE16_SCRATCH"] + "/it17"
fl = pd.read_parquet(S + "/post17_fills.parquet")
txs = sorted(set(fl[(fl.role == "M") & (fl.side == 0)].tx.str.lower()) - set(fl[(fl.role == "T")].tx.str.lower()))
print("maker-only txs", len(txs), flush=True)
cd = calldata.to_frame(calldata.fetch_txs(txs, threads=2, log_every=40))
cd.to_parquet(S + "/post17_mk_cd.parquet", index=False)
print("DONE", len(cd), cd.tx.nunique(), flush=True)

"""Iteration 10 (panel iter9 information P2 = X74): V2 calldata of EVERY BTC 5m match tx recorded by my unthrottled book
(btc5m_clob_raw2 trade records with tx hashes, 10-31 14:55-17:55 UTC, development block 12-18), decoded fields only, so that
the crowd's fresh-signed taker orders give exact decision times (sign_ms). Cluster txs already in it9/cd9.parquet are skipped.
Output: .cache/re/btc5m-bot/it10/cdall10.parquet (+ match server ms per tx).
Usage: python fetchcrowd10.py"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import calldata

C = L.C
A, B = 1793458500, 1793469300

mt = {}
for r in L.recs("btc5m_clob_raw2", A - 60, B + 60):
    if r.get("k") == "x" and r.get("h"):
        h = r["h"].lower(); s = int(r["s"])
        if h not in mt or s < mt[h]:
            mt[h] = s
cd9 = set(pd.read_parquet(C + "/it9/cd9.parquet", columns=["tx"]).tx.str.lower())
need = [h for h, s in mt.items() if A * 1000 <= s < B * 1000 and h not in cd9]
print("txs", len(mt), "need", len(need), flush=True)
rows = calldata.fetch_txs(need, threads=2, log_every=40)
df = calldata.to_frame(rows)
df["txl"] = df.tx.str.lower(); df["m"] = df.txl.map(mt)
keep = [c for c in df.columns if c not in ("signature",)]
df[keep].to_parquet(C + "/it10/cdall10.parquet")
pd.DataFrame({"tx": list(mt), "m": list(mt.values())}).to_parquet(C + "/it10/txms10.parquet")
print("saved", len(df), "rows", df.tx.nunique(), "txs", flush=True)

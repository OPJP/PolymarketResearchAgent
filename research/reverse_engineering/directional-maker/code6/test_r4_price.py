"""Iteration 6: standalone check of final_rule.price_match_clock on a live development block (activity-derived fills,
maker role from calldata). python code6/test_r4_price.py <start_ts> <end_ts>"""
import glob, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F
C = ROOT / ".cache/re/directional-maker"
a, b = int(sys.argv[1]), int(sys.argv[2])
NAME2 = {v: k for k, v in F.CLUSTER.items()}
w = F._windows(a, b)
acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))]).drop_duplicates(subset=["transactionHash", "asset", "w", "size", "price"])
acts = acts[(acts.type == "TRADE") & (acts.side == "BUY") & (acts.timestamp >= a) & (acts.timestamp < b)]
cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata/live*.parquet"))])
mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.str.lower().isin(F.CLUSTER), "tx"].str.lower())
acts = acts[acts.transactionHash.str.lower().isin(mk_tx)]
toks = set(w.up_token) | set(w.down_token)
mk = pd.DataFrame({"tx": acts.transactionHash.str.lower(), "token_id": acts.asset.astype(str), "price": acts.price.astype(float),
                   "wallet": acts.w.map(NAME2), "ts": acts.timestamp.astype(int), "shares": acts["size"].astype(float)})
mk = mk[mk.token_id.isin(toks)]
t0 = time.time()
r = F.price_match_clock(mk, w, a, b, pd.DataFrame({"tx": [], "token_id": [], "pred_block": []}))
r["seconds"] = round(time.time() - t0, 1); r["windows"] = int(len(w))
print(json.dumps(r, indent=1, default=str))
(HERE.parent / "results" / f"iter6_r4_price_{a}_{b}.json").write_text(json.dumps(r, indent=1, default=str))

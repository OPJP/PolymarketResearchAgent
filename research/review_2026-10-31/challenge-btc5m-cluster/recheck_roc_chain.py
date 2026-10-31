"""Recompute peak capital / ROC and the on-chain sample for the cluster wallets from the cached activity + receipts."""
import sys, json, time
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import numpy as np, pandas as pd
from polyrea.workflows.investigate import load_window, verify_onchain
from polyrea.analysis.ledger import capital_and_roc
from polyrea.analysis.pnl import daily_frame
from polyrea.adapters.polymarket import PolymarketData
AS_OF = 1793318400
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
pm = PolymarketData()
out = {}
for name in sys.argv[1:]:
    w = W[name]; t0 = time.time()
    win = load_window(w, days=30, as_of=AS_OF, pm=pm)
    body, _ = pm.user_pnl(w, max_age=None)
    df = daily_frame(body["points"], as_of=AS_OF)
    daily = df["d_economic_pnl"].iloc[1:]
    roc = capital_and_roc(win["ledger"], daily, window_days=30)
    tr = win["trades"]
    # alternative capital measure: max over time of total USD committed to windows not yet resolved (both sides, gross)
    tr = tr.copy()
    oc = verify_onchain(w, win["trades"], sample=150 if name == "GF" else 200, seed=0)
    oc.pop("sources", None)
    out[name] = {"roc": roc, "fills": int(len(tr)), "onchain": oc, "secs": round(time.time() - t0)}
    print(name, json.dumps(out[name], default=float), flush=True)
json.dump(out, open(f"/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster/recheck_roc_chain_{'_'.join(sys.argv[1:])}.json", "w"), indent=1, default=float)

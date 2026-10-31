import json
import numpy as np, pandas as pd
from polyrea.workflows.investigate import load_window
from polyrea.analysis.profile import per_market_decomposition, resolution_info
w = "0xed107a85a4585a381e48c7f7ca4144909e7dd2e5"
prof = json.load(open(f"research/wallets/{w}/profile.json"))
win = load_window(w, days=30, as_of=prof["subject"]["as_of"])
tr, mk = win["trades"], win["markets"]
pm = per_market_decomposition(tr, mk); res = pm[pm.resolved].set_index("condition_id")
rows = []
for cid, g in tr.groupby("condition_id"):
    if cid not in res.index: continue
    m = mk[cid]; r = resolution_info(m); t = json.loads(m["clobTokenIds"])
    sg = np.where(g.side == "BUY", 1, -1)
    pay = g.outcome_index.map({0: r["payout"].get(str(t[0]), 0), 1: r["payout"].get(str(t[1]), 0)})
    rows.append((cid, res.loc[cid, "pnl"], float((g["size"] * sg * pay).sum() - (g.usdc * sg).sum()), bool((g.side == "SELL").any())))
d = pd.DataFrame(rows, columns=["cid", "coded", "correct", "has_sell"])
print("recorded market_win_rate", prof["derived"]["profile"]["market_win_rate"])
print(f"market_win_rate coded {(d.coded>0).mean():.3f} correct {(d.correct>0).mean():.3f}; resolved {len(d)}")
print(d[d.has_sell].to_string())

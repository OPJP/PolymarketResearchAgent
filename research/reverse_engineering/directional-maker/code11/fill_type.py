"""Iteration 11 (E2 / E4): how the cluster's BTC 5m maker BUY fills were matched, per split and per day: complement mint
(the taker BUYS the other outcome) vs direct (the taker SELLS the same outcome), and on which side of the market
(favourite = last clean print of the bought token > 0.5). VALIDATE: aggregates per day only.
    python code11/fill_type.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
SPLIT_V = 1793059200
W = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
F = F[(F.role == "maker") & (F.side == "BUY") & F.cid.isin(W.index)].copy()
F["txh"] = F.txh.str.lower()
out_rows = []
for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
    T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "price", "size", "tx"])
    T["tx"] = T.tx.str.lower()
    fd = F[(F.ts >= day) & (F.ts < day + 86400 + 600)]
    tk = T[T.tx.isin(set(fd.txh))].drop_duplicates("tx").set_index("tx")
    for r in fd.itertuples(index=False):
        if r.txh not in tk.index:
            continue
        t = tk.loc[r.txh]
        same = str(t.asset) == str(r.token_id)
        typ = "direct" if (same and t.side == "SELL") else ("mint" if ((not same) and t.side == "BUY") else "other")
        up = str(W.at[r.cid, "up_token"])
        pay = W.at[r.cid, "up_payout"] if str(r.token_id) == up else 1 - W.at[r.cid, "up_payout"]
        out_rows.append((day, typ, float(r.price), float(r.shares), float(pay)))
D = pd.DataFrame(out_rows, columns=["day", "typ", "price", "shares", "pay"])
D["fav"] = D.price > 0.5
D["won"] = D.pay > 0.5
D["pnl"] = D.shares * (D.pay - D.price)
res = {}
for sp, d in (("study", D[D.day < SPLIT_V]), ("validate", D[D.day >= SPLIT_V])):
    rec = {"fills": int(len(d)), "type_share": d.typ.value_counts(normalize=True).round(4).to_dict(),
           "fav_share_by_type": d.groupby("typ").fav.mean().round(4).to_dict(),
           "won_by_type": d.groupby("typ").won.mean().round(4).to_dict(),
           "return_by_type": (d.groupby("typ").pnl.sum() / (d.price * d.shares).groupby(d.typ).sum()).round(4).to_dict(),
           "by_day": {str(pd.to_datetime(k, unit="s").date()): {"mint_share": round(float((g.typ == "mint").mean()), 3),
                                                                "fav_share": round(float(g.fav.mean()), 3),
                                                                "won": round(float(g.won.mean()), 3)} for k, g in d.groupby("day")}}
    res[sp] = rec
print(json.dumps(res, indent=1))
(HERE.parent / "results" / "iter11_fill_type.json").write_text(json.dumps(res, indent=1))

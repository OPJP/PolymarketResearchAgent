"""Iteration 6, X76 (mechanics panel iter5 P2, step 1; DIAGNOSTIC: uses the wallet's real maker fills as an oracle maker
leg): how far does a PUBLIC residual control on top of an exact copy of its maker leg go on the outcome item?

Per market (16-22 Oct, its 229 markets): its maker fills in block order (calldata_all, maker rows) build an inventory
I = shares(outcome 0) - shares(outcome 1). Hedge rule H(X): whenever |I| > X after a fill, buy (|I| - X / 2) shares of
the short outcome at the first public taker print on that outcome at least 2 s later (windowed taker tapes, wallet txs
excluded), at that print's price + 1c (a price someone else paid, plus a tick), if one comes within 120 s; the hedge
updates I. Settled at resolution. X chosen on BUILD by min(Pearson, Spearman) of the per-market PnL against the
wallet's; reported on both splits and on each half of each split (earlier / later markets by game start).
Output: results/hedge_ceiling.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0 = 1792540800
XS = [100, 200, 300, 400, 600, 800, 1e9]


def main():
    pm = pd.read_parquet(OUT / "per_market.parquet", columns=["cid", "gs", "pnl", "win"])
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "oi", "fill", "price", "cid", "bts"])
    wtx = set(ca.tx)
    mk = ca[(ca.maker == WALLET) & (ca.idx >= 0)].sort_values("bts")
    by = {c: g for c, g in mk.groupby("cid")}
    rows = []
    for r in pm.itertuples():
        g = by.get(r.cid)
        tp = OUT / "tapes" / f"{r.cid}_tkw.parquet"
        if g is None or not tp.exists() or r.win not in (0, 1):
            continue
        d = pd.read_parquet(tp, columns=["timestamp", "price", "side", "outcomeIndex", "transactionHash"])
        d = d[(~d.transactionHash.isin(wtx)) & (d.side.astype(str).str.upper() == "BUY")].sort_values("timestamp")
        pt = {k: (x.timestamp.to_numpy(float), x.price.to_numpy(float)) for k, x in d.groupby("outcomeIndex")}
        base = float((np.where(g.oi == r.win, g.fill, 0.0) - g.fill * g.price).sum())
        rec = {"cid": r.cid, "gs": r.gs, "w": r.pnl, "maker_only": base}
        for X in XS:
            inv = 0.0
            pnl = base
            for f in g.itertuples():
                inv += f.fill if f.oi == 0 else -f.fill
                if abs(inv) > X:
                    short = 1 if inv > 0 else 0
                    qty = abs(inv) - X / 2.0
                    ts, ps = pt.get(short, (np.array([]), np.array([])))
                    j = np.searchsorted(ts, f.bts + 2.0)
                    if j < len(ts) and ts[j] <= f.bts + 120.0:
                        price = min(ps[j] + 0.01, 0.999)
                        pnl += qty * ((1.0 if short == r.win else 0.0) - price)
                        inv += qty if short == 0 else -qty
            rec[f"H{int(X) if X < 1e8 else 'inf'}"] = pnl
        rows.append(rec)
    D = pd.DataFrame(rows)

    def corr(x, cols):
        return {c: [round(float(pearsonr(x[c], x.w)[0]), 3), round(float(spearmanr(x[c], x.w)[0]), 3)] for c in cols}

    cols = ["maker_only"] + [f"H{int(X) if X < 1e8 else 'inf'}" for X in XS]
    tr, va = D[D.gs < VAL0], D[D.gs >= VAL0]
    ctr = corr(tr, cols)
    best = max(cols[1:], key=lambda c: min(ctr[c]))
    res = {"markets": {"BUILD": int(len(tr)), "VALIDATE": int(len(va))}, "BUILD": ctr, "VALIDATE": corr(va, cols),
           "chosen_on_BUILD": best, "sum_pnl": {c: [round(float(tr[c].sum()), 0), round(float(va[c].sum()), 0)] for c in cols}}
    halves = {}
    for nm, x in (("BUILD", tr), ("VALIDATE", va)):
        x = x.sort_values("gs")
        h = len(x) // 2
        halves[nm] = {"early": corr(x.iloc[:h], [best])[best], "late": corr(x.iloc[h:], [best])[best]}
    res["halves_chosen"] = halves
    (RES / "hedge_ceiling.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

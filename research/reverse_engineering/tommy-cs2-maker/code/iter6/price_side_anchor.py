"""Iteration 6, price (historical, examinable on h1 / h2): an aggressor-side-adjusted last print as the maker anchor.

For each in-play CS2 maker order of the wallet (calldata_all; one row per order: salt + sign_ms), at its signing time s
the latest public print of the market before s (windowed taker tapes, wallet txs excluded; block clock) is mapped to the
order's token z: p_z = price if the print is on z else 1 - price. The aggressor either HIT z's bid (taker SELL z, or
taker BUY of the complement) or LIFTED z's ask (taker BUY z, or taker SELL of the complement). Anchor =
p_z - k_hit or p_z - k_lift (cents), with (k_hit, k_lift) chosen on BUILD to maximize the share within one in-play tick
(0.01 for 0.04 <= anchor <= 0.96, else 0.001), scored on VALIDATE against the plain last print (0.305) and the best
single shift. Also the same with the last print restricted to prints on the order's own token.
Output: results/price_side_anchor.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600


def within(p, a):
    tick = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return np.abs(p - a) <= tick + 1e-9


def main():
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "oi", "price", "sign_ms", "salt", "cid", "gs_ts"])
    wtx = set(ca.tx)
    mo = ca[(ca.maker == WALLET) & (ca.idx >= 0)].drop_duplicates(["salt", "sign_ms"]).copy()
    mo = mo[(mo.sign_ms / 1000 >= mo.gs_ts) & (mo.sign_ms > 1.7e12)]
    pm = pd.read_parquet(OUT / "per_market.parquet", columns=["cid", "smt"])
    rows = []
    for cid, g in mo.groupby("cid"):
        tp = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not tp.exists():
            continue
        d = pd.read_parquet(tp, columns=["timestamp", "price", "side", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        if d.empty:
            continue
        t = d.timestamp.to_numpy(float)
        pr = d.price.to_numpy(float)
        oi = d.outcomeIndex.to_numpy(int)
        buy = (d.side.astype(str).str.upper() == "BUY").to_numpy()
        s = g.sign_ms.to_numpy(float) / 1000.0
        j = np.searchsorted(t, s, side="left") - 1
        ok = j >= 0
        jj = np.clip(j, 0, None)
        z = g.oi.to_numpy(int)
        on_z = oi[jj] == z
        pz = np.where(on_z, pr[jj], 1 - pr[jj])
        # aggressor lifted z's ask iff (taker BUY on z) or (taker SELL on the complement)
        lift = np.where(on_z, buy[jj], ~buy[jj])
        # last print on the order's own token only
        rows.append(pd.DataFrame({"cid": cid, "gs": g.gs_ts.to_numpy(float), "p": g.price.to_numpy(float), "pz": np.round(pz, 2),
                                  "lift": lift, "ok": ok, "age": s - t[jj]}))
    R = pd.concat(rows, ignore_index=True)
    R = R[R.ok].copy()
    R["split"] = np.where(R.gs < VAL0, "BUILD", "VALIDATE")
    tr, va = R[R.split == "BUILD"], R[R.split == "VALIDATE"]
    res = {"orders": {"BUILD": int(len(tr)), "VALIDATE": int(len(va))}}
    for nm, x in (("BUILD", tr), ("VALIDATE", va)):
        dd = np.round((x.p - x.pz) * 100).clip(-6, 6)
        res[f"p_minus_last_print_c_{nm}"] = {"lift": dd[x.lift].value_counts(normalize=True).sort_index().round(3).to_dict(),
                                             "hit": dd[~x.lift].value_counts(normalize=True).sort_index().round(3).to_dict(),
                                             "share_lift": round(float(x.lift.mean()), 3)}
    ks = [0, 1, 2, 3, 4]
    best_single = max(ks, key=lambda k: float(within(tr.p.to_numpy(), tr.pz.to_numpy() - k / 100).mean()))
    grid = [(a, b) for a in ks for b in ks]
    best_pair = max(grid, key=lambda ab: float(within(tr.p.to_numpy(), tr.pz.to_numpy() - np.where(tr.lift, ab[1], ab[0]) / 100).mean()))
    for nm, x in (("BUILD", tr), ("VALIDATE", va)):
        res[nm] = {"last_print": round(float(within(x.p.to_numpy(), x.pz.to_numpy()).mean()), 3),
                   f"last_print_minus_{best_single}c": round(float(within(x.p.to_numpy(), x.pz.to_numpy() - best_single / 100).mean()), 3),
                   "side_adjusted": round(float(within(x.p.to_numpy(), x.pz.to_numpy() - np.where(x.lift, best_pair[1], best_pair[0]) / 100).mean()), 3),
                   "side_adjusted_exact": round(float((np.abs(x.p.to_numpy() - (x.pz.to_numpy() - np.where(x.lift, best_pair[1], best_pair[0]) / 100)) <= 0.001).mean()), 3)}
        for lo, hi in ((0, 2), (2, 10), (10, 60), (60, 1e9)):
            m = (x.age >= lo) & (x.age < hi)
            if m.sum() > 50:
                res[nm][f"side_adjusted_age_{lo}_{int(min(hi, 9999))}s"] = [int(m.sum()), round(float(within(x.p[m].to_numpy(), x.pz[m].to_numpy() - np.where(x.lift[m], best_pair[1], best_pair[0]) / 100).mean()), 3)]
    res["fitted"] = {"best_single_shift_c": best_single, "k_hit_c": best_pair[0], "k_lift_c": best_pair[1]}
    (RES / "price_side_anchor.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

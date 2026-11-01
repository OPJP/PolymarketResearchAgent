"""X176 step 6 (mechanics panel iter-12 P1): historical uncensoring of the ladder with the operator's 5-share
accounts. For every wallet maker burst (same token, signed within 50 ms) with at least one same-process sibling order
(0x52661b8e, 0x67119033, 0x7d67f01d) signed 0-10 ms after the burst's first order on the same token, take the union
of filled prices (both accounts) as a partial view of one ladder. Check against the frozen X163 machine (slots V, V-1c,
..., V-4c inside [0.05, 0.95], whole cents, top-first): share of union prices inside [V - 4c, V] with V = the union top,
share of sibling prices equal to a wallet price in the burst, share of sibling prices strictly below every wallet
price of the burst (unfilled wallet slots), and the slot index distribution of sibling prices (V - price in cents).
Output: results/ladder_union_hist.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SIB = ["0x52661b8e13158f23d94a9e8302ab0295704c22ac", "0x671190333b064b0899b4ac1aec86744b1f82885b", "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"]


def main():
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["idx", "maker", "token_id", "price", "sign_ms", "salt"])
    cd["maker"] = cd.maker.str.lower()
    cd["token_id"] = cd.token_id.astype(str)
    o = cd[cd.idx != -1].drop_duplicates(["maker", "salt", "sign_ms"])
    w = o[o.maker == W].sort_values("sign_ms")
    s = o[o.maker.isin(SIB)].sort_values("sign_ms")
    sb = {t: (g.sign_ms.to_numpy(np.int64), g.price.to_numpy(float)) for t, g in s.groupby("token_id")}
    rows = []
    for tok, g in w.groupby("token_id"):
        if tok not in sb:
            continue
        ss, sp = sb[tok]
        t = g.sign_ms.to_numpy(np.int64)
        p = g.price.to_numpy(float)
        st = 0
        for i in range(1, len(t) + 1):
            if i == len(t) or t[i] - t[i - 1] > 50:
                t0, t1 = t[st], t[i - 1]
                j0, j1 = np.searchsorted(ss, t0, side="left"), np.searchsorted(ss, t1 + 10, side="right")
                if j1 > j0:
                    wp = p[st:i]
                    spp = sp[j0:j1]
                    V = max(wp.max(), spp.max())
                    rows.append({"tok": tok, "n_w": int(i - st), "n_s": int(j1 - j0), "V": V, "w_top": wp.max(),
                                 "s_eq_w": int(np.sum(np.isin(np.round(spp, 2), np.round(wp, 2)))),
                                 "s_below_all_w": int(np.sum(spp < wp.min() - 1e-9)),
                                 "s_above_w_top": int(np.sum(spp > wp.max() + 1e-9)),
                                 "slots_s": [int(round((V - x) * 100)) for x in spp],
                                 "union_in_5": bool(np.all((V - np.concatenate([wp, spp])) <= 0.04 + 1e-9))})
                st = i
    R = pd.DataFrame(rows)
    out = {"co_bursts": int(len(R))}
    if len(R):
        sl = np.concatenate([np.array(x) for x in R.slots_s])
        out.update({"sibling_orders": int(R.n_s.sum()), "sibling_equal_to_a_wallet_price": round(float(R.s_eq_w.sum() / R.n_s.sum()), 3),
                    "sibling_below_every_wallet_price": round(float(R.s_below_all_w.sum() / R.n_s.sum()), 3),
                    "sibling_above_wallet_top": round(float(R.s_above_w_top.sum() / R.n_s.sum()), 3),
                    "union_within_V_minus_4c": round(float(R.union_in_5.mean()), 3),
                    "sibling_slot_hist_cents_below_V": {int(k): int(v) for k, v in zip(*np.unique(sl, return_counts=True))}})
    (RES / "ladder_union_hist.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

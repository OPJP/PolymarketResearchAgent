"""Iteration 3, mechanics panel P2 (X26, first part): does the maker leg pull its complement bids when its own taker
leg fires? 16-22 Oct calldata (all txs with a wallet fill; signing ms of every order).
For each wallet taker order (BUY team X, signed at t): wallet maker fills on the complement token of the same market
inside other takers' transactions whose taker signed in (t, t + 2.5 s] (they match ~1.04 s later, inside the window
in which the wallet already knows the event). Reported: share of taker orders with such fills, the age of the filled
complement maker orders at t (negative = signed before the take: a stale bid it did not pull), the shares relative to
the taker fill, the pair cost (taker VWAP + complement VWAP) and the takers' identity; control window
(t - 30 s, t - 27.5 s]. Split BUILD / VALIDATE by gameStart. Output: results/stale_complement.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET, PACK  # noqa: E402

VAL0 = 1792540800


def main():
    cd = pd.read_parquet(OUT / "calldata_all.parquet")
    o = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "token_id", "oi", "gs_ts"]).drop_duplicates("token_id")
    oi = dict(zip(o.token_id.astype(str), o.oi))
    gs = dict(zip(o.cid, o.gs_ts))
    cd["tok"] = cd.token_id.astype(str)
    cd = cd[cd.tok.isin(oi)].copy()
    cd["oi"] = cd.tok.map(oi)
    cd["cid"] = cd.tok.map(dict(zip(o.token_id.astype(str), o.cid)))
    tk_sign = cd[cd.idx == -1].drop_duplicates("tx").set_index("tx")
    T = cd[(cd.idx == -1) & (cd.maker == WALLET) & (cd.side == 0)].drop_duplicates("tx")
    M = cd[(cd.idx >= 0) & (cd.maker == WALLET) & (cd.side == 0)].copy()
    M["t_sign"] = M.tx.map(tk_sign.sign_ms)
    M["t_who"] = M.tx.map(tk_sign.maker)
    M = M[M.t_who != WALLET]
    res = {}
    for split, sel in (("BUILD", T.cid.map(gs) < VAL0), ("VALIDATE", T.cid.map(gs) >= VAL0)):
        TT = T[sel.to_numpy()]
        out = {}
        for lab, a, b in (("after_take", 0, 2500), ("control_minus30s", -30000, -27500)):
            rows = []
            for r in TT.itertuples():
                g = M[(M.cid == r.cid) & (M.oi == 1 - r.oi) & (M.t_sign > r.sign_ms + a) & (M.t_sign <= r.sign_ms + b)]
                if len(g) == 0:
                    rows.append({"has": False})
                    continue
                sh = float(g.fill.sum())
                vw = float((g.fill * g.price).sum() / max(sh, 1e-9))
                rows.append({"has": True, "sh_ratio": sh / max(r.fill, 1e-9), "pair_cost": r.price + vw,
                             "stale_share": float((g.fill[g.sign_ms < r.sign_ms]).sum() / max(sh, 1e-9)),
                             "age_med_s": float(np.median((g.sign_ms - r.sign_ms) / 1000)),
                             "pack_share": float((g.fill[g.t_who.isin(PACK)]).sum() / max(sh, 1e-9))})
            x = pd.DataFrame(rows)
            h = x[x.has] if "sh_ratio" in x else x.iloc[0:0]
            out[lab] = {"taker_orders": int(len(x)), "share_with_complement_fills": round(float(x.has.mean()), 3),
                        "shares_ratio_median": round(float(h.sh_ratio.median()), 3) if len(h) else None,
                        "pair_cost_median": round(float(h.pair_cost.median()), 3) if len(h) else None,
                        "pair_cost_iqr": [round(float(h.pair_cost.quantile(q)), 3) for q in (0.25, 0.75)] if len(h) else None,
                        "stale_share_median": round(float(h.stale_share.median()), 3) if len(h) else None,
                        "stale_share_mean": round(float(h.stale_share.mean()), 3) if len(h) else None,
                        "maker_age_at_take_median_s": round(float(h.age_med_s.median()), 2) if len(h) else None,
                        "pack_taker_share_mean": round(float(h.pack_share.mean()), 3) if len(h) else None}
        res[split] = out
    json.dump(res, open(RES / "stale_complement.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

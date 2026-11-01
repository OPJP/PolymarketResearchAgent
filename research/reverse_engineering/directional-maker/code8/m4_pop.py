"""Iteration 8, panel iter7 mechanics M4 (X66) step 1 on VALIDATE (2026-10-27..30, aggregate only): who pays the cluster.
Each cluster maker BUY fill in the lot's VALIDATE calldata (b1_cluster_orders_valid) joined to the taker order of its
transaction (b1_takers_valid): taker signatureType (0 EOA, 1 Magic proxy, 2 Safe, 3 other), round-USD BUY orders
(front-end 'buy $X'), taker limit looseness vs the cluster's level (cents), non-zero builder code. Return of the cluster's
fills held to resolution (payout from Gamma up_payout), share of PnL, window-block bootstrap 95% CI of the return.
    python code8/m4_pop.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache/re/directional-maker"
OUT = ROOT / "research/reverse_engineering/directional-maker/results"


def main():
    co = pd.read_parquet(C / "b1_cluster_orders_valid.parquet")
    tk = pd.read_parquet(C / "b1_takers_valid.parquet")
    tk = tk[tk.role == "taker"].drop_duplicates("tx")
    w = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    w = w[(w.start_ts >= 1793059200) & (w.start_ts < 1793404800)]
    tok = {**{str(t): (c, 1, p) for t, c, p in zip(w.up_token, w.cid, w.up_payout)},
           **{str(t): (c, 0, p) for t, c, p in zip(w.down_token, w.cid, w.up_payout)}}
    co = co[(co.role == "maker") & (co.oside == 0)].copy()
    co["token_id"] = co.token_id.astype(str)
    co = co[co.token_id.isin(tok.keys())]
    co["cid"] = co.token_id.map(lambda t: tok[t][0])
    co["won"] = co.token_id.map(lambda t: tok[t][2] if tok[t][1] == 1 else 1 - tok[t][2])
    co["q"] = co.maker_amount.astype(float) / co.taker_amount.astype(float)
    co["sh"] = co.shares.astype(float)
    co["usd"] = co.usdc.astype(float)
    co = co.dropna(subset=["won"])
    t = tk.set_index("tx")
    co = co.join(t[["sig_type", "oside", "maker_amount", "taker_amount", "token_id", "builder"]].rename(columns=lambda c: "t_" + c), on="tx")
    co = co.dropna(subset=["t_sig_type"])
    same = co.t_token_id.astype(str) == co.token_id
    tbuy = co.t_oside == 0
    lim_buy = co.t_maker_amount.astype(float) / co.t_taker_amount.astype(float)
    lim_sell = co.t_taker_amount.astype(float) / co.t_maker_amount.astype(float)
    co["loose_c"] = np.where(same & ~tbuy, (co.q - lim_sell) * 100, np.where(~same & tbuy, (lim_buy - (1 - co.q)) * 100, np.nan))
    co["round_usd"] = tbuy & ((co.t_maker_amount.astype(np.int64) % 1_000_000) == 0)
    co["builder_nz"] = co.t_builder.astype(str).str.strip("0") != ""
    co["pnl"] = co.won * co.sh - co.usd
    tot = float(co.pnl.sum())
    rng = np.random.default_rng(8)
    cids = co.cid.unique()

    def summ(mask):
        sub = co[mask]
        if not len(sub):
            return None
        r = float(sub.pnl.sum() / sub.usd.sum())
        by = sub.groupby("cid")[["pnl", "usd"]].sum()
        bs = []
        keys = by.index.to_numpy()
        for _ in range(300):
            pick = rng.choice(keys, len(keys), replace=True)
            b = by.loc[pick]
            bs.append(b.pnl.sum() / b.usd.sum())
        return {"fills": int(len(sub)), "share_fills": round(len(sub) / len(co), 3), "return": round(r, 4),
                "ci95": [round(float(np.quantile(bs, .025)), 4), round(float(np.quantile(bs, .975)), 4)],
                "share_pnl": round(float(sub.pnl.sum() / tot), 3) if tot else None}
    out = {"fills": int(len(co)), "pnl_usd": round(tot, 1), "return": round(tot / float(co.usd.sum()), 4),
           "complement_share": round(float((~same).mean()), 3)}
    out["by_taker_sig_type"] = {str(int(k)): summ(co.t_sig_type == k) for k in sorted(co.t_sig_type.unique())}
    out["round_usd_buy"] = {"yes": summ(co.round_usd), "no": summ(~co.round_usd)}
    out["builder_nonzero"] = {"yes": summ(co.builder_nz), "no": summ(~co.builder_nz)}
    lc = co.loose_c
    out["taker_limit_looseness_cents"] = {"<=0.5": summ(lc <= 0.5), "0.5-3": summ((lc > 0.5) & (lc <= 3)), "3-10": summ((lc > 3) & (lc <= 10)),
                                          ">10": summ(lc > 10)}
    (OUT / "iter8_m4_pop_validate.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

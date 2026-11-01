"""Iteration 8, X57 step 4 (panel-assumptions iter7 P4): do the live-decoded parameters transfer to h1 / VALIDATE?
Calldata of VALIDATE sampled hours (calldata_sample.parquet, b1_orders_sample.parquet) vs the 10-31 13:00-14:47 development
block (post/cd6_live.parquet, live6_takers.parquet): size menu and large share per wallet, pay-up rate (limit above the best
consumed effective ask, as final_rule._calldata_touch), the signing-burst phases (rel of the signing time), and the
cross-wallet share of consecutive same-token cluster taker txs in a block (tx_index order). Writes results/version8.json."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import final_rule as FR

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
VAL0, H = 1792108800, 1792713600


def payup(d):
    d = d.copy()
    d["px"] = np.where(d.oside == 0, d.maker_amt / d.taker_amt, d.taker_amt / d.maker_amt)
    tk = d[(d.role == "T") & d.maker.str.lower().isin(FR.WALLETS)].copy()
    mk = d[d.role == "M"][["tx", "token", "oside", "px"]].merge(tk[["tx", "token"]].rename(columns={"token": "t_token"}), on="tx")
    same = mk.token == mk.t_token
    mk["eff"] = np.where(same & (mk.oside == 1), mk.px, np.where(~same & (mk.oside == 0), 1.0 - mk.px, np.nan))
    tk = tk.join(mk.groupby("tx").eff.min().rename("best"), on="tx")
    tk = tk[tk.best.notna()]
    tk["wallet"] = tk.maker.str.lower().map(FR.WALLETS)
    tk["pay"] = (tk.px - tk.best).round(4) > 0.0001
    tk["size"] = tk.taker_amt.round(0)
    return tk


def cross_share(tk):
    """same block, same token, consecutive tx_index: share of cross-wallet pairs and of +-1 c limit differences."""
    tk = tk.sort_values(["block", "tx_index"])
    n = cross = adj = 0
    for (blk, tok), g in tk.groupby(["block", "token"]):
        if len(g) < 2:
            continue
        w = g.wallet.to_numpy(); p = g.px.to_numpy()
        for i in range(len(g) - 1):
            n += 1; cross += int(w[i] != w[i + 1]); adj += int(abs(round((p[i + 1] - p[i]) * 100)) == 1)
    return {"pairs": n, "cross_wallet": round(cross / max(n, 1), 3), "plus_minus_1c": round(adj / max(n, 1), 3)}


res = {}
cs = pd.read_parquet(os.path.join(C, "calldata_sample.parquet"))
b1 = pd.read_parquet(os.path.join(C, "b1_orders_sample.parquet"))
blk_ts = b1.groupby("token").first_ts.min()  # not used for timing; the hour split uses b1 below
tkv = payup(cs)
# VALIDATE hours via the order sample's first fill times (token, salt) -> first_ts
b1k = b1[["salt", "first_ts", "rel_sign", "size", "wal"]].copy(); b1k["salt"] = b1k.salt.astype(str)
tkv["salt"] = tkv.salt.astype(str)
tkv = tkv.merge(b1k[["salt", "first_ts", "rel_sign"]].drop_duplicates("salt"), on="salt", how="left")
for nm, k in (("VALIDATE_hours", tkv.first_ts >= VAL0), ("BUILD_hours", tkv.first_ts < VAL0)):
    x = tkv[k]
    res[nm] = {"n_taker_orders": int(len(x)), "payup_share": round(float(x.pay.mean()), 3),
               "payup_by_wallet": x.groupby("wallet").pay.mean().round(3).to_dict(),
               "size_menu_by_wallet": {w: g["size"].value_counts(normalize=True).head(4).round(3).to_dict() for w, g in x.groupby("wallet")},
               "consecutive_pairs": cross_share(x)}
    rs = x.rel_sign.dropna()
    res[nm]["sign_rel_quantiles"] = [round(float(q), 1) for q in rs.quantile([0.05, 0.25, 0.5, 0.75, 0.95])] if len(rs) else None
    res[nm]["sign_rel_modes"] = pd.cut(rs, [-200, -60, 0, 100, 160, 300]).value_counts(normalize=True).round(3).sort_index().astype(float).rename(index=str).to_dict() if len(rs) else None
live = pd.read_parquet(os.path.join(C, "post", "cd6_live.parquet"))
tkl = payup(live)
lt = pd.read_parquet(os.path.join(C, "live6_takers.parquet"), columns=["tx", "start"]).drop_duplicates("tx")
tkl = tkl.merge(lt, on="tx", how="left")
tkl["rel_sign"] = tkl.sign_ms / 1000.0 - tkl.start
res["live_10_31_13_00_14_47"] = {"n_taker_orders": int(len(tkl)), "payup_share": round(float(tkl.pay.mean()), 3),
                                 "payup_by_wallet": tkl.groupby("wallet").pay.mean().round(3).to_dict(),
                                 "size_menu_by_wallet": {w: g["size"].value_counts(normalize=True).head(4).round(3).to_dict() for w, g in tkl.groupby("wallet")},
                                 "consecutive_pairs": cross_share(tkl),
                                 "sign_rel_quantiles": [round(float(q), 1) for q in tkl.rel_sign.dropna().quantile([0.05, 0.25, 0.5, 0.75, 0.95])],
                                 "sign_rel_modes": pd.cut(tkl.rel_sign.dropna(), [-200, -60, 0, 100, 160, 300]).value_counts(normalize=True).round(3).sort_index().astype(float).rename(index=str).to_dict()}
for k, v in res.items():
    print(k, json.dumps(v, default=str))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "version8.json"), "w"), indent=1, default=str)

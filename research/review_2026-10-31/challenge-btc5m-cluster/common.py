import pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue
from grid import Grid, DYN

W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
CLS = set(W.values())

def load(slim=True):
    d = pickle.load(open("slim.pkl" if slim else "data.pkl", "rb"))
    G = {per: Grid(d[per]) for per in ("fit", "test")}
    return d, G

def base_frame(d, per):
    P = d[per]["prints"]
    P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True).copy()
    P["rel"] = P.ts - P.start_ts
    return P

def dyn_frame(G, per, P, shift_of=None):
    cols = {c: np.full(len(P), np.nan) for c in DYN + ["up_last_side"]}
    for cid, idx in P.groupby("condition_id").indices.items():
        s = shift_of.get(cid, 0) if shift_of else 0
        f = G[per].feats(cid, P.ts.to_numpy()[idx], P.is_up.to_numpy()[idx], shift_windows=s)
        if f is None:
            continue
        for c in cols:
            cols[c][idx] = f[c]
    return pd.DataFrame(cols)

def static_frame(P):
    return pd.DataFrame({"price": P.price, "price2": P.price ** 2, "price3": P.price ** 3, "rel": P.rel / 300, "rel2": (P.rel / 300) ** 2, "is_up": P.is_up.astype(float)})

def taker_bt(P, sel, cap=25.0, exclude_cluster=False):
    p = P[sel & P.up_payout.notna()]
    if exclude_cluster:
        p = p[~p.wallet.isin(CLS)]
    if len(p) == 0:
        return {"trades": 0}
    usd = np.minimum(p["size"] * p.price, cap)
    sh = usd / p.price
    pay = np.where(p.is_up, p.up_payout, 1 - p.up_payout)
    fee = p.fee_rate * p.price * (1 - p.price) * sh
    pnl = sh * pay - usd - fee
    per_w = pd.Series(pnl.to_numpy(), index=p.condition_id.to_numpy()).groupby(level=0).sum()
    # windows without trades count as zero PnL days for the per-window series
    t = hac_t_test(per_w.to_numpy())
    b = stationary_bootstrap_pvalue(per_w.to_numpy(), n_boot=2000)
    return {"trades": int(len(p)), "windows": int(per_w.size), "usd": float(usd.sum()), "pnl": float(pnl.sum()), "fees": float(fee.sum()),
            "gross_pnl": float((sh * pay - usd).sum()), "ret": float(pnl.sum() / usd.sum()), "gross_ret": float((sh * pay - usd).sum() / usd.sum()),
            "per_window_t": t.statistic, "per_window_p": t.p_value, "bootstrap_p": b.p_value}

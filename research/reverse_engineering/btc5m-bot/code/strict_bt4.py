"""Iteration 4 (late): strict-fill backtest of the frozen rule on VALIDATE (observed-liquidity method, as in
polyrea.analysis.updown.backtest). At second s the rule decides with information up to s-1: if the presence score of
the side-model's outcome o is >= 0.30 (P_THRESH), it sends a 30-share BUY limit at the last implied ask of o (seen at
s-1). Latency >= 2 s: it can only fill against OTHER traders' taker BUY prints on o in [s+1, s+3] (block ts, i.e. at
least 2 s after the information horizon) at a price <= its limit, at that print's price, for min(print size, remaining
shares) (capture 1.0, i.e. an upper bound: we assume we win the whole contested print). Cluster prints are excluded.
One order per (window, outcome) at a time: a new order only after the previous one's fill window closed. Taker fee
0.07 p (1-p). Per-window PnL vs the cluster's (before rebates). Uses val_outcome_it4b.parquet (plain it4b side model)."""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
FEE = 0.07; SH = 30.0; PT = 0.30
O = pd.read_parquet(f"{C}/val_outcome_it4b.parquet")
win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
fills = pd.read_parquet(f"{C}/fills.parquet", columns=["cid", "is_up", "shares", "price", "fee_usd", "usdc", "up_payout"])
fills = fills[fills.cid.isin(set(O.cid))]
rows = []
for cid, g in O.groupby("cid", sort=False):
    tp = f"{C}/tapes/{cid}.parquet"
    if not os.path.exists(tp) or cid not in win.index:
        continue
    st = int(win.at[cid, "start_ts"]); pay_up = float(win.at[cid, "up_payout"])
    d = pd.read_parquet(tp, columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome"])
    d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(W)]
    d = d.assign(rel=d.timestamp - st, up=(d.outcome == "Up")).sort_values("rel")
    g = g.sort_values("rel")
    side_up = g.ps.to_numpy() >= 0.5
    p_side = np.where(side_up, g.pu.to_numpy(), g.pd.to_numpy())
    lim = np.where(side_up, g.ask_u.to_numpy(), g.ask_d.to_numpy())
    rel = g.rel.to_numpy()
    busy = {True: -1, False: -1}
    for i in np.where((p_side >= PT) & np.isfinite(lim) & (lim > 0.05) & (lim < 0.95))[0]:
        o = bool(side_up[i]); s = int(rel[i])
        if s <= busy[o]:
            continue
        cand = d[(d.up == o) & (d.rel >= s + 1) & (d.rel <= s + 3) & (d.price <= lim[i] + 1e-9)]
        busy[o] = s + 3
        left = SH
        for r in cand.itertuples():
            q = min(left, float(r.size)); left -= q
            pay = pay_up if o else 1 - pay_up
            rows.append((cid, o, s, float(r.price), q, q * (pay - r.price) - FEE * r.price * (1 - r.price) * q))
            if left <= 0:
                break
T = pd.DataFrame(rows, columns=["cid", "up", "s", "price", "shares", "pnl"])
f = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout))
f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
ww = f.groupby("cid").agg(pnl=("pnl", "sum"), usd=("usdc", "sum"))
rw = T.assign(usd=T.price * T.shares).groupby("cid").agg(pnl=("pnl", "sum"), usd=("usd", "sum"))
b = rw.join(ww, rsuffix="_w", how="outer").fillna(0.0)
res = {"windows": int(b.shape[0]), "rule_fills": int(len(T)), "rule_windows_traded": int(rw.shape[0]), "rule_usd": round(float(T.price.mul(T.shares).sum()), 1),
       "rule_pnl_before_rebates": round(float(T.pnl.sum()), 1), "rule_return_before_rebates": round(float(T.pnl.sum() / T.price.mul(T.shares).sum()), 4),
       "rule_fee_usd": round(float((FEE * T.price * (1 - T.price) * T.shares).sum()), 1),
       "rule_return_with_50pct_fee_rebate": round(float((T.pnl.sum() + 0.5 * (FEE * T.price * (1 - T.price) * T.shares).sum()) / T.price.mul(T.shares).sum()), 4),
       "per_window_pnl_corr_pearson": round(float(b.pnl.corr(b.pnl_w)), 4), "per_window_pnl_corr_spearman": round(float(b.pnl.corr(b.pnl_w, method="spearman")), 4),
       "wallet_return_before_rebates": round(float(ww.pnl.sum() / ww.usd.sum()), 4),
       "note": "observed-liquidity strict fills, latency >= 2 s after the information horizon, capture 1.0 (upper bound), 30-share orders, taker only"}
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_strict_backtest_iter4.json", "w"), indent=1)

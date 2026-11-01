"""Iteration 6 (X26 = panel-mechanics proposal 3): the touch at every match is on chain. For each cluster TAKER order in a
matchOrders tx (calldata sample, 11 development hours, decoded fields only), the effective ask of every maker order it
consumed: a SELL of the same token at p is an ask at p; a BUY of the complementary token at q is an ask at 1 - q (mint).
Compare the bot's limit with the best (lowest) and worst (highest) consumed effective ask. Also by wallet, half, and day.
This measures the decoded price rule (limit = touch at the match, no sweep); it is NOT a point-in-time forecast of the
touch (the touch is taken from the match itself).
Usage: python calldata_touch6.py [CALLDATA_PARQUET]"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def order_price(df):
    # BUY (oside 0): maker_amt = USDC, taker_amt = shares; SELL (oside 1): maker_amt = shares, taker_amt = USDC
    return np.where(df.oside == 0, df.maker_amt / df.taker_amt, df.taker_amt / df.maker_amt)


def touch_table(cd):
    cd = cd.copy()
    cd["px"] = order_price(cd)
    tk = cd[(cd.role == "T") & cd.maker.isin(W.keys())].copy()
    mk = cd[cd.role == "M"][["tx", "token", "oside", "px", "maker"]].copy()
    m = mk.merge(tk[["tx", "token"]].rename(columns={"token": "t_token"}), on="tx")
    # effective ask for the taker's token
    same = m.token == m.t_token
    m["eff_ask"] = np.where(same & (m.oside == 1), m.px, np.where(~same & (m.oside == 0), 1.0 - m.px, np.nan))
    m["kind"] = np.where(same & (m.oside == 1), "sell_same", np.where(~same & (m.oside == 0), "buy_comp", "other"))
    g = m.groupby("tx").agg(best=("eff_ask", "min"), worst=("eff_ask", "max"), n_mk=("eff_ask", "size"), share_comp=("kind", lambda s: float((s == "buy_comp").mean())))
    tk = tk.merge(g, left_on="tx", right_index=True, how="left")
    tk["limit"] = tk.px.round(4)
    tk["d_best"] = (tk.limit - tk.best).round(4)
    tk["d_worst"] = (tk.limit - tk.worst).round(4)
    tk["wal"] = tk.maker.map(W)
    return tk, m


def summ(x):
    x = x[x.best.notna()]
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "limit_eq_best": round(float((x.d_best.abs() < 1e-6).mean()), 4), "limit_within_tick_best": round(float((x.d_best.abs() <= 0.0100001).mean()), 4),
            "limit_eq_worst": round(float((x.d_worst.abs() < 1e-6).mean()), 4), "single_level": round(float(((x.best - x.worst).abs() < 1e-6).mean()), 4),
            "limit_above_worst": round(float((x.d_worst > 1e-6).mean()), 4)}


def main(path):
    cd = pd.read_parquet(path)
    tk, m = touch_table(cd)
    res = {"n_cluster_taker_orders": int(len(tk)), "maker_kinds": m.kind.value_counts().to_dict(), "all": summ(tk),
           "by_wallet": {w: summ(g) for w, g in tk.groupby("wal")},
           "d_best_counts": {str(k): int(v) for k, v in tk.d_best.value_counts().head(10).items()},
           "d_worst_counts": {str(k): int(v) for k, v in tk.d_worst.value_counts().head(10).items()}}
    tk["hour"] = (tk.sign_ms // 3600000).astype(int)
    res["by_hour"] = {str(h * 3600): summ(g) for h, g in tk.groupby("hour")}
    tk["sz"] = np.where(tk.oside == 0, tk.taker_amt, tk.maker_amt).round(2)
    res["by_size"] = {str(s): summ(g) for s, g in tk.groupby("sz") if len(g) >= 100}
    return res, tk


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else C + "/calldata_sample.parquet"
    res, tk = main(path)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_calldata_touch_iter6.json")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "by_hour"}, indent=1)[:3000])

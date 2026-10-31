"""Iteration 7: is the side Binance-USD-M-first? Per live interval, per-series agreement in the reaction window
[m - 600, m - 100) ms among weak-vote matches (|vote| <= 2), and a hierarchical rule: side = sign of the Binance USD-M
microprice composite (BTC + ETH / 1.235) when it ticked (> 0.002 bp), else the ten-series vote. Rule chosen on the first
two intervals, checked on the third (16:04-16:25). Development blocks only. Usage: python bnfirst7.py"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
from lag7 import micro_series, mv


def run(own, a, b, feed):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].drop_duplicates(["tx", "token"])
    S = micro_series(feed, a, b); keys = sorted(S)
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool); sg = np.where(up, 1, -1)
    Q = {k: mv(S, k, m - 600, m - 100) for k in keys}
    Qa = np.vstack([Q[k] for k in keys]); cov = np.isfinite(Qa).any(axis=0)
    vote = np.nansum(np.sign(Qa) * (np.abs(Qa) > 0.002), axis=0)
    weak = cov & (np.abs(vote) >= 1) & (np.abs(vote) <= 2)
    out = {"interval": [a, b], "n": int(len(m)), "weak_n": int(weak.sum()), "per_series_in_weak": {}}
    for k in keys:
        q = Q[k]; t = weak & np.isfinite(q) & (np.abs(q) > 0.002)
        out["per_series_in_weak"][f"{k[0]}_{k[1]}"] = [round(float((np.sign(q[t]) == sg[t]).mean()), 3) if t.any() else None, int(t.sum())]
    bf = np.nan_to_num(Q.get(("bf", "BTC"), np.full(len(m), np.nan))) + np.nan_to_num(Q.get(("bf", "ETH"), np.full(len(m), np.nan)))
    bft = np.abs(bf) > 0.002
    side = np.where(bft, np.sign(bf), np.sign(vote))
    k_ = cov & (side != 0)
    out["vote"] = {"cover": round(float((cov & (vote != 0)).sum() / max(cov.sum(), 1)), 3), "agree": round(float((np.sign(vote[cov & (vote != 0)]) == sg[cov & (vote != 0)]).mean()), 4)}
    out["binance_first"] = {"cover": round(float(k_.sum() / max(cov.sum(), 1)), 3), "agree": round(float((side[k_] == sg[k_]).mean()), 4),
                            "binance_ticked_share": round(float((cov & bft).mean()), 3), "agree_when_binance_ticked": round(float((np.sign(bf[cov & bft]) == sg[cov & bft]).mean()), 4)}
    return out


if __name__ == "__main__":
    out = []
    for own, a, b, feed in [(".cache/re/btc5m-bot/post/own6_all.parquet", 1793456040, 1793458080, "btc5m_venues"),
                            (".cache/re/btc5m-bot/post/own_1793458200_1793462700.parquet", 1793458200, 1793462640, "btc5m_venues2"),
                            (".cache/re/btc5m-bot/post/own_1793462640_1793464380.parquet", 1793462640, 1793463900, "btc5m_venues2")]:
        r = run(own, a, b, feed); out.append(r); print(json.dumps(r))
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "bnfirst7.json"), "w"), indent=1)

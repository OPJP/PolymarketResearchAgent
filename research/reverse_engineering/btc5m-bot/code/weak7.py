"""Iteration 7: what are the weak-vote decisions? Underdog share and side agreement of 'buy the underdog' among live taker
matches by vote strength (frozen ten-series vote over [m - 600, m - 100) ms). Development blocks only. Usage: python weak7.py"""
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
    tk["price"] = tk.mamt / tk.tamt  # BUY: USDC / shares
    S = micro_series(feed, a, b); keys = sorted(S)
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys]); cov = np.isfinite(Q).any(axis=0)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0); av = np.abs(vote)
    pr = tk.price.to_numpy(float); und = pr < 0.48; fav = pr > 0.52
    rel = m / 1000 - tk.start.to_numpy()
    out = {"interval": [a, b], "n": int(len(m))}
    for nm, s in (("no_vote", cov & (av == 0)), ("weak_1_2", cov & (av >= 1) & (av <= 2)), ("mid_3_4", cov & (av >= 3) & (av <= 4)), ("strong_5plus", cov & (av >= 5))):
        out[nm] = {"n": int(s.sum()), "underdog_share": round(float(und[s].mean()), 3) if s.any() else None, "favourite_share": round(float(fav[s].mean()), 3) if s.any() else None,
                   "mean_rel": round(float(rel[s].mean()), 1) if s.any() else None, "median_abs_p_minus_half": round(float(np.median(np.abs(pr[s] - 0.5))), 3) if s.any() else None}
    return out


if __name__ == "__main__":
    out = []
    for own, a, b, feed in [(".cache/re/btc5m-bot/post/own_1793458200_1793462700.parquet", 1793458200, 1793462640, "btc5m_venues2"),
                            (".cache/re/btc5m-bot/post/own_1793462640_1793464380.parquet", 1793462640, 1793463900, "btc5m_venues2")]:
        r = run(own, a, b, feed); out.append(r); print(json.dumps(r))
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "weak7.json"), "w"), indent=1)

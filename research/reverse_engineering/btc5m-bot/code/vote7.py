"""Iteration 7: is the decay of the live side agreement (86% -> 83% -> 75%) a regime-mix effect? Per interval, the frozen
ten-series vote over [m - 600, m - 100) ms by vote strength |vote| (number of net agreeing series) and by the composite
move. Development blocks only. Usage: python vote7.py"""
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
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys])
    cov = np.isfinite(Q).any(axis=0)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0); comp = np.nansum(Q, axis=0)
    ok = (vote > 0) == up
    rel = (m / 1000 - tk.start.to_numpy())
    out = {"interval": [a, b], "n": int(len(m)), "covered": int(cov.sum())}
    av = np.abs(vote)
    out["by_abs_vote"] = {str(v): [round(float(ok[cov & (av == v)].mean()), 3), int((cov & (av == v)).sum())] for v in (1, 2, 3, 4, 5)}
    out["abs_vote_ge6"] = [round(float(ok[cov & (av >= 6)].mean()), 3), int((cov & (av >= 6)).sum())] if (cov & (av >= 6)).any() else None
    out["share_abs_vote_le2_of_voted"] = round(float((cov & (av >= 1) & (av <= 2)).sum() / max((cov & (av >= 1)).sum(), 1)), 3)
    cb = pd.cut(np.abs(comp), [-1, 0.01, 0.1, 0.5, 100])
    out["by_abs_comp_bp"] = {str(k): [round(float(ok[cov & (av > 0) & (cb == k)].mean()), 3) if (cov & (av > 0) & (cb == k)).any() else None, int((cov & (av > 0) & (cb == k)).sum())] for k in cb.categories}
    out["by_rel_third"] = {f"{lo}-{lo + 100}": [round(float(ok[cov & (av > 0) & (rel >= lo) & (rel < lo + 100)].mean()), 3), int((cov & (av > 0) & (rel >= lo) & (rel < lo + 100)).sum())] for lo in (0, 100, 200)}
    return out


if __name__ == "__main__":
    out = []
    for own, a, b, feed in [(".cache/re/btc5m-bot/post/own6_all.parquet", 1793456040, 1793458080, "btc5m_venues"),
                            (".cache/re/btc5m-bot/post/own_1793458200_1793462700.parquet", 1793458200, 1793462640, "btc5m_venues2"),
                            (".cache/re/btc5m-bot/post/own_1793462640_1793464380.parquet", 1793462640, 1793463900, "btc5m_venues2")]:
        r = run(own, a, b, feed); out.append(r); print(json.dumps(r))
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "vote7.json"), "w"), indent=1)

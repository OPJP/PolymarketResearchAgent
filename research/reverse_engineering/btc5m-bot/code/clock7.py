"""Iteration 7 (catalog X38 = panel-information iter6 P4): the block-clock limit per wallet. Same live taker matches,
ten-series microprice vote over [t - 600, t - 100) ms with t = (i) the matching-engine ms m, (ii) block ts - 2.0 s
(DECISION_LAG_S, the historical decision clock), (iii) block ts - 2.0 s with the window widened to [t - 1600, t - 100).
Development blocks only. Usage: python clock7.py OWN_PARQUET START END FEED"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
from lag7 import micro_series, mv


def main(own, a, b, feed):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].drop_duplicates(["tx", "token", "wal"])
    S = micro_series(feed, a, b); keys = sorted(S)
    up = tk.is_up.to_numpy(bool); wal = tk.wal.to_numpy()
    m = tk.m.to_numpy(np.int64); bt = tk.ts.to_numpy(np.int64) * 1000 - 2000
    res = {"interval": [a, b], "n": int(len(tk)), "block_minus_match_ms_median": float(np.median(tk.ts.to_numpy() * 1000 - m))}
    for nm, t, w0 in (("match_ms", m, 600), ("block_minus_2s", bt, 600), ("block_minus_2s_wide", bt, 1600)):
        Q = np.vstack([mv(S, k, t - w0, t - 100) for k in keys])
        cov = np.isfinite(Q).any(axis=0)
        vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0)
        k_ = cov & (vote != 0); ok = (vote > 0) == up
        r = {"cover": round(float(k_.sum() / max(cov.sum(), 1)), 4), "agree": round(float(ok[k_].mean()), 4)}
        for w in ("DS", "GF", "XM"):
            s = k_ & (wal == w)
            if s.sum() >= 5:
                r[w] = [round(float(ok[s].mean()), 4), int(s.sum())]
        res[nm] = r
    return res


if __name__ == "__main__":
    out = []
    for own, a, b, feed in [(".cache/re/btc5m-bot/post/own_1793458200_1793462700.parquet", 1793458200, 1793462640, "btc5m_venues2"),
                            (".cache/re/btc5m-bot/post/own_1793462640_1793464380.parquet", 1793462640, 1793463900, "btc5m_venues2")]:
        r = main(own, a, b, feed); out.append(r); print(json.dumps(r))
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "clock7.json"), "w"), indent=1)

"""Iteration 7 (catalog X41 = panel-mechanics iter6 P3): per-series reaction kernel of the bot's taker matches. For each of
the ten sized quote series (feed btc5m_venues2), the microprice move in 50-ms bins [m + k, m + k + 50) for k in
[-1000, +200) ms: share of matches with a tick (> 0.002 bp) in the bin, side agreement of that tick, and the same at
placebo times (m +- U(5, 60) s). Directional excess = (moved share x (2 agree - 1)) - placebo. Development block only.
Usage: python kernel7.py OWN_PARQUET START END FEED"""
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
    tk = tk[tk.m.notna()].sort_values("m").drop_duplicates(["tx", "token"])
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool); sg = np.where(up, 1.0, -1.0)
    rng = np.random.default_rng(11)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    S = micro_series(feed, a, b)
    res = {"n": int(len(m)), "series": {}}
    for key in sorted(S):
        prof = []
        for k0 in range(-1000, 200, 50):
            q = mv(S, key, m + k0, m + k0 + 50); qp = mv(S, key, pl + k0, pl + k0 + 50)
            cov = np.isfinite(q); covp = np.isfinite(qp)
            t = cov & (np.abs(q) > 0.002); tp = covp & (np.abs(qp) > 0.002)
            mvd = t.sum() / max(cov.sum(), 1); mvp = tp.sum() / max(covp.sum(), 1)
            ag = float((np.sign(q[t]) == sg[t]).mean()) if t.any() else np.nan
            agp = float((np.sign(qp[tp]) == sg[tp]).mean()) if tp.any() else np.nan
            dx = mvd * (2 * ag - 1) - (mvp * (2 * agp - 1) if np.isfinite(agp) else 0)
            prof.append((k0, round(float(mvd), 3), round(ag, 3) if np.isfinite(ag) else None, round(float(mvp), 3), round(agp, 3) if np.isfinite(agp) else None, round(float(dx), 4)))
        best = max(prof, key=lambda r: r[5])
        res["series"][f"{key[0]}_{key[1]}"] = {"peak_bin_ms": best[0], "peak_directional_excess": best[5], "peak_moved": best[1], "peak_agree": best[2],
                                               "profile": prof}
    return res


if __name__ == "__main__":
    own, a, b, feed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    r = main(own, a, b, feed)
    json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", f"kernel7_{a}.json"), "w"), indent=1)
    for k, v in r["series"].items():
        print(k, v["peak_bin_ms"], v["peak_directional_excess"], v["peak_moved"], v["peak_agree"])

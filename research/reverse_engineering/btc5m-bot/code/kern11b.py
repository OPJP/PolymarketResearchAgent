"""Iteration 11 (X60 comparison for kern11): the same kernel on 10-31 14:55-17:55 (D = 150 ms): directional excess of the sign of
the Binance USD-M BTC bookTicker MID change toward the bought outcome over [m - L - 50, m - L) for the cluster's taker matches
(server ms), against placebo instants; per wallet. kern11 uses trade prices on 08-06 (no bookTicker archive): both are reported.
Usage: python kern11b.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, live6

A, B = 1793458500, 1793469300


def r4(x):
    return round(float(x), 4)


def main(out):
    d = live6.own_taker(stale9.OWN, A, B)
    tok, books, trades = L.load_books(A, B)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["up"] = tk.token.map(lambda t: tok[t][2]); tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].drop_duplicates(["tx", "token"])
    rows = []
    for r in L.recs("btc5m_venues2", A - 30, B + 5):
        if r.get("v") == "bf" and r.get("y") == "BTC" and r.get("b") and r.get("a"):
            rows.append((r.get("E") or r["t"], (r["b"] + r["a"]) / 2))
    x = np.array(rows, float); x = x[np.argsort(x[:, 0], kind="stable")]
    T = x[:, 0].astype(np.int64); p = x[:, 1]
    # trade-like proxy: last aggressive trade price is not recorded for Binance here, so the mid is used
    def px(t):
        i = np.searchsorted(T, t, "right") - 1
        v = p[np.clip(i, 0, None)]; return np.where(i >= 0, v, np.nan)
    rng = np.random.default_rng(11)
    m = tk.m.to_numpy(np.int64); sg = np.where(tk.up.to_numpy(bool), 1.0, -1.0)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    prof = {}
    for Lg in range(0, 1001, 25):
        a = np.sign(px(m - Lg) - px(m - Lg - 50)) * sg; b = np.sign(px(pl - Lg) - px(pl - Lg - 50)) * sg
        prof[Lg] = [r4(np.nanmean(a)), r4(np.nanmean(b))]
    best = max(prof.items(), key=lambda kv: kv[1][0] - kv[1][1])
    res = {"matches": int(len(m)), "kernel_excess_by_L_ms (cluster, placebo)": prof, "kernel_peak_L_ms": int(best[0]), "peak_excess_minus_placebo": r4(best[1][0] - best[1][1])}
    for w, g in tk.groupby("wal"):
        mm = g.m.to_numpy(np.int64); ss = np.where(g.up.to_numpy(bool), 1.0, -1.0)
        pr = {Lg: r4(np.nanmean(np.sign(px(mm - Lg) - px(mm - Lg - 50)) * ss)) for Lg in range(0, 801, 50)}
        res.setdefault("kernel_by_wallet", {})[w] = {"n": int(len(mm)), "peak_L": int(max(pr, key=pr.get)), "profile": pr}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "kernel_excess_by_L_ms (cluster, placebo)"}, indent=1)[:3000])


if __name__ == "__main__":
    main(sys.argv[1])

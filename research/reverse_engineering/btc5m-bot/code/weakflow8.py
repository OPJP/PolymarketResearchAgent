"""Iteration 8, X44 step 0 (panel-information iter7 P1): on live taker matches whose frozen ten-series microprice vote is weak
(|vote| <= 2) or silent, does the SIGNED AGGRESSIVE NOTIONAL on Binance USD-M BTC / ETH (REST aggTrades at exchange ms,
already on disk: post/rest6_bnf_*) over [m - 600, m - 100) predict the side? Placebo: the same matches shifted by -3 s
([m - 3600, m - 3100)). Also the 50-ms kernel of the directional excess of signed notional over [m - 1000, m + 200).
Development blocks only (10-31 14:22-14:47 and 14:54-15:10, the span rest6 covers). Writes results/weakflow8.json."""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
from lag7 import micro_series, mv

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")


def agg(sym):
    fs = sorted(glob.glob(os.path.join(C, "post", f"rest6_bnf_{sym}_*.parquet")))
    d = pd.concat([pd.read_parquet(x) for x in fs]).drop_duplicates().sort_values("T", kind="stable")
    return d["T"].to_numpy(np.int64), (d["p"] * d["q"] * d["s"]).to_numpy(float)


def flow(T, N, t0, t1):
    c = np.concatenate([[0.0], np.cumsum(N)])
    return c[np.searchsorted(T, t1, "left")] - c[np.searchsorted(T, t0, "left")]


def matches(own, a, b, feed):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].drop_duplicates(["tx", "token"])
    tk = tk[(tk.m >= a * 1000) & (tk.m < b * 1000)]
    S = micro_series(feed, a, b); keys = sorted(S)
    m = tk.m.to_numpy(np.int64)
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys]); cov = np.isfinite(Q).any(axis=0)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0)
    tk["vote"] = np.where(cov, vote, np.nan)
    return tk


if __name__ == "__main__":
    parts = [matches(os.path.join(C, "post", "own_1793456520_1793458020.parquet"), 1793456520, 1793458020, "btc5m_venues"),
             matches(os.path.join(C, "post", "own_1793458200_1793462700.parquet"), 1793458456, 1793459400, "btc5m_venues2")]
    tk = pd.concat(parts, ignore_index=True)
    sgn = np.where(tk.is_up.to_numpy(bool), 1.0, -1.0)  # toward the bought outcome: Up <-> BTC up
    m = tk.m.to_numpy(np.int64)
    out = {"n_matches": int(len(tk))}
    FL = {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        T, N = agg(sym)
        FL[sym] = (T, N)
    vote = tk.vote.to_numpy(float)
    groups = {"all": np.ones(len(tk), bool), "voted_strong_3plus": np.abs(vote) >= 3, "weak_1_2": (np.abs(vote) >= 1) & (np.abs(vote) <= 2),
              "no_vote_or_uncovered": ~(np.abs(vote) >= 1)}
    for sym, (T, N) in FL.items():
        f0 = flow(T, N, m - 600, m - 100) * sgn
        fp = flow(T, N, m - 3600, m - 3100) * sgn
        r = {}
        for g, k in groups.items():
            nz, nzp = k & (f0 != 0), k & (fp != 0)
            r[g] = {"n": int(k.sum()), "cover": round(float(nz.sum() / max(k.sum(), 1)), 3), "agree": round(float((f0[nz] > 0).mean()), 3) if nz.any() else None,
                    "placebo_cover": round(float(nzp.sum() / max(k.sum(), 1)), 3), "placebo_agree": round(float((fp[nzp] > 0).mean()), 3) if nzp.any() else None,
                    "agree_big_10k": round(float((f0[k & (np.abs(f0) > 1e4)] > 0).mean()), 3) if (k & (np.abs(f0) > 1e4)).any() else None,
                    "n_big_10k": int((k & (np.abs(f0) > 1e4)).sum())}
        # 50-ms kernel (all matches): directional excess = moved share x (2 agree - 1)
        ker = []
        for lo in range(-1000, 200, 50):
            x = flow(T, N, m + lo, m + lo + 50) * sgn
            xp = flow(T, N, m + lo - 3000, m + lo - 2950) * sgn
            e = float((x != 0).mean() * (2 * (x[x != 0] > 0).mean() - 1)) if (x != 0).any() else 0.0
            ep = float((xp != 0).mean() * (2 * (xp[xp != 0] > 0).mean() - 1)) if (xp != 0).any() else 0.0
            ker.append([lo, round(e - ep, 4), round(float((x != 0).mean()), 3)])
        r["kernel_50ms_excess_minus_placebo"] = ker
        out[sym] = r
        print(sym, json.dumps({g: r[g] for g in groups}))
        print(" kernel peak", sorted(ker, key=lambda z: -z[1])[:4])
    json.dump(out, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "weakflow8.json"), "w"), indent=1)

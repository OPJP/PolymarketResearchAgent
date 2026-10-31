"""Iteration 8 (follow-up of gate8, X56; and X44 weak-vote side): on live taker matches, does the SIDE follow the Polymarket
book itself? For each match at server ms m: the Up mid / Up ask / Up bid change over [m - W, m - 100) from my unthrottled
book (server ms); rules: PM momentum (buy Up if the Up mid rose), PM value (buy the outcome whose ask fell). By frozen
ten-series vote strength (as weak7). Placebo: the same matches shifted by -3 s. Usage: python pmside8.py OWN A B VFEED CFEED"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
from lag7 import micro_series, mv
from gate8 import raw_touch


def main(own, a, b, vf, cf):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].sort_values("m").drop_duplicates(["tx", "token"])
    tk = tk[(tk.m >= a * 1000 + 5000) & (tk.m < b * 1000)]
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool); stt = tk.start.to_numpy()
    S = micro_series(vf, a, b); keys = sorted(S)
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys]); cov = np.isfinite(Q).any(axis=0)
    vote = np.where(cov, np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0), np.nan)
    R = raw_touch(cf, a, b)
    out = {"interval": [a, b], "n": int(len(m))}
    for W in (600, 1500, 3000):
        res = {}
        for sh, nm in ((0, "real"), (-3000, "placebo")):
            dmid = np.full(len(m), np.nan); dask = np.full(len(m), np.nan); dbid = np.full(len(m), np.nan)
            for s0, rg in R.groupby("m"):
                sel = np.where(stt == s0)[0]
                if not len(sel):
                    continue
                rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float); bb = rg.bb.to_numpy(float)
                def at(x, tt):
                    i = np.searchsorted(rs, tt, "right") - 1
                    o = x[np.clip(i, 0, None)].astype(float); o[i < 0] = np.nan
                    return o
                t1 = m[sel] + sh - 100; t0 = m[sel] + sh - W
                dask[sel] = at(ba, t1) - at(ba, t0); dbid[sel] = at(bb, t1) - at(bb, t0)
                dmid[sel] = (at(ba, t1) + at(bb, t1) - at(ba, t0) - at(bb, t0)) / 2
            # momentum: buy Up if Up mid rose; value: buy the outcome whose ask fell (Up ask fell -> Up; Down ask = 1 - bb fell <=> bb rose -> Down)
            mom = np.where(dmid > 0, 1, np.where(dmid < 0, 0, -1))
            val = np.where((dask < 0) & ~(dbid > 0), 1, np.where((dbid > 0) & ~(dask < 0), 0, -1))
            r = {}
            av = np.abs(vote)
            for g, k in (("all", np.ones(len(m), bool)), ("strong_3plus", av >= 3), ("weak_1_2", (av >= 1) & (av <= 2)), ("no_vote", ~(av >= 1))):
                km = k & (mom >= 0); kv = k & (val >= 0)
                r[g] = {"n": int(k.sum()), "mom_cover": round(float(km.sum() / max(k.sum(), 1)), 3), "mom_agree": round(float((mom[km] == up[km]).mean()), 3) if km.any() else None,
                        "val_cover": round(float(kv.sum() / max(k.sum(), 1)), 3), "val_agree": round(float((val[kv] == up[kv]).mean()), 3) if kv.any() else None}
            res[nm] = r
        out[f"W{W}"] = res
        print(W, json.dumps(res))
    return out


if __name__ == "__main__":
    own, a, b, vf, cf = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
    out = main(own, a, b, vf, cf)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", f"pmside8_{a}.json"), "w"), indent=1)

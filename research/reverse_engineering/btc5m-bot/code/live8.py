"""Iteration 8: the FOURTH out-of-sample live interval (10-31 16:33-17:55, development block 12-18) for the frozen live side
rule, and the out-of-sample test of the decision-level hazard with the stale-liquidity gate (X52, gate8.py).
1. final_rule._live_vote (frozen, exam-input feeds btc5m_xclob / btc5m_xven) on the new interval, plus the ten-series vote
   (lab feed btc5m_venues2) by vote strength (as vote7).
2. Hazard models of gate8.design fitted on one interval and scored on a later one (no refit):
   lab feeds  : fit 14:55-16:04 (venues2 + clob_raw2) -> score 16:04-16:33 and 16:33-17:55
   exam feeds : fit 16:04-16:33 (xven + xclob)        -> score 16:33-17:55
   AUC of activity, activity+gate_only (the Polymarket book/trade activity baseline), activity+tick, activity+tick+gate;
   gain of the tick over the activity+gate_only baseline with a 5-minute-window bootstrap (2,000 draws).
Writes results/live8.json."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
import gate8
from lag7 import micro_series, mv
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
import final_rule as FR

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
P = os.path.join(ROOT, ".cache", "re", "btc5m-bot", "post")
OWN = {"A": (os.path.join(P, "own_1793458200_1793462700.parquet"), 1793458500, 1793462640),
       "B": (os.path.join(P, "own_1793462640_1793464380.parquet"), 1793462640, 1793464380),
       "C": (os.path.join(P, "own_1793464380_1793469400.parquet"), 1793464380, 1793469300)}


def fills_for(own, a, b):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    d = d[d.token.isin(tok.keys())].copy()
    d["start"] = d.token.map(lambda t: tok[t][1]); d["is_up"] = d.token.map(lambda t: tok[t][2])
    d = d[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in d.start], bool)]
    return d.rename(columns={"wal": "wallet"}), tok, trades


def vote_strength(own, a, b, feed):
    d, tok, trades = fills_for(own, a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[d.role == "T"].drop_duplicates(["tx", "token"]).copy(); tk["m"] = tk.tx.map(mt); tk = tk[tk.m.notna()]
    tk = tk[(tk.m >= a * 1000 + 5000) & (tk.m < b * 1000)]
    S = micro_series(feed, a, b); keys = sorted(S)
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys]); cov = np.isfinite(Q).any(axis=0)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0)
    ok = (vote > 0) == up; av = np.abs(vote)
    out = {"n": int(len(m)), "covered": int(cov.sum()), "voted": int((cov & (av > 0)).sum()),
           "agree_voted": round(float(ok[cov & (av > 0)].mean()), 4) if (cov & (av > 0)).any() else None,
           "weak_share_of_voted": round(float(((av >= 1) & (av <= 2) & cov).sum() / max((cov & (av > 0)).sum(), 1)), 3)}
    for lo, hi, nm in ((1, 1, "1"), (2, 2, "2"), (3, 4, "3-4"), (5, 99, "5+")):
        s = cov & (av >= lo) & (av <= hi)
        out["by_strength_" + nm] = [round(float(ok[s].mean()), 3) if s.any() else None, int(s.sum())]
    return out


def boot_gain(y, s1, s0, units, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    uu = np.unique(units); idx = {u: np.where(units == u)[0] for u in uu}
    g = []
    for _ in range(n):
        pick = np.concatenate([idx[u] for u in rng.choice(uu, len(uu))])
        if y[pick].min() == y[pick].max():
            continue
        g.append(roc_auc_score(y[pick], s1[pick]) - roc_auc_score(y[pick], s0[pick]))
    g = np.array(g)
    return [round(float(np.percentile(g, 2.5)), 4), round(float(np.percentile(g, 97.5)), 4), round(float((g <= 0).mean()), 4)]


def design_with_units(own, a, b, vf, cf):
    gate8.DESIGN_ONLY = True
    y, X = gate8.main(own, a, b, vf, cf)
    gate8.DESIGN_ONLY = False
    return y, X


if __name__ == "__main__":
    res = {}
    own, a, b = OWN["C"]
    fC, tokC, trC = fills_for(own, a, b)
    res["frozen_live_vote_exam_feeds_C"] = FR._live_vote(fC, None, a, b)
    print("frozen _live_vote C", json.dumps(res["frozen_live_vote_exam_feeds_C"]), flush=True)
    res["ten_series_vote_C"] = vote_strength(own, a, b, "btc5m_venues2")
    print("ten-series C", json.dumps(res["ten_series_vote_C"]), flush=True)
    # hazard out of sample
    for tag, fit, tests, vf, cf in (("lab", "A", ["B", "C"], "btc5m_venues2", "btc5m_clob_raw2"), ("exam", "B", ["C"], "btc5m_xven", "btc5m_xclob")):
        yf, Xf = design_with_units(*OWN[fit], vf, cf)
        models = {k: LogisticRegression(max_iter=3000).fit(v, yf) for k, v in Xf.items()}
        for t in tests:
            yt, Xt = design_with_units(*OWN[t], vf, cf)
            sc = {k: models[k].predict_proba(Xt[k])[:, 1] for k in Xt}
            r = {"fit": fit, "n_fit": int(len(yf)), "n_test": int(len(yt)), "base_rate_test": round(float(yt.mean()), 4)}
            for k, s in sc.items():
                r["auc_" + k] = round(float(roc_auc_score(yt, s)), 4)
            # units: 5-minute blocks of grid order (grid is window-major, 2,800 points per window per outcome block)
            units = np.arange(len(yt)) // 2800
            r["gain_tick_over_pm_activity_ci95_pnull"] = boot_gain(yt, sc["activity+tick+gate"], sc["activity+gate_only"], units)
            res[f"hazard_{tag}_{fit}_to_{t}"] = r
            print(tag, fit, "->", t, json.dumps(r), flush=True)
    json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "live8.json"), "w"), indent=1, default=str)

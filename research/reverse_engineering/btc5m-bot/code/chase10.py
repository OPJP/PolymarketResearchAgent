"""Iteration 10 (panel iter9 mechanics P4 = X80, descriptive first step): chase episodes as a readout of a reservation price.
Decisions = cluster taker-first orders (limit from calldata, at the match ms) + located lost-race insertions (limit L, at the
insertion ms), 10-31 14:55-17:55, any wallet. Episode = same window and outcome, gaps < 1 s. Per episode: decisions, the walk
of the limits (up / flat / down steps), the reach R_hat = max limit - o's ask 500 ms before the first decision (cents), the
venue move toward o from 500 ms before the start to the last decision (Binance USD-M BTC microprice, bp) and Delta_o at
sigma = 0.67 bp / sqrt(s); the stop: o's ask 1 s after the last decision minus the max limit. A reservation price
R = mid0 + k Delta dS - c predicts reach ~ k Delta dS - c and a stop where the next ask exceeds R.
Usage: python chase10.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm, spearmanr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9, gate8
from lag7 import micro_series, mv

C = L.C
A, B = 1793458500, 1793469300


def main(out):
    o, _ = ins9.load_orders(A, B)
    tokmap = {}; txms = {}
    for r in L.recs("btc5m_clob_raw2", A - 600, B + 60):
        k = r.get("k")
        if k == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
        elif k == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy(); o["mstart"] = o.mstart.astype(int); o["m0"] = o.tx0.str.lower().map(txms)
    T = o[(o["first"] == "T") & o.m0.notna() & o.Lim.notna()]
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet"); Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])]
    D = pd.concat([pd.DataFrame({"st": T.mstart, "up": T.is_up.astype(bool), "s": T.m0.astype(np.int64), "L": T.Lim.astype(float), "w": T.w, "kind": "T"}),
                   pd.DataFrame({"st": Mi.mstart.astype(int), "up": Mi.is_up.astype(bool), "s": Mi.s_ins.astype(np.int64), "L": Mi.L.astype(float), "w": Mi.w, "kind": "M"})])
    D = D.sort_values(["st", "up", "s"]).reset_index(drop=True)
    gap = D.groupby(["st", "up"]).s.diff()
    D["ep"] = ((gap.isna()) | (gap > 1000)).cumsum()
    R = gate8.raw_touch("btc5m_clob_raw2", A, B)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    S = micro_series("btc5m_venues2", A, B)

    def ask_at(st, up, t):
        x = tch.get(int(st))
        if x is None:
            return np.nan
        rs, bb, ba = x; j = np.searchsorted(rs, t, "right") - 1
        if j < 0:
            return np.nan
        return ba[j] if up else 1 - bb[j]

    rows = []
    for ep, g in D.groupby("ep"):
        st, up = int(g.st.iloc[0]), bool(g.up.iloc[0]); s0, s1 = int(g.s.iloc[0]), int(g.s.iloc[-1])
        a0 = ask_at(st, up, s0 - 500); a_end = ask_at(st, up, s1 + 1000)
        steps = np.diff(g.L.to_numpy()) * 100
        tau = max(5.0, st + 300 - s0 / 1000)
        mid0 = a0 - 0.005 if np.isfinite(a0) else np.nan
        dl = norm.pdf(norm.ppf(np.clip(mid0, 0.02, 0.98))) / (0.67 * np.sqrt(tau)) if np.isfinite(mid0) else np.nan
        mvb = mv(S, ("bf", "BTC"), np.array([s0 - 500]), np.array([s1]))[0] if ("bf", "BTC") in S else np.nan
        dS = (1 if up else -1) * mvb
        rows.append((ep, len(g), g.w.nunique(), (g.L.max() - a0) * 100 if np.isfinite(a0) else np.nan, (a_end - g.L.max()) * 100 if np.isfinite(a_end) else np.nan,
                     dS, dl, int((steps > 0.5).sum()), int((np.abs(steps) <= 0.5).sum()), int((steps < -0.5).sum()), a0))
    E = pd.DataFrame(rows, columns=["ep", "n", "wallets", "reach_c", "stop_gap_c", "dS_bp", "delta", "up", "flat", "down", "a0"])
    multi = E[E.n >= 2]
    res = {"decisions": int(len(D)), "episodes": int(len(E)), "multi_decision_episodes": int(len(multi)),
           "n_q50_90": [float(x) for x in np.percentile(E.n, [50, 90])],
           "steps_up_flat_down": [int(multi.up.sum()), int(multi.flat.sum()), int(multi.down.sum())],
           "reach_c_q10_50_90": [float(x) for x in np.nanpercentile(E.reach_c, [10, 50, 90])],
           "stop_gap_c_q10_50_90": [float(x) for x in np.nanpercentile(E.stop_gap_c, [10, 50, 90])],
           "P(next ask > max limit at stop)": round(float(np.nanmean(E.stop_gap_c > 0.5)), 4)}
    k = np.isfinite(E.reach_c) & np.isfinite(E.dS_bp) & np.isfinite(E.delta)
    x = (100 * E.delta * E.dS_bp)[k]; y = E.reach_c[k]
    res["spearman(reach, 100 Delta dS)"] = round(float(spearmanr(x, y).statistic), 4) if k.sum() > 20 else None
    res["spearman(reach, dS)"] = round(float(spearmanr(E.dS_bp[k], y).statistic), 4) if k.sum() > 20 else None
    if k.sum() > 20:
        b = np.polyfit(x, y, 1)
        res["reach = a + b x 100 Delta dS (OLS)"] = [round(float(b[1]), 3), round(float(b[0]), 3)]
    res["reach by n"] = {str(n_): [round(float(np.nanmedian(g.reach_c)), 2), int(len(g))] for n_, g in E.groupby(E.n.clip(upper=4))}
    json.dump(res, open(out, "w"), indent=1, default=lambda v: v.item() if hasattr(v, "item") else str(v))
    print(json.dumps(res, indent=1, default=lambda v: v.item() if hasattr(v, "item") else str(v)))


if __name__ == "__main__":
    main(sys.argv[1])

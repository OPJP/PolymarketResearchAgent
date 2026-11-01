"""Iteration 9 (panel iter8 information P4 = X62, first step): how informative are the fair-value brackets of opposite-outcome
pairs? For every pair of cluster taker-first orders on opposite outcomes of the same window matched within 1 s (10-31
14:14-17:55, calldata limits, raw-feed match ms), the bot's FV_up must lie in [L_up, 1 - L_down] (+/- its margin). Bracket width,
whether the Polymarket Up mid at the first match (raw-feed touch, 50 ms before) lies inside, and the midpoint minus that mid,
against the Binance USD-M BTC move over the 500 ms before the first match (a lagging-mid anchor would put the midpoint on the
side of the move). Usage: python bracket9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9, gate8
from lag7 import micro_series, mv

C = L.C


def main(out):
    a, b = 1793458456, 1793469300
    o, _ = ins9.load_orders(a, b)
    tokmap = {}; txms = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        k = r.get("k")
        if k == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
        elif k == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna() & (o["first"] == "T")].copy(); o["Lx"] = o.Lim.fillna(o.px0); o["m0"] = o.tx0.str.lower().map(txms)
    o = o[o.m0.notna()].sort_values("m0")
    R = gate8.raw_touch("btc5m_clob_raw2", a, b)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    S = micro_series("btc5m_venues2", a, b)
    pairs = []
    for st, g in o.groupby("mstart"):
        u = g[g.is_up == True]; d = g[g.is_up == False]
        if not len(u) or not len(d):
            continue
        dm = d.m0.to_numpy(); dl = d.Lx.to_numpy()
        for r in u.itertuples():
            j = np.where(np.abs(dm - r.m0) <= 1000)[0]
            if not len(j):
                continue
            jj = j[np.argmin(np.abs(dm[j] - r.m0))]
            t0 = min(r.m0, dm[jj])
            tc = tch.get(int(st))
            if tc is None:
                continue
            i = np.searchsorted(tc[0], t0 - 50, "right") - 1
            if i < 0:
                continue
            mid = (tc[1][i] + tc[2][i]) / 2
            lo, hi = r.Lx, 1 - dl[jj]
            pairs.append((lo, hi, mid, t0))
    P = pd.DataFrame(pairs, columns=["lo", "hi", "mid", "t0"])
    P["width_c"] = ((P.hi - P.lo) * 100).round(1)
    P["inside"] = (P.mid >= P.lo - 1e-9) & (P.mid <= P.hi + 1e-9)
    P["midpt_minus_mid_c"] = (((P.lo + P.hi) / 2 - P.mid) * 100).round(2)
    if ("bf", "BTC") in S:
        P["move_bp"] = mv(S, ("bf", "BTC"), P.t0.to_numpy(np.int64) - 500, P.t0.to_numpy(np.int64))
    res = {"pairs": int(len(P)), "width_c": P.width_c.clip(-5, 6).value_counts().sort_index().to_dict(),
           "share_width_le_1c": round(float((P.width_c <= 1.0).mean()), 4), "share_negative_width(pair cost > 1)": round(float((P.width_c < 0).mean()), 4),
           "pm_mid_inside": round(float(P.inside.mean()), 4),
           "midpoint_minus_mid_c_q": [float(x) for x in np.percentile(P.midpt_minus_mid_c, [10, 50, 90])]}
    if "move_bp" in P:
        k = P.move_bp.notna() & (np.abs(P.move_bp) > 0.1)
        res["corr(midpoint - mid, move)"] = round(float(np.corrcoef(P.midpt_minus_mid_c[k], P.move_bp[k])[0, 1]), 4) if k.sum() > 10 else None
        res["sign_agree(midpoint - mid, move) |move|>0.1bp, midpoint != mid"] = round(float((np.sign(P.midpt_minus_mid_c[k & (P.midpt_minus_mid_c != 0)]) == np.sign(P.move_bp[k & (P.midpt_minus_mid_c != 0)])).mean()), 4) if (k & (P.midpt_minus_mid_c != 0)).sum() > 10 else None
        res["n_moving"] = int(k.sum())
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

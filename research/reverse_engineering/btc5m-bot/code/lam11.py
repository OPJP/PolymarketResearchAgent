"""Iteration 11 (panel iter10 assumptions P3 = X98, step 2): the bot's VIEW LAG of the Polymarket book, Lambda, read from its
limits. Decisions of 10-31 14:55-17:55 (development): won races (taker-first orders, limit from calldata, arrival a = match -
150 ms) and located lost races (limit L, a = insertion - 150). Restricted to decisions whose o-ask CHANGED in [a - 400, a]
(otherwise every Lambda gives the same ask). Profile: share with limit == o's ask at a - Lambda, and limit >= o's ask at
a - Lambda, for Lambda = -150..500 ms in 10-ms steps (negative = after the arrival, i.e. during the hold: a placebo for what the
bot could not have seen). The peak of 'limit == ask(a - Lambda)' estimates Lambda (+ the bot's processing).
Usage: python lam11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9, gate8

C = L.C
A, B = 1793458500, 1793469300


def main(out):
    o, _ = ins9.load_orders(A, B)
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", A - 600, B + 60):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    tm = pd.read_parquet(C + "/it10/txms10.parquet"); mt = dict(zip(tm.tx, tm.m))
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy(); o["m0"] = o.tx0.str.lower().map(mt)
    T = o[(o["first"] == "T") & o.m0.notna() & o.Lim.notna()]
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet"); Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])]
    D = pd.concat([pd.DataFrame({"st": T.mstart.astype(int), "up": T.is_up.astype(bool), "a": T.m0.astype(np.int64) - 150, "L": T.Lim.astype(float), "w": T.w, "kind": "won"}),
                   pd.DataFrame({"st": Mi.mstart.astype(int), "up": Mi.is_up.astype(bool), "a": Mi.s_ins.astype(np.int64) - 150, "L": Mi.L.astype(float), "w": Mi.w, "kind": "lost"})], ignore_index=True)
    R = gate8.raw_touch("btc5m_clob_raw2", A, B)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    lams = np.arange(-150, 510, 10)
    asks = np.full((len(D), len(lams)), np.nan); chg = np.zeros(len(D), bool)
    for i, (st, up, a) in enumerate(zip(D.st.to_numpy(), D.up.to_numpy(), D.a.to_numpy(np.int64))):
        x = tch.get(int(st))
        if x is None:
            continue
        rs, bb, ba = x
        tt = a - lams
        j = np.searchsorted(rs, tt, "right") - 1
        v = np.where(j >= 0, (ba if up else 1 - bb)[np.clip(j, 0, None)], np.nan)
        asks[i] = np.round(v, 4)
        w = (lams >= 0) & (lams <= 400)
        vv = v[w]
        chg[i] = np.isfinite(vv).all() and (np.nanmax(vv) - np.nanmin(vv) > 0.005)
    Lr = np.round(D.L.to_numpy(float), 4)
    res = {"decisions": int(len(D)), "with_ask_change_in_[a-400,a]": int(chg.sum())}
    for nm, sel in (("all", np.ones(len(D), bool)), ("changed", chg), ("changed_won", chg & (D.kind == "won").to_numpy()), ("changed_lost", chg & (D.kind == "lost").to_numpy())):
        eq = np.nanmean(np.abs(asks[sel] - Lr[sel, None]) < 1e-6, axis=0); ge = np.nanmean(Lr[sel, None] >= asks[sel] - 1e-6, axis=0)
        k = int(np.argmax(eq))
        res[nm] = {"n": int(sel.sum()), "peak_lambda_eq": int(lams[k]), "peak_eq": round(float(eq[k]), 4),
                   "eq_by_lambda": {int(l): round(float(e), 4) for l, e in zip(lams, eq) if l % 30 == 0},
                   "ge_by_lambda": {int(l): round(float(e), 4) for l, e in zip(lams, ge) if l % 30 == 0}}
    for w in ("DS", "GF", "XM"):
        sel = chg & (D.w == w).to_numpy()
        if sel.sum() > 30:
            eq = np.nanmean(np.abs(asks[sel] - Lr[sel, None]) < 1e-6, axis=0); k = int(np.argmax(eq))
            res[f"changed_{w}"] = {"n": int(sel.sum()), "peak_lambda_eq": int(lams[k]), "peak_eq": round(float(eq[k]), 4),
                                   "eq_at": {int(l): round(float(e), 4) for l, e in zip(lams, eq) if l in (-60, 0, 30, 60, 90, 120, 150, 210, 300)}}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1)[:5000])


if __name__ == "__main__":
    main(sys.argv[1])

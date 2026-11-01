"""Iteration 12, panel iter11 information P2 steps 1-2 (X101): the independent FAST CROWD as a second label. For every
clean onset of the 10-31 onset tables (A / C), crowd_fast = any non-operator taker BUY of o (calldata of 10-31 match txs,
it9/cd9 + it10/cdall10) whose sign-to-match is 180-400 ms and whose match falls in [tau + 150, tau + 700) ms. Diagnostic
only, never a rule feature. Reports the co-take table, then for candidate public inputs X (the evt10-style FULL design,
FULL + the Coinbase class of cbx12) the odds ratio of crowd_fast in logit(y_cluster ~ X + crowd_fast) fitted on one half
and the share of the raw co-take log odds ratio that X explains."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import live_lab as L
import statsmodels.api as sm
from cbx12 import cb_series, classify, design
C = L.C
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
A0, B0 = 1793458500, 1793469300
OPS = set(L.W) | {"0xd84403efd50b49a1d8a7181627e00307e6ea5908"}


def main():
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", A0 - 600, B0 + 60):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    tm = pd.read_parquet(C + "/it10/txms10.parquet"); mt = dict(zip(tm.tx.str.lower(), tm.m))
    cd = pd.concat([pd.read_parquet(C + "/it9/cd9.parquet"), pd.read_parquet(C + "/it10/cdall10.parquet")], ignore_index=True)
    cd["m"] = cd.tx.str.lower().map(mt)
    cr = cd[(cd.role == "T") & ~cd.maker.str.lower().isin({x.lower() for x in OPS}) & (cd.oside == 0) & cd.m.notna() & cd.sign_ms.notna()].drop_duplicates(["tx", "maker", "token"]).copy()
    cr["lat"] = cr.m.astype(float) - cr.sign_ms.astype(float)
    cr = cr[(cr.lat >= 180) & (cr.lat <= 400)]
    cr["st"] = cr.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[0]); cr["up"] = cr.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[1])
    cr = cr[cr.st.notna()]
    crg = {(int(k[0]), bool(k[1])): np.sort(g.m.to_numpy(np.int64)) for k, g in cr.groupby(["st", "up"])}
    res = {"fast_crowd_orders": int(len(cr)), "fast_crowd_wallets": int(cr.maker.nunique())}
    E = {}
    for nm in ("A", "C"):
        e = pd.read_parquet(f"{C}/it11/onset_{nm}.parquet")
        e = e[e.clean.astype(bool)].reset_index(drop=True)
        cb = cb_series(e.tau.min() / 1000 - 5, e.tau.max() / 1000 + 5)
        e["cbcls"], e["cbmv"] = classify(e, cb)
        f = np.zeros(len(e))
        for i, (st, sg, tau) in enumerate(zip(e.st.to_numpy(), e.sgn.to_numpy(), e.tau.to_numpy(float))):
            g = crg.get((int(st), bool(sg > 0)))
            if g is not None:
                f[i] = float(np.searchsorted(g, tau + 700) > np.searchsorted(g, tau + 150))
        e["crowd"] = f
        y = e.y.to_numpy(float)
        tab = {"P(crowd | taken)": round(float(f[y == 1].mean()), 4), "P(crowd | skipped)": round(float(f[y == 0].mean()), 4),
               "P(taken | crowd)": round(float(y[f == 1].mean()), 4), "P(taken | no crowd)": round(float(y[f == 0].mean()), 4)}
        a, b, c_, d = ((y == 1) & (f == 1)).sum(), ((y == 1) & (f == 0)).sum(), ((y == 0) & (f == 1)).sum(), ((y == 0) & (f == 0)).sum()
        tab["raw_log_OR"] = round(float(np.log((a + 0.5) * (d + 0.5) / ((b + 0.5) * (c_ + 0.5)))), 4)
        pr = (e.cls == "PRICE").to_numpy()
        tab["price_events"] = {"P(crowd | taken)": round(float(f[pr & (y == 1)].mean()), 4), "P(crowd | skipped)": round(float(f[pr & (y == 0)].mean()), 4), "n": int(pr.sum())}
        res[nm] = {"events": int(len(e)), "co_take": tab}
        E[nm] = e
    # conditional association: logit(y ~ X + crowd) on each half (in-sample per half; the crowd coefficient is the quantity)
    for nm in ("A", "C"):
        e = E[nm]; y = e.y.to_numpy(float)
        out = {}
        for lab, wc in (("none", None), ("FULL", False), ("FULL+coinbase", True)):
            X = pd.DataFrame({"crowd": e.crowd.to_numpy(float)}) if wc is None else design(e, wc).assign(crowd=e.crowd.to_numpy(float))
            try:
                fit = sm.Logit(y, sm.add_constant(X.astype(float))).fit(disp=0, maxiter=200)
                out[lab] = {"crowd_log_OR": round(float(fit.params["crowd"]), 4), "se": round(float(fit.bse["crowd"]), 4)}
            except Exception as ex:
                out[lab] = {"error": repr(ex)[:120]}
        raw = out["none"].get("crowd_log_OR")
        for lab in ("FULL", "FULL+coinbase"):
            if raw and "crowd_log_OR" in out[lab]:
                out[lab]["share_of_raw_log_OR_explained"] = round(float(1 - out[lab]["crowd_log_OR"] / raw), 4)
        res[nm]["conditional"] = out
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(R, "coat12.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

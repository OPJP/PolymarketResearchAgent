"""Builds code/hazflowD15.py from code/hazflow14.py (pre-registration 8 edits only)."""
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
DOC_OLD = s.split('"""')[1]
DOC_NEW = """Iteration 15, PRE-REGISTRATION 8 (X144 step 2 = X143 step 4): the DEPTH-WEIGHTED decision-hazard nowcast for condition 5. Every
50-ms bin of every (window, outcome) of 10-20..22 is scored with the frozen model_it14_hazard_full.txt (as hazflow14); each bin's
probability is weighted by the expected realized taker fill at the bot's Polymarket view (grid time e + 50 ms, server clock):
E[min(menu, D1)] = (1 - pL) min(30, D1) + pL min(100, D1), D1 = the capture's ask depth at best + 0..1 c of that outcome (l2ingest15),
pL = P(original size >= 90) of the operator taker orders on the pre-10-20 calldata hours of the 30 / 100 menu.
hD(s) = sum over bins with end e in [s - 2, s - 1) s of P^(Up) w(Up) - P^(Down) w(Down); nfhazD15 = cD x hD, cD = no-intercept OLS of
the operator's per-second signed flow on hD on 10-20 ONLY (the only capture-L2 day before the score days). Score days 10-21..22
(576 windows): tracker trk_a (frozen constants, strict fills) with avg, mix14 (frozen) and mix15 = 0.5 avg + 0.5 nfhazD15.
Adoption: mix15 replaces mix14 only if it beats mix14 on BOTH pooled Pearson and Spearman over the 576 windows of 10-21..22.
Usage: python hazflowD15.py HF_DIR TAPE_DIR L2_DIR OUT_DIR"""
s = s.replace(DOC_OLD, DOC_NEW, 1)


def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b)


rep('DAYS = ["2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]\nFIT = set(DAYS[:3])',
    'DAYS = ["2026-10-20", "2026-10-21", "2026-10-22"]\nFIT = set(DAYS[:1])')
rep("    A, TD, OUT = sys.argv[1], sys.argv[2], sys.argv[3]\n    t0 = time.time()",
    """    A, TD, L2, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    t0 = time.time()
    cd = pd.read_parquet(f"{C}/calldata_sample.parquet", columns=["tx", "role", "maker", "taker_amt"])
    cd = cd[(cd.role == "T") & cd.maker.str.lower().isin(CL)].merge(pd.read_parquet(f"{C}/calldata_sample_txs.parquet"), on="tx", how="left")
    cd = cd[(cd.ts < 1792454400) & cd.taker_amt.astype(float).round().isin([30.0, 100.0])]
    PL = float((cd.taker_amt.astype(float) >= 90).mean()) if len(cd) > 100 else 0.15
    print("pL", PL, len(cd), flush=True)
    GR = {}
    for day in DAYS:
        tk = pd.read_parquet(f"{L2}/l2tok_{day}.parquet"); gd = pd.read_parquet(f"{L2}/l2grid_{day}.parquet", columns=["ti", "k", "c1"])
        c1 = gd.c1.to_numpy(np.float32).reshape(len(tk), -1)
        for i, r in enumerate(tk.itertuples()):
            if int(r.start_ts) >= int(pd.Timestamp(day, tz="UTC").timestamp()) and int(r.start_ts) < int(pd.Timestamp(day, tz="UTC").timestamp()) + 86400:
                GR[(r.cid, int(r.is_up))] = c1[i]
        del gd

    def wexp(D):
        return (1 - PL) * np.minimum(30.0, D) + PL * np.minimum(100.0, D)""")
rep("""                sec = ((ee - st) // 1000 + 2).astype(np.int64)
                hh = np.bincount(sec, weights=ps[1] - ps[0], minlength=302)[:300]
                aa = np.bincount(sec, weights=ps[1] + ps[0], minlength=302)[:300]
                HS.append(pd.DataFrame({"cid": r.cid, "rel": np.arange(300), "h": hh.astype(np.float32), "act": aa.astype(np.float32), "day": day}))""",
    """                sec = ((ee - st) // 1000 + 2).astype(np.int64)
                kk = 1201 + np.arange(1, 5401)
                wu = wexp(GR[(r.cid, 1)][kk]) if (r.cid, 1) in GR else np.full(len(ee), 30.0)
                wd = wexp(GR[(r.cid, 0)][kk]) if (r.cid, 0) in GR else np.full(len(ee), 30.0)
                hh = np.bincount(sec, weights=ps[1] - ps[0], minlength=302)[:300]
                hd = np.bincount(sec, weights=ps[1] * wu - ps[0] * wd, minlength=302)[:300]
                aa = np.bincount(sec, weights=ps[1] + ps[0], minlength=302)[:300]
                HS.append(pd.DataFrame({"cid": r.cid, "rel": np.arange(300), "h": hh.astype(np.float32), "hd": hd.astype(np.float32), "act": aa.astype(np.float32), "day": day}))""")
rep("""    c = float((Hs.h[fit] * Hs.y[fit]).sum() / (Hs.h[fit] ** 2).sum())
    Hs["nfhaz"] = c * Hs.h
    Hs.to_parquet(f"{OUT}/hazflow14.parquet", index=False)""",
    """    c = float((Hs.hd[fit] * Hs.y[fit]).sum() / (Hs.hd[fit] ** 2).sum())
    Hs["nfhazD"] = c * Hs.hd
    h14 = pd.read_parquet(os.path.join(os.path.dirname(OUT.rstrip("/")), "it14", "hazflow14.parquet"), columns=["cid", "rel", "nfhaz", "h"]).rename(columns={"h": "h14"})
    Hs = Hs.merge(h14, on=["cid", "rel"], how="left")
    Hs.to_parquet(f"{OUT}/hazflowD15.parquet", index=False)""")
rep("""    S["avg"] = 0.5 * (S.nf + S.nf12b.fillna(0)); S["mix14"] = 0.5 * S.avg + 0.5 * S.nfhaz
    g = S.groupby("cid").agg(y=("y", "sum"), nfhaz=("nfhaz", "sum"), avg=("avg", "sum"), mix14=("mix14", "sum"))
    res = {"c_fit": round(c, 3), "per_second_r_fit": round(float(np.corrcoef(Hs.h[fit], Hs.y[fit])[0, 1]), 4),
           "per_second_r_score": round(float(np.corrcoef(S.h, S.y)[0, 1]), 4),
           "window_net_r_10_20_22": {k: round(float(g.y.corr(g[k])), 4) for k in ("nfhaz", "avg", "mix14")}}""",
    """    S["avg"] = 0.5 * (S.nf + S.nf12b.fillna(0)); S["mix14"] = 0.5 * S.avg + 0.5 * S.nfhaz; S["mix15"] = 0.5 * S.avg + 0.5 * S.nfhazD
    g = S.groupby("cid").agg(y=("y", "sum"), nfhaz=("nfhaz", "sum"), nfhazD=("nfhazD", "sum"), avg=("avg", "sum"), mix14=("mix14", "sum"), mix15=("mix15", "sum"))
    res = {"pL": PL, "cD_fit_10_20": round(c, 5), "check_h_vs_h14_r": round(float(np.corrcoef(Hs.h.fillna(0), Hs.h14.fillna(0))[0, 1]), 4),
           "per_second_r_fit": round(float(np.corrcoef(Hs.hd[fit], Hs.y[fit])[0, 1]), 4),
           "per_second_r_score": round(float(np.corrcoef(S.hd, S.y)[0, 1]), 4), "per_second_r_score_h14": round(float(np.corrcoef(S.h, S.y)[0, 1]), 4),
           "window_net_r_10_21_22": {k: round(float(g.y.corr(g[k])), 4) for k in ("nfhaz", "nfhazD", "avg", "mix14", "mix15")},
           "window_net_spearman_10_21_22": {k: round(float(g.y.corr(g[k], method="spearman")), 4) for k in ("nfhaz", "nfhazD", "avg", "mix14", "mix15")}}""")
rep("""    half = winx.loc[cids, "start_ts"].to_numpy() < int(pd.Timestamp("2026-10-21 12:00", tz="UTC").timestamp())
    for nm in ("avg", "mix14", "nfhaz"):""",
    """    half = winx.loc[cids, "start_ts"].to_numpy() < int(pd.Timestamp("2026-10-22 00:00", tz="UTC").timestamp())
    for nm in ("avg", "mix14", "mix15", "nfhazD"):""")
rep("""    a, b = res["tracker_trk_a_avg"]["pool"], res["tracker_trk_a_mix14"]["pool"]
    res["adopted_mix14"] = bool(b[0] > a[0] and b[1] > a[1])
    json.dump(res, open(f"{R}/hazflow14.json", "w"), indent=1)
    print("adopted", res["adopted_mix14"], round(time.time() - t0))""",
    """    a, b = res["tracker_trk_a_mix14"]["pool"], res["tracker_trk_a_mix15"]["pool"]
    res["adopted_mix15"] = bool(b[0] > a[0] and b[1] > a[1])
    json.dump(res, open(f"{R}/hazflowD15.json", "w"), indent=1)
    print("adopted", res["adopted_mix15"], round(time.time() - t0))""")
open(dst, "w").write(s)
print("ok")

"""Iteration 14, PRE-REGISTRATION 5 scoring (X125 = X135): fit the re-anchored decision-clock side models on 10-17..19 and score them
ONCE on 10-20..22, with the pre-registered controls. Input: the frame of dcclock14.py. Usage: python dcfit14.py FRAME_DIR"""
import os, sys, json
import numpy as np, pandas as pd, lightgbm as lgb

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
CODE = os.path.dirname(os.path.abspath(__file__))
FIT = ["2026-10-17", "2026-10-18", "2026-10-19"]
KS = (100, 250, 500, 1000, 2000)
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=13)
ROUNDS = 300
SPOT = [f"{nm}_{K}" for nm in ("bs_mic", "bs_mid", "bt") for K in KS]
VEN = [f"{nm}_{K}" for nm in ("bf_btc", "bf_eth", "ok_btc", "by_btc", "by_eth") for K in KS]
PM = ["pm_last", "pm_d500", "pm_d3000", "pm_f1", "pm_f5", "pm_dist"]
CSCAN = list(range(400, 140, -10))


def mat(X, tag, cols, rel="rel"):
    M = pd.DataFrame({"rel": X[rel].to_numpy() + (3.0 if tag == "plp" else (-3.0 if tag == "plm" else 0.0))})
    for c in cols:
        M[c] = X[f"{tag}_{c}"].to_numpy()
    return M


def acc(ok, sel=None):
    ok = np.asarray(ok, float)
    if sel is not None:
        ok = ok[np.asarray(sel, bool)]
    return round(float(ok.mean()), 4) if len(ok) else None


def two_seg(cs, a):
    cs, a = np.asarray(cs, float), np.asarray(a, float)
    best = None
    for k in cs[1:-1]:
        x1 = np.where(cs >= k, cs - k, 0.0); x2 = np.where(cs < k, cs - k, 0.0)
        Z = np.column_stack([np.ones_like(cs), x1, x2]); b, *_ = np.linalg.lstsq(Z, a, rcond=None)
        sse = float(((Z @ b - a) ** 2).sum())
        if best is None or sse < best[1]:
            best = (float(k), sse, [float(v) for v in b])
    return {"knee_c": best[0], "level_at_knee": round(best[2][0], 4), "slope_before_per_10ms": round(best[2][1] * -10, 4), "slope_after_per_10ms": round(best[2][2] * -10, 4)}


def main():
    D = sys.argv[1]
    X = pd.read_parquet(f"{D}/dcclock14_frame.parquet")
    y = X.up.to_numpy()
    fit = X.day.isin(FIT).to_numpy(); sc = ~fit
    res = {"n_fit": int(fit.sum()), "n_score": int(sc.sum()), "anchor": {"c_exchange_ms": 260, "book_receive_cut_ms_before_m": 129}}
    W = X.wallet.to_numpy(); first = (X["rank"] == 0).to_numpy()
    st = X.start_ts.to_numpy(np.int64)
    half_split = int(pd.Timestamp("2026-10-21 12:00", tz="UTC").timestamp())
    rel = X.rel.to_numpy()
    out = {}
    models = {}
    for name, cols in (("dc14_spot", SPOT), ("dc14_full", SPOT + VEN), ("market_only_pm", PM)):
        Mf = mat(X[fit], "own", cols)
        m = lgb.train(PARAMS, lgb.Dataset(Mf, y[fit]), num_boost_round=ROUNDS)
        models[name] = m
        o = {}
        for tag in ("own", "dec", "plm", "plp"):
            if name == "market_only_pm" and tag in ("plm", "plp"):
                continue
            Ms = mat(X[sc], tag, cols, rel="rel_dec" if tag == "dec" else "rel")
            p = m.predict(Ms, num_threads=4)
            ok = (p > 0.5).astype(int) == y[sc]
            o[tag] = {"all": acc(ok), "first_legs": acc(ok, first[sc]),
                      "by_wallet": {w: acc(ok, W[sc] == w) for w in ("DS", "GF", "XM")},
                      "first_legs_by_wallet": {w: acc(ok, first[sc] & (W[sc] == w)) for w in ("DS", "GF", "XM")}}
            if tag in ("own", "dec"):
                o[tag]["by_day"] = {d: acc(ok, X.day.to_numpy()[sc] == d) for d in sorted(X.day[sc].unique())}
                o[tag]["by_half_36h"] = [acc(ok, st[sc] < half_split), acc(ok, st[sc] >= half_split)]
                rb = rel[sc]
                o[tag]["by_minute"] = {f"{a}-{b}": acc(ok, (rb >= a) & (rb < b)) for a, b in ((0, 60), (60, 120), (120, 180), (180, 240), (240, 300))}
                lg = X.osz.to_numpy()[sc] >= 45
                o[tag]["by_size"] = {"large": acc(ok, lg), "small": acc(ok, ~lg)}
                X.loc[sc, f"p_{name}_{tag}"] = p
        if name != "market_only_pm":
            imp = pd.Series(m.feature_importance("gain"), index=Mf.columns).sort_values(ascending=False)
            o["importance_top8"] = {k: round(float(v / imp.sum()), 4) for k, v in imp.head(8).items()}
        out[name] = o
        print(name, json.dumps({k: (v if k != "importance_top8" else v) for k, v in o.items() if k in ("own", "dec", "plm", "plp")})[:1500], flush=True)
    res["models"] = out
    models["dc14_spot"].save_model(f"{CODE}/model_it14_dcside_spot.txt")
    # the frozen old-anchor exam route (model_it13_dcside_spot) on the same scored orders
    mo = lgb.Booster(model_file=f"{CODE}/model_it13_dcside_spot.txt")
    Mo = pd.DataFrame({"rel": X.rel.to_numpy()[sc]})
    for nm in ("mic", "mid"):
        for K in KS:
            Mo[f"bs_{nm}_{K}"] = X[f"old_bs_{nm}_{K}"].to_numpy()[sc]
    po = mo.predict(Mo[mo.feature_name()]); oko = (po > 0.5).astype(int) == y[sc]
    res["old_anchor_frozen_route_same_orders"] = {"all": acc(oko), "first_legs": acc(oko, first[sc]), "by_wallet": {w: acc(oko, W[sc] == w) for w in ("DS", "GF", "XM")}}
    X.loc[sc, "p_old"] = po
    # own-inventory-only baseline: complement of the operator's realized net (fills with block ts <= m/1000 - 2)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["ts", "cid", "is_up", "shares", "start_ts"])
    fl = fl[fl.start_ts >= 1792195200]
    net = np.zeros(len(X))
    FG = {k: g for k, g in fl.groupby("cid")}
    for cid, g in X.groupby("cid"):
        h = FG.get(cid)
        if h is None or not len(h):
            continue
        o = np.argsort(h.ts.to_numpy()); ts = h.ts.to_numpy(float)[o]
        cs = np.cumsum((np.where(h.is_up.to_numpy(int) == 1, 1.0, -1.0) * h.shares.to_numpy(float))[o])
        j = np.searchsorted(ts, g.m.to_numpy() / 1000.0 - 2.0, "right") - 1
        net[g.index.to_numpy()] = np.where(j >= 0, cs[np.clip(j, 0, len(cs) - 1)], 0.0)
    okn = np.where(net[sc] == 0, 0.5, ((net[sc] < 0).astype(int) == y[sc]).astype(float))
    res["own_inventory_baseline"] = {"all": acc(okn), "coverage": round(float((net[sc] != 0).mean()), 4), "by_wallet": {w: acc(okn, W[sc] == w) for w in ("DS", "GF", "XM")}}
    # one-sided windows per wallet (mean p of the wallet's orders in the window), own and dec anchors and the old route
    one = {}
    for w in ("DS", "GF", "XM"):
        g = X[sc & (W == w)].groupby("cid").agg(nup=("up", "sum"), n=("up", "size"), p_own=("p_dc14_spot_own", "mean"), p_dec=("p_dc14_spot_dec", "mean"),
                                                 p_full=("p_dc14_full_own", "mean"), p_old=("p_old", "mean"), st=("start_ts", "first"), day=("day", "first"))
        o1 = g[(g.nup == 0) | (g.nup == g.n)]; yy = (o1.nup > 0).astype(int).to_numpy()
        one[w] = {"windows": int(len(g)), "one_sided": int(len(o1)), "share": round(float(len(o1) / max(len(g), 1)), 4)}
        for k in ("p_own", "p_dec", "p_full", "p_old"):
            okw = (o1[k].to_numpy() > 0.5).astype(int) == yy
            one[w][k] = acc(okw)
            one[w][f"{k}_by_day"] = {d: acc(okw, o1.day.to_numpy() == d) for d in sorted(o1.day.unique())}
            one[w][f"{k}_halves"] = [acc(okw, o1.st.to_numpy() < half_split), acc(okw, o1.st.to_numpy() >= half_split)]
    res["one_sided_windows"] = one
    # knee scan on FIT days only (first legs), per wallet and weekend; and the crowd control
    ks = {}
    for lab, sel in (("fit_first_legs", fit & first), ("fit_first_legs_weekend_1017_1018", fit & first & X.day.isin(["2026-10-17", "2026-10-18"]).to_numpy()),
                     ("fit_first_legs_1019", fit & first & (X.day == "2026-10-19").to_numpy())) + tuple((f"fit_first_legs_{w}", fit & first & (W == w)) for w in ("DS", "GF", "XM")):
        prof = []
        for c in CSCAN:
            s = X[f"k{c}"].to_numpy()[sel]; yy = np.where(y[sel] == 1, 1, -1)
            prof.append(round(float(np.where(s != 0, np.sign(s) == yy, 0.5).mean()), 4))
        ks[lab] = {"n": int(sel.sum()), "profile_c_400_to_150": dict(zip(CSCAN, prof)), "two_segment": two_seg(CSCAN, prof),
                   "gain_260_to_200": round(prof[CSCAN.index(200)] - prof[CSCAN.index(260)], 4), "gain_320_to_260": round(prof[CSCAN.index(260)] - prof[CSCAN.index(320)], 4)}
    res["knee_fit_days"] = ks
    CB = pd.read_parquet(f"{D}/dcclock14_crowd.parquet")
    cr = {}
    for lab, sel in (("all_days", np.ones(len(CB), bool)), ("fit_days", CB.day.isin(FIT).to_numpy())):
        yy = np.where(CB.up.to_numpy()[sel] == 1, 1, -1); prof = []
        for c in CSCAN:
            s = CB[f"k{c}"].to_numpy()[sel]
            prof.append(round(float(np.where(s != 0, np.sign(s) == yy, 0.5).mean()), 4))
        cr[lab] = {"n": int(sel.sum()), "profile_c_400_to_150": dict(zip(CSCAN, prof)), "gain_320_to_260": round(prof[CSCAN.index(260)] - prof[CSCAN.index(320)], 4),
                   "gain_260_to_200": round(prof[CSCAN.index(200)] - prof[CSCAN.index(260)], 4)}
    res["crowd_control_non_coarriving_buys"] = cr
    X[["cid", "wallet", "up", "m", "m0", "rank", "ev", "osz", "start_ts", "day", "rel"] + [c for c in X.columns if c.startswith("p_")]].to_parquet(f"{D}/dcfit14_pred.parquet", index=False)
    json.dump(res, open(f"{R}/dcclock14.json", "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("old_anchor_frozen_route_same_orders", "own_inventory_baseline")}))
    print(json.dumps(res["one_sided_windows"])[:2500])
    for k, v in ks.items():
        print(k, v["n"], v["two_segment"], "gain260->200", v["gain_260_to_200"], "gain320->260", v["gain_320_to_260"], {c: v["profile_c_400_to_150"][c] for c in (400, 320, 280, 260, 240, 200, 150)})
    for k, v in cr.items():
        print("crowd", k, v["n"], "gain320->260", v["gain_320_to_260"], "gain260->200", v["gain_260_to_200"], {c: v["profile_c_400_to_150"][c] for c in (400, 320, 280, 260, 240, 200, 150)})


if __name__ == "__main__":
    main()

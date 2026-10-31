"""Iteration 4: presence and side models with the cross-asset (ETH perpetual) PIT features added to the iteration-3 six-series
rule. Reference features are computed on the fly (no sidecar files): BUILD = 2026-10-09..16 (positives + 30% of negatives,
weight 1/0.3, plus every one-sided second for the side model), VALIDATE = 2026-10-16..23 (all cells). Same parameters as
train3/train4. The iteration-3 frozen models (model_it3s_*) are scored on exactly the same VALIDATE rows (pipeline check).
BETA of the ETH-minus-BTC relative move is measured on BUILD side rows only.
Saves model_it4_*.txt, results_iter4_models.json, .cache/re/btc5m-bot/val_pred_it4.parquet and val_side_it4.parquet."""
import os, sys, glob, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
from scipy import stats
import train3 as t3
from ofi import Agg
from fut_cells import fut_feats, FUT_FEATS, load_agg
from venue_cells import ven_feats, venue_frame, VEN_FEATS
from venue_cells2 import ven2_feats, VEN2_FEATS, SPOT_VENUES
from alt_cells import alt_feats, alt_frame, ALT_FEATS, ALTS, ALT4_FEATS, ALTS4, add_composites
C = t3.C; R = t3.R; V0, V1 = t3.V0, t3.V1
FOUR = len(sys.argv) > 1 and sys.argv[1] == "four"   # it4b: ETH + SOL + XRP + DOGE perps and alt composites
TAG = "it4b" if FOUR else "it4"
ALTS_USE = ALTS4 if FOUR else ALTS
AF = ALT4_FEATS if FOUR else ALT_FEATS
PRIMARY3 = t3.PRIMARY + VEN_FEATS + VEN2_FEATS
PRIMARY4 = PRIMARY3 + ALT_FEATS
PRIMARY = PRIMARY3 + AF
DSIDE = t3.DSIDE
SIDE3 = PRIMARY3 + ["D_" + k for k in DSIDE]
SIDE = PRIMARY + ["D_" + k for k in DSIDE]
SIDE4 = PRIMARY4 + ["D_" + k for k in DSIDE]
SPARAMS_BIG = dict(t3.SPARAMS, learning_rate=0.03, num_leaves=63)
REFS = FUT_FEATS + VEN_FEATS + VEN2_FEATS + AF


def ref_feats(c, d0, spot):
    fa = load_agg(d0, f"{C}/fut")
    F = fut_feats(c, fa, spot)
    aggs = {}
    for p, v in (("O", "okx"), ("B", "bybit")):
        vf = venue_frame(v, d0, f"{C}/venues"); aggs[p] = Agg(vf) if vf is not None else None
    Vn = ven_feats(c, aggs, {w: F[f"F_pm{w}"].to_numpy() for w in (1000, 2000, 3000, 5000)})
    for p, v in SPOT_VENUES:
        vf = venue_frame(v, d0, f"{C}/venues"); aggs[p] = Agg(vf) if vf is not None else None
    aggs["F"] = fa
    pm_other = {("F", w): F[f"F_pm{w}"].to_numpy() for w in (1000, 2000, 3000)}
    pm_other.update({(p, w): Vn[f"{p}_pm{w}"].to_numpy() for p in ("O", "B") for w in (1000, 2000, 3000)})
    V2 = ven2_feats(c, aggs, pm_other); del aggs
    alt = {}
    for p, sub in ALTS_USE:
        af = alt_frame(sub, d0, f"{C}/venues"); alt[p] = Agg(af) if af is not None else None
    A = alt_feats(c, alt, {w: V2[f"C6_pm{w}"].to_numpy() for w in (1000, 2000, 3000)}, beta={p: 1.0 for p, _ in ALTS_USE}, alts=ALTS_USE)
    out = pd.concat([F.reset_index(drop=True), Vn.reset_index(drop=True), V2.reset_index(drop=True), A.reset_index(drop=True)], axis=1)
    out.index = c.index
    return out.astype(np.float32)


def side_rows(sub, iu, n):
    U = sub.loc[iu]; Dn = sub.loc[iu + n]
    s = U.copy()
    for k in DSIDE:
        s["D_" + k] = Dn[k].to_numpy()
    s["truth_up"] = U.y.to_numpy().astype(int)
    s["yT_one"] = (U.yT.to_numpy() + Dn.yT.to_numpy()) == 1; s["yT_up"] = U.yT.to_numpy()
    s["p_up_src"] = 0.0
    return s


def set_rel(df, beta):
    for p, _ in ALTS_USE:
        for w in (1000, 2000, 3000):
            df[f"{p}_rel{w}"] = (df[f"{p}_pm{w}"].astype(float) - beta[p] * df[f"C6_pm{w}"].fillna(0).astype(float)).astype(np.float32)
    if len(ALTS_USE) > 1:
        add_composites(df, ALTS_USE, beta)


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(0)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0 and os.path.exists(f"{C}/fut/{os.path.basename(f)}")]
    vf_ = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    need = set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z"}
    parts, sparts = [], []
    for fp in bf:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=sorted(need)); n = len(c) // 2
        y = c.y.to_numpy()
        one = (y[:n] + y[n:]) == 1; iu = np.where(one)[0]
        keep = (y == 1) | (rng.random(len(c)) < 0.3)
        idx = np.union1d(np.where(keep)[0], np.r_[iu, iu + n])
        sub = c.iloc[idx].copy(); sub.index = idx
        RF = ref_feats(sub, d0, spot)
        for k in RF.columns:
            sub[k] = RF[k].to_numpy()
        sparts.append(side_rows(sub, iu, n)[SIDE + ["truth_up"]])
        pr = sub.loc[np.where(keep)[0]].copy(); pr["w"] = np.where(pr.y == 1, 1.0, 1 / 0.3).astype(np.float32)
        parts.append(pr[PRIMARY + t3.OWN + ["y", "yT", "yM", "w"]])
        del c, sub, RF
        print("build day", d0, len(pr), "side", len(iu), round(time.time() - t0), flush=True)
    B = pd.concat(parts, ignore_index=True); S = pd.concat(sparts, ignore_index=True); del parts, sparts
    # BETA on BUILD side rows: slope of the ETH 3-s move on the six-series mean 3-s move (Up-oriented)
    beta = {}
    for p, _ in ALTS_USE:
        x = S["C6_pm3000"].to_numpy(float); yv = S[f"{p}_pm3000"].to_numpy(float); m = np.isfinite(x) & np.isfinite(yv)
        beta[p] = round(float(np.sum(x[m] * yv[m]) / np.sum(x[m] ** 2)), 3)
    print("BETA (BUILD)", beta, flush=True)
    set_rel(B, beta); set_rel(S, beta)
    print("BUILD rows", len(B), "side rows", len(S), round(time.time() - t0), flush=True)
    models = {}
    for nm, fs, labs in [("all", PRIMARY, ["y", "yT", "yM"]), ("all_own", PRIMARY + t3.OWN, ["y"])]:
        for lab in labs:
            m = lgb.train(t3.PARAMS, lgb.Dataset(B[fs], B[lab], weight=B.w), num_boost_round=200)
            m.save_model(f"{CODE}/model_{TAG}_{nm}_{lab}.txt"); models[(nm, lab)] = m
            print("trained", nm, lab, round(time.time() - t0), flush=True)
    imp_p = sorted(zip(PRIMARY, models[("all", "y")].feature_importance("gain")), key=lambda q: -q[1]); tp = sum(x for _, x in imp_p)
    ms = lgb.train(t3.SPARAMS, lgb.Dataset(S[SIDE], S.truth_up), 300); ms.save_model(f"{CODE}/model_{TAG}_side.txt")
    msb = lgb.train(SPARAMS_BIG, lgb.Dataset(S[SIDE], S.truth_up), 900); msb.save_model(f"{CODE}/model_{TAG}_side_big.txt")
    print("trained side", round(time.time() - t0), flush=True)
    del B, S
    m3 = {k: lgb.Booster(model_file=f"{CODE}/model_it3s_{k}.txt") for k in ("all_y", "side")}
    m4 = {k: lgb.Booster(model_file=f"{CODE}/model_it4_{k}.txt") for k in ("all_y", "side")} if FOUR else None
    mk = lgb.Booster(model_file=f"{CODE}/model_it2_market_only_y.txt")
    V, SV = [], []
    for fp in vf_:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=sorted(need)); n = len(c) // 2
        RF = ref_feats(c, d0, spot)
        for k in RF.columns:
            c[k] = RF[k].to_numpy()
        del RF
        set_rel(c, beta)
        c["p"] = models[("all", "y")].predict(c[PRIMARY]); c["pT"] = models[("all", "yT")].predict(c[PRIMARY])
        c["pM"] = models[("all", "yM")].predict(c[PRIMARY]); c["pO"] = models[("all_own", "y")].predict(c[PRIMARY + t3.OWN])
        c["p3"] = m3["all_y"].predict(c[PRIMARY3]); c["p_mkt"] = mk.predict(c[t3.MKT])
        c["p4"] = m4["all_y"].predict(c[PRIMARY4]) if FOUR else c["p"]
        y = c.y.to_numpy(); one = (y[:n] + y[n:]) == 1; iu = np.where(one)[0]
        s = side_rows(c, iu, n)
        s["ps"] = ms.predict(s[SIDE]); s["psb"] = msb.predict(s[SIDE]); s["ps3"] = m3["side"].predict(s[SIDE3])
        s["ps4"] = m4["side"].predict(s[SIDE4]) if FOUR else s["ps"]
        s["p_up"] = c.p.to_numpy()[iu]; s["p_dn"] = c.p.to_numpy()[iu + n]
        s["mx6"] = np.nanmax(np.abs(np.stack([s[f"{q}_pm3000"].to_numpy(float) for q in "FOBSYK"], 1)), 1)
        keepc = ["cid", "rel", "start_ts", "truth_up", "yT_one", "yT_up", "ps", "psb", "ps3", "ps4", "p_up", "p_dn", "mx6", "m_last", "r3",
                 "E_pm2000", "E_pm3000", "E_rel3000", "C6_pm2000", "C6_mx2000", "F_pm3000"]
        SV.append(s[keepc])
        V.append(c[["cid", "start_ts", "is_up", "rel", "y", "yT", "yM", "yGF", "yXM", "yDS", "p", "pT", "pM", "pO", "p3", "p4", "p_mkt", "ask_o", "m_last"]].copy())
        del c, s
        print("val day", d0, round(time.time() - t0), flush=True)
    V = pd.concat(V, ignore_index=True); SV = pd.concat(SV, ignore_index=True)
    auc = lambda yy, pp: round(float(roc_auc_score(yy, pp)), 4)
    res = {"beta_build": beta, "build_days": len(bf), "val_days": len(vf_), "presence": {
        "auc_any": auc(V.y, V.p), "auc_taker": auc(V.yT, V.pT), "auc_maker": auc(V.yM, V.pM), "auc_with_own": auc(V.y, V.pO),
        "auc_it3s_same_rows": auc(V.y, V.p3), "auc_it4_same_rows": auc(V.y, V.p4), "auc_market_only_baseline": auc(V.y, V.p_mkt),
        "by_wallet": {w: auc(V[f"y{w}"], V.p) for w in ("GF", "XM", "DS")}, "at_0.30": t3.rl(V.y, V.p >= 0.30)}}
    up = SV.truth_up.to_numpy() == 1
    acc = lambda pr, m=None: round(float(((pr >= 0.5) == up)[m].mean() if m is not None else ((pr >= 0.5) == up).mean()), 4)
    nomove = SV.mx6.to_numpy() <= 0.1; tk = SV.yT_one.to_numpy()
    e1 = nomove & (np.abs(SV.E_pm3000.to_numpy()) >= 1.0)
    sd = {"n": int(len(SV)), "share_nomove": round(float(nomove.mean()), 4)}
    for nm, col in [(f"side_{TAG}", "ps"), (f"side_{TAG}_big", "psb"), ("side_it3s", "ps3"), ("side_it4", "ps4")]:
        pr = SV[col].to_numpy()
        sd[nm] = {"acc": acc(pr), "taker": acc(pr, tk), "nomove": acc(pr, nomove), "moving": acc(pr, ~nomove), "nomove_eth_ge1bp": acc(pr, e1)}
    a_ok = (SV.ps.to_numpy() >= 0.5) == up; b_ok = (SV.ps3.to_numpy() >= 0.5) == up
    b01, b10 = int((a_ok & ~b_ok).sum()), int((~a_ok & b_ok).sum())
    sd["mcnemar_it4_vs_it3s"] = {"it4_only_right": b01, "it3s_only_right": b10, "p": float(stats.binomtest(b01, b01 + b10, 0.5).pvalue)}
    res["side"] = sd
    imp = sorted(zip(SIDE, ms.feature_importance("gain")), key=lambda q: -q[1]); tot = sum(x for _, x in imp)
    res["side_top_gain"] = [(k, round(float(x / tot), 3)) for k, x in imp[:20]]
    res["presence_top_gain"] = [(k, round(float(x / tp), 3)) for k, x in imp_p[:15]]
    res["alt_gain_share_side"] = round(float(sum(x for k, x in imp if k[:2] in ("E_", "L_", "X_", "G_", "A_")) / tot), 4)
    print(json.dumps(res))
    json.dump(res, open(f"{R}/results_iter4_models{'_four' if FOUR else ''}.json", "w"), indent=1)
    V.to_parquet(f"{C}/val_pred_{TAG}.parquet", index=False); SV.to_parquet(f"{C}/val_side_{TAG}.parquet", index=False)
    print("done", round(time.time() - t0), flush=True)

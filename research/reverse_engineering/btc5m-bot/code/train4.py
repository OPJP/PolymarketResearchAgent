"""Iteration 3 (b/c): presence and side models with Binance futures + OKX + Bybit perpetual PIT features (multi-venue
composite); with argument "six": also Binance spot aggTrades, Bybit spot, OKX spot and the six-series composite (venue_cells2). Same split, sampling and parameters as train3.py. Saves model_it3v_*.txt, results_iter3_venues.json,
.cache/re/btc5m-bot/val_pred_it3v.parquet and val_side_it3v.parquet."""
import os, sys, glob, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
from scipy import stats
import train3 as t3
from venue_cells import VEN_FEATS
from venue_cells2 import VEN2_FEATS
SIX = len(sys.argv) > 1 and sys.argv[1] == "six"
TAG = "it3s" if SIX else "it3v"
C = t3.C; R = t3.R; V0, V1 = t3.V0, t3.V1
PRIMARY = t3.PRIMARY + VEN_FEATS + (VEN2_FEATS if SIX else [])
NOFUT_VEN = t3.OLD + VEN_FEATS  # venues without Binance futures (ablation)
DSIDE = t3.DSIDE
SIDE_FEATS = PRIMARY + ["D_" + k for k in DSIDE]


def load_day(fp):
    c = t3.load_day(fp)
    d0 = os.path.basename(fp)
    Vn = pd.read_parquet(f"{C}/cells_ven/{d0}")
    for k in Vn.columns:
        c[k] = Vn[k].to_numpy()
    if SIX:
        V2 = pd.read_parquet(f"{C}/cells_ven2/{d0}")
        for k in V2.columns:
            c[k] = V2[k].to_numpy()
    return c


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(0)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    have = lambda f: os.path.exists(f"{C}/cells_ven{'2' if SIX else ''}/{os.path.basename(f)}")
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0 and have(f)]
    vf = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1 and have(f)]
    parts, sparts = [], []
    for fp in bf:
        c = load_day(fp)
        s, _ = t3.side_frame(c)
        for k in DSIDE:
            pass
        sparts.append(s[[k for k in SIDE_FEATS if k in s.columns] + ["truth_up"]])
        keep = (c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3)
        c = c[keep].copy(); c["w"] = np.where(c.y == 1, 1.0, 1 / 0.3).astype(np.float32)
        parts.append(c[PRIMARY + t3.OWN + ["y", "yT", "yM", "w"]])
    B = pd.concat(parts, ignore_index=True); S = pd.concat(sparts, ignore_index=True); del parts, sparts
    print("BUILD rows", len(B), "side rows", len(S), round(time.time() - t0), flush=True)
    models = {}
    for nm, fs, labs in [("all", PRIMARY, ["y", "yT", "yM"]), ("all_own", PRIMARY + t3.OWN, ["y"]), ("nofut", NOFUT_VEN, ["y"])]:
        if SIX and nm == "nofut":
            models[(nm, "y")] = lgb.Booster(model_file=f"{CODE}/model_it3v_nofut_y.txt"); continue
        for lab in labs:
            m = lgb.train(t3.PARAMS, lgb.Dataset(B[fs], B[lab], weight=B.w), num_boost_round=200)
            m.save_model(f"{CODE}/model_{TAG}_{nm}_{lab}.txt"); models[(nm, lab)] = m
            print("trained", nm, lab, round(time.time() - t0), flush=True)
    ms = lgb.train(t3.SPARAMS, lgb.Dataset(S[SIDE_FEATS], S.truth_up), 300)
    ms.save_model(f"{CODE}/model_{TAG}_side.txt")
    m3 = lgb.Booster(model_file=f"{CODE}/model_it3_side.txt")
    del B, S
    V, SV = [], []
    for fp in vf:
        c = load_day(fp)
        c["p"] = models[("all", "y")].predict(c[PRIMARY]); c["pT"] = models[("all", "yT")].predict(c[PRIMARY])
        c["pM"] = models[("all", "yM")].predict(c[PRIMARY]); c["pO"] = models[("all_own", "y")].predict(c[PRIMARY + t3.OWN])
        c["pN"] = models[("nofut", "y")].predict(c[NOFUT_VEN])
        s, one = t3.side_frame(c)
        n = len(c) // 2
        s["ps"] = ms.predict(s[SIDE_FEATS]); s["ps3"] = m3.predict(s[t3.SIDE_FEATS])
        for k in ("p",):
            s[k + "_up"] = c[k].to_numpy()[:n][one]; s[k + "_dn"] = c[k].to_numpy()[n:][one]
        s["r3"] = c.r3.to_numpy()[:n][one]; s["F_pm3000u"] = c.F_pm3000.to_numpy()[:n][one]
        s["has_ven"] = np.isfinite(c.O_pm1000.to_numpy()[:n][one]) & np.isfinite(c.B_pm1000.to_numpy()[:n][one])
        SV.append(s[["cid", "rel", "start_ts", "truth_up", "yT_one", "yT_up", "ps", "ps3", "r3", "F_pm3000u", "has_ven", "m_last", "p_up", "p_dn"]])
        V.append(c[["cid", "start_ts", "is_up", "rel", "y", "yT", "yM", "yGF", "yXM", "yDS", "p", "pT", "pM", "pO", "pN", "ask_o", "m_last"]])
        print("val day", os.path.basename(fp), round(time.time() - t0), flush=True)
    V = pd.concat(V, ignore_index=True); SV = pd.concat(SV, ignore_index=True)
    A = lambda y, p: round(float(roc_auc_score(y, p)), 4)
    res = {"build_days": len(bf), "val_days": len(vf),
           "presence": {"auc_any": A(V.y, V.p), "auc_taker": A(V.yT, V.pT), "auc_maker": A(V.yM, V.pM), "auc_with_own": A(V.y, V.pO),
                        "auc_venues_without_binance_futures": A(V.y, V.pN), "by_wallet": {w: A(V[f"y{w}"], V.p) for w in ("GF", "XM", "DS")},
                        "at_0.30": t3.rl(V.y, V.p >= t3.P_THRESH)}}
    t = SV.truth_up.to_numpy() == 1; quiet = np.abs(SV.r3.to_numpy()) < 0.01
    flat = quiet & (np.abs(SV.F_pm3000u.to_numpy()) < 0.3); hv = SV.has_ven.to_numpy()
    sd = {"n": int(len(SV)), "share_with_venue_data": round(float(hv.mean()), 4)}
    for nm, pred in [("side_model_venues", SV.ps >= 0.5), ("side_model_fut_it3", SV.ps3 >= 0.5), ("presence_venues", SV.p_up >= SV.p_dn)]:
        ok = pred.to_numpy() == t
        sd[nm] = {"acc": round(float(ok.mean()), 4), "acc_with_venue_data": round(float(ok[hv].mean()), 4), "acc_spot_r3_zero": round(float(ok[quiet].mean()), 4),
                  "acc_binance_flat": round(float(ok[flat].mean()), 4), "acc_moving": round(float(ok[~quiet].mean()), 4)}
    tt = SV[SV.yT_one]
    sd["taker_side_model_venues"] = round(float(((tt.ps >= 0.5).to_numpy() == (tt.yT_up == 1).to_numpy()).mean()), 4)
    oks = (SV.ps >= 0.5).to_numpy() == t; ok3 = (SV.ps3 >= 0.5).to_numpy() == t
    b_ = int((oks & ~ok3).sum()); c_ = int((~oks & ok3).sum())
    sd["mcnemar_p_venues_vs_fut_only"] = float(stats.binomtest(b_, b_ + c_, 0.5, alternative="greater").pvalue) if b_ + c_ else None
    res["side"] = sd
    imp = sorted(zip(SIDE_FEATS, ms.feature_importance("gain")), key=lambda q: -q[1]); tot = sum(x for _, x in imp)
    res["side_top_gain"] = [(k, round(float(x / tot), 3)) for k, x in imp[:15]]
    imp = sorted(zip(PRIMARY, models[("all", "y")].feature_importance("gain")), key=lambda q: -q[1]); tot = sum(x for _, x in imp)
    res["presence_top_gain"] = [(k, round(float(x / tot), 3)) for k, x in imp[:12]]
    json.dump(res, open(f"{R}/results_iter3_{'six' if SIX else 'venues'}.json", "w"), indent=1)
    V.to_parquet(f"{C}/val_pred_{TAG}.parquet", index=False); SV.to_parquet(f"{C}/val_side_{TAG}.parquet", index=False)
    print(json.dumps(res)[:3000]); print("done", round(time.time() - t0))

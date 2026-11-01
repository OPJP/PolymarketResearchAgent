"""Iteration 3: presence and side models with point-in-time Binance futures features (fut_cells.py).

BUILD = 2026-10-09 .. 10-16 (7 day files), VALIDATE = 2026-10-16 .. 10-23 (7 day files). Negatives subsampled 30%
(weight 1/0.3) for presence. Side model: one row per second where the cluster bought exactly one outcome (label y),
Up-cell features + Down-cell non-mirror features, label = Up. Saves model_it3_*.txt, results_iter3_models.json and
.cache/re/btc5m-bot/val_pred_it3.parquet (VALIDATE scores for later analyses)."""
import os, sys, glob, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
from scipy import stats
from cells import FEATS
from tape_feats import TAPE_FEATS
from build_cells_day import OWN, EXTRA
from fut_cells import FUT_FEATS
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
P_THRESH = 0.30
PRIMARY = FEATS + TAPE_FEATS + EXTRA + FUT_FEATS
SETS = {"spot_tape_fut": PRIMARY, "spot_tape_fut_own": PRIMARY + OWN}
MKT = ["rel", "tau"] + TAPE_FEATS + EXTRA
OLD = FEATS + TAPE_FEATS + EXTRA
DSIDE = ["ask_o", "bid_o", "age_ask", "age_bid", "n1", "n2", "n5", "n30", "vol30", "dm5", "dm10", "dm30", "F_gap_ask", "F_gap_m", "gap_ask", "gap_m"]
SIDE_FEATS = PRIMARY + ["D_" + k for k in DSIDE]
PARAMS = dict(objective="binary", learning_rate=0.08, num_leaves=63, min_data_in_leaf=300, feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
SPARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
LABS = ["y", "yT", "yM", "yGF", "yXM", "yDS"]
COLS = sorted(set(OLD + OWN + LABS) | {"cid", "rel", "is_up", "start_ts"})


def load_day(fp):
    d0 = int(os.path.basename(fp)[:-8])
    c = pd.read_parquet(fp, columns=COLS)
    F = pd.read_parquet(f"{C}/cells_fut/{d0}.parquet")
    for k in F.columns:
        c[k] = F[k].to_numpy()
    return c


def side_frame(c):
    """one row per (cid, rel) where the cluster bought exactly one outcome; Up features + D_ Down features."""
    n = len(c) // 2
    up, dn = c.iloc[:n].reset_index(drop=True), c.iloc[n:].reset_index(drop=True)
    assert up.is_up.all() and (~dn.is_up).all() and (up.cid.to_numpy() == dn.cid.to_numpy()).all() and (up.rel.to_numpy() == dn.rel.to_numpy()).all()
    one = (up.y.to_numpy() + dn.y.to_numpy()) == 1
    u = up[one].copy()
    for k in DSIDE:
        u["D_" + k] = dn[k].to_numpy()[one]
    u["truth_up"] = up.y.to_numpy()[one].astype(int)
    oneT = ((up.yT.to_numpy() + dn.yT.to_numpy()) == 1)[one]
    u["yT_one"] = oneT; u["yT_up"] = up.yT.to_numpy()[one]
    return u, one


def rl(y, flag):
    y = np.asarray(y).astype(bool); flag = np.asarray(flag).astype(bool)
    base = y.mean(); rec = flag[y].mean(); prec = y[flag].mean() if flag.any() else np.nan
    k, n = int(y[flag].sum()), int(flag.sum())
    return {"recall": round(float(rec), 4), "lift": round(float(prec / base), 3), "flag_share": round(float(flag.mean()), 4), "p_value": float(stats.binomtest(k, n, base, alternative="greater").pvalue) if n else None}


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(0)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0 and os.path.exists(f"{C}/cells_fut/{os.path.basename(f)}")]
    vf = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    parts, sparts = [], []
    for fp in bf:
        c = load_day(fp)
        s, _ = side_frame(c); sparts.append(s[SIDE_FEATS + ["truth_up"]])
        keep = (c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3)
        c = c[keep].copy(); c["w"] = np.where(c.y == 1, 1.0, 1 / 0.3).astype(np.float32)
        parts.append(c)
    B = pd.concat(parts, ignore_index=True); S = pd.concat(sparts, ignore_index=True); del parts, sparts
    print("BUILD rows", len(B), "side rows", len(S), round(time.time() - t0), flush=True)
    models = {}
    for nm, fs in SETS.items():
        for lab in (["y", "yT", "yM"] if nm == "spot_tape_fut" else ["y"]):
            m = lgb.train(PARAMS, lgb.Dataset(B[fs], B[lab], weight=B.w), num_boost_round=200)
            m.save_model(f"{CODE}/model_it3_{nm}_{lab}.txt"); models[(nm, lab)] = m
            print("trained", nm, lab, round(time.time() - t0), flush=True)
    ms = lgb.train(SPARAMS, lgb.Dataset(S[SIDE_FEATS], S.truth_up), 300)
    ms.save_model(f"{CODE}/model_it3_side.txt")
    del B, S
    old = {k: lgb.Booster(model_file=f"{CODE}/model_it2_{k}.txt") for k in ("spot_tape_y", "market_only_y")}
    V, SV = [], []
    for fp in vf:
        c = load_day(fp)
        c["p"] = models[("spot_tape_fut", "y")].predict(c[PRIMARY]); c["pT"] = models[("spot_tape_fut", "yT")].predict(c[PRIMARY])
        c["pM"] = models[("spot_tape_fut", "yM")].predict(c[PRIMARY]); c["pO"] = models[("spot_tape_fut_own", "y")].predict(c[PRIMARY + OWN])
        c["p_old"] = old["spot_tape_y"].predict(c[OLD]); c["p_mkt"] = old["market_only_y"].predict(c[MKT])
        s, one = side_frame(c)
        n = len(c) // 2
        s["ps"] = ms.predict(s[SIDE_FEATS])
        for k in ("p", "p_old", "p_mkt", "pO"):
            s[k + "_up"] = c[k].to_numpy()[:n][one]; s[k + "_dn"] = c[k].to_numpy()[n:][one]
        s["r3"] = c.r3.to_numpy()[:n][one]; s["F_pm3000u"] = c.F_pm3000.to_numpy()[:n][one]
        SV.append(s[["cid", "rel", "start_ts", "truth_up", "yT_one", "yT_up", "ps", "r3", "F_pm3000u", "m_last"] + [k + sfx for k in ("p", "p_old", "p_mkt", "pO") for sfx in ("_up", "_dn")]])
        V.append(c[["cid", "start_ts", "is_up", "rel", "y", "yT", "yM", "yGF", "yXM", "yDS", "p", "pT", "pM", "pO", "p_old", "p_mkt", "ask_o", "m_last", "F_fv", "fv"]])
        print("val day", os.path.basename(fp), round(time.time() - t0), flush=True)
    V = pd.concat(V, ignore_index=True); SV = pd.concat(SV, ignore_index=True)
    res = {"build_days": len(bf), "val_days": len(vf)}
    A = lambda y, p: round(float(roc_auc_score(y, p)), 4)
    res["presence"] = {"auc_any_fut": A(V.y, V.p), "auc_taker_fut": A(V.yT, V.pT), "auc_maker_fut": A(V.yM, V.pM),
                       "auc_with_own_fut": A(V.y, V.pO), "auc_any_it2": A(V.y, V.p_old), "co_occurrence_baseline": A(V.y, V.p_mkt),
                       "by_wallet": {w: A(V[f"y{w}"], V.p) for w in ("GF", "XM", "DS")}, "at_0.30": rl(V.y, V.p >= P_THRESH)}
    sd = {}
    t = SV.truth_up.to_numpy() == 1; quiet = np.abs(SV.r3.to_numpy()) < 0.01
    for nm, pred in [("side_model_fut", SV.ps.to_numpy() >= 0.5), ("presence_fut", SV.p_up >= SV.p_dn), ("presence_it2", SV.p_old_up >= SV.p_old_dn),
                     ("market_only", SV.p_mkt_up >= SV.p_mkt_dn), ("presence_fut_own", SV.pO_up >= SV.pO_dn), ("favourite", SV.m_last >= 0.5),
                     ("sign_futures_3s", SV.F_pm3000u > 0)]:
        ok = pred == t
        sd[nm] = {"acc": round(float(ok.mean()), 4), "acc_spot_r3_zero": round(float(ok[quiet].mean()), 4), "acc_moving": round(float(ok[~quiet].mean()), 4)}
    okm = (SV.p_mkt_up >= SV.p_mkt_dn).to_numpy() == t; oks = (SV.ps.to_numpy() >= 0.5) == t
    b_ = int((oks & ~okm).sum()); c_ = int((~oks & okm).sum())
    sd["n"] = int(len(SV)); sd["share_spot_r3_zero"] = round(float(quiet.mean()), 4)
    sd["mcnemar_p_side_model_vs_market_only"] = float(stats.binomtest(b_, b_ + c_, 0.5, alternative="greater").pvalue)
    tt = SV[SV.yT_one]
    sd["taker_side_model_fut"] = round(float(((tt.ps >= 0.5).to_numpy() == (tt.yT_up == 1).to_numpy()).mean()), 4)
    # confidence curve: accuracy by side-model confidence decile
    conf = np.abs(SV.ps.to_numpy() - 0.5)
    qs = np.quantile(conf, [0.5, 0.8, 0.9])
    sd["acc_top50pct_conf"] = round(float(oks[conf >= qs[0]].mean()), 4); sd["acc_top20pct_conf"] = round(float(oks[conf >= qs[1]].mean()), 4)
    sd["acc_top10pct_conf"] = round(float(oks[conf >= qs[2]].mean()), 4)
    res["side"] = sd
    imp = sorted(zip(PRIMARY, models[("spot_tape_fut", "y")].feature_importance("gain")), key=lambda q: -q[1]); tot = sum(x for _, x in imp)
    res["presence_top_gain"] = [(k, round(float(x / tot), 3)) for k, x in imp[:15]]
    imp = sorted(zip(SIDE_FEATS, ms.feature_importance("gain")), key=lambda q: -q[1]); tot = sum(x for _, x in imp)
    res["side_top_gain"] = [(k, round(float(x / tot), 3)) for k, x in imp[:15]]
    json.dump(res, open(f"{R}/results_iter3_models.json", "w"), indent=1)
    V.to_parquet(f"{C}/val_pred_it3.parquet", index=False); SV.to_parquet(f"{C}/val_side_it3.parquet", index=False)
    print(json.dumps(res, indent=1)[:4000]); print("done", round(time.time() - t0))

"""Iteration 12, panel iter11 assumptions P1 step 5 (X109): port the slow public state to the block clock. The frozen
block-second presence model (model_it5_blk_full, it4b features) is retrained on the same BUILD block seconds with the
outcome-signed spot-only slow features of nf12b added (M1, M2, since-open, lagged minutes, 2 / 5 / 15-min moves, previous
window outcome proxy, ask sum, FV gap) and scored on every VALIDATE block second next to the frozen full model and the
frozen pure market-activity baseline (same rows). Measurement only (the frozen rule is not changed this iteration)."""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
sys.argv = [sys.argv[0], "four"] + sys.argv[1:]
import train5 as t5
import train3 as t3
import nf12 as nf12mod
from alt_cells import BETA
from block_bins import block_seconds
from decision_presence import MKT_PURE, FULL
from block_presence import keep_mask
C = t3.C; R = t3.R; V0, V1 = t3.V0, t3.V1
DIR = ["M1", "M2", "since_open", "since_open_n", "lag1", "lag2", "r120", "r300", "r900", "prev_up_spot"]
SLOWP = DIR + ["ask_sum", "ask_other", "fvc_gap"]
FULL_S = list(FULL) + SLOWP


def add_slow(c, px, s0):
    """c = one day's cell frame (Up rows then Down rows, aligned); adds outcome-signed slow features."""
    n = len(c) // 2
    sl = nf12mod.slow_feats(c, px, s0, pd.Series(dtype=float))
    sg = np.where(c.is_up.to_numpy(), 1.0, -1.0)
    for k in DIR:
        c[k] = (sl[k].to_numpy() * sg).astype(np.float32)
    a = c.ask_o.to_numpy(float)
    c["ask_other"] = np.r_[a[n:], a[:n]].astype(np.float32)
    c["ask_sum"] = (a + c.ask_other.to_numpy(float)).astype(np.float32)
    c["fvc_gap"] = (c.fv.to_numpy(float) - a).astype(np.float32)
    return c


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(0)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet"); spot["sec"] = spot.sec.astype(np.int64)
    s0 = int(spot.sec.min()); px = spot.set_index("sec").close.reindex(np.arange(s0, int(spot.sec.max()) + 1)).ffill().to_numpy(float)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts"])
    bs = block_seconds(fl[fl.ts < V1])
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0 and os.path.exists(f"{C}/fut/{os.path.basename(f)}")]
    vf_ = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    need = sorted(set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z", "fv"})
    parts = []
    for fp in bf:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=need)
        c = add_slow(c, px, s0)
        k = keep_mask((c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64), bs)
        sel = k & ((c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3))
        sub = c[sel].copy()
        RF = t5.ref_feats(sub, d0, spot)
        for k2 in RF.columns:
            sub[k2] = RF[k2].to_numpy()
        t5.set_rel(sub, BETA)
        sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
        parts.append(sub[sorted(set(FULL_S)) + ["y", "w"]]); del c, sub, RF
        print("build day", d0, round(time.time() - t0), flush=True)
    B = pd.concat(parts, ignore_index=True); del parts
    ms = lgb.train(t3.PARAMS, lgb.Dataset(B[FULL_S], B.y, weight=B.w), num_boost_round=200); ms.save_model(f"{CODE}/model_it12_blk_slow.txt")
    del B
    mf = lgb.Booster(model_file=f"{CODE}/model_it5_blk_full.txt"); mp = lgb.Booster(model_file=f"{CODE}/model_it5_blk_pure.txt")
    print("trained", round(time.time() - t0), flush=True)
    Y, PS, PF, PP, TT = [], [], [], [], []
    for fp in vf_:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=need)
        c = add_slow(c, px, s0)
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        k = keep_mask(t, bs)
        c = c[k].copy(); t = t[k]
        RF = t5.ref_feats(c, d0, spot)
        for k2 in RF.columns:
            c[k2] = RF[k2].to_numpy()
        del RF
        t5.set_rel(c, BETA)
        PS.append(ms.predict(c[FULL_S]).astype(np.float32)); PF.append(mf.predict(c[mf.feature_name()]).astype(np.float32)); PP.append(mp.predict(c[mp.feature_name()]).astype(np.float32))
        Y.append(c.y.to_numpy()); TT.append(t)
        del c
        print("val day", d0, round(time.time() - t0), flush=True)
    y = np.concatenate(Y); ps = np.concatenate(PS); pf = np.concatenate(PF); pp = np.concatenate(PP); tt = np.concatenate(TT)
    auc = lambda yy, q: round(float(roc_auc_score(yy, q)), 4)
    import final_rule as fr
    imp = pd.Series(ms.feature_importance("gain"), index=FULL_S)
    res = {"val_cells": int(len(y)), "auc_full_frozen": auc(y, pf), "auc_full_plus_slow": auc(y, ps), "auc_pure_baseline": auc(y, pp),
           "gain_frozen_over_pure": round(auc(y, pf) - auc(y, pp), 4), "gain_slow_over_pure": round(auc(y, ps) - auc(y, pp), 4),
           "slow_minus_frozen_block_bootstrap_2h": fr._block_boot_gain(y, ps, pf, tt // 7200, n_boot=1000),
           "slow_importance_share": round(float(imp[SLOWP].sum() / imp.sum()), 4),
           "slow_importance": {k: round(float(imp[k] / imp.sum()), 4) for k in SLOWP}}
    half = tt < (V0 + V1) // 2
    res["halves"] = {nm: {"frozen": auc(y[m], pf[m]), "slow": auc(y[m], ps[m]), "pure": auc(y[m], pp[m])} for nm, m in (("first", half), ("second", ~half))}
    json.dump(res, open(f"{R}/results/blkslow12.json", "w"), indent=1)
    print(json.dumps(res, indent=1)); print("done", round(time.time() - t0), flush=True)

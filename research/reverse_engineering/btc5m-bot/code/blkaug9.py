"""Iteration 9 (panel iter8 assumptions P4 = X70, partial; strong form of X4): audit the block-second presence gain against a
STRONGER market-activity baseline. The iteration-5 pure baseline (MKT_PURE: rel, tau, tape state and flows, dm5/10/30) gains
these market-only features, all from the same point-in-time cells (no reference feed, no own state):
  dm1, dm2   = change of the outcome's last tape price over 1 and 2 s (m_last(s) - m_last(s - k), same window and outcome);
  O_*        = the OTHER outcome's tape state at the same second: ask_o, bid_o, age_ask, age_bid, n1, n2, n5, n30, vol30,
               flow1, flow2, flow5, dm5, dm10;
  ask_sum    = ask_o + O_ask_o (the Up + Down implied ask sum).
Same LightGBM parameters and budget (t3.PARAMS, 200 rounds), BUILD block seconds (positives + 30% negatives, weight 1/0.3).
VALIDATE block seconds scored with the frozen model_it5_blk_full.txt, the frozen pure baseline and the augmented baseline;
AUCs, gains, per wallet, halves, 2-h block bootstrap (2,000 draws) of full - augmented. Not covered (needs the tapes again):
counts of other traders' bot-size prints, sub-second intensities, W4's prints removed from both models.
Usage: python blkaug9.py OUT_JSON"""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
sys.argv = [sys.argv[0], "four"] + sys.argv[1:]
import train5 as t5
import train3 as t3
from alt_cells import BETA
from block_bins import block_seconds
from decision_presence import MKT_PURE, FULL
from block_presence import keep_mask
C = t3.C; V0, V1 = t3.V0, t3.V1
OTH = ["ask_o", "bid_o", "age_ask", "age_bid", "n1", "n2", "n5", "n30", "vol30", "flow1", "flow2", "flow5", "dm5", "dm10"]
AUG = ["dm1", "dm2", "ask_sum"] + ["O_" + k for k in OTH]


def add_aug(c):
    c = c.sort_values(["wi", "is_up", "rel"]).reset_index(drop=True)
    g = c.groupby(["wi", "is_up"], sort=False).m_last
    for k in (1, 2):
        prev = g.shift(k)
        same = c.rel.to_numpy() - c.groupby(["wi", "is_up"], sort=False).rel.shift(k).to_numpy() == k
        c[f"dm{k}"] = np.where(same, c.m_last.to_numpy() - prev.to_numpy(), np.nan).astype(np.float32)
    o = c[["wi", "rel", "is_up"] + OTH].copy()
    o["is_up"] = ~o.is_up.astype(bool)
    o = o.rename(columns={k: "O_" + k for k in OTH})
    c["is_up"] = c.is_up.astype(bool)
    c = c.merge(o, on=["wi", "rel", "is_up"], how="left")
    c["ask_sum"] = (c.ask_o + c.O_ask_o).astype(np.float32)
    return c


def main(out):
    t0 = time.time(); rng = np.random.default_rng(0)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts"])
    bs = block_seconds(fl[fl.ts < V1])
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0 and os.path.exists(f"{C}/fut/{os.path.basename(f)}")]
    vf_ = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    need = sorted(set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z", "wi"} | set(OTH))
    parts = []
    for fp in bf:
        c = pd.read_parquet(fp, columns=need)
        c = add_aug(c)
        k = keep_mask((c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64), bs)
        sel = k & ((c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3))
        sub = c[sel]
        sub = sub[MKT_PURE + AUG + ["y"]].copy(); sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
        parts.append(sub); del c
        print("build", os.path.basename(fp), round(time.time() - t0), flush=True)
    B = pd.concat(parts, ignore_index=True); del parts
    ma = lgb.train(t3.PARAMS, lgb.Dataset(B[MKT_PURE + AUG], B.y, weight=B.w), num_boost_round=200)
    ma.save_model(f"{CODE}/model_it9_blk_aug.txt")
    imp = dict(zip(MKT_PURE + AUG, ma.feature_importance("gain").round(0).tolist()))
    del B
    mf = lgb.Booster(model_file=f"{CODE}/model_it5_blk_full.txt"); mp = lgb.Booster(model_file=f"{CODE}/model_it5_blk_pure.txt")
    print("trained", round(time.time() - t0), flush=True)
    Y, PF, PP, PA, TT, W = [], [], [], [], [], {w: [] for w in ("GF", "XM", "DS")}
    for fp in vf_:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=sorted(set(need) | {"yGF", "yXM", "yDS"}))
        c = add_aug(c)
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        k = keep_mask(t, bs)
        c = c[k].copy(); t = t[k]
        RF = t5.ref_feats(c, d0, spot)
        for k2 in RF.columns:
            c[k2] = RF[k2].to_numpy()
        del RF
        t5.set_rel(c, BETA)
        PF.append(mf.predict(c[FULL]).astype(np.float32)); PP.append(mp.predict(c[MKT_PURE]).astype(np.float32))
        PA.append(ma.predict(c[MKT_PURE + AUG]).astype(np.float32))
        Y.append(c.y.to_numpy()); TT.append(t)
        for w in W:
            W[w].append(c[f"y{w}"].to_numpy())
        del c
        print("val", d0, round(time.time() - t0), flush=True)
    y = np.concatenate(Y); pf = np.concatenate(PF); pp = np.concatenate(PP); pa = np.concatenate(PA); tt = np.concatenate(TT)
    auc = lambda yy, q: round(float(roc_auc_score(yy, q)), 4)
    import final_rule as fr
    res = {"val_cells": int(len(y)), "auc_full": auc(y, pf), "auc_pure_baseline_it5": auc(y, pp), "auc_augmented_baseline": auc(y, pa)}
    res["gain_vs_pure"] = round(res["auc_full"] - res["auc_pure_baseline_it5"], 4)
    res["gain_vs_augmented"] = round(res["auc_full"] - res["auc_augmented_baseline"], 4)
    res["by_wallet"] = {}
    for w in W:
        yw = np.concatenate(W[w])
        res["by_wallet"][w] = {"full": auc(yw, pf), "pure": auc(yw, pp), "augmented": auc(yw, pa)}
        res["by_wallet"][w]["gain_vs_augmented"] = round(res["by_wallet"][w]["full"] - res["by_wallet"][w]["augmented"], 4)
    half = tt < (V0 + V1) // 2
    res["halves"] = {nm: {"full": auc(y[m], pf[m]), "augmented": auc(y[m], pa[m]), "gain": round(auc(y[m], pf[m]) - auc(y[m], pa[m]), 4)}
                     for nm, m in (("first", half), ("second", ~half))}
    res["gain_vs_augmented_block_bootstrap_2h"] = fr._block_boot_gain(y, pf, pa, tt // 7200, n_boot=2000)
    res["augmented_importance_top"] = dict(sorted(imp.items(), key=lambda kv: -kv[1])[:15])
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1)); print("done", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main(sys.argv[-1])

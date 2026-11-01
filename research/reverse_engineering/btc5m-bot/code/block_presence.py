"""Iteration 5: presence on BLOCK SECONDS (the only seconds that can hold a fill; Polygon blocks every 1.5 s, chain
clock fitted per hour by block_bins.block_seconds from (block number, timestamp) pairs). Retrains the it4b-feature
presence model and the PURE market-activity baseline on BUILD block seconds only (positives + 30% negatives, weight
1/0.3, same LightGBM parameters), scores all VALIDATE block seconds, reports AUCs, per wallet, per VALIDATE half, and a
2-hour block bootstrap of the gain (2,000 draws). Saves model_it5_blk_full.txt / model_it5_blk_pure.txt and
results_block_presence_iter5.json."""
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
C = t3.C; R = t3.R; V0, V1 = t3.V0, t3.V1


def keep_mask(t, bs):
    hrs = t // 3600; keep = np.ones(len(t), bool)
    for h in np.unique(hrs):
        lk, secs, _, _ = bs.get(int(h), (False, set(), 0, 0))
        if lk:
            idx = np.where(hrs == h)[0]
            keep[idx] = np.isin(t[idx], np.fromiter(secs, np.int64))
    return keep


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(0)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts"])
    bs = block_seconds(fl[fl.ts < V1])
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0 and os.path.exists(f"{C}/fut/{os.path.basename(f)}")]
    vf_ = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    need = sorted(set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z"})
    parts = []; kept_b = []; pos_lost = 0
    for fp in bf:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=need)
        k = keep_mask((c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64), bs)
        pos_lost += int(((c.y.to_numpy() == 1) & ~k).sum()); kept_b.append(k.mean())
        sel = k & ((c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3))
        sub = c[sel].copy()
        RF = t5.ref_feats(sub, d0, spot)
        for k2 in RF.columns:
            sub[k2] = RF[k2].to_numpy()
        t5.set_rel(sub, BETA)
        sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
        parts.append(sub[sorted(set(FULL) | set(MKT_PURE)) + ["y", "w"]]); del c, sub, RF
        print("build day", d0, round(time.time() - t0), flush=True)
    B = pd.concat(parts, ignore_index=True); del parts
    mf = lgb.train(t3.PARAMS, lgb.Dataset(B[FULL], B.y, weight=B.w), num_boost_round=200); mf.save_model(f"{CODE}/model_it5_blk_full.txt")
    mp = lgb.train(t3.PARAMS, lgb.Dataset(B[MKT_PURE], B.y, weight=B.w), num_boost_round=200); mp.save_model(f"{CODE}/model_it5_blk_pure.txt")
    print("trained", round(time.time() - t0), flush=True)
    del B
    Y, PF, PP, TT, W = [], [], [], [], {w: [] for w in ("GF", "XM", "DS")}
    for fp in vf_:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=sorted(set(need) | {"yGF", "yXM", "yDS"}))
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        k = keep_mask(t, bs)
        c = c[k].copy(); t = t[k]
        RF = t5.ref_feats(c, d0, spot)
        for k2 in RF.columns:
            c[k2] = RF[k2].to_numpy()
        del RF
        t5.set_rel(c, BETA)
        PF.append(mf.predict(c[FULL]).astype(np.float32)); PP.append(mp.predict(c[MKT_PURE]).astype(np.float32))
        Y.append(c.y.to_numpy()); TT.append(t)
        for w in W:
            W[w].append(c[f"y{w}"].to_numpy())
        del c
        print("val day", d0, round(time.time() - t0), flush=True)
    y = np.concatenate(Y); pf = np.concatenate(PF); pp = np.concatenate(PP); tt = np.concatenate(TT)
    auc = lambda yy, q: round(float(roc_auc_score(yy, q)), 4)
    import final_rule as fr
    res = {"build_block_second_share": round(float(np.mean(kept_b)), 4), "build_positives_outside_block_seconds": pos_lost,
           "val_cells": int(len(y)), "auc_full": auc(y, pf), "auc_pure_baseline": auc(y, pp)}
    res["gain"] = round(res["auc_full"] - res["auc_pure_baseline"], 4)
    res["by_wallet"] = {w: {"full": auc(np.concatenate(W[w]), pf), "pure": auc(np.concatenate(W[w]), pp)} for w in W}
    for w in res["by_wallet"]:
        res["by_wallet"][w]["gain"] = round(res["by_wallet"][w]["full"] - res["by_wallet"][w]["pure"], 4)
    half = tt < (V0 + V1) // 2
    res["halves"] = {nm: {"full": auc(y[m], pf[m]), "pure": auc(y[m], pp[m]), "gain": round(auc(y[m], pf[m]) - auc(y[m], pp[m]), 4)} for nm, m in (("first", half), ("second", ~half))}
    res["gain_block_bootstrap_2h"] = fr._block_boot_gain(y, pf, pp, tt // 7200, n_boot=2000)
    res["at_p0.30"] = fr._recall_lift(y, pf >= 0.30)
    json.dump(res, open(f"{R}/results_block_presence_iter5.json", "w"), indent=1)
    print(json.dumps(res, indent=1)); print("done", round(time.time() - t0), flush=True)

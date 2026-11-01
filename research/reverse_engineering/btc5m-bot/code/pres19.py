"""Iteration 19, X191 consequence for condition 2 (pre-registration 22, written 11-01 ~14:00 UTC before the run): is the block-second
presence margin over the capture-aware market baseline (pres14: +0.024 pooled on 10-20..22) concentrated in Globex-CLOSED hours?
pres14's pipeline unchanged (frozen model_it5_blk_full.txt = 'pf'; MSB = MKT_PURE + AUG + capture prints, t3.PARAMS, 200 rounds,
positives + 30% negatives), run in both directions: forward = MSB fitted on 10-17..19, scored on 10-20..22 (as pres14); reverse = MSB
fitted on 10-20..22, scored on 10-17..19 (the frozen pf was fitted on BUILD, so it can be scored on either). Reported: pooled and
per-session AUC of pf and MSB, the gain and its 2-h block bootstrap (2,000 draws), per wallet. Prediction of the Globex account: the
gain is larger in closed hours (the operator's trigger is on Binance) than in open hours (part of its trigger is invisible).
Usage: python pres19.py HF_DIR TAPE_DIR"""
import os, sys, json, time, gc
import numpy as np, pandas as pd, lightgbm as lgb
ARGV = sys.argv[1:3]  # captured before pres14's imports rewrite sys.argv
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import pres14 as p14
from sklearn.metrics import roc_auc_score
from dc_exam14 import globex_open_ms
import final_rule as fr

C, R, H, DAYS0 = p14.C, p14.R, p14.H, p14.DAYS0


def main():
    A, TD = ARGV
    t0 = time.time(); rng = np.random.default_rng(19)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts", "tx", "start_ts"])
    bs = p14.block_seconds(fl[fl.ts < H])
    op_tx = set(fl.loc[fl.start_ts >= 1792195200, "tx"].str.lower())
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
    win = win[(win.start_ts >= DAYS0[0]) & (win.start_ts < H)]
    win_tok = {r.cid: (str(r.up_token), str(r.down_token)) for r in win.itertuples()}
    w45 = set()
    for cc in win.cid:
        p = f"{TD}/{cc}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "transactionHash"])
            w45 |= set(d.loc[d.proxyWallet.str.lower().isin(p14.W45), "transactionHash"].str.lower())
    excl = op_tx | w45
    need = sorted(set(p14.t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z", "wi"} | set(p14.ba.OTH) | {"yGF", "yXM", "yDS"})
    mf = lgb.Booster(model_file=f"{CODE}/model_it5_blk_full.txt")
    FCOL = mf.feature_name()
    MSB = p14.MKT_PURE + p14.ba.AUG + p14.PMF
    fitp, scp = {}, {}
    for d0 in DAYS0:
        day = time.strftime("%Y-%m-%d", time.gmtime(d0))
        c = pd.read_parquet(f"{C}/cells/{d0}.parquet", columns=need)
        c = p14.ba.add_aug(c)
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        k = p14.keep_mask(t, bs); c = c[k].reset_index(drop=True); t = t[k]
        RF = p14.t5.ref_feats(c, d0, spot)
        for k2 in RF.columns:
            c[k2] = RF[k2].to_numpy()
        del RF
        p14.t5.set_rel(c, p14.BETA)
        ex = p14.day_extra(day, d0, c, win_tok, excl, A)
        for k2, v in ex.items():
            c[k2] = v
        sel = (c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3)
        sub = c.loc[sel, MSB + ["y"]].copy(); sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
        fitp[d0] = sub
        scp[d0] = c[MSB + ["y", "yGF", "yXM", "yDS"]].assign(t=t, pf=mf.predict(c[FCOL]).astype(np.float32))
        del c; gc.collect()
        print(day, round(time.time() - t0), flush=True)
    auc = lambda yy, q: round(float(roc_auc_score(yy, q)), 4) if 0 < yy.sum() < len(yy) else None
    res = {"prereg": "22", "splits": {}}
    for nm, fd, sd in (("forward", DAYS0[:3], DAYS0[3:]), ("reverse", DAYS0[3:], DAYS0[:3])):
        B = pd.concat([fitp[d] for d in fd], ignore_index=True)
        S = pd.concat([scp[d] for d in sd], ignore_index=True)
        m = lgb.train(p14.t3.PARAMS, lgb.Dataset(B[MSB], B.y, weight=B.w), num_boost_round=200)
        pm = m.predict(S[MSB]).astype(np.float32)
        y = S.y.to_numpy(); pf = S.pf.to_numpy(); blocks = S.t.to_numpy() // 7200
        gx = globex_open_ms(S.t.to_numpy(np.int64) * 1000)
        o = {"cells": int(len(S)), "pooled": {"pf": auc(y, pf), "MSB": auc(y, pm), "boot": fr._block_boot_gain(y, pf, pm, blocks, n_boot=2000)}}
        for sn, mk in (("open", gx), ("closed", ~gx)):
            if mk.sum() < 1000:
                continue
            o[sn] = {"cells": int(mk.sum()), "pf": auc(y[mk], pf[mk]), "MSB": auc(y[mk], pm[mk]), "boot": fr._block_boot_gain(y[mk], pf[mk], pm[mk], blocks[mk], n_boot=2000),
                     "by_wallet": {w: {"pf": auc(S[f"y{w}"].to_numpy()[mk], pf[mk]), "MSB": auc(S[f"y{w}"].to_numpy()[mk], pm[mk])} for w in ("DS", "GF", "XM")}}
        res["splits"][nm] = o
        print(nm, json.dumps(o), flush=True)
        del B, S; gc.collect()
    json.dump(res, open(f"{R}/pres19.json", "w"), indent=1)
    print("done", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()

"""Iteration 6 (X14, per-wallet side; the brief's side condition likely applies to XM, one-sided in 24.3% of its windows).
Rows = seconds where wallet W bought exactly one outcome (label yW from the cells), features = the frozen side features
(train5.SIDE + side_lag.LAG, no book), truth = W bought Up. Models: (a) the frozen pooled model model_it4b_side_lag.txt
applied to W's rows; (b) a per-wallet model trained on BUILD W rows (all of BUILD); (c) per-wallet trained on the
post-switch part of BUILD only (start >= 2026-10-13 14:10 UTC, the volume-share step found by the panel). Evaluated on
VALIDATE W rows, also split into the seconds where the pooled cluster was one-sided and where a sibling bought the other
outcome; halves by time. Usage: python -I side_wallet6.py XM"""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
W = sys.argv[1] if len(sys.argv) > 1 else "XM"
sys.argv = [sys.argv[0], "four"]
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
import train5 as t5
import train3 as t3
import side_lag as sl
C = t3.C; R = t3.R
SWITCH = 1792332600  # 2026-10-13 14:10 UTC


def side_day_w(fp, spot, lab):
    d0 = int(os.path.basename(fp)[:-8])
    cols = sorted(set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z", lab})
    c = pd.read_parquet(fp, columns=cols); n = len(c) // 2
    yw = c[lab].to_numpy(); yp = c.y.to_numpy()
    iu = np.where((yw[:n] + yw[n:]) == 1)[0]
    pooled_one = ((yp[:n] + yp[n:]) == 1)[iu]
    idx = np.r_[iu, iu + n]; sub = c.iloc[idx].copy(); sub.index = idx
    sub["y"] = sub[lab]  # side_rows reads y
    RF = t5.ref_feats(sub, d0, spot)
    for k in RF.columns:
        sub[k] = RF[k].to_numpy()
    t5.set_rel(sub, sl.beta)
    s = sl.add_lag(t5.side_rows(sub, iu, n))
    s["pooled_one"] = pooled_one
    return s


if __name__ == "__main__":
    t0 = time.time()
    lab = "y" + W
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    F2 = t5.SIDE + sl.LAG
    keep = list(dict.fromkeys(F2 + ["truth_up", "yT_one", "start_ts", "rel", "pooled_one"]))
    B = pd.concat([side_day_w(fp, spot, lab)[keep] for fp in files if int(os.path.basename(fp)[:-8]) < t3.V0 and os.path.exists(f"{C}/fut/{os.path.basename(fp)}")], ignore_index=True)
    print("BUILD rows", len(B), round(time.time() - t0), flush=True)
    m_all = lgb.train(t3.SPARAMS, lgb.Dataset(B[F2], B.truth_up), 300)
    Bp = B[B.start_ts >= SWITCH]
    m_post = lgb.train(t3.SPARAMS, lgb.Dataset(Bp[F2], Bp.truth_up), 300) if len(Bp) > 2000 else None
    nB, nBp = len(B), len(Bp)
    del B, Bp
    m0 = lgb.Booster(model_file=f"{CODE}/model_it4b_side_lag.txt")
    V = pd.concat([side_day_w(fp, spot, lab)[keep] for fp in files if t3.V0 <= int(os.path.basename(fp)[:-8]) < t3.V1], ignore_index=True)
    up = V.truth_up.to_numpy() == 1
    po = V.pooled_one.to_numpy(bool)
    mid = np.median(V.start_ts)
    h1 = V.start_ts.to_numpy() < mid
    res = {"wallet": W, "build_rows": nB, "build_rows_post_switch": nBp, "validate_rows": int(len(V)), "share_pooled_one_sided": round(float(po.mean()), 4)}
    for nm, mdl in (("pooled_frozen", m0), ("wallet_all_build", m_all), ("wallet_post_switch", m_post)):
        if mdl is None:
            continue
        p = mdl.predict(V[F2]); ok = (p >= 0.5) == up
        res[nm] = {"all": round(float(ok.mean()), 4), "pooled_one_sided": round(float(ok[po].mean()), 4), "sibling_other_side": round(float(ok[~po].mean()), 4) if (~po).any() else None,
                   "half1": round(float(ok[h1].mean()), 4), "half2": round(float(ok[~h1].mean()), 4), "taker_seconds": round(float(ok[V.yT_one.to_numpy(bool)].mean()), 4)}
    json.dump(res, open(f"{R}/results_side_wallet_iter6_{W}.json", "w"), indent=1)
    print(json.dumps(res, indent=1)); print("done", round(time.time() - t0))

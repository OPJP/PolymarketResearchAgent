"""Iteration 5 (X6): Bybit BTCUSDT perpetual top-of-book features (public orderbook.200 archive, 100-ms buckets with
T < (s-1)*1000 ms) in the PRESENCE model (block-second label), against the pure market-activity baseline.
Same BUILD / VALIDATE, sampling and LightGBM parameters as decision_presence.py. Writes results_presence_book_iter5.json."""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
sys.argv = [sys.argv[0], "four"] + sys.argv[1:]
import train5 as t5
import train3 as t3
from alt_cells import BETA
from book_feats import BK, book_arrays, book_feats
C = t3.C; R = t3.R; V0, V1 = t3.V0, t3.V1
OB = C + "/bybit_ob"
FULL = t5.PRIMARY
FULLB = FULL + list(BK)


def add_book(c, d0):
    A = book_arrays(d0, {dd: f"{OB}/linear_{dd}.parquet" for dd in (d0 - 86400, d0)})
    f = book_feats(c.start_ts.to_numpy(np.int64) + c.rel.to_numpy(np.int64), A)
    for k in BK:
        c[k] = f[k]
    del A


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(0)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0 and os.path.exists(f"{C}/fut/{os.path.basename(f)}")]
    vf_ = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    need = sorted(set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z"})
    parts = []
    for fp in bf:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=need)
        keep = (c.y.to_numpy() == 1) | (rng.random(len(c)) < 0.3)
        sub = c[keep].copy()
        RF = t5.ref_feats(sub, d0, spot)
        for k2 in RF.columns:
            sub[k2] = RF[k2].to_numpy()
        t5.set_rel(sub, BETA); add_book(sub, d0)
        sub["w"] = np.where(sub.y == 1, 1.0, 1 / 0.3)
        parts.append(sub[FULLB + ["y", "w"]]); del c, sub, RF
        print("build day", d0, round(time.time() - t0), flush=True)
    B = pd.concat(parts, ignore_index=True); del parts
    m_b = lgb.train(t3.PARAMS, lgb.Dataset(B[FULLB], B.y, weight=B.w), num_boost_round=200)
    m_b.save_model(f"{CODE}/model_it5_presence_book_y.txt")
    imp = sorted(zip(FULLB, m_b.feature_importance("gain")), key=lambda q: -q[1]); tot = sum(x for _, x in imp)
    del B
    m_f = lgb.Booster(model_file=f"{CODE}/model_it5_dp_k0_full.txt"); m_p = lgb.Booster(model_file=f"{CODE}/model_it5_dp_k0_pure.txt")
    Y, PB, PF, PP, W = [], [], [], [], {w: [] for w in ("GF", "XM", "DS")}
    for fp in vf_:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=sorted(set(need) | {"yGF", "yXM", "yDS"}))
        RF = t5.ref_feats(c, d0, spot)
        for k2 in RF.columns:
            c[k2] = RF[k2].to_numpy()
        del RF
        t5.set_rel(c, BETA); add_book(c, d0)
        PB.append(m_b.predict(c[FULLB]).astype(np.float32)); PF.append(m_f.predict(c[m_f.feature_name()]).astype(np.float32))
        PP.append(m_p.predict(c[m_p.feature_name()]).astype(np.float32)); Y.append(c.y.to_numpy())
        for w in W:
            W[w].append(c[f"y{w}"].to_numpy())
        del c
        print("val day", d0, round(time.time() - t0), flush=True)
    y = np.concatenate(Y); pb = np.concatenate(PB); pf = np.concatenate(PF); pp = np.concatenate(PP)
    auc = lambda yy, q: round(float(roc_auc_score(yy, q)), 4)
    res = {"auc_full_plus_book": auc(y, pb), "auc_full": auc(y, pf), "auc_pure_baseline": auc(y, pp),
           "gain_book_over_pure": round(auc(y, pb) - auc(y, pp), 4), "gain_full_over_pure": round(auc(y, pf) - auc(y, pp), 4),
           "by_wallet": {w: {"full_book": auc(np.concatenate(W[w]), pb), "pure": auc(np.concatenate(W[w]), pp)} for w in W},
           "book_gain_share": round(float(sum(x for k, x in imp if k.startswith("BK_")) / tot), 4),
           "top_gain": [(k, round(float(x / tot), 4)) for k, x in imp[:12]]}
    json.dump(res, open(f"{R}/results_presence_book_iter5.json", "w"), indent=1)
    pd.DataFrame({"y": y.astype(np.int8), "pb": pb, "pp": pp}).to_parquet(f"{C}/val_presence_book.parquet", index=False)
    print(json.dumps(res, indent=1)); print("done", round(time.time() - t0), flush=True)

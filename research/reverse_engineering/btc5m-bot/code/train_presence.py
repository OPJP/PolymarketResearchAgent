"""Iteration 2: retrain the PIT presence models on BUILD cells (the iteration-1 model files were lost with the cloud
machine). Negatives are subsampled (weight = 1/rate). Feature sets: spot+tape (primary, no own state), market-only
co-occurrence baseline (tape + rel/tau, no Binance), spot+tape+own (secondary). Evaluates on VALIDATE, saves models.
Usage: python train_presence.py [neg_rate]"""
import os, sys, glob, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
from scipy import stats
from cells import FEATS
from tape_feats import TAPE_FEATS
from build_cells_day import OWN, EXTRA
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
LABS = ["y", "yT", "yM", "yGF", "yXM", "yDS"]
P_THRESH = 0.30
SETS = {"spot_tape": FEATS + TAPE_FEATS + EXTRA, "market_only": ["rel", "tau"] + TAPE_FEATS + EXTRA,
        "spot_only": FEATS, "spot_tape_own": FEATS + TAPE_FEATS + EXTRA + OWN}
PARAMS = dict(objective="binary", learning_rate=0.08, num_leaves=63, min_data_in_leaf=300, feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
COLS = sorted(set(sum(SETS.values(), [])) | set(LABS) | {"cid", "rel", "is_up", "start_ts"})


def load(files, neg_rate=None, seed=0):
    rng = np.random.default_rng(seed); out = []
    for fp in files:
        c = pd.read_parquet(fp, columns=COLS)
        if neg_rate is not None:
            keep = (c.y.to_numpy() == 1) | (rng.random(len(c)) < neg_rate)
            c = c[keep].copy(); c["w"] = np.where(c.y == 1, 1.0, 1.0 / neg_rate).astype(np.float32)
        out.append(c)
    return pd.concat(out, ignore_index=True)


def rl(y, flag):
    y = np.asarray(y).astype(bool); flag = np.asarray(flag).astype(bool)
    base = y.mean(); rec = flag[y].mean(); prec = y[flag].mean() if flag.any() else np.nan
    k, n = int(y[flag].sum()), int(flag.sum())
    return {"recall": round(float(rec), 4), "lift": round(float(prec / base), 3), "flag_share": round(float(flag.mean()), 4), "p_value": float(stats.binomtest(k, n, base, alternative="greater").pvalue) if n else None}


if __name__ == "__main__":
    t0 = time.time(); neg = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bf = [f for f in files if int(os.path.basename(f)[:-8]) < V0]; vf = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    B = load(bf, neg); print("BUILD rows", len(B), "pos", int(B.y.sum()), round(time.time() - t0), flush=True)
    res = {"build_days": len(bf), "val_days": len(vf), "neg_rate": neg}
    models = {}
    for nm, fs in SETS.items():
        for lab in (["y", "yT", "yM"] if nm == "spot_tape" else ["y"]):
            if lab != "y":
                Bl = B  # negatives subsampled on y; for yT/yM keep same rows (y=1 rows include all yT/yM positives)
            m = lgb.train(PARAMS, lgb.Dataset(B[fs], B[lab], weight=B.w), num_boost_round=200)
            models[(nm, lab)] = m
            if True:  # save every model (the frozen rule loads spot_tape, market_only and spot_tape_own)
                m.save_model(f"{CODE}/model_it2_{nm}_{lab}.txt")
            print("trained", nm, lab, round(time.time() - t0), flush=True)
    del B
    V = load(vf); print("VALIDATE rows", len(V), round(time.time() - t0), flush=True)
    for (nm, lab), m in models.items():
        p = m.predict(V[SETS[nm]])
        r = {"auc": round(float(roc_auc_score(V[lab], p)), 4)}
        if lab == "y":
            r["by_wallet"] = {w: round(float(roc_auc_score(V[f"y{w}"], p)), 4) for w in ("GF", "XM", "DS")}
            r["at_0.30"] = rl(V.y, p >= P_THRESH)
            if nm == "spot_tape":
                V["p_y"] = p
        if nm == "spot_tape" and lab != "y":
            V[f"p_{lab}"] = p
        imp = sorted(zip(SETS[nm], m.feature_importance("gain")), key=lambda t: -t[1]); tot = sum(x for _, x in imp)
        r["top_gain"] = [(k, round(float(x / tot), 3)) for k, x in imp[:10]]
        res[f"{nm}:{lab}"] = r
        print(nm, lab, r["auc"], r.get("by_wallet"), r.get("at_0.30"), flush=True)
    json.dump(res, open(f"{R}/results_presence_iter2.json", "w"), indent=1)
    V[["cid", "start_ts", "is_up", "rel", "y", "yT", "yM", "p_y", "p_yT", "p_yM", "ask_o", "bid_o", "m_last", "fv"]].to_parquet(f"{C}/val_pred_presence.parquet", index=False)
    print("done", round(time.time() - t0))

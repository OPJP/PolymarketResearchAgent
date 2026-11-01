"""Iteration 2: the SIDE decision. For seconds where the cluster bought exactly one outcome (separately for any fill,
taker fills, maker fills), compare simple PIT rules and LightGBM side models (BUILD -> VALIDATE), with and without
own-state inventory; market-only baseline = side model on tape features + rel only (no Binance).
Usage: python side_study.py  (reads .cache/re/btc5m-bot/cells/*.parquet)"""
import os, sys, glob, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats
from cells import FEATS
from tape_feats import TAPE_FEATS
from build_cells_day import OWN, EXTRA
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
LABS = ["y", "yT", "yM"]


def one_sided(day_files, lab_list=LABS):
    out = []
    for fp in day_files:
        c = pd.read_parquet(fp)
        n = len(c) // 2
        up, dn = c.iloc[:n].reset_index(drop=True), c.iloc[n:].reset_index(drop=True)
        assert up.is_up.all() and (~dn.is_up).all() and (up.cid.to_numpy() == dn.cid.to_numpy()).all()
        keep = np.zeros(n, bool)
        for lab in lab_list:
            keep |= (up[lab].to_numpy() + dn[lab].to_numpy()) == 1
        u = up[keep].copy()
        for lab in lab_list:
            u[f"{lab}_one"] = ((up[lab].to_numpy() + dn[lab].to_numpy()) == 1)[keep]
            u[f"{lab}_up"] = up[lab].to_numpy()[keep]
        # Down-cell features that are not mirror images
        for k in ["age_ask", "age_bid", "n1", "n2", "n5", "n30", "vol30", "dm5", "dm10", "dm30", "ask_o", "bid_o"]:
            u[f"D_{k}"] = dn[k].to_numpy()[keep]
        out.append(u)
    return pd.concat(out, ignore_index=True)


def acc(pred, truth):
    pred = np.asarray(pred, float); truth = np.asarray(truth, float)
    ok = np.isfinite(pred)
    return round(float((pred[ok] == truth[ok]).mean()), 4), round(float(ok.mean()), 4)


if __name__ == "__main__":
    t0 = time.time()
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    bfiles = [f for f in files if int(os.path.basename(f)[:-8]) < V0]
    vfiles = [f for f in files if V0 <= int(os.path.basename(f)[:-8]) < V1]
    B = one_sided(bfiles); V = one_sided(vfiles)
    print("one-sided rows BUILD", len(B), "VALIDATE", len(V), round(time.time() - t0), flush=True)
    res = {"n_build_files": len(bfiles), "n_val_files": len(vfiles)}
    SPOT = FEATS; TAPE = TAPE_FEATS + EXTRA + [f"D_{k}" for k in ["age_ask", "age_bid", "n1", "n2", "n5", "n30", "vol30", "dm5", "dm10", "dm30", "ask_o", "bid_o"]]
    sets = {"spot_only": SPOT, "market_only": ["rel", "tau"] + TAPE, "spot_tape": SPOT + TAPE, "spot_tape_own": SPOT + TAPE + OWN, "own_only": ["rel", "tau"] + OWN}
    params = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
    for lab in LABS:
        b = B[B[f"{lab}_one"]]; v = V[V[f"{lab}_one"]]
        truth = v[f"{lab}_up"].to_numpy()
        r = {"n_build": int(len(b)), "n_val": int(len(v)), "val_share_up": round(float(truth.mean()), 4)}
        rules = {
            "favourite": np.where(np.isfinite(v.m_last), v.m_last >= 0.5, np.nan),
            "underdog": np.where(np.isfinite(v.m_last), v.m_last < 0.5, np.nan),
            "flow5_momentum": np.where(v.flow5 != 0, v.flow5 > 0, np.nan),
            "dm10_momentum": np.where(np.isfinite(v.dm10) & (v.dm10 != 0), v.dm10 > 0, np.nan),
            "gap_m_cheap_vs_fv": np.where(np.isfinite(v.gap_m), v.gap_m > 0, np.nan),
            "inv_balance_less_held": np.where(v.inv_o != v.inv_other, v.inv_o < v.inv_other, np.nan),
        }
        for h in (1, 2, 3, 5, 10, 30):
            rules[f"binance_r{h}_sign"] = np.where(v[f"r{h}"] != 0, v[f"r{h}"] > 0, np.nan)
        r["rules"] = {k: acc(p, truth) for k, p in rules.items()}
        r["models"] = {}
        for nm, fs in sets.items():
            m = lgb.train(params, lgb.Dataset(b[fs], b[f"{lab}_up"]), num_boost_round=300)
            p = m.predict(v[fs])
            imp = sorted(zip(fs, m.feature_importance("gain")), key=lambda t: -t[1]); tot = sum(x for _, x in imp)
            a = float(((p >= 0.5) == truth).mean())
            r["models"][nm] = {"acc": round(a, 4), "top": [(k, round(float(x / tot), 3)) for k, x in imp[:8]]}
            if nm == "spot_tape":
                V.loc[v.index, f"pside_{lab}"] = p
            if nm == "market_only":
                V.loc[v.index, f"pside_mkt_{lab}"] = p
            print(lab, nm, r["models"][nm]["acc"], round(time.time() - t0), flush=True)
        # McNemar spot_tape vs market_only
        a1 = (V.loc[v.index, f"pside_{lab}"].to_numpy() >= 0.5) == truth; a0 = (V.loc[v.index, f"pside_mkt_{lab}"].to_numpy() >= 0.5) == truth
        bb, cc = int((a1 & ~a0).sum()), int((~a1 & a0).sum())
        r["mcnemar_spot_tape_vs_market_only_p"] = float(stats.binomtest(bb, bb + cc, 0.5, alternative="greater").pvalue) if bb + cc else None
        # accuracy by size of the visible Binance move
        mv = np.abs(v.r3.to_numpy())
        pr = V.loc[v.index, f"pside_{lab}"].to_numpy() >= 0.5
        r["acc_by_abs_r3_bp"] = {f"{lo}-{hi}": [round(float((pr[(mv >= lo) & (mv < hi)] == truth[(mv >= lo) & (mv < hi)]).mean()), 4), int(((mv >= lo) & (mv < hi)).sum())] for lo, hi in [(0, 0.01), (0.01, 0.5), (0.5, 1), (1, 2), (2, 5), (5, 1e9)]}
        res[lab] = r
        print(lab, json.dumps(r["rules"]), flush=True)
    json.dump(res, open(f"{R}/results_side_iter2.json", "w"), indent=1)
    V[["cid", "start_ts", "rel"] + [c for c in V.columns if c.startswith("pside") or c.endswith("_one") or c.endswith("_up")]].to_parquet(f"{C}/val_side_pred.parquet", index=False)
    print("done", round(time.time() - t0))

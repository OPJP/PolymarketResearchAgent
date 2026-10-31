"""Iteration 5 (D1 decision-aligned presence + a PURE market-activity baseline).
1. Baseline bug found: the earlier "market-only" co-occurrence baseline (MKT = rel, tau + TAPE_FEATS + EXTRA) contains
   reference-feed features: sp_since (Binance move since the last print) and gap_m / gap_ask / gap_vw / dgap5 / dgap10
   (Binance fair value minus Polymarket prices). The brief's baseline is market activity only. MKT_PURE drops them.
2. Decision alignment: the live lab shows the bot's order matches ~2.0 s (median) before its block timestamp, and its
   pre-signed orders make the SUBMISSION the decision. Label y_k(s) = cluster fill at block second s + k, features of
   cell s (horizon s-1, i.e. label block - 1 - k). k = 1 puts the horizon at the decision time (block - 2 s).
BUILD = 2026-10-09..16 (positives + 30% negatives per k, weight 1/0.3), VALIDATE = 2026-10-16..23 (all cells).
Writes results_decision_presence_iter5.json."""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
sys.argv = [sys.argv[0], "four"] + sys.argv[1:]
import train5 as t5
import train3 as t3
from alt_cells import BETA
C = t3.C; R = t3.R; V0, V1 = t3.V0, t3.V1
KS = (0, 1, 2)
PURE_DROP = {"sp_since", "gap_m", "gap_ask", "gap_vw", "dgap5", "dgap10"}
MKT_PURE = [c for c in t3.MKT if c not in PURE_DROP]
FULL = t5.PRIMARY


def shift(y, k):
    if k == 0:
        return y.copy()
    out = np.zeros_like(y)
    rel_ok = (np.arange(len(y)) % 300) + k < 300
    out[:-k] = y[k:]
    return np.where(rel_ok, out, 0)


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
        ys = {k: shift(c.y.to_numpy(), k) for k in KS}
        r = rng.random(len(c))
        keep = (r < 0.3)
        for k in KS:
            keep |= ys[k] == 1
        idx = np.where(keep)[0]
        sub = c.iloc[idx].copy(); sub.index = idx
        RF = t5.ref_feats(sub, d0, spot)
        for k2 in RF.columns:
            sub[k2] = RF[k2].to_numpy()
        t5.set_rel(sub, BETA)
        for k in KS:
            sub[f"y{k}"] = ys[k][idx]
        sub["r"] = r[idx]
        parts.append(sub[sorted(set(FULL) | set(t3.MKT)) + [f"y{k}" for k in KS] + ["r"]])
        del c, sub, RF
        print("build day", d0, round(time.time() - t0), flush=True)
    B = pd.concat(parts, ignore_index=True); del parts
    models = {}
    for k in KS:
        m_k = (B[f"y{k}"] == 1) | (B.r < 0.3)
        Bk = B[m_k]; w = np.where(Bk[f"y{k}"] == 1, 1.0, 1 / 0.3)
        for nm, fs in (("full", FULL), ("pure", MKT_PURE), ("old_mkt", t3.MKT)):
            if nm == "old_mkt" and k != 0 and k != 1:
                continue
            models[(k, nm)] = lgb.train(t3.PARAMS, lgb.Dataset(Bk[fs], Bk[f"y{k}"], weight=w), num_boost_round=200)
            print("trained", k, nm, round(time.time() - t0), flush=True)
    imp = sorted(zip(MKT_PURE, models[(1, "pure")].feature_importance("gain")), key=lambda q: -q[1])
    del B
    P = {key: [] for key in models}; Y = {k: [] for k in KS}; WAL = {k: {w: [] for w in ("GF", "XM", "DS")} for k in KS}
    for fp in vf_:
        d0 = int(os.path.basename(fp)[:-8])
        c = pd.read_parquet(fp, columns=sorted(set(need) | {"yGF", "yXM", "yDS"}))
        RF = t5.ref_feats(c, d0, spot)
        for k2 in RF.columns:
            c[k2] = RF[k2].to_numpy()
        del RF
        t5.set_rel(c, BETA)
        for key, m in models.items():
            P[key].append(m.predict(c[FULL if key[1] == "full" else (MKT_PURE if key[1] == "pure" else t3.MKT)]).astype(np.float32))
        for k in KS:
            Y[k].append(shift(c.y.to_numpy(), k))
            for w in ("GF", "XM", "DS"):
                WAL[k][w].append(shift(c[f"y{w}"].to_numpy(), k))
        del c
        print("val day", d0, round(time.time() - t0), flush=True)
    auc = lambda yy, pp: round(float(roc_auc_score(yy, pp)), 4)
    res = {"note": __doc__.split("\n")[0], "mkt_pure_features": MKT_PURE, "dropped_from_old_baseline": sorted(PURE_DROP)}
    for k in KS:
        y = np.concatenate(Y[k]); r = {"base_rate": round(float(y.mean()), 5)}
        for nm in ("full", "pure", "old_mkt"):
            if (k, nm) in P:
                r[f"auc_{nm}"] = auc(y, np.concatenate(P[(k, nm)]))
        r["gain_full_over_pure"] = round(r["auc_full"] - r["auc_pure"], 4)
        if "auc_old_mkt" in r:
            r["gain_full_over_old_mkt"] = round(r["auc_full"] - r["auc_old_mkt"], 4)
        pf = np.concatenate(P[(k, "full")]); pp = np.concatenate(P[(k, "pure")])
        r["by_wallet"] = {w: {"full": auc(np.concatenate(WAL[k][w]), pf), "pure": auc(np.concatenate(WAL[k][w]), pp)} for w in ("GF", "XM", "DS")}
        res[f"k{k}"] = r
    res["pure_baseline_top_gain_k1"] = [(a, round(float(b), 1)) for a, b in imp[:10]]
    json.dump(res, open(f"{R}/results_decision_presence_iter5.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
    # keep VALIDATE predictions for k = 0 and 1 (for the block bootstrap of the gain)
    out = pd.DataFrame({"y0": np.concatenate(Y[0]).astype(np.int8), "y1": np.concatenate(Y[1]).astype(np.int8),
                        "f0": np.concatenate(P[(0, "full")]), "b0": np.concatenate(P[(0, "pure")]),
                        "f1": np.concatenate(P[(1, "full")]), "b1": np.concatenate(P[(1, "pure")])})
    out.to_parquet(f"{C}/val_decision_presence.parquet", index=False)
    for k in KS:
        for nm in ("full", "pure"):
            models[(k, nm)].save_model(f"{CODE}/model_it5_dp_k{k}_{nm}.txt")
    print("done", round(time.time() - t0), flush=True)

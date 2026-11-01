"""Iteration 12: nf12c = per-second cluster net-flow model with the it4b side-frame features (spot, tape, futures, OKX /
Bybit perps, six-series, four alt perps; the frozen it4b netflow model's inputs, computed exactly as val_outcome4.py does)
PLUS the spot-only slow path features of nf12b (computable inside final_rule). Target: signed net share flow at block
second s (Up +). BUILD (10-09..16) rows: every nonzero-target row + 30% of the zero rows (weight 1 / 0.3), as the it4b
netflow model; VALIDATE predictions saved to .cache/re/btc5m-bot/it12/nf12c_val.parquet. Nothing fitted on VALIDATE."""
import os, sys, glob, json, time
sys.argv = [sys.argv[0], "four"] + sys.argv[1:]   # train5 reads the alt set from argv at import (it4b = "four")
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
import train5 as t5
import train3 as t3
import nf12 as nf12mod
from alt_cells import BETA
C = t3.C
R = t3.R + "/results"
VAL0, H = t3.V0, t3.V1
beta = {p: BETA[p] for p, _ in t5.ALTS_USE}
SLOWC = nf12mod.SLOW_SPOT
FEATS_C = t5.SIDE + SLOWC
PARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=63, min_data_in_leaf=300, feature_fraction=0.8, bagging_fraction=0.7,
              bagging_freq=1, verbose=-1, num_threads=4, max_bin=63, seed=12)
ROUNDS = 400


def add_slow(s, px, s0):
    """s: side rows (Up-cell features + D_ of DSIDE) with cid, start_ts, rel, sig, tau, ask_o, D_ask_o, fv."""
    sl = nf12mod.slow_feats(s, px, s0, pd.Series(dtype=float))
    for k in sl.columns:
        s[k] = sl[k].to_numpy()
    s["ask_sum"] = (s.ask_o + s.D_ask_o).astype(np.float32)
    s["ask_diff"] = (s.ask_o - s.D_ask_o).astype(np.float32)
    s["fvc_gap_u"] = (s.fv - s.ask_o).astype(np.float32)
    s["fvc_gap_d"] = ((1 - s.fv) - s.D_ask_o).astype(np.float32)
    return s


def main():
    t0 = time.time(); rng = np.random.default_rng(12)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot["sec"] = spot.sec.astype(np.int64)
    s0 = int(spot.sec.min()); px = spot.set_index("sec").close.reindex(np.arange(s0, int(spot.sec.max()) + 1)).ffill().to_numpy(float)
    fills = pd.read_parquet(f"{C}/fills.parquet", columns=["cid", "rel", "is_up", "shares", "start_ts"])
    need = set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z", "fv"}
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    parts, preds = [], []
    model = None
    for phase in ("build", "val"):
        if phase == "val":
            B = pd.concat(parts, ignore_index=True); del parts
            model = lgb.train(PARAMS, lgb.Dataset(B[FEATS_C], B.net, weight=B.w), num_boost_round=ROUNDS)
            model.save_model(f"{CODE}/model_it12_nf12c.txt")
            imp = pd.Series(model.feature_importance("gain"), index=FEATS_C).sort_values(ascending=False)
            del B
            print("trained", round(time.time() - t0), flush=True)
        for fp in files:
            d0 = int(os.path.basename(fp)[:-8])
            if (phase == "build" and not d0 < VAL0) or (phase == "val" and not VAL0 <= d0 < H) or not os.path.exists(f"{C}/fut/{d0}.parquet"):
                continue
            c = pd.read_parquet(fp, columns=sorted(need)); n = len(c) // 2
            lab = None
            if phase == "build":
                import val_outcome4 as vo4
                lab = vo4.net_label(c, fills[(fills.start_ts >= d0) & (fills.start_ts < d0 + 86400)])
                keep = (lab != 0) | (rng.random(n) < 0.3)
            else:
                keep = np.ones(n, bool)
            idx = np.where(keep)[0]; idx2 = np.r_[idx, idx + n]
            sub = c.iloc[idx2].copy(); sub.index = idx2
            RF = t5.ref_feats(sub, d0, spot)
            for k in RF.columns:
                sub[k] = RF[k].to_numpy()
            del RF
            t5.set_rel(sub, beta)
            s = t5.side_rows(sub, idx, n)
            s = add_slow(s.reset_index(drop=True), px, s0)
            if phase == "build":
                s["net"] = lab[keep].astype(np.float32); s["w"] = np.where(lab[keep] != 0, 1.0, 1 / 0.3).astype(np.float32)
                parts.append(s[FEATS_C + ["net", "w"]].astype(np.float32))
            else:
                preds.append(pd.DataFrame({"cid": s.cid.to_numpy(), "rel": s.rel.to_numpy(), "nf12c": model.predict(s[FEATS_C], num_threads=4).astype(np.float32)}))
            del c, sub, s
            print(phase, d0, round(time.time() - t0), flush=True)
    P = pd.concat(preds, ignore_index=True)
    P.to_parquet(f"{C}/it12/nf12c_val.parquet")
    g = fills[(fills.start_ts >= VAL0) & (fills.rel >= 0) & (fills.rel < 300)]
    net = (g.shares * np.where(g.is_up, 1.0, -1.0)).groupby(g.cid).sum()
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf"])
    nb = pd.read_parquet(f"{C}/it12/nf12b_val.parquet")
    W = pd.DataFrame({"c": P.groupby("cid").nf12c.sum(), "a": vo.groupby("cid").nf.sum(), "b": nb.groupby("cid").nf12b.sum()})
    W["net"] = net.reindex(W.index).fillna(0)
    res = {"validate_window_net_corr": {"nf12c": round(float(W.net.corr(W.c)), 4), "nf_it4b": round(float(W.net.corr(W.a)), 4), "nf12b": round(float(W.net.corr(W.b)), 4),
                                        "avg_it4b_nf12b": round(float(W.net.corr(0.5 * W.a + 0.5 * W.b)), 4), "avg3": round(float(W.net.corr((W.a + W.b + W.c) / 3)), 4),
                                        "avg_nf12c_nf12b": round(float(W.net.corr(0.5 * W.c + 0.5 * W.b)), 4)},
           "importance_gain_top20": {k: round(float(v / imp.sum()), 4) for k, v in imp.head(20).items()},
           "importance_slow_share": round(float(imp[SLOWC].sum() / imp.sum()), 4), "elapsed_s": round(time.time() - t0)}
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{R}/nf12c.json", "w"), indent=1)


if __name__ == "__main__":
    main()

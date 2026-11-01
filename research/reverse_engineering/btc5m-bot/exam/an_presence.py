"""Examiner r1: independent recomputation of the PRESENCE and SELECTION metrics on the h1 lot from the frozen rule's own predictions
(saved by run_eval.py) and the examiner's own BUILD-fitted market baselines (own_baseline.py). Pooled, per half, per wallet; gains with
a 2-h block bootstrap (2,000 draws, one-sided p); window-permutation null (2,000 draws) for the frozen full score.
Usage: python an_presence.py OUT_JSON"""
import os, sys, json, glob, time
ARGS = sys.argv[1:]
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"; sys.path.insert(0, CODE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
import own_baseline as ob

EX = f"{ROOT}/.cache/exam/btc5m-bot"; AN = f"{EX}/an"; os.makedirs(AN, exist_ok=True)
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
CUT = 1793059200  # earlier / later half (listing start time)
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def chunks():
    out = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        a, b = map(int, os.path.basename(os.path.dirname(p)).split("_"))
        if any(x <= a < y for x, y in LOT) or os.environ.get("EXAM_TEST"):
            out.append((a, b, os.path.dirname(p)))
    return out


def shift1(y):
    out = np.zeros_like(y); out[:-1] = y[1:]
    return np.where((np.arange(len(y)) % 300) + 1 < 300, out, 0)


def build_arrays():
    models = {nm: lgb.Booster(model_file=f"{EX}/models/own_{nm}.txt") for nm in ("PURE", "AUG", "MKTX")}
    for a, b, d in chunks():
        o = f"{AN}/pres_{a}_{b}.npz"
        if os.path.exists(o):
            continue
        P = np.load(f"{d}/pred.npz")
        kb = np.load(f"{d}/block_keep.npy")
        c = pd.read_parquet(f"{d}/cells.parquet", columns=sorted(set(ob.NEED) | {"p", "p_mkt", "yT", "yM"}))
        c["_row"] = np.arange(len(c))
        t = (c.start_ts.to_numpy() + c.rel.to_numpy()).astype(np.int64)
        y = c.y.to_numpy().astype(np.int8)
        y1 = shift1(y)
        x = ob.mktx(c.copy()).sort_values("_row")
        own = {nm: m.predict(x[m.feature_name()].astype(np.float32)).astype(np.float32) for nm, m in models.items()}
        # W4 / W5 (the operator's fan-out wallets per the RE's B1 finding): flag cells with a W4 / W5 print stamped in [s-3, s-1] on
        # either outcome of the window (the frozen tape features count these prints as market activity)
        w45 = np.zeros(len(c), bool)
        cid_arr = c.cid.to_numpy(); st_arr = c.start_ts.to_numpy(np.int64); rel_arr = c.rel.to_numpy(np.int64)
        for cc in np.unique(cid_arr):
            tp = f"{EX}/eval/tapes/{cc}.parquet"
            if not os.path.exists(tp):
                continue
            tt = pd.read_parquet(tp)
            if not len(tt) or "proxyWallet" not in tt:
                continue
            ts45 = np.sort(tt.loc[tt.proxyWallet.str.lower().isin(W45), "timestamp"].to_numpy(np.int64))
            if not len(ts45):
                continue
            ii = np.where(cid_arr == cc)[0]; ss = st_arr[ii] + rel_arr[ii]
            w45[ii] = np.searchsorted(ts45, ss - 1, "right") > np.searchsorted(ts45, ss - 3, "left")
        pf = P["model_it5_blk_full.txt__0"]; pp = P["model_it5_blk_pure.txt__0"]
        assert len(pf) == kb.sum()
        np.savez_compressed(o, t=t, y=y, y1=y1, kb=kb, cid=c.cid.to_numpy().astype(str), is_up=c.is_up.to_numpy(bool),
                            yGF=c.yGF.to_numpy(np.int8), yXM=c.yXM.to_numpy(np.int8), yDS=c.yDS.to_numpy(np.int8), yT=c.yT.to_numpy(np.int8), yM=c.yM.to_numpy(np.int8), rel=c.rel.to_numpy(np.int16), w45=w45,
                            pf=pf, pp=pp, dpf=P["model_it5_dp_k1_full.txt__0"], dpp=P["model_it5_dp_k1_pure.txt__0"],
                            p_all=c.p.to_numpy(np.float32), p_mkt=c.p_mkt.to_numpy(np.float32), **{f"own_{k}": v for k, v in own.items()})
        print("arrays", a, b, len(c), round(float(kb.mean()), 3), flush=True)
        del c, x


def auc(y, s, w=None):
    y = np.asarray(y); s = np.asarray(s)
    if len(y) == 0 or y.min() == y.max():
        return float("nan")
    return float(roc_auc_score(y, s, sample_weight=w))


def boot_gain(y, a, b, blocks, n=2000, seed=7, bar=0.0):
    """2-h block bootstrap of AUC(a) - AUC(b) (whole-block integer weights). Returns lo, hi, one-sided p of gain <= bar."""
    ub, inv = np.unique(blocks, return_inverse=True); rng = np.random.default_rng(seed)
    def prep(s):
        o = np.argsort(s, kind="mergesort"); ss = s[o]; g = np.empty(len(s), np.int64); g[o] = np.r_[0, np.cumsum(ss[1:] != ss[:-1])]
        return g, int(g.max()) + 1
    def wauc(g, ng, w):
        gp = np.bincount(g, y * w, ng); gn = np.bincount(g, (1 - y) * w, ng); below = np.cumsum(gn) - gn
        return float((gp * (below + 0.5 * gn)).sum() / (gp.sum() * gn.sum()))
    y = y.astype(float); ga, na = prep(np.asarray(a)); gb, nb = prep(np.asarray(b)); out = []
    for _ in range(n):
        cnt = np.bincount(rng.integers(0, len(ub), len(ub)), minlength=len(ub)).astype(float); w = cnt[inv]
        out.append(wauc(ga, na, w) - wauc(gb, nb, w))
    g = np.array(out)
    return {"lo95": round(float(np.quantile(g, 0.025)), 4), "hi95": round(float(np.quantile(g, 0.975)), 4),
            "p_gain_le_0": round(float((g <= 0).mean()), 5), f"p_gain_le_{bar}": round(float((g <= bar).mean()), 5), "n_boot": n, "blocks": int(len(ub))}


def perm_null(y_full, kb, cid, s_kb, n=2000, seed=11):
    """window-permutation null over whole windows: window k's scores (block seconds only) are paired with window j's label track at
    the same (outcome, rel) positions (every window has the same 600-cell layout); one-sided p of AUC >= observed."""
    obs = auc(y_full[kb], s_kb)
    u, inv = np.unique(cid, return_inverse=True)
    order = np.argsort(inv, kind="stable"); cnt = np.bincount(inv)
    assert (cnt == 600).all(), "window layout"
    M = order.reshape(len(u), 600)  # row indices per window: Up rel 0..299, then Down rel 0..299 (cells order)
    rng = np.random.default_rng(seed); vals = []
    pos = np.empty(len(y_full), np.int64); pos[kb] = np.arange(kb.sum())
    for _ in range(n):
        perm = rng.permutation(len(u)); yy = np.empty_like(y_full)
        yy[M.ravel()] = y_full[M[perm].ravel()]
        vals.append(auc(yy[kb], s_kb))
    v = np.array(vals)
    return {"observed": round(obs, 4), "null_mean": round(float(v.mean()), 4), "null_max": round(float(v.max()), 4),
            "p_one_sided": round(float(((v >= obs).sum() + 1) / (n + 1)), 5), "draws": n}


def main(out_json):
    t0 = time.time()
    build_arrays()
    F = sorted(glob.glob(f"{AN}/pres_*.npz"))
    D = {k: [] for k in ("t", "y", "y1", "kb", "cid", "is_up", "yGF", "yXM", "yDS", "pf", "pp", "dpf", "dpp", "own_PURE", "own_AUG", "own_MKTX", "p_all", "p_mkt")}
    for f in F:
        z = np.load(f, allow_pickle=True)
        for k in D:
            D[k].append(z[k])
    D = {k: np.concatenate(v) for k, v in D.items()}
    kb = D["kb"]
    B = {k: D[k][kb] for k in ("t", "y", "cid", "yGF", "yXM", "yDS", "own_PURE", "own_AUG", "own_MKTX")}
    B["pf"] = D["pf"]; B["pp"] = D["pp"]
    res = {"chunks": len(F), "cells": int(len(D["y"])), "block_seconds": int(kb.sum()), "positives_block": int(B["y"].sum()),
           "positives_outside_block_seconds": int(((D["y"] == 1) & ~kb).sum())}
    half = B["t"] < CUT; blocks = B["t"] // 7200
    base_names = {"RE_pure(model_it5_blk_pure)": "pp", "own_PURE_refit": "own_PURE", "own_AUG(RE iter-9 feature set, refit)": "own_AUG", "own_MKTX": "own_MKTX"}
    msb = [f.replace("pres_", "msb_").replace(".npz", ".npy") for f in F]
    if all(os.path.exists(f) for f in msb):
        B["msb"] = np.concatenate([np.load(f) for f in msb]); assert len(B["msb"]) == len(B["pf"])
        base_names["RE_MSB(pres14 capture-aware, refit 10-17..19)"] = "msb"
    res["msb_available"] = "msb" in B
    res["block_second_unit"] = {}
    for sl_name, sl in (("pooled", np.ones(len(half), bool)), ("first_half", half), ("second_half", ~half)):
        r = {"auc_full": round(auc(B["y"][sl], B["pf"][sl]), 4)}
        for nm, k in base_names.items():
            r[nm] = round(auc(B["y"][sl], B[k][sl]), 4)
        r["by_wallet"] = {w: {"full": round(auc(B[f"y{w}"][sl], B["pf"][sl]), 4), **{nm: round(auc(B[f"y{w}"][sl], B[k][sl]), 4) for nm, k in base_names.items()}}
                          for w in ("GF", "XM", "DS")}
        res["block_second_unit"][sl_name] = r
    strongest = max(base_names, key=lambda nm: res["block_second_unit"]["pooled"][nm])
    res["strongest_baseline_block_unit"] = strongest
    g = {}
    for nm, k in base_names.items():
        g[nm] = {"gain": round(res["block_second_unit"]["pooled"]["auc_full"] - res["block_second_unit"]["pooled"][nm], 4),
                 **boot_gain(B["y"], B["pf"], B[k], blocks, bar=0.05)}
        print("boot", nm, g[nm], round(time.time() - t0), flush=True)
    res["gain_bootstrap_block_unit"] = g
    # per half / per wallet gains vs the strongest baseline
    k = base_names[strongest]
    res["gain_vs_strongest_by_half_wallet"] = {}
    for sl_name, sl in (("first_half", half), ("second_half", ~half)):
        res["gain_vs_strongest_by_half_wallet"][sl_name] = {"pooled": round(auc(B["y"][sl], B["pf"][sl]) - auc(B["y"][sl], B[k][sl]), 4),
                                                            **{w: round(auc(B[f"y{w}"][sl], B["pf"][sl]) - auc(B[f"y{w}"][sl], B[k][sl]), 4) for w in ("GF", "XM", "DS")}}
    try:
        w45 = np.concatenate([np.load(f, allow_pickle=True)["w45"] for f in F])[kb]
        k2 = base_names[strongest]; m2 = ~w45
        res["w45_check"] = {"share_block_cells_with_w45_print_in_s-3_s-1": round(float(w45.mean()), 4),
                            "share_positives_with_w45_print": round(float(w45[B["y"] == 1].mean()), 4),
                            "auc_full_excl": round(auc(B["y"][m2], B["pf"][m2]), 4), "auc_strongest_excl": round(auc(B["y"][m2], B[k2][m2]), 4),
                            "gain_excl": round(auc(B["y"][m2], B["pf"][m2]) - auc(B["y"][m2], B[k2][m2]), 4)}
    except Exception as e:
        res["w45_check"] = {"error": repr(e)[:200]}
    res["perm_null_full_block_unit"] = perm_null(D["y"], kb, D["cid"], B["pf"], n=2000)
    # decision-aligned unit (label = block second s + 1 from cell s: >= 2 s between the information horizon s-1 and the fill stamp)
    y1 = D["y1"]; tt = D["t"]; h1 = tt < CUT
    res["decision_aligned_unit_label_s_plus_1"] = {
        "auc_full_dp_k1": round(auc(y1, D["dpf"]), 4), "auc_RE_pure_dp_k1": round(auc(y1, D["dpp"]), 4),
        "auc_own_MKTX_on_shifted_label": round(auc(y1, D["own_MKTX"]), 4),
        "halves_full_pure": [[round(auc(y1[m], D["dpf"][m]), 4), round(auc(y1[m], D["dpp"][m]), 4)] for m in (h1, ~h1)],
        "boot_full_vs_RE_pure": boot_gain(y1, D["dpf"], D["dpp"], tt // 7200, bar=0.05),
        "boot_full_vs_own_MKTX": boot_gain(y1, D["dpf"], D["own_MKTX"], tt // 7200, bar=0.05)}
    res["all_seconds_unit"] = {"auc_full_p": round(auc(D["y"], D["p_all"]), 4), "auc_market_model_it2": round(auc(D["y"], D["p_mkt"]), 4),
                               "auc_own_MKTX": round(auc(D["y"], D["own_MKTX"]), 4)}
    # recall / lift at the frozen threshold 0.30 on block seconds
    fl = B["pf"] >= 0.30
    res["at_threshold_0.30_block_unit"] = {"recall": round(float(fl[B["y"] == 1].mean()), 4), "precision": round(float(B["y"][fl].mean()), 4),
                                           "lift": round(float(B["y"][fl].mean() / B["y"].mean()), 3), "flag_share": round(float(fl.mean()), 4)}
    res["elapsed_s"] = round(time.time() - t0)
    json.dump(res, open(out_json, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(ARGS[0])

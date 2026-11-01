"""Examiner r1: pooled recomputation of the frozen SELECTION score (v3 size classes: 2 x full size + 1 x partial size + cell presence
score p, flag = full OR (partial AND p >= 0.30)) over every in-window taker print of every trader on the h1 lot, against the RE's
pure market baseline (same size terms + p_pure of the cell = model_it5_dp_k0_pure) and the examiner's own MKTX cell score; per half,
per wallet (label = that wallet's prints), 2-h block bootstrap of the gain. Usage: python an_selection.py OUT_JSON"""
import os, sys, json, glob, time
ARGS = sys.argv[1:]
ROOT = os.getcwd(); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from an_presence import boot_gain

EX = f"{ROOT}/.cache/exam/btc5m-bot"; AN = f"{EX}/an"
LOT = [(1792713600, 1792800000), (1792886400, 1792972800), (1793059200, 1793145600), (1793232000, 1793318400)]
CUT = 1793059200
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
FULL = (30.0, 50.0, 60.0, 100.0); PART = (5.0, 10.0, 15.0, 20.0, 25.0)


def auc(y, s):
    return float(roc_auc_score(y, s)) if len(y) and 0 < y.sum() < len(y) else float("nan")


def main(out_json):
    rows = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        d = os.path.dirname(p); a, b = map(int, os.path.basename(d).split("_"))
        if not any(x <= a < y for x, y in LOT):
            continue
        win = pd.read_parquet(f"{d}/windows_all.parquet"); win = win[(win.start_ts >= a) & (win.start_ts < b)]
        for r in win.itertuples():
            tp = f"{EX}/eval/tapes/{r.cid}.parquet"
            if not os.path.exists(tp):
                continue
            t = pd.read_parquet(tp)
            if not len(t) or "timestamp" not in t:
                continue
            t = t.assign(rel=t.timestamp - r.start_ts, is_up=(t.outcome == "Up"), cid=r.cid)
            t = t[(t.rel >= 0) & (t.rel < 300)]
            rows.append(t[["cid", "is_up", "rel", "proxyWallet", "size", "timestamp"]])
        print("sel chunk", a, b, flush=True)
    T = pd.concat(rows, ignore_index=True)
    # attach cell scores (cells of all chunks)
    S = []
    for p in sorted(glob.glob(f"{EX}/chunks/*_*/evaluate.json")):
        d = os.path.dirname(p); a, b = map(int, os.path.basename(d).split("_"))
        if not any(x <= a < y for x, y in LOT):
            continue
        z = np.load(f"{AN}/pres_{a}_{b}.npz", allow_pickle=True)
        c = pd.read_parquet(f"{d}/cells.parquet", columns=["cid", "is_up", "rel", "p"])
        P = np.load(f"{d}/pred.npz")
        c["p_pure"] = P["model_it5_dp_k0_pure.txt__0"]; c["own"] = z["own_MKTX"]
        S.append(c)
    S = pd.concat(S, ignore_index=True).set_index(["cid", "is_up", "rel"])
    T = T.join(S, on=["cid", "is_up", "rel"])
    T = T[np.isfinite(T.p.to_numpy(float))]
    lab = T.proxyWallet.str.lower().isin(WAL).to_numpy()
    sz = np.round(T["size"].astype(float).to_numpy(), 2)
    full = np.isin(sz, FULL); part = np.isin(sz, PART)
    s_rule = 2.0 * full + 1.0 * part + T.p.to_numpy(); s_pure = 2.0 * full + 1.0 * part + T.p_pure.to_numpy(); s_own = 2.0 * full + 1.0 * part + T.own.to_numpy()
    flag = full | (part & (T.p.to_numpy() >= 0.30))
    half = T.timestamp.to_numpy() < CUT; blocks = T.timestamp.to_numpy() // 7200
    def rl(y, f):
        return {"recall": round(float(f[y].mean()), 4), "precision": round(float(y[f].mean()), 4), "lift": round(float(y[f].mean() / y.mean()), 3), "flag_share": round(float(f.mean()), 4)}
    res = {"prints": int(len(T)), "cluster_share": round(float(lab.mean()), 4)}
    for nm, m in (("pooled", np.ones(len(T), bool)), ("first_half", half), ("second_half", ~half)):
        res[nm] = {"auc_rule": round(auc(lab[m], s_rule[m]), 4), "auc_RE_pure_baseline": round(auc(lab[m], s_pure[m]), 4), "auc_own_MKTX_baseline": round(auc(lab[m], s_own[m]), 4),
                   "at_flag": rl(lab[m], flag[m])}
    res["by_wallet"] = {}
    pw = T.proxyWallet.str.lower().map(WAL).to_numpy()
    for w in ("GF", "XM", "DS"):
        keep = (pw == w) | ~lab  # the wallet's prints vs every non-cluster print
        y = (pw == w)[keep]
        res["by_wallet"][w] = {"auc_rule": round(auc(y, s_rule[keep]), 4), "auc_RE_pure_baseline": round(auc(y, s_pure[keep]), 4),
                               "auc_own_MKTX_baseline": round(auc(y, s_own[keep]), 4), "at_flag": rl(y, flag[keep])}
    strongest = "auc_RE_pure_baseline" if res["pooled"]["auc_RE_pure_baseline"] >= res["pooled"]["auc_own_MKTX_baseline"] else "auc_own_MKTX_baseline"
    sb = s_pure if strongest == "auc_RE_pure_baseline" else s_own
    res["strongest_baseline"] = strongest
    res["gain_vs_strongest"] = round(res["pooled"]["auc_rule"] - res["pooled"][strongest], 4)
    res["gain_boot"] = boot_gain(lab.astype(np.int8), s_rule, sb, blocks, n=2000, bar=0.05)
    json.dump(res, open(out_json, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(ARGS[0])

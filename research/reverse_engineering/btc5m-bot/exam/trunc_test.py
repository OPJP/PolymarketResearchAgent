"""Examiner r1, leakage audit: TRUNCATION / CORRUPTION test of the frozen historical pipeline (cells -> tape -> reference features ->
frozen LightGBM models) on the seeded listing sample of step 0 (12 windows x 20 decision seconds, seed 20261101).

For every sampled window and decision second s, every input is CORRUPTED after a cut (values replaced by noise, timestamps kept, so a
coverage flag cannot hide a leak) and the features of the window are rebuilt with the frozen functions of code/ (cells.build_cells,
tape_feats.add_tape_feats, build_cells_day.add_inv / add_extra, final_rule.add_reference_feats with the archives of the lot):
  cut A ("stated horizon"): spot 1-s closes of seconds >= s-1, tape prints stamped >= s, venue trades with T >= (s-1)*1000 ms.
     The frozen code claims to use only data before these points; predictions of the cells (s, Up) and (s, Down) must be identical.
  cut B ("block-time slack 2 s"): the same at s-1 for prints and venue trades with T >= (s-2)*1000 (spot unchanged): data that may
     post-date the wallet's decision for a fill stamped s. Differences here measure how much the block-second presence score uses
     information from inside the 2-s slack (by design of that unit; the decision-aligned unit is the slack-clean variant).
Models checked: presence model_it5_blk_full / model_it5_blk_pure, decision-aligned model_it5_dp_k1_full, net-flow it4b (tracker input).
Also checks that the clean rebuild reproduces the predictions evaluate() produced for the same cells.
Usage: python trunc_test.py OUT_JSON"""
import os, sys, json, glob, time, tempfile, shutil
ARGS = sys.argv[1:]
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"; EX = f"{ROOT}/.cache/exam/btc5m-bot"
sys.path.insert(0, CODE); sys.path.insert(0, ROOT)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
import final_rule as fr
import cells as cellsmod, tape_feats as tf, spot as spotmod
from build_cells_day import add_inv, add_extra
from ofi import Agg

fr.EVAL_DIR = f"{EX}/eval"
STEP0 = json.load(open(f"{ROOT}/research/reverse_engineering/btc5m-bot/results/exam_r1_step0.json"))
VENUES = ["fut", "okx", "bybit", "bnspot", "bybitspot", "okxspot"] + list(fr.ALT_SYMBOLS)
rng = np.random.default_rng(99)


def chunk_dir(st):
    for p in glob.glob(f"{EX}/chunks/*_*"):
        a, b = map(int, os.path.basename(p).split("_"))
        if a <= st < b and os.path.exists(f"{p}/evaluate.json"):
            return p, a, b
    return None, None, None


def main(out_json):
    t0 = time.time()
    M = {k: lgb.Booster(model_file=v) for k, v in (("blk_full", fr.MODEL_BLK_FULL), ("blk_pure", fr.MODEL_BLK_PURE), ("dp_full", fr.MODEL_DP_FULL))}
    res = {"sample_seed": STEP0["truncation_sample"]["seed"], "windows": [], "cutA_identical": 0, "cutA_total": 0, "cutB_changed": 0, "cutB_total": 0,
           "clean_vs_evaluate_max_abs_diff": 0.0}
    _orig_agg = fr._agg
    for w in STEP0["truncation_sample"]["windows"]:
        d, a, b = chunk_dir(int(w["start_ts"]))
        if d is None:
            res["windows"].append({"cid": w["cid"], "status": "chunk not evaluated"}); continue
        win = pd.read_parquet(f"{d}/windows_all.parquet"); win1 = win[win.cid == w["cid"]].reset_index(drop=True)
        fills = pd.read_parquet(f"{d}/fills.parquet"); fw = fills[fills.cid == w["cid"]].copy()
        st = int(win1.start_ts.iloc[0]); en = int(win1.end_ts.iloc[0]); d0 = (st // 86400) * 86400
        _, spot_frame = fr.load_spot(a, b)
        raw = {}
        for v in VENUES:
            lo_, hi_ = (st - 3600) * 1000, (en + 600) * 1000
            parts = [pd.read_parquet(p, filters=[("T", ">=", lo_), ("T", "<", hi_)]) for p in (fr._archive(v, dd, b) for dd in (d0 - 86400, d0, d0 + 86400)) if p]
            if parts:
                raw[v] = pd.concat(parts, ignore_index=True).drop_duplicates().sort_values("T", kind="stable").reset_index(drop=True)
        tape = pd.read_parquet(f"{fr.EVAL_DIR}/tapes/{w['cid']}.parquet")
        tmp = tempfile.mkdtemp(dir=EX)

        def build(cut_spot, cut_print, cut_ven_ms):
            sf = spot_frame.copy()
            if cut_spot is not None:
                m_ = sf.sec >= cut_spot; sf.loc[m_, "close"] = sf.loc[m_, "close"] * (1 + rng.normal(0, 0.01, m_.sum()))
            tp = tape.copy()
            if cut_print is not None and len(tp):
                m_ = tp.timestamp >= cut_print; k = int(m_.sum())
                tp.loc[m_, "price"] = rng.uniform(0.01, 0.99, k); tp.loc[m_, "size"] = rng.uniform(1, 500, k)
                tp.loc[m_, "side"] = rng.choice(["BUY", "SELL"], k); tp.loc[m_, "outcome"] = rng.choice(["Up", "Down"], k)
            tp.to_parquet(f"{tmp}/{w['cid']}.parquet", index=False)
            cor = {}
            for v, x in raw.items():
                y = x.copy()
                if cut_ven_ms is not None:
                    m_ = y["T"] >= cut_ven_ms; k = int(m_.sum())
                    y.loc[m_, "p"] = y.loc[m_, "p"] * (1 + rng.normal(0, 0.01, k)); y.loc[m_, "q"] = rng.uniform(0.001, 5, k).astype(np.float32)
                    y.loc[m_, "m"] = rng.random(k) < 0.5
                cor[v] = y
            fr._agg = lambda venue, days, end_ts, _c=cor: Agg(_c[venue]) if venue in _c and len(_c[venue]) else None
            tf.TAPE_DIR = tmp
            sp = spotmod.Spot(frame=sf)
            c = cellsmod.build_cells(win1, fw, sp); c = tf.add_tape_feats(c, fw, sp); c = add_inv(c, fw, 1); c = add_extra(c)
            c = fr.add_reference_feats(c, sf, b)
            fr._agg = _orig_agg
            out = {}
            for k, m in M.items():
                out[k] = m.predict(c[m.feature_name()].astype(np.float32))
            up, dn = fr._pairs(c)
            Xs = pd.concat([up[fr.FEATURES].reset_index(drop=True), pd.DataFrame({"D_" + k: dn[k].to_numpy() for k in fr.DSIDE})], axis=1)
            out["netflow_up_rows"] = lgb.Booster(model_file=fr.MODEL_NETFLOW).predict(Xs[fr.SIDE_FEATURES])
            return c[["is_up", "rel"]].reset_index(drop=True), out

        keyc, clean = build(None, None, None)
        # clean rebuild vs evaluate(): the dp_full predictions of the same cells
        cells_ev = pd.read_parquet(f"{d}/cells.parquet", columns=["cid", "is_up", "rel"])
        P = np.load(f"{d}/pred.npz"); dpf = P["model_it5_dp_k1_full.txt__0"]
        sel = (cells_ev.cid == w["cid"]).to_numpy()
        ev = pd.DataFrame({"is_up": cells_ev.is_up[sel].to_numpy(), "rel": cells_ev.rel[sel].to_numpy(), "ev": dpf[sel]})
        mm = keyc.assign(cl=clean["dp_full"]).merge(ev, on=["is_up", "rel"])
        diff_ev = float(np.abs(mm.cl - mm.ev).max())
        res["clean_vs_evaluate_max_abs_diff"] = max(res["clean_vs_evaluate_max_abs_diff"], diff_ev)
        wr = {"cid": w["cid"], "start_ts": st, "clean_vs_evaluate_max_abs_diff": round(diff_ev, 8), "A_max_abs_diff": 0.0, "B_changed_cells": 0, "B_max_abs_diff": 0.0, "B_cells": 0}
        for s in w["decision_rels"]:
            S = st + int(s)
            _, A = build(S - 1, S, (S - 1) * 1000)
            _, Bc = build(None, S - 1, (S - 2) * 1000)
            rows = np.where(keyc.rel.to_numpy() == s)[0]
            for k in M:
                dA = float(np.abs(A[k][rows] - clean[k][rows]).max()); wr["A_max_abs_diff"] = max(wr["A_max_abs_diff"], dA)
                res["cutA_total"] += 1; res["cutA_identical"] += int(dA == 0.0)
                if k == "blk_full":
                    dB = np.abs(Bc[k][rows] - clean[k][rows]); wr["B_changed_cells"] += int((dB > 1e-12).sum()); wr["B_cells"] += len(rows)
                    wr["B_max_abs_diff"] = max(wr["B_max_abs_diff"], float(dB.max()))
                    res["cutB_total"] += len(rows); res["cutB_changed"] += int((dB > 1e-12).sum()); res.setdefault("cutB_abs_diffs", []).extend(dB.tolist())
            iu = int(s)
            dnf = float(abs(A["netflow_up_rows"][iu] - clean["netflow_up_rows"][iu])); wr["A_max_abs_diff_netflow"] = max(wr.get("A_max_abs_diff_netflow", 0.0), dnf)
            res["cutA_total"] += 1; res["cutA_identical"] += int(dnf == 0.0)
        shutil.rmtree(tmp, ignore_errors=True)
        res["windows"].append(wr)
        print(json.dumps(wr), round(time.time() - t0), flush=True)
    res["elapsed_s"] = round(time.time() - t0)
    dd = np.array(res.pop("cutB_abs_diffs", [0.0]))
    res["cutB_abs_diff_mean_median_p90"] = [round(float(dd.mean()), 4), round(float(np.median(dd)), 4), round(float(np.quantile(dd, 0.9)), 4)]
    json.dump(res, open(out_json, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "windows"}, indent=1))


if __name__ == "__main__":
    main(ARGS[0])

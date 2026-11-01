"""Iteration 2: does Binance order flow (aggTrades, ms) explain the side? One-sided cluster seconds (taker and any) in
the sampled aggTrades hours; rules and LightGBM side models with and without OFI features (BUILD hours -> VALIDATE
hours). Non-PIT diagnostics (horizon ending at s or s+1) are reported separately and never used in a rule."""
import os, sys, glob, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from side_study import one_sided
from cells import FEATS
from tape_feats import TAPE_FEATS
from build_cells_day import EXTRA
from ofi import add_ofi, OFI_FEATS, load_hours
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"; V0 = 1792108800
hours = load_hours()
days = sorted(set(h // 86400 * 86400 for h in hours))
files = [f"{C}/cells/{d}.parquet" for d in days if os.path.exists(f"{C}/cells/{d}.parquet")]
D = one_sided(files, ["y", "yT"])
D["s"] = D.start_ts + D.rel
D = D[((D.s - 12) // 3600 * 3600).isin(hours.keys()) & ((D.s - 12) // 3600 == (D.s + 2) // 3600)].reset_index(drop=True)
D = add_ofi(D, "s", 1.0)                       # PIT
D = add_ofi(D, "s", 0.0, prefix="diag0_")      # NON-PIT: horizon ends at s
D = add_ofi(D, "s", -1.0, prefix="diag1_")     # NON-PIT: horizon ends at s+1
D = D[np.isfinite(D.ofi1000)]
print("rows", len(D), "BUILD", int((D.s < V0).sum()), "VAL", int((D.s >= V0).sum()), flush=True)
res = {"hours": {"build": int(sum(h < V0 for h in hours)), "val": int(sum(h >= V0 for h in hours))}}
TAPE = TAPE_FEATS + EXTRA + [c for c in D.columns if c.startswith("D_")]
params = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=100, feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
for lab in ("yT", "y"):
    d = D[D[f"{lab}_one"]]; truth = d[f"{lab}_up"].to_numpy().astype(bool)
    v = d.s.to_numpy() >= V0
    r = {"n_build": int((~v).sum()), "n_val": int(v.sum())}
    quiet = np.abs(d.r3.to_numpy()) < 0.5
    rules = {}
    for k in ["ofi500", "ofi1000", "ofi2000", "ofi3000", "pm500", "pm1000", "pm2000", "r2", "diag0_ofi1000", "diag0_pm1000", "diag1_ofi1000", "diag1_pm1000"]:
        x = d[k].to_numpy(); nz = x != 0
        rules[k] = {"all": [round(float(((x[nz & v] > 0) == truth[nz & v]).mean()), 4), round(float((nz & v).sum() / v.sum()), 3)],
                    "quiet_r3": [round(float(((x[nz & v & quiet] > 0) == truth[nz & v & quiet]).mean()), 4), int((nz & v & quiet).sum())]}
    r["rules_val"] = rules
    r["models_val"] = {}
    for nm, fs in [("spot_tape", FEATS + TAPE), ("spot_tape_ofi", FEATS + TAPE + OFI_FEATS), ("ofi_only", ["rel", "tau"] + OFI_FEATS),
                   ("DIAG_nonpit_spot_tape_ofi_s", FEATS + TAPE + OFI_FEATS + ["diag0_" + k for k in OFI_FEATS])]:
        m = lgb.train(params, lgb.Dataset(d[fs][~v], truth[~v].astype(int)), 300)
        p = m.predict(d[fs][v])
        imp = sorted(zip(fs, m.feature_importance("gain")), key=lambda t: -t[1]); tot = sum(x for _, x in imp)
        r["models_val"][nm] = {"acc": round(float(((p >= 0.5) == truth[v]).mean()), 4), "acc_quiet_r3": round(float(((p >= 0.5) == truth[v])[quiet[v]].mean()), 4),
                               "top": [(k, round(float(x / tot), 3)) for k, x in imp[:8]]}
        print(lab, nm, r["models_val"][nm]["acc"], r["models_val"][nm]["acc_quiet_r3"], flush=True)
    res[lab] = r
    print(lab, json.dumps(rules), flush=True)
json.dump(res, open(f"{R}/results_ofi_side_iter2.json", "w"), indent=1)

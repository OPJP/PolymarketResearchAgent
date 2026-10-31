"""Rotation null with 99 draws for the frozen selection score on VALIDATE (negatives subsampled 10%, weights 10)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd, lightgbm as lgb
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sel2
from features2 import Spot
from panel2 import OUT, WALLETS
VAL0, H = 1792108800, 1792713600
N = int(sys.argv[1]) if len(sys.argv) > 1 else 99
w = pd.read_parquet(OUT / "windows_5m.parquet")
spd = pd.read_parquet(OUT / "spot_btc_1s.parquet"); sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
mk_tx = set(fills.loc[fills["role"] == "maker", "tx"]); cw = set(WALLETS.values())
m = lgb.Booster(model_file=str(HERE / "selection2_all.txt"))
rng = np.random.default_rng(21)
obs, S = [], []
for d in range(VAL0, H, 86400):
    te, pan, wd = sel2.day_prints(d, w, sp, mk_tx, cw, 0.10, rng)
    te = te.reset_index(drop=True)
    te["rid"] = np.arange(len(te))
    key = (te["day"] // 86400 * 1000 + te["widx"]).astype(np.int64)
    obs.append(pd.DataFrame({"cid": key, "y": te["y"].astype(np.int8), "wt": te["wt"], "q": te["q"], "rel_p": te["rel_p"], "side_up": te["side_up"],
                             "s": m.predict(te[sel2.F_ALL]).astype(np.float32)}))
    prng = np.random.default_rng(500 + d % 1000)
    sd = np.full((N, len(te)), np.nan, np.float32)
    for i in range(N):
        r = sel2.rotated(te, pan, wd, sp, int(prng.integers(1, len(wd))))
        sd[i, r["rid"].to_numpy()] = m.predict(r[sel2.F_ALL]).astype(np.float32)
    S.append(sd)
    print("day", d, flush=True)
o = pd.concat(obs, ignore_index=True)
S = np.concatenate(S, axis=1)
gg, gw = sel2.strata(o, 50, 40, False), sel2.strata(o, 10, 10, True)
y, wt = o["y"].to_numpy(), o["wt"].to_numpy()
og = sel2.wauc(o["s"].to_numpy(), y, wt, gg)
ow = sel2.wauc(o["s"].to_numpy(), y, wt, gw)
ng, nw = [], []
for i in range(N):
    ok = np.isfinite(S[i])
    ng.append(sel2.wauc(S[i][ok], y[ok], wt[ok], gg[ok]))
    nw.append(sel2.wauc(S[i][ok], y[ok], wt[ok], gw[ok]))
ng, nw = np.array(ng), np.array(nw)
res = {"n_perm": N, "rows": int(len(o)), "pos": int(y.sum()), "obs_strat_global": og, "obs_strat_window": ow,
       "null_global_mean": float(ng.mean()), "null_global_max": float(ng.max()), "null_global_sd": float(ng.std(ddof=1)),
       "null_window_mean": float(nw.mean()), "null_window_max": float(nw.max()), "null_window_sd": float(nw.std(ddof=1)),
       "p_global": float((1 + (ng >= og).sum()) / (N + 1)), "p_window": float((1 + (nw >= ow).sum()) / (N + 1))}
res["p"] = max(res["p_global"], res["p_window"])
res["z_global"] = float((og - ng.mean()) / ng.std(ddof=1)); res["z_window"] = float((ow - nw.mean()) / nw.std(ddof=1))
print(json.dumps(res, indent=1))
(HERE.parent / "results_iter2_selection_null99.json").write_text(json.dumps(res, indent=1))

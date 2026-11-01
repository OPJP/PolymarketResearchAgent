"""Iteration 4 (late): decision-time alignment for the side model. The bot's side agrees most with moves in [s-3, s-2)
(BTC futures and ETH), but the PIT features are windows ending at the horizon s-1 ([s-2, s-1), [s-3, s-1), [s-4, s-1)).
Adds explicit lagged segments derived from them: q_d21 = q_pm2000 - q_pm1000 ([s-3, s-2)) and q_d32 = q_pm3000 - q_pm2000
([s-4, s-3)) for the ten series (six BTC + four alts, alts in BTC-equivalent units), the signed largest d21 across series,
the net count of series moving >= 0.3 bp each way in [s-3, s-2), and the same for the composites. Side model only, same
parameters; BUILD -> VALIDATE one-sided seconds; compared with model_it4b_side on the same rows.
Usage: python -I side_lag.py"""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
sys.argv = [sys.argv[0], "four"]
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats
import train5 as t5
import train3 as t3
from alt_cells import BETA
C = t3.C; R = t3.R
beta = {p: BETA[p] for p, _ in t5.ALTS_USE}
SER = ["F", "O", "B", "S", "Y", "K", "E", "L", "X", "G"]
LAG = [f"{q}_{k}" for q in SER for k in ("d21", "d32")] + ["M_d21", "N_d21", "C6_d21", "C6_d32", "A_d21", "A_d32"]


def add_lag(s):
    sc = {q: (beta[q] if q in beta else 1.0) for q in SER}
    st = []
    for q in SER:
        a1, a2, a3 = (s[f"{q}_pm{w}"].astype(float) / sc[q] for w in (1000, 2000, 3000))
        s[f"{q}_d21"] = (a2 - a1).astype(np.float32); s[f"{q}_d32"] = (a3 - a2).astype(np.float32); st.append((a2 - a1).to_numpy())
    st = np.stack(st, 1); ab = np.where(np.isfinite(st), np.abs(st), -1.0); j = ab.argmax(1)
    s["M_d21"] = np.where(ab.max(1) >= 0, st[np.arange(len(st)), j], np.nan).astype(np.float32)
    s["N_d21"] = (np.nansum(st >= 0.3, 1) - np.nansum(st <= -0.3, 1)).astype(np.float32)
    s["C6_d21"] = (s.C6_pm2000 - s.C6_pm1000).astype(np.float32); s["C6_d32"] = (s.C6_pm3000 - s.C6_pm2000).astype(np.float32)
    s["A_d21"] = (s.A_pmmean2000 - s.A_pmmean1000).astype(np.float32); s["A_d32"] = (s.A_pmmean3000 - s.A_pmmean2000).astype(np.float32)
    return s


def side_day(fp, spot):
    d0 = int(os.path.basename(fp)[:-8])
    c = pd.read_parquet(fp, columns=sorted(set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z"})); n = len(c) // 2
    y = c.y.to_numpy(); iu = np.where((y[:n] + y[n:]) == 1)[0]
    idx = np.r_[iu, iu + n]; sub = c.iloc[idx].copy(); sub.index = idx
    RF = t5.ref_feats(sub, d0, spot)
    for k in RF.columns:
        sub[k] = RF[k].to_numpy()
    t5.set_rel(sub, beta)
    return add_lag(t5.side_rows(sub, iu, n))


if __name__ == "__main__":
    t0 = time.time()
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    B = pd.concat([side_day(fp, spot)[t5.SIDE + LAG + ["truth_up"]] for fp in files if int(os.path.basename(fp)[:-8]) < t3.V0 and os.path.exists(f"{C}/fut/{os.path.basename(fp)}")], ignore_index=True)
    print("BUILD side rows", len(B), round(time.time() - t0), flush=True)
    F2 = t5.SIDE + LAG
    m = lgb.train(t3.SPARAMS, lgb.Dataset(B[F2], B.truth_up), 300); m.save_model(f"{CODE}/model_it4b_side_lag.txt"); del B
    m0 = lgb.Booster(model_file=f"{CODE}/model_it4b_side.txt")
    V = pd.concat([side_day(fp, spot) for fp in files if t3.V0 <= int(os.path.basename(fp)[:-8]) < t3.V1], ignore_index=True)
    up = V.truth_up.to_numpy() == 1
    p1 = m.predict(V[F2]); p0 = m0.predict(V[t5.SIDE])
    ok1 = (p1 >= 0.5) == up; ok0 = (p0 >= 0.5) == up; tk = V.yT_one.to_numpy()
    b01, b10 = int((ok1 & ~ok0).sum()), int((~ok1 & ok0).sum())
    res = {"n": int(len(V)), "side_lag": round(float(ok1.mean()), 4), "side_it4b": round(float(ok0.mean()), 4),
           "taker_lag": round(float(ok1[tk].mean()), 4), "taker_it4b": round(float(ok0[tk].mean()), 4),
           "mcnemar": {"lag_only_right": b01, "it4b_only_right": b10, "p": float(stats.binomtest(b01, b01 + b10, 0.5).pvalue)},
           "lag_gain_share": round(float(sum(g for k, g in zip(F2, m.feature_importance("gain")) if k in LAG) / m.feature_importance("gain").sum()), 4)}
    print(json.dumps(res)); json.dump(res, open(f"{R}/results_side_lag_iter4.json", "w"), indent=1)
    print("done", round(time.time() - t0))

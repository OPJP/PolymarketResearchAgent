"""iteration 18, T10 = X227 (assumptions panel P3; pre-registered in NOTES.md 13:05 UTC 11-01): the ladder centre of
iteration 16 re-fitted with the scheduled fair F_sched = Phi(Phi^-1(F1_rep) x s0 / max(s0, P x v)) (s0 = futures sigma300 in
$ per root second from dm_bnf; P = utc_N28 profile of the unit's 5-min UTC slot, per-second log vol; v = the report).
c - mid = const + w (F - mid) + g (0.5 - mid), window-clustered s.e., per block, and w per 15-min bin on 11-01."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code14"))
import sched_vol as sv  # noqa: E402
from lagged_quote import fut_mid, sec_sigma  # noqa: E402

C = sv.C
BLOCKS = {"1031_1729_1800": (1793467740, 1793469600), "1101_0700_0915": (1793516400, 1793524500)}


def fit(d, F):
    y = d.c - d["mid"]
    X = sm.add_constant(np.column_stack([F - d["mid"], 0.5 - d["mid"]]))
    r = sm.OLS(y.to_numpy(), X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.w)[0]})
    return {"w": round(float(r.params[1]), 4), "w_se": round(float(r.bse[1]), 4), "g": round(float(r.params[2]), 4),
            "g_se": round(float(r.bse[2]), 4), "r2": round(float(r.rsquared), 4), "n": int(len(d))}


def main():
    T = pd.read_parquet(C / "it18" / "slot_rv.parquet")
    Pf = sv.profiles(T)["utc_N28"]
    out = {}
    for name, (a, b) in BLOCKS.items():
        d = pd.read_parquet(C / f"it16_center_units_{a}_{b}.parquet")
        d = d[np.isfinite(d.F1_rep) & np.isfinite(d["mid"])].reset_index(drop=True)
        E, M = fut_mid(a - 900, b)
        sig = sec_sigma(E, M, 300)
        t = d.P.to_numpy(np.int64)
        s0 = sig.reindex(t // 1000).to_numpy(float)
        sec = t // 1000
        day = sec // 86400 * 86400
        slot = (sec - day) // 300
        P = np.array([Pf(int(x), int(s)) for x, s in zip(day, slot)])
        sP = P * d.v.to_numpy(float)
        f1 = np.clip(d.F1_rep.to_numpy(float), 1e-9, 1 - 1e-9)
        z = norm.ppf(f1)
        ratio = s0 / np.maximum(s0, sP)
        Fs = norm.cdf(z * ratio)
        ok = np.isfinite(Fs) & np.isfinite(s0)
        d, Fs, f1, ratio = d[ok].reset_index(drop=True), Fs[ok], f1[ok], ratio[ok]
        rec = {"units": int(len(d)), "share_profile_binds": round(float((ratio < 1).mean()), 3),
               "median_profile_over_s0": round(float(np.median(1 / ratio)), 3),
               "F1": fit(d, f1), "F_sched": fit(d, Fs)}
        if name.startswith("1101"):
            bins = (d.P // 1000 // 900).to_numpy()
            ws1, wss = [], []
            for bb in np.unique(bins):
                m = bins == bb
                if m.sum() >= 30:
                    ws1.append(fit(d[m], f1[m])["w"])
                    wss.append(fit(d[m], Fs[m])["w"])
            rec["w_15min_F1"] = ws1
            rec["w_15min_F_sched"] = wss
            rec["w_15min_sd"] = {"F1": round(float(np.std(ws1)), 4), "F_sched": round(float(np.std(wss)), 4)}
        out[name] = rec
    a_, b_ = out["1031_1729_1800"]["F_sched"], out["1101_0700_0915"]["F_sched"]
    out["reading_met"] = bool(abs(a_["g"]) <= 0.03 and abs(b_["g"]) <= 0.03 and abs(a_["w"] - b_["w"]) <= 0.05 and
                              out["1101_0700_0915"]["w_15min_sd"]["F_sched"] <= 0.5 * out["1101_0700_0915"]["w_15min_sd"]["F1"])
    (HERE.parent / "results" / "iter18_center_sched.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

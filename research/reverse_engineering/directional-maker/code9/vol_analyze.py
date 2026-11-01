"""Iteration 9: score the pre-registered sigma family on the block-clock per-fill tables of code9/vol_hist.py.
    python code9/vol_analyze.py build,study          (choice: case by case allowed)
    python code9/vol_analyze.py validate <cand> <k>  (aggregate only: the frozen choice vs R6's 1.4 x v300)
Reports accuracy of 'Up iff Phi(x/(k sigma sqrt(tau))) > mid_up' per candidate and k, by regime (v300/v3600), by region
(D: reference and market disagree on the favourite, sigma-free; A: they agree, a volatility comparison), with a 2-h
block bootstrap of the gain over R6's sigma."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker" / "it9"
RES = HERE.parent / "results"


def cands(D):
    c = {f"v{L}": D[f"v{L}"].to_numpy() for L in (120, 300, 900, 1800, 3600, 7200)}
    c.update({f"e{h}": D[f"e{h}"].to_numpy() for h in (300, 900, 1800, 3600)})
    c["cap1.0"] = np.minimum(1.4 * D.v300.to_numpy(), 1.0 * D.v3600.to_numpy()) / 1.4
    c["cap1.4"] = np.minimum(1.4 * D.v300.to_numpy(), 1.4 * D.v3600.to_numpy()) / 1.4
    c["v3600_open"] = D.v3600_open.to_numpy()
    return c


def pred(D, s, k):
    x = np.log(D.S.to_numpy() / D.K.to_numpy())
    f = norm.cdf(x / (k * s * np.sqrt(D.tau.to_numpy())))
    return f > D.mid_up.to_numpy()


def boot_gain(ok1, ok0, blk, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    u, inv = np.unique(blk, return_inverse=True)
    s1 = np.bincount(inv, ok1.astype(float))
    s0 = np.bincount(inv, ok0.astype(float))
    cn = np.bincount(inv)
    g = []
    for _ in range(n):
        idx = rng.integers(0, len(u), len(u))
        g.append((s1[idx].sum() - s0[idx].sum()) / cn[idx].sum())
    return float(np.quantile(g, 0.025)), float(np.quantile(g, 0.975)), float(np.mean(np.array(g) <= 0))


def table(D, label):
    y = D.is_up.to_numpy() == 1
    x = np.log(D.S.to_numpy() / D.K.to_numpy())
    zm = norm.ppf(np.clip(D.mid_up.to_numpy(), 0.005, 0.995))
    regA = np.sign(x) == np.sign(zm)
    ratio = D.v300.to_numpy() / D.v3600.to_numpy()
    reg = np.select([ratio > 1.5, ratio > 1.15, ratio > 0.85, ratio > 0.6], ["a>1.5", "b1.15-1.5", "c0.85-1.15", "d0.6-0.85"], "e<0.6")
    C_ = cands(D)
    rows = []
    for nm, s in C_.items():
        for k in (0.8, 1.0, 1.2, 1.4):
            ok = pred(D, s, k) == y
            r = dict(cand=nm, k=k, all=ok.mean(), A=ok[regA].mean(), D=ok[~regA].mean())
            for g in np.unique(reg):
                r[g] = ok[reg == g].mean()
            rows.append(r)
    R = pd.DataFrame(rows)
    n = {"n": int(len(D)), "share_regionA": float(regA.mean()), **{g: int((reg == g).sum()) for g in np.unique(reg)}}
    print(f"== {label}", n)
    print("baselines: always-Up %.3f cheaper %.3f mid>0.5(fav) %.3f" % (y.mean(), np.mean((D.mid_up.to_numpy() < 0.5) == y), np.mean((D.mid_up.to_numpy() > 0.5) == y)))
    return R, n


def main():
    split = sys.argv[1]
    if split != "validate":
        Ds = {s: pd.read_parquet(C / f"volhist_{s}.parquet") for s in split.split(",")}
        D = pd.concat(Ds.values(), ignore_index=True)
        out = {}
        for lab, d in list(Ds.items()) + [("pooled", D)]:
            R, n = table(d, lab)
            ref = R[(R.cand == "v300") & (R.k == 1.4)].iloc[0]
            print("R6 ref (1.4 x v300):", {k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in ref.to_dict().items()})
            best = R.sort_values("all", ascending=False).groupby("cand").head(1).sort_values("all", ascending=False)
            print(best.round(3).to_string(index=False))
            out[lab] = {"n": n, "ref": ref.to_dict(), "best_per_cand": best.to_dict("records")}
        (RES / "iter9_volhist_buildstudy.json").write_text(json.dumps(out, indent=1, default=float))
    else:
        cand, k = sys.argv[2], float(sys.argv[3])
        D = pd.read_parquet(C / "volhist_validate.parquet")
        y = D.is_up.to_numpy() == 1
        C_ = cands(D)
        ok1 = pred(D, C_[cand], k) == y
        ok0 = pred(D, C_["v300"], 1.4) == y
        ratio = D.v300.to_numpy() / D.v3600.to_numpy()
        burst = ratio > 1.5
        blk = (D.b.to_numpy() // 7200)
        x = np.log(D.S.to_numpy() / D.K.to_numpy())
        zm = norm.ppf(np.clip(D.mid_up.to_numpy(), 0.005, 0.995))
        regA = np.sign(x) == np.sign(zm)
        out = {"n": int(len(D)), "cand": cand, "k": k, "acc_cand": float(ok1.mean()), "acc_R6": float(ok0.mean()),
               "gain": float(ok1.mean() - ok0.mean()), "gain_ci95_p": boot_gain(ok1, ok0, blk),
               "burst_n": int(burst.sum()), "burst_acc_cand": float(ok1[burst].mean()), "burst_acc_R6": float(ok0[burst].mean()),
               "regionA_share": float(regA.mean()), "regionA_acc_cand": float(ok1[regA].mean()), "regionA_acc_R6": float(ok0[regA].mean()),
               "regionD_acc": float(ok1[~regA].mean()),
               "baseline_always_up": float(y.mean()), "baseline_cheaper": float(np.mean((D.mid_up.to_numpy() < 0.5) == y)),
               "baseline_favourite": float(np.mean((D.mid_up.to_numpy() > 0.5) == y))}
        per_w = {}
        for wv, nm in (("0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "bosona"), ("0x3725d52f3c252e8374999cc8617292ea2608ad88", "almach"), ("0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "mo-money")):
            m = (D.wallet == wv).to_numpy()
            per_w[nm] = {"n": int(m.sum()), "acc_cand": float(ok1[m].mean()), "acc_R6": float(ok0[m].mean())}
        out["per_wallet"] = per_w
        days = (D.b.to_numpy() // 86400)
        out["per_day"] = {str(int(d)): {"n": int((days == d).sum()), "cand": float(ok1[days == d].mean()), "R6": float(ok0[days == d].mean())} for d in np.unique(days)}
        print(json.dumps(out, indent=1))
        (RES / f"iter9_volhist_validate_{cand}_{k}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

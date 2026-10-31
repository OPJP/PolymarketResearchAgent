"""Iteration 9 (assumptions B4 = X86): is there a window-level anchor the fair does not carry? For every window of the
10-31 12:00-18:00 match-clock fill table (side_D) with >= 8 fills: the z-shift delta (Phi(z + delta) > mid) that
maximises agreement with the cluster's fill sides (diagnostic, one parameter per window), with the frozen sigma and the
slow sigma; then the Spearman correlation of delta with public window-level candidates at the window's first fill
(Binance spot returns over 30 / 60 / 300 s, strike minus spot at the open in sigma units, v300/v3600, time left).
Development, descriptive; fit/test split by time (12-15 vs 15-18) for the single best term."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker/it9"


def main():
    D = pd.read_parquet(C / "side_D_1793448000_1793469600.parquet")
    sp = pd.read_parquet(C / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    v = lambda i, L: np.sqrt((cs[i + 1] - cs[i + 1 - L]) / L)  # noqa: E731
    rows = []
    grid = np.arange(-2.0, 2.01, 0.05)
    for (st, en), g in D.groupby(["st", "en"]):
        if len(g) < 8:
            continue
        T = g["T"].to_numpy()
        i = T // 1000 - 1 - b0
        tau = np.maximum(en - T / 1000, 1.0)
        x = np.log(g.cl.to_numpy(float) / g.K.to_numpy(float))
        m = g.mid_up.to_numpy()
        y = g.is_up.to_numpy() == 1
        rec = {"st": int(st), "fam": "15m" if en - st == 900 else "5m", "n": int(len(g))}
        for nm, sg in (("frozen", 1.4 * v(i, 300)), ("slow", v(i, 3600))):
            z = x / (sg * np.sqrt(tau))
            accs = np.array([np.mean((norm.cdf(z + d) > m) == y) for d in grid])
            best = accs.max()
            ds = grid[accs >= best - 1e-9]
            rec[f"delta_{nm}"] = float(ds[np.argmin(np.abs(ds))])
            rec[f"acc0_{nm}"] = float(accs[np.argmin(np.abs(grid))])
            rec[f"accbest_{nm}"] = float(best)
        i0 = int(T.min() // 1000 - 1 - b0)
        s0 = int(st - 1 - b0)
        rec.update(r30=float(np.log(px[i0] / px[i0 - 30])), r60=float(np.log(px[i0] / px[i0 - 60])), r300=float(np.log(px[i0] / px[i0 - 300])),
                   open_gap=float(np.log(px[s0] / g.K.iloc[0]) / (v(s0, 3600) * np.sqrt(en - st))), vr=float(v(i0, 300) / v(i0, 3600)),
                   tau0=float(en - T.min() / 1000))
        rows.append(rec)
    W = pd.DataFrame(rows)
    out = {"windows": int(len(W)), "share_delta0_frozen": float((W.delta_frozen == 0).mean()), "share_delta0_slow": float((W.delta_slow == 0).mean()),
           "failing_frozen_lt0.7": int((W.acc0_frozen < 0.7).sum()), "failing_slow_lt0.7": int((W.acc0_slow < 0.7).sum())}
    cand = ["r30", "r60", "r300", "open_gap", "vr", "tau0"]
    for nm in ("frozen", "slow"):
        nz = W[f"delta_{nm}"] != 0
        out[f"spearman_{nm}"] = {c: [round(float(spearmanr(W[f"delta_{nm}"], W[c]).correlation), 3),
                                     round(float(spearmanr(W[f"delta_{nm}"][nz], W[c][nz]).correlation), 3) if nz.sum() > 5 else None] for c in cand}
        # sign of delta vs sign of the recent trend in failing windows
        fail = W[f"acc0_{nm}"] < 0.7
        out[f"failing_{nm}_delta_sign_eq_r60_sign"] = float(np.mean(np.sign(W[f"delta_{nm}"][fail]) == np.sign(W.r60[fail]))) if fail.any() else None
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_b4_anchor.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

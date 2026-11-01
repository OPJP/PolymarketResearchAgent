"""iteration 18, T9 = X222 (information panel I17-3, event version at hourly resolution; pre-registered in NOTES.md 13:02 UTC
11-01): are the BTC 5m module's off-runs preceded by news bursts or volatility jumps? Development 08-02..10-22.
On = >= 1 cluster BUY trade in the BTC 5m window (activity of the three accounts). Off-run = >= 12 consecutive off windows
after >= 3 consecutive on windows; its start = the first off window. Indicators in the hour before the start (point in
time): GDELT 'bitcoin' and '(crypto OR fed OR cpi)' hourly article counts (the last complete hour) at or above the 95th
percentile of the previous 168 hours; Binance BTC slot realised vol: the max over the 12 slots before the start at or
above the 95th percentile of the previous 7 days' slots. Placebo: 20 starts per off-run at the same hour-of-week in other
weeks where the module was on in the 3 windows before. Reading: burst share >= 0.5 and >= 3 x the placebo share
(binomial p < 0.01) -> a shock trigger; else not shown."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pnl_by_ratio as pr  # noqa: E402

C = pr.C
T0, T1 = 1785628800, 1792713600  # 08-02 .. 10-23


def main():
    A = pr.trades()
    on_w = set(A.st.astype(int).unique())
    grid = np.arange(T0, T1, 300)
    on = np.array([int(t) in on_w for t in grid])
    starts = []
    i = 3
    while i < len(grid) - 12:
        if on[i - 3:i].all() and not on[i:i + 12].any():
            starts.append(int(grid[i]))
            j = i
            while j < len(grid) and not on[j]:
                j += 1
            i = j
        else:
            i += 1
    G = pd.read_parquet(C / "it18" / "gdelt_hourly.parquet")
    T = pd.read_parquet(C / "it18" / "slot_rv.parquet")
    rvs = T.assign(t=T.day + T.slot * 300).set_index("t").rv.sort_index()
    ser = {q: g.set_index("ts").n.sort_index() for q, g in G.groupby("q")}

    def burst(q, t):
        s = ser[q]
        h = (t // 3600) * 3600 - 3600  # last complete hour before t
        if h not in s.index:
            return np.nan
        prev = s[(s.index >= h - 168 * 3600) & (s.index < h)]
        return float(s[h] >= np.quantile(prev, 0.95)) if len(prev) >= 100 else np.nan

    def voljump(t):
        x = rvs[(rvs.index >= t - 3600) & (rvs.index < t)]
        prev = rvs[(rvs.index >= t - 7 * 86400) & (rvs.index < t - 3600)]
        return float(x.max() >= np.quantile(prev, 0.95)) if len(x) and len(prev) > 500 else np.nan

    def ind(t):
        return {"bitcoin": burst("bitcoin", t), "macro": burst("macro", t), "vol": voljump(t)}
    rng = np.random.default_rng(0)
    obs = [ind(t) for t in starts]
    plc = []
    idx_on3 = {int(grid[k]) for k in range(3, len(grid)) if on[k - 3:k].all()}
    for t in starts:
        cands = [t + 7 * 86400 * k for k in range(-12, 13) if k != 0 and (t + 7 * 86400 * k) in idx_on3 and T0 <= t + 7 * 86400 * k < T1]
        for c in rng.choice(cands, size=min(20, len(cands)), replace=False) if cands else []:
            plc.append(ind(int(c)))
    out = {"windows": int(len(grid)), "on_share": round(float(on.mean()), 3), "off_runs": len(starts),
           "starts_utc": [pd.Timestamp(t, unit="s").strftime("%m-%d %H:%M") for t in starts][:60]}
    for k in ("bitcoin", "macro", "vol"):
        o = np.array([x[k] for x in obs], float)
        p = np.array([x[k] for x in plc], float)
        o, p = o[np.isfinite(o)], p[np.isfinite(p)]
        po = float(p.mean()) if len(p) else np.nan
        out[k] = {"n_obs": int(len(o)), "share_obs": round(float(o.mean()), 3) if len(o) else None, "n_placebo": int(len(p)),
                  "share_placebo": round(po, 3) if np.isfinite(po) else None,
                  "binom_p": float(binomtest(int(o.sum()), len(o), max(po, 1e-3), alternative="greater").pvalue) if len(o) and np.isfinite(po) else None}
        out[k]["reading_met"] = bool(out[k]["share_obs"] is not None and out[k]["share_obs"] >= 0.5 and np.isfinite(po)
                                     and out[k]["share_obs"] >= 3 * po and (out[k]["binom_p"] or 1) < 0.01)
    (HERE.parent / "results" / "iter18_offrun_shocks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

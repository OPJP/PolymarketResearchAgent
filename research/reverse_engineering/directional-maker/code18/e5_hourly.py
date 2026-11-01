"""iteration 18, T17 = E5 hourly screen (information panel I17-3 regression form at hourly resolution; pre-registered in
NOTES.md 13:27 UTC 11-01). Hours 08-02..10-22: dependent = the BTC 5m module-on share of the hour (share of its 12
windows with >= 1 cluster BUY trade). Regressors, lagged one hour (point in time): z of log(1 + GDELT article count) for
'bitcoin' and '(crypto OR fed OR cpi)' against the previous 168 hours, z of the log mean Binance slot rv of the previous
hour against the previous 168 hours. OLS with hour-of-week fixed effects, s.e. clustered by day; also per half of the
period. Reading: a news coefficient with p < 0.01, |effect| >= 0.05 on-share per sd and the same sign in both halves -> the
news dimension relates to selection at the hourly scale; else no association (power stated by the s.e.)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pnl_by_ratio as pr  # noqa: E402

CACHE = pr.C
T0, T1 = 1785628800, 1792713600


def zprev(s, n=168):
    m = s.shift(1).rolling(n, min_periods=100).mean()
    sd = s.shift(1).rolling(n, min_periods=100).std()
    return (s - m) / sd


def main():
    A = pr.trades()
    on_w = set(A.st.astype(int).unique())
    hrs = np.arange(T0, T1, 3600)
    H = pd.DataFrame({"h": hrs})
    H["on"] = [np.mean([int(h + 300 * k) in on_w for k in range(12)]) for h in hrs]
    G = pd.read_parquet(CACHE / "it18" / "gdelt_hourly.parquet")
    for q, g in G.groupby("q"):
        s = g.set_index("ts").n.reindex(hrs)
        z = zprev(np.log1p(s))
        H[f"z_{q}"] = z.shift(1).to_numpy()  # the previous complete hour
    T = pd.read_parquet(CACHE / "it18" / "slot_rv.parquet")
    T["h"] = (T.day + T.slot * 300) // 3600 * 3600
    rvh = T.groupby("h").rv.mean().reindex(hrs)
    H["z_vol"] = zprev(np.log(rvh)).shift(1).to_numpy()
    H["how"] = ((H.h // 3600 + 72) % 168).astype(int)  # hour of week (epoch starts on a Thursday)
    H["day"] = (H.h // 86400).astype(int)
    out = {"hours": int(len(H)), "coverage": {c: round(float(H[c].notna().mean()), 3) for c in H.columns if c.startswith("z_")}}
    for nm in ("z_bitcoin", "z_macro", "z_vol"):
        d = H.dropna(subset=[nm])
        if len(d) < 200:
            out[nm] = {"n": int(len(d)), "note": "too few hours"}
            continue
        rec = {}
        for part, dd in (("all", d), ("half1", d[d.h < (T0 + T1) // 2]), ("half2", d[d.h >= (T0 + T1) // 2])):
            if len(dd) < 150:
                rec[part] = {"n": int(len(dd))}
                continue
            r = smf.ols(f"on ~ {nm} + C(how)", data=dd).fit(cov_type="cluster", cov_kwds={"groups": dd.day})
            rec[part] = {"n": int(len(dd)), "coef": round(float(r.params[nm]), 4), "se": round(float(r.bse[nm]), 4), "p": float(r.pvalues[nm])}
        a = rec.get("all", {})
        rec["reading_met"] = bool(a.get("p", 1) < 0.01 and abs(a.get("coef", 0)) >= 0.05 and
                                  np.sign(rec.get("half1", {}).get("coef", 0)) == np.sign(rec.get("half2", {}).get("coef", 1)) == np.sign(a.get("coef", 0)))
        out[nm] = rec
    (HERE.parent / "results" / "iter18_e5_hourly.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

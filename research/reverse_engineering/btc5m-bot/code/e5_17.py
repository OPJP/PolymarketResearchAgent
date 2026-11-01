"""Iteration 17, E5 (first screen): do the operator's CONFIGURATION changes and whole-cluster OUTAGES coincide with news bursts?
The decisions follow a 255-ms Binance knee in every window, so information can only enter through the schedule. GDELT DOC 2.0
timeline volume (15-min bins, development time only: 2026-10-09 .. 10-22) for 'polymarket' and 'bitcoin'; z-score of the volume at
each dated change / outage start (NOTES: 10-13 14:10 XM share drop, 10-19 01:00 and 13:00 size phase, 10-20 19:00 size phase, 10-21
16:00 and 10-22 13:00 dispatch phase; outages 10-09 09:35, 10-11 12:35, 10-12 09:15, 10-21 07:15) against 5,000 random bins of
the same hours of day (permutation p of the mean |z|). Usage: python e5_17.py"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
from polyrea.adapters.http import HttpClient
cl = HttpClient(rates={"api.gdeltproject.org": 0.2})
EV = {"10-13 14:10 XM share drop": "2026-10-13 14:10", "10-19 01:00 size phase on": "2026-10-19 01:00", "10-19 13:00 size phase off": "2026-10-19 13:00",
      "10-20 19:00 size phase": "2026-10-20 19:00", "10-21 16:00 dispatch phase on": "2026-10-21 16:00", "10-22 13:00 dispatch phase off": "2026-10-22 13:00",
      "outage 10-09 09:35": "2026-10-09 09:35", "outage 10-11 12:35": "2026-10-11 12:35", "outage 10-12 09:15": "2026-10-12 09:15", "outage 10-21 07:15": "2026-10-21 07:15"}
res = {"source": "https://api.gdeltproject.org/api/v2/doc/doc (mode timelinevolraw, 15-min)", "events": EV}
rng = np.random.default_rng(5)
for q in ("polymarket", "bitcoin"):
    try:
        js, src = cl.get_json("https://api.gdeltproject.org/api/v2/doc/doc", {"query": q, "mode": "timelinevolraw", "format": "json",
                              "startdatetime": "20261009000000", "enddatetime": "20261022235959"}, adapter="gdelt", max_age=None)
        tl = js.get("timeline", [{}])[0].get("data", [])
        df = pd.DataFrame([{"t": pd.Timestamp(x["date"]), "v": float(x["value"]), "n": float(x.get("norm", np.nan))} for x in tl])
    except Exception as e:  # record the failure as evidence
        res[q] = {"error": repr(e)[:300]}; print(q, "ERROR", repr(e)[:300]); continue
    if not len(df):
        res[q] = {"error": "empty timeline"}; print(q, "empty"); continue
    df = df.sort_values("t").reset_index(drop=True)
    df["share"] = df.v / df.n.where(df.n > 0)
    x = np.log1p(df.share.fillna(0) * 1e6) if df.n.notna().any() else np.log1p(df.v)
    mu = x.rolling(96, min_periods=24).mean().shift(1); sd = x.rolling(96, min_periods=24).std().shift(1)
    z = ((x - mu) / sd).to_numpy()
    tt = df.t.dt.tz_localize(None) if df.t.dt.tz is not None else df.t
    zs = {}
    for k, v in EV.items():
        i = int(np.searchsorted(tt.to_numpy(), np.datetime64(pd.Timestamp(v).floor("15min")), "left"))
        win = z[max(i - 2, 0): i + 3]                       # +-30 min around the change
        zs[k] = round(float(np.nanmax(np.abs(win))), 3) if np.isfinite(win).any() else None
    ok = [v for v in zs.values() if v is not None]
    hod = tt.dt.hour.to_numpy()
    null = []
    good = np.where(np.isfinite(z))[0]
    for _ in range(5000):
        idx = rng.choice(good, len(ok))
        null.append(np.mean([np.nanmax(np.abs(z[max(j - 2, 0): j + 3])) for j in idx]))
    res[q] = {"bins": int(len(df)), "max_abs_z_pm30min": zs, "mean": round(float(np.mean(ok)), 3) if ok else None,
              "null_mean": round(float(np.mean(null)), 3), "p_perm": round(float((np.array(null) >= np.mean(ok)).mean()), 4) if ok else None,
              "top_bins": [[str(tt[j]), round(float(z[j]), 2)] for j in np.argsort(-np.nan_to_num(z, nan=-9))[:5]]}
    print(q, json.dumps(res[q]), flush=True)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/e5_17.json", "w"), indent=1, default=str)

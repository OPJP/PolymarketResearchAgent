"""I4 (panel X13): implied vol (Deribit DVOL, 1-min) vs realised 1-s vol as the vol input of the fair value.
Cluster BTC 5m maker BUY fill prices vs a TWAP-60 digital fair of Binance spot (fill second - 2 s), sigma = k x realised
(1-s log returns over 30 min) or k x DVOL (annualised -> per sqrt second). k fitted on STUDY (MAD), applied on VALIDATE
(aggregate only). Also the per-day fitted k for both inputs (stable k = the right input)."""
import json
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache" / "re" / "directional-maker"
OUT = ROOT / "research" / "reverse_engineering" / "directional-maker" / "results"


def dvol(a, b):
    f = C / f"dvol_{a}_{b}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    cl = httpx.Client(timeout=30, headers={"User-Agent": "polyrea-research"})
    rows = []
    for s in range(a, b, 43200):
        r = cl.get("https://www.deribit.com/api/v2/public/get_volatility_index_data",
                   params={"currency": "BTC", "start_timestamp": s * 1000, "end_timestamp": min(s + 43200, b) * 1000, "resolution": "60"})
        rows += r.json()["result"]["data"]
        time.sleep(0.3)
    d = pd.DataFrame(rows, columns=["ms", "o", "h", "l", "c"]).drop_duplicates("ms").sort_values("ms")
    d.to_parquet(f)
    return d


def main():
    a, b = 1792713600 - 3600, 1793404800
    dv = dvol(a, b)
    dv_t, dv_c = (dv.ms.to_numpy() // 1000), dv.c.to_numpy() / 100 / np.sqrt(365 * 24 * 3600)
    sp = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet").sort_values("sec")
    sec, px = sp.sec.to_numpy(), sp.px.to_numpy().astype(float)
    lr = np.r_[0, np.diff(np.log(px))]
    c1, c2 = np.cumsum(lr), np.cumsum(lr ** 2)
    w = pd.read_parquet(C / "exam" / "windows_5m.parquet").set_index("cid")
    f = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["token_id", "ts", "side", "price", "cid", "role"])
    f = f[(f.role == "maker") & (f.side == "BUY") & f.cid.isin(w.index)].copy()
    f["start"], f["end"] = f.cid.map(w.start_ts), f.cid.map(w.end_ts)
    f["up"] = f.token_id == f.cid.map(w.up_token)
    t = (f.ts - 2).to_numpy()
    i = np.clip(np.searchsorted(sec, t, side="right") - 1, 0, len(sec) - 1)
    st = px[i]
    a0, a1 = np.searchsorted(sec, f.start.to_numpy() - 60), np.searchsorted(sec, f.start.to_numpy())
    cs = np.r_[0, np.cumsum(px)]
    s0 = (cs[a1] - cs[a0]) / np.maximum(a1 - a0, 1)
    lo = np.clip(i - 1800, 0, None)
    n = np.maximum(i - lo, 1)
    var = (c2[i] - c2[lo]) / n - ((c1[i] - c1[lo]) / n) ** 2
    sig_r = np.sqrt(np.maximum(var, 1e-14))
    j = np.clip(np.searchsorted(dv_t, t, side="right") - 1, 0, len(dv_t) - 1)
    sig_d = dv_c[j]
    end = f.end.to_numpy()
    twap_start = end - 60
    before = t < twap_start
    var_b = np.clip(twap_start - t, 0, None) + 20.0
    r = np.clip(end - t, 0, None).astype(float)
    k0, k1 = np.searchsorted(sec, twap_start), np.searchsorted(sec, np.minimum(t, end))
    a_known = np.where(k1 > k0, (cs[np.maximum(k1, k0)] - cs[k0]) / np.maximum(k1 - k0, 1), st)
    mean = np.where(before, st, ((60 - r) * a_known + r * st) / 60)
    sdu = np.where(before, np.sqrt(var_b), (r / 60) * np.sqrt(np.maximum(r, 1e-9) / 3.0))
    f["d"] = pd.to_datetime(f.ts, unit="s").dt.strftime("%m-%d")
    f["study"] = f.start < 1793059200
    res = {"fills": int(len(f)), "dvol_points": int(len(dv)), "dvol_over_realised_median": round(float(np.median(sig_d / sig_r)), 3)}
    for name, sig in (("realised", sig_r), ("dvol", sig_d)):
        out = {}
        best = None
        for k in (0.6, 0.8, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5):
            with np.errstate(invalid="ignore", divide="ignore"):
                fu = stats.norm.cdf((mean - s0) / (st * sig * k * sdu))
            fair = np.where(f.up, fu, 1 - fu)
            e = f.price.to_numpy() - fair
            ok = (fair > 0.05) & (fair < 0.95) & np.isfinite(e)
            ms = f.study.to_numpy() & ok
            mad_s = float(np.median(np.abs(e[ms] - np.median(e[ms]))))
            out[k] = mad_s
            if best is None or mad_s < best[1]:
                best = (k, mad_s, e, ok)
        k, _, e, ok = best
        mv = (~f.study.to_numpy()) & ok
        # per-day best k (STUDY days case by case; VALIDATE days aggregate)
        perday = {}
        for dday in sorted(f.d.unique()):
            md = (f.d == dday).to_numpy()
            bk = None
            for kk in (0.6, 0.8, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5):
                with np.errstate(invalid="ignore", divide="ignore"):
                    fu = stats.norm.cdf((mean - s0) / (st * sig * kk * sdu))
                fair = np.where(f.up, fu, 1 - fu)
                ee = f.price.to_numpy() - fair
                oo = md & (fair > 0.05) & (fair < 0.95) & np.isfinite(ee)
                if oo.sum() < 200:
                    continue
                m_ = float(np.median(np.abs(ee[oo] - np.median(ee[oo]))))
                if bk is None or m_ < bk[1]:
                    bk = (kk, round(m_, 4))
            perday[dday] = bk
        res[name] = {"study_mad_by_k": {str(kk): round(v, 4) for kk, v in out.items()}, "best_k_study": k,
                     "validate_mad_at_best_k": round(float(np.median(np.abs(e[mv] - np.median(e[mv])))), 4),
                     "validate_within_0.02": round(float(np.mean(np.abs(e[mv] - np.median(e[mv])) <= 0.02)), 3),
                     "per_day_best_k": perday}
    print(json.dumps(res, indent=1))
    (OUT / "iter5_dvol.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

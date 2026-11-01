"""Iteration 9 (X75 I8-2 candidate (d): Deribit implied volatility with a fixed scale as the engine's sigma). DVOL (BTC,
1-min, annualised %) converted to per-second sigma = DVOL/100/sqrt(365*86400), last value published before the decision
second; candidates c x sigma_DVOL, c in {0.2, 0.3, 0.4, 0.5, 0.7, 1.0}, against the frozen 1.4 x v300 and v3600 on the
block-clock tables (5m and 15m; STUDY case by case, VALIDATE aggregate) and the live 10-31 12-18 match-clock fills
(DVOL fetched from Deribit's public get_volatility_index_data). Also the median realised vol by split."""
import json
import time
from pathlib import Path
import httpx
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
SEC = np.sqrt(365 * 86400)


def dvol_live(a, b):
    f = C / "it9" / f"dvol_{a}_{b}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    rows, t = [], a
    with httpx.Client(timeout=20) as c:
        while t < b:
            r = c.get("https://www.deribit.com/api/v2/public/get_volatility_index_data", params={"currency": "BTC", "start_timestamp": t * 1000,
                      "end_timestamp": min(t + 6 * 3600, b) * 1000, "resolution": "60"})
            for x in (r.json().get("result") or {}).get("data", []):
                rows.append((int(x[0]), float(x[4])))
            t += 6 * 3600
            time.sleep(0.2)
    d = pd.DataFrame(rows, columns=["ms", "c"]).drop_duplicates("ms").sort_values("ms")
    d.to_parquet(f)
    return d


def sig_dvol(dv, tsec):
    ms, c = dv.ms.to_numpy(), dv.c.to_numpy()
    j = np.searchsorted(ms, (tsec - 60) * 1000, side="right") - 1  # minute bar closed (published) by t
    return np.where(j >= 0, c[np.maximum(j, 0)], np.nan) / 100 / SEC


def score(y, x, m, st, sigs):
    return {k: round(float(np.mean((norm.cdf(x / (s * st)) > m) == y)), 4) for k, s in sigs.items()}


def main():
    dvh = pd.read_parquet(C / "dvol_1792710000_1793404800.parquet")[["ms", "c"]]
    out = {}
    for fam in ("", "15"):
        for sp_ in ("study", "validate"):
            D = pd.read_parquet(C / "it9" / f"volhist{fam}_{sp_}.parquet")
            y = D.is_up.to_numpy() == 1; x = np.log(D.S / D.K).to_numpy(); m = D.mid_up.to_numpy(); st = np.sqrt(D.tau.to_numpy())
            sd = sig_dvol(dvh, D.b.to_numpy() - 3)
            sigs = {"frozen": 1.4 * D.v300.to_numpy(), "v3600": D.v3600.to_numpy(), **{f"dvol x{c}": c * sd for c in (0.2, 0.3, 0.4, 0.5, 0.7, 1.0)}}
            ok = np.isfinite(sd)
            out[f"btc{fam or '5'}m_{sp_}"] = {"n": int(ok.sum()), **score(y[ok], x[ok], m[ok], st[ok], {k: v[ok] for k, v in sigs.items()}),
                                              "median_v300": float(np.median(D.v300)), "median_v3600": float(np.median(D.v3600)), "median_sig_dvol": float(np.nanmedian(sd))}
    D = pd.read_parquet(C / "it9" / "side_D_1793448000_1793469600.parquet")
    dv = dvol_live(1793440800, 1793469600)
    sp = pd.read_parquet(C / "it9" / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0]); px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan); px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy(); rr = np.r_[0.0, np.diff(np.log(px))]; cs = np.r_[0.0, np.cumsum(rr * rr)]
    i = D["T"].to_numpy() // 1000 - 1 - b0
    v300 = np.sqrt((cs[i + 1] - cs[i + 1 - 300]) / 300); v3600 = np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600)
    tau = np.sqrt(np.maximum(D.en.to_numpy() - D["T"].to_numpy() / 1000, 1.0)); x = np.log(D.cl.to_numpy(float) / D.K.to_numpy(float))
    m = D.mid_up.to_numpy(); y = D.is_up.to_numpy() == 1
    sd = sig_dvol(dv, D["T"].to_numpy() // 1000)
    fam = np.where(D.en - D.st == 900, "15m", "5m")
    for f in ("5m", "15m"):
        g = (fam == f) & np.isfinite(sd)
        sigs = {"frozen": 1.4 * v300, "v3600": v3600, **{f"dvol x{c}": c * sd for c in (0.2, 0.3, 0.4, 0.5, 0.7, 1.0)}}
        out[f"live_{f}"] = {"n": int(g.sum()), **score(y[g], x[g], m[g], tau[g], {k: v[g] for k, v in sigs.items()}),
                            "median_v300": float(np.median(v300[g])), "median_v3600": float(np.median(v3600[g])), "median_sig_dvol": float(np.nanmedian(sd[g]))}
    for k, v in out.items():
        print(k, {kk: vv for kk, vv in v.items() if not kk.startswith("median")}, "| med v300 %.2e v3600 %.2e dvol %.2e" % (v["median_v300"], v["median_v3600"], v["median_sig_dvol"]))
    (HERE.parent / "results" / "iter9_dvol_sigma.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

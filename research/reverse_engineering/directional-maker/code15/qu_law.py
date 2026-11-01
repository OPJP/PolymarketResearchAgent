"""directional-maker iteration 15, T3 (X166, information I14-4) and T4 (X170, mechanics P3) on the rebuilt quote unit of
10-31 14:00-18:00 (code14/qu_oos.py table: every schedule-size add at the touch of a BTC 5m/15m window, full-depth book).

T3: the settlement-average variance law, no fitting. Settlement = mean of the Chainlink values over the last 60 s.
  tau > 60: centre S, sd = sigma sqrt(tau - 40);  tau <= 60: centre ((60 - tau) A + tau S) / 60 with A the mean of the
  values already stamped in [end - 60, now], sd = sigma tau^1.5 / (60 sqrt 3). sigma = 1.0 x futures-mid sigma300.
  Against one global k 1.0 (sd = sigma sqrt(tau)) and the iteration-14 band fit (k 0.3 in the last 60 s, else 1.0).
T4: the quote-unit side by label class: 500 at non-extreme bid prices (0.03 < bid < 0.97), 500 extreme, 1000, 250, 62.
Clocks: the point-in-time-safe stamp lag 1,432 ms (14-18) and the exact public publish clock (dy_rtds P, 17:29-18:00).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code15/qu_law.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code14"))
from lagged_quote import fut_mid, sec_sigma, cl_source, live  # noqa: E402

a, b = 1793455200, 1793469600
RES = HERE.parent / "results"


def main():
    A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet")
    A = A[A.mid_prev.notna()].reset_index(drop=True)
    E, M = fut_mid(a - 600, b)
    sig = sec_sigma(E, M, 300)
    clv = cl_source.cl_values(list(range(a - 400, b + 1)), allow_sealed=False, fetch=False)
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(A.w)))
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    t = A.s.to_numpy(np.int64)
    st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
    en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300)
    tau = np.maximum(en - t / 1000.0, 0.5)
    s0 = sig.reindex(t // 1000).to_numpy(float)
    kk = A.w.map(K).to_numpy(float)
    mid = A.mid_prev.to_numpy(float)
    y = (A.sd == 1).to_numpy(float)
    bid = np.where(A.sd == 1, A.p, 1 - A.p)
    cls = np.where(A.dz == 500, np.where((bid > 0.03) & (bid < 0.97), "500_mid", "500_extreme"), A.dz.astype(int).astype(str))
    # Chainlink by stamp; the clocks
    cl_sec = pd.Series(clv).sort_index()
    cls_idx = cl_sec.index.to_numpy(np.int64)
    cls_val = cl_sec.to_numpy(float)

    def cl_at_stamp(stamp_ms):
        i = np.searchsorted(cls_idx, stamp_ms // 1000, side="right") - 1
        return np.where(i >= 0, cls_val[np.clip(i, 0, None)], np.nan), np.where(i >= 0, cls_idx[np.clip(i, 0, None)], -1)
    pub = []
    for r in live.iter_live("dy_rtds", 1793467740, b):
        if r.get("tp") == "cl" and r.get("sy") == "btc" and r.get("P"):
            pub.append((int(r["P"]), int(r["ts"]) // 1000, float(r["v"])))
    Pb = pd.DataFrame(pub, columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P")
    pm, pts, pv = Pb.P.to_numpy(np.int64), Pb.ts.to_numpy(np.int64), Pb.v.to_numpy(float)
    exact = t >= int(pm.min()) + 5000

    def clock(name):
        if name == "safe1432":
            v, stp = cl_at_stamp(t - 1432)
            return v, stp, np.ones(len(t), bool)
        i = np.searchsorted(pm, t, side="right") - 1
        v = np.where(i >= 0, pv[np.clip(i, 0, None)], np.nan)
        stp = np.where(i >= 0, pts[np.clip(i, 0, None)], -1)
        return v, stp, exact

    # A: mean of the values stamped in [end - 60, latest known stamp]
    def avg_known(stp):
        out = np.full(len(t), np.nan)
        cs = np.concatenate([[0.0], np.cumsum(cls_val)])
        lo = np.searchsorted(cls_idx, en - 60, side="left")
        hi = np.searchsorted(cls_idx, stp, side="right")
        n = hi - lo
        ok = n > 0
        out[ok] = (cs[hi[ok]] - cs[lo[ok]]) / n[ok]
        return out, n

    res = {}
    half = t < (a + (b - a) // 2) * 1000
    bands = [(0, 30), (30, 60), (60, 120), (120, 300), (300, 600), (600, 901)]
    for ck in ("safe1432", "exact_publish"):
        S, stp, avail = clock(ck)
        Akn, nkn = avg_known(stp)
        lock = tau <= 60
        centre = np.where(lock & np.isfinite(Akn), ((60 - tau) * Akn + tau * S) / 60.0, S)
        sd_law = np.where(lock, s0 * tau ** 1.5 / (60 * np.sqrt(3)), s0 * np.sqrt(np.maximum(tau - 40, 1e-6)))
        F_law = norm.cdf((centre - kk) / sd_law)
        F_k1 = norm.cdf((S - kk) / (1.0 * s0 * np.sqrt(tau)))
        F_band = norm.cdf((S - kk) / (np.where(tau <= 60, 0.3, 1.0) * s0 * np.sqrt(tau)))
        r = {}
        for nm, F in (("law", F_law), ("k1.0", F_k1), ("band_k0.3_last60", F_band)):
            P = (F > mid).astype(float)
            ok = np.isfinite(F) & np.isfinite(mid) & avail
            row = {}
            for cl in ("500_mid", "500_extreme", "1000", "250", "62"):
                m = ok & (cls == cl)
                row[cl] = [round(float((P[m] == y[m]).mean()), 4) if m.sum() else None, int(m.sum())]
            for lo_, hi_ in bands:
                m = ok & (cls == "500_mid") & (tau > lo_) & (tau <= hi_)
                row[f"500_mid_tau{lo_}-{hi_}"] = [round(float((P[m] == y[m]).mean()), 4) if m.sum() else None, int(m.sum())]
            m = ok & (cls == "500_mid")
            row["500_mid_fit14-16"] = [round(float((P[m & half] == y[m & half]).mean()), 4) if (m & half).sum() else None, int((m & half).sum())]
            row["500_mid_test16-18"] = [round(float((P[m & ~half] == y[m & ~half]).mean()), 4) if (m & ~half).sum() else None, int((m & ~half).sum())]
            m = ok & (cls == "500_mid") & (tau <= 120)
            row["500_mid_last120"] = [round(float((P[m] == y[m]).mean()), 4) if m.sum() else None, int(m.sum())]
            for hh, mm in (("fit", half), ("test", ~half)):
                m2 = m & mm
                row[f"500_mid_last120_{hh}"] = [round(float((P[m2] == y[m2]).mean()), 4) if m2.sum() else None, int(m2.sum())]
            r[nm] = row
        res[ck] = r
    res["class_counts"] = pd.Series(cls).value_counts().to_dict()
    res["note"] = ("bid = the posted outcome's bid price; 500_extreme = 500 posts at bid <= 0.03 or >= 0.97 (other makers' "
                   "0.01/0.99 bids and the deep module); exact_publish = latest report published before the post (dy_rtds P, "
                   "from 17:29 + 5 s)")
    (RES / "iter15_qu_law.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()

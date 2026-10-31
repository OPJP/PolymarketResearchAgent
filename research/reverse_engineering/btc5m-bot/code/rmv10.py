"""Iteration 10 (panel iter9 mechanics P3 = X79, first step): what precedes the removal of a resting cluster remainder?
Never-filled T-first remainders found in the book (ghost10, it10/rem10.parquet) with a located cancel: at the removal time r and
at a matched control instant c inside the same order's life (uniform in [insertion + 50 ms, r - 100 ms]), compare
  o's ask - L (cents; did the market leave the level?), o's bid > L (outbid?), the Binance USD-M BTC + OKX microprice move toward o
  over [x - 400, x - 100) ms (tick toward / against o), and other trades at L in [x - 300, x).
Candidate rules: (a) a drawn TTL (life distribution only), (b) leave when o's ask is >= k c above L, (c) cancel on an adverse tick.
Usage: python rmv10.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import gate8
from lag7 import micro_series, mv

C = L.C
A, B = 1793458500, 1793469300


def main(out):
    rem = pd.read_parquet(C + "/it10/rem10.parquet")
    r = rem[rem.found & (rem.fate == "cancel") & rem.life.notna()].copy()
    r["s_ins"] = r.m0 + r.lag; r["s_rm"] = r.s_ins + r.life
    rng = np.random.default_rng(10)
    lo = r.s_ins + 50; hi = np.maximum(r.s_rm - 100, lo + 1)
    r["s_ct"] = (lo + rng.random(len(r)) * (hi - lo)).astype(np.int64)
    R = gate8.raw_touch("btc5m_clob_raw2", A, B)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    S = micro_series("btc5m_venues2", A, B)
    res = {"n_removals": int(len(r)), "life_q10_50_90": [float(x) for x in np.percentile(r.life, [10, 50, 90])]}
    rows = {}
    for nm, col in (("removal", "s_rm"), ("control_inside_life", "s_ct"), ("insertion", "s_ins")):
        t = r[col].to_numpy(np.int64)
        ask = np.full(len(r), np.nan); bid = np.full(len(r), np.nan)
        for i, (m, up) in enumerate(zip(r.mstart.to_numpy(), r.is_up.to_numpy())):
            T = tch.get(int(m))
            if T is None:
                continue
            rs, bb, ba = T; j = np.searchsorted(rs, t[i] - 1, "right") - 1
            if j >= 0:
                ask[i] = ba[j] if up else 1 - bb[j]; bid[i] = bb[j] if up else 1 - ba[j]
        Lx = r.Lx.to_numpy(float)
        sg = np.where(r.is_up.to_numpy(bool), 1.0, -1.0)
        mvv = np.zeros(len(r)); n = np.zeros(len(r))
        for key in (("bf", "BTC"), ("ok", "BTC")):
            if key in S:
                x = mv(S, key, t - 400, t - 100); mvv += np.nan_to_num(x); n += np.isfinite(x)
        mvv = sg * np.where(n > 0, mvv / np.maximum(n, 1), np.nan)
        da = (ask - Lx) * 100
        rows[nm] = {"ask_minus_L_c_q25_50_75": [float(x) for x in np.nanpercentile(da, [25, 50, 75])],
                    "P(ask >= L + 1c)": round(float(np.nanmean(da >= 0.99)), 4), "P(ask >= L + 2c)": round(float(np.nanmean(da >= 1.99)), 4),
                    "P(bid > L)": round(float(np.nanmean((bid - Lx) * 100 >= 0.99)), 4),
                    "P(tick toward o > 0.05 bp)": round(float(np.nanmean(mvv > 0.05)), 4), "P(tick against o < -0.05 bp)": round(float(np.nanmean(mvv < -0.05)), 4)}
    res["at"] = rows
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

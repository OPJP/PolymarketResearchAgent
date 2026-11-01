"""iteration 18, T2 = X215 identification with a market control (assumptions P1 step 2; pre-registered in NOTES.md 12:37
UTC 11-01). BUILD 10-09..22 weekday BTC 5m windows of the maker-row tapes (it12/maker_rows.parquet, 672 BUILD windows):
window cheap share of (a) the cluster's maker BUY rows and (b) the other makers' rows (BUY rows; and all rows by the token
they are exposed to), mid-band 0.15-0.85, >= 5 rows; OLS on log P (pooled N 28 profile of the window's slot) with the
window's |5-min log return| and the trailing 1-h mean |5-min return| as controls; 13:30 / 13:35 UTC windows excluded."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sched_vol as sv  # noqa: E402

C = sv.C
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
B0, B1 = 1791504000, 1792713600


def fit(df, ycol):
    d = df[np.isfinite(df[ycol])]
    X = sm.add_constant(d[["logP", "absret", "trail1h"]])
    r = sm.OLS(d[ycol], X).fit(cov_type="HC1")
    return {"n": int(len(d)), "slope": round(float(r.params["logP"]), 4), "se": round(float(r.bse["logP"]), 4),
            "p_one_sided_pos": float(r.pvalues["logP"] / 2 if r.params["logP"] > 0 else 1 - r.pvalues["logP"] / 2),
            "ctrl_absret": round(float(r.params["absret"]), 3), "ctrl_trail1h": round(float(r.params["trail1h"]), 3)}


def main():
    codes = pd.read_parquet(C / "it12" / "maker_wallet_codes.parquet")
    cw = set(codes[codes.pw.str.lower().isin(CLUSTER)].wid)
    M = pd.read_parquet(C / "it12" / "maker_rows.parquet")
    M = M[(M.st >= B0) & (M.st < B1)].copy()
    M["clu"] = M.wid.isin(cw)
    # exposure token price: BUY of token at p -> p; SELL of token at p -> exposure to the complement at 1 - p
    M["xp"] = np.where(M.buy, M.price, 1 - M.price)
    M = M[(M.xp >= 0.15) & (M.xp <= 0.85)]
    M["cheap"] = (M.xp < 0.5).astype(float)
    wd = pd.to_datetime(M.st, unit="s").dt.weekday
    slot_utc = (M.st % 86400) // 300
    M = M[(wd < 5) & ~slot_utc.isin([162, 163])]  # 13:30 = slot 162, 13:35 = slot 163
    g_cl = M[M.clu & M.buy].groupby("st").agg(n=("cheap", "size"), y=("cheap", "mean"))
    g_mb = M[~M.clu & M.buy].groupby("st").agg(n=("cheap", "size"), y=("cheap", "mean"))
    g_ma = M[~M.clu].groupby("st").agg(n=("cheap", "size"), y=("cheap", "mean"))
    W = pd.DataFrame(index=sorted(set(M.st)))
    W["y_cluster"] = g_cl.y.where(g_cl.n >= 5)
    W["y_mkt_buy"] = g_mb.y.where(g_mb.n >= 5)
    W["y_mkt_all"] = g_ma.y.where(g_ma.n >= 5)
    T = pd.read_parquet(C / "it18" / "slot_rv.parquet")
    PV = sv.profiles(T)
    st = W.index.to_numpy(np.int64)
    W["logP"] = np.log(sv.prof_col(PV["pooled_N28"], st))
    r5 = {(int(d), int(s)): float(v) for d, s, v in zip(T.day, T.slot, T.r5)}
    day = st // 86400 * 86400
    slot = (st - day) // 300
    W["absret"] = [abs(r5.get((int(d), int(s)), np.nan)) for d, s in zip(day, slot)]
    tr = []
    for t0 in st:
        vals = [abs(r5.get((int((t0 - 300 * j) // 86400 * 86400), int(((t0 - 300 * j) % 86400) // 300)), np.nan)) for j in range(1, 13)]
        tr.append(np.nanmean(vals))
    W["trail1h"] = tr
    W = W[np.isfinite(W.logP) & np.isfinite(W.absret) & np.isfinite(W.trail1h)]
    out = {"windows": int(len(W)), "cluster": fit(W, "y_cluster"), "market_buy_rows": fit(W, "y_mkt_buy"), "market_all_rows": fit(W, "y_mkt_all")}
    both = W[np.isfinite(W.y_cluster) & np.isfinite(W.y_mkt_all)]
    out["same_windows"] = {"n": int(len(both)), "cluster": fit(both, "y_cluster"), "market_all_rows": fit(both, "y_mkt_all"),
                           "market_buy_rows": fit(both[np.isfinite(both.y_mkt_buy)], "y_mkt_buy")}
    d = out["same_windows"]
    out["reading_met"] = bool(d["cluster"]["slope"] > 0 and d["cluster"]["p_one_sided_pos"] < 0.01 and
                              d["cluster"]["slope"] - max(d["market_all_rows"]["slope"], d["market_buy_rows"]["slope"]) >= 0.10)
    (HERE.parent / "results" / "iter18_ident_slope.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

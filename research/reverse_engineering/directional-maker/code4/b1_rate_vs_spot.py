"""Does the order-signing rate (salt counter increments) follow Binance activity? STUDY half, all markets."""
import pandas as pd, numpy as np
C = ".cache/re/directional-maker/"
x = pd.read_parquet(C + "b1_counter_study.parquet")
x = x[x.mk.str.contains("5m|15m", regex=True)]
s = pd.read_parquet(C + "exam/spot_btc_1s.parquet").sort_values("sec")
s["chg"] = (s.px.diff() != 0).astype(int)
s["absr"] = np.abs(np.log(s.px).diff()).fillna(0)
res = {}
for B in (60, 300, 3600):
    s["b"] = s.sec // B
    sp = s.groupby("b").agg(nchg=("chg", "sum"), absr=("absr", "sum"))
    out = []
    for w, g in x.groupby("w"):
        g = g.copy(); g["b"] = g.bts // B
        hb = g.groupby("b").salt_i.quantile(0.9)
        hb = hb.reindex(range(int(hb.index.min()), int(hb.index.max()) + 1))
        inc = hb.diff() / B
        inc = inc[(inc > 0) & (inc < 200)]
        df = pd.DataFrame({"rate": inc}).join(sp, how="inner")
        df["w"] = w
        out.append(df)
    df = pd.concat(out)
    res[B] = {"n": len(df), "corr_rate_nchg": round(df.rate.corr(df.nchg, method="spearman"), 3),
              "corr_rate_absr": round(df.rate.corr(df.absr, method="spearman"), 3),
              "rate_by_absr_quintile": df.groupby(pd.qcut(df.absr, 5, labels=False)).rate.median().round(1).tolist()}
print(res)

"""Is the salt counter global per wallet (all markets) or per process/market? STUDY half only."""
import pandas as pd, numpy as np
from pathlib import Path
C = Path(".cache/re/directional-maker")
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
     "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
d = pd.concat([pd.read_parquet(p) for p in sorted((C / "calldata").glob("othstudy_*.parquet"))], ignore_index=True)
oth = pd.read_parquet(C / "other_mkts_study.parquet")
txts = oth.groupby("txh").ts.min(); slug = oth.groupby("txh").slug.first()
d = d[d.maker.isin(list(W))].copy()
d["bts"] = d.tx.map(txts); d["slug"] = d.tx.map(slug); d["w"] = d.maker.map(W)
d["mk"] = d.slug.str.extract(r"^([a-z]+-updown-[0-9a-z]+)")[0].fillna("other")
d["salt_i"] = d.salt.astype("int64")
print("other-market cluster order rows", len(d), "ts0 share", (d.sign_ms == 0).mean().round(4), d.mk.value_counts().head(8).to_dict())
b5 = pd.read_parquet(C / "b1_cluster_orders_study.parquet"); b5["salt_i"] = b5.salt.astype("int64"); b5["mk"] = "btc-updown-5m"
x = pd.concat([b5[["w", "bts", "salt_i", "mk", "role", "token_id"]], d[["w", "bts", "salt_i", "mk", "role", "token_id"]]])
x = x.drop_duplicates(["w", "salt_i", "token_id"]).sort_values(["w", "bts"])
for w, g in x.groupby("w"):
    g = g.copy()
    # interleaving test: within +-60 s, do other-market salts sit on the same line as BTC 5m salts?
    g5 = g[g.mk == "btc-updown-5m"]; go = g[g.mk != "btc-updown-5m"]
    idx = np.searchsorted(g5.bts.values, go.bts.values)
    ok = (idx > 0) & (idx < len(g5))
    dt = np.minimum(np.abs(go.bts.values[ok] - g5.bts.values[idx[ok] - 1]), np.abs(g5.bts.values[idx[ok]] - go.bts.values[ok]))
    near = dt <= 30
    rel = np.abs(go.salt_i.values[ok][near] - g5.salt_i.values[idx[ok][near] - 1]) / np.maximum(g5.salt_i.values[idx[ok][near] - 1], 1)
    print(w, "other-mkt orders within 30 s of a BTC5m fill", near.sum(), "median |salt diff|/salt", np.round(np.median(rel), 4) if near.sum() else None,
          "share within 1%", np.round((rel < 0.01).mean(), 3) if near.sum() else None)
    # resets on the combined series
    dd = g.salt_i.diff()
    rs = g[dd < -5000]
    print("  resets (combined)", [(pd.to_datetime(t, unit="s").strftime("%m-%d %H:%M"), m) for t, m in zip(rs.bts, rs.mk)])
    # rate per hour from the upper envelope: (max salt in hour - max salt in previous hour)/3600 when no reset
    g["h"] = g.bts // 3600
    hm = g.groupby("h").salt_i.max()
    rate = (hm.diff() / 3600).where(hm.diff() > 0)
    print("  orders/s per hour: median", np.round(rate.median(), 1), "q10-q90", np.round(rate.quantile([.1, .9]).tolist(), 1))
    # off-period check: salts of other-market fills during 10-24 00:00-15:25 and 10-25 00:00-13:33
    for a, b in ((1792800000, 1792855500), (1792886400, 1792935180)):
        z = g[(g.bts >= a) & (g.bts < b)]
        print("  off", pd.to_datetime(a, unit="s").strftime("%m-%d %H:%M"), "n", len(z), "mk", z.mk.value_counts().head(3).to_dict(),
              "salt first/last", (int(z.salt_i.iloc[0]), int(z.salt_i.iloc[-1])) if len(z) else None)
x.to_parquet(C / "b1_counter_study.parquet")

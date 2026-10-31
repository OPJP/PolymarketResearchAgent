"""Age of the cluster's filled BTC 5m orders from the salt counter (STUDY half), vs other makers' ages (ms timestamps)."""
import pandas as pd, numpy as np
C = ".cache/re/directional-maker/"
x = pd.read_parquet(C + "b1_counter_study.parquet")
x = x[x.mk.str.contains("5m|15m", regex=True)].sort_values(["w", "bts", "salt_i"]).reset_index(drop=True)
rows = []
for w, g in x.groupby("w"):
    g = g.copy()
    # restart segments: salt drops below 100k after being above 300k
    seg = ((g.salt_i < 100_000) & (g.salt_i.shift().fillna(0) > 300_000)).cumsum()
    g["seg"] = seg.values
    for sg, h in g.groupby("seg"):
        h = h.sort_values("bts")
        S = h.salt_i.cummax().values  # max salt filled at or before each fill
        # use the max salt strictly from fills in [t-0, t]: cummax over time-sorted fills (same-second ties included)
        t = h.bts.values
        # same-second: take max over all fills with bts <= t
        last_idx = np.searchsorted(t, t, side="right") - 1
        S_t = S[last_idx]
        # local rate: salt increase over the trailing 600 s envelope
        j = np.searchsorted(t, t - 600, side="left")
        rate = (S_t - S[np.maximum(j, 0)]) / np.maximum(t - t[np.maximum(j, 0)], 1)
        h = h.assign(lag=S_t - h.salt_i.values, rate=rate)
        rows.append(h)
z = pd.concat(rows)
z = z[(z.mk == "btc-updown-5m") & (z.role == "maker")]
z["age_s"] = z.lag / z.rate.clip(lower=3)
q = z.age_s.quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.99]).round(2).to_dict()
print("cluster BTC5m maker fills", len(z), "age (s, salt-lag / local rate) quantiles", q, "share lag==0", round((z.lag == 0).mean(), 3))
# other makers: sign->block from ms timestamps
am = pd.read_parquet(C + "b1_all_makers_study.parquet")
o = am[(~am.clu) & (am.sign_ms > 0)]
print("other makers' sign->block (s) quantiles", o.life.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(2).to_dict())
z.to_parquet(C + "b1_age_study.parquet")
# link to PnL: fills_holdout prices & outcomes
f = pd.read_parquet(C + "exam/fills_holdout.parquet")
win = pd.read_parquet(C + "exam/windows_5m.parquet")
up = dict(zip(win.up_token, win.up_payout)); dn = dict(zip(win.down_token, 1 - win.up_payout))
pay = {**up, **dn}
st = dict(zip(win.cid, win.start_ts))
f = f[(f.role == "maker") & (f.ts < 1793059200)].copy()
f["payout"] = f.token_id.map(pay); f["rel"] = f.ts - f.cid.map(st)
f["pnl"] = f.shares * (f.payout - f.price); f["usd"] = f.shares * f.price
# join age by (wallet, tx, token) -> order salt
cm = pd.read_parquet(C + "b1_cluster_orders_study.parquet")[["tx", "maker", "token_id", "salt"]]
cm["salt_i"] = cm.salt.astype("int64")
f = f.merge(cm.rename(columns={"tx": "txh", "maker": "wallet"}).drop(columns="salt"), on=["txh", "wallet", "token_id"], how="left")
f = f.merge(z[["w", "salt_i", "token_id", "age_s", "lag"]].drop_duplicates(["salt_i", "token_id", "w"]).rename(columns={"w": "wn"}),
            on=["salt_i", "token_id"], how="left")
f = f[f.age_s.notna()]
f["ab"] = pd.cut(f.age_s, [-1, 0.5, 2, 5, 15, 60, 1e9], labels=["<0.5", "0.5-2", "2-5", "5-15", "15-60", ">60"])
t = f.groupby("ab", observed=True).agg(n=("pnl", "size"), usd=("usd", "sum"), pnl=("pnl", "sum"), med_sh=("shares", "median"))
t["ret"] = (t.pnl / t.usd).round(4)
print(t.round(1).to_string())
f["sb"] = pd.cut(f.shares, [0, 40, 1e9], labels=["<=40", ">40"])
print(f.groupby(["sb", "ab"], observed=True).apply(lambda g: pd.Series({"n": len(g), "ret": g.pnl.sum() / g.usd.sum()})).round(3).unstack(0).to_string())

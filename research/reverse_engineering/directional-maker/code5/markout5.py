"""Q5 (panel X25): is the BTC 5m on/off switch a risk controller on markouts?
Per BTC 5m window (2026-10-09..30): market-wide maker return per share on the clean tape (every clean taker print is a
maker trade at the implied maker price; payout - price), known once the window resolves; the cluster's own maker return
(own state, reported separately). Trailing features at window k use windows <= k-2 only (resolved before k starts).
Window-level activity (cluster has >= 1 maker fill) vs the trailing features: AUC fitted on 2026-10-09..19, tested on
10-20..26 (BUILD-era), plus an event study around switch-offs (an active run of >= 6 windows followed by >= 12 off).
VALIDATE (10-27..30) aggregate only.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache" / "re" / "directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}

w = pd.concat([pd.read_parquet(C / "windows_5m.parquet"), pd.read_parquet(C / "exam" / "windows_5m.parquet")]).drop_duplicates("cid")
w = w.sort_values("start_ts").reset_index(drop=True)
f1 = pd.read_parquet(C / "cluster_btc5m_fills.parquet", columns=["tx", "token_id", "ts", "side", "price", "shares", "cid", "role"])
f2 = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh", "token_id", "ts", "side", "price", "shares", "cid", "role"]).rename(columns={"txh": "tx"})
fills = pd.concat([f1, f2]).drop_duplicates(subset=["tx", "token_id", "price", "shares"])
mk = fills[(fills.role == "maker") & (fills.side == "BUY")]
ctx = set(fills.tx.str.lower())
pay = w.set_index("cid").up_payout
upt = w.set_index("cid").up_token
mk = mk.assign(won=np.where(mk.token_id == mk.cid.map(upt), mk.cid.map(pay), 1 - mk.cid.map(pay)))
own = mk.assign(p=(mk.won - mk.price) * mk.shares, u=mk.price * mk.shares).groupby("cid")[["p", "u"]].sum()
rows = []
for d in range(1791504000, 1793404800, 86400):
    f = C / f"taker5m_day_{d}.parquet"
    if not f.exists():
        f = C / "exam" / f"taker5m_day_{d}.parquet"
    if not f.exists():
        continue
    t = pd.read_parquet(f, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
    t = t[~t.wallet.isin(CL) & ~t.tx.str.lower().isin(ctx)]
    t = t.join(w.set_index("cid")[["start_ts", "end_ts", "up_token", "up_payout"]], on="cid")
    t = t[(t.ts >= t.start_ts) & (t.ts < t.end_ts)]
    is_up = t.asset == t.up_token
    buy = t.side.astype(str) == "BUY"
    pay_x = np.where(is_up, t.up_payout, 1 - t.up_payout)
    # maker side: taker BUY x at p -> maker effectively long the complement at 1-p; taker SELL x at p -> maker long x at p
    mret = np.where(buy, (1 - pay_x) - (1 - t.price), pay_x - t.price)
    t = t.assign(mret=mret * t["size"], musd=np.where(buy, 1 - t.price, t.price) * t["size"])
    g = t.groupby("cid")[["mret", "musd"]].sum()
    rows.append(g)
mw = pd.concat(rows)
w = w.join(mw, on="cid").join(own, on="cid")
w["active"] = w.cid.isin(set(mk.cid)).astype(int)
w["mkt_ret"] = w.mret / w.musd
w["own_ret"] = w.p / w.u
for k in (12, 36, 72):
    # windows k-2 back: shift by 2 then rolling
    w[f"mkt_ret_{k}"] = (w.mret.shift(2).rolling(k, min_periods=k // 2).sum() / w.musd.shift(2).rolling(k, min_periods=k // 2).sum())
    w[f"own_ret_{k}"] = (w.p.shift(2).fillna(0).rolling(k, min_periods=1).sum() / w.u.shift(2).fillna(0).rolling(k, min_periods=1).sum().replace(0, np.nan))
w["prev_active"] = w.active.shift(1)
res = {}
fit = (w.start_ts >= 1791504000 + 86400) & (w.start_ts < 1792540800)       # 10-10..19
test = (w.start_ts >= 1792540800) & (w.start_ts < 1793059200)               # 10-20..26
val = (w.start_ts >= 1793059200) & (w.start_ts < 1793404800)                # VALIDATE aggregate
for name, cols in (("market_markouts", ["mkt_ret_12", "mkt_ret_36", "mkt_ret_72"]), ("own_markouts", ["own_ret_12", "own_ret_36", "own_ret_72"])):
    z = w.dropna(subset=cols)
    m = LogisticRegression(max_iter=1000).fit(z[fit.loc[z.index]][cols], z[fit.loc[z.index]].active)
    out = {}
    for nm, msk in (("fit_10-10..19", fit), ("test_10-20..26", test), ("validate_10-27..30", val)):
        zz = z[msk.loc[z.index]]
        if zz.active.nunique() == 2:
            out[nm] = {"n": int(len(zz)), "active_share": round(float(zz.active.mean()), 3), "auc": round(float(roc_auc_score(zz.active, m.predict_proba(zz[cols])[:, 1])), 4)}
    res[name] = out
# event study: switch-offs (>= 6 active windows then >= 12 inactive) in 10-09..26
a = w.active.to_numpy()
offs = [i for i in range(6, len(a) - 12) if a[i - 6:i].all() and not a[i:i + 12].any() and w.start_ts.iloc[i] < 1793059200]
ons = [i for i in range(12, len(a) - 6) if not a[i - 12:i].any() and a[i:i + 6].all() and w.start_ts.iloc[i] < 1793059200]
res["switch_offs"] = [{"t": pd.to_datetime(int(w.start_ts.iloc[i]), unit="s").strftime("%m-%d %H:%M"), "mkt_ret_12": round(float(w.mkt_ret_12.iloc[i]), 4),
                       "mkt_ret_36": round(float(w.mkt_ret_36.iloc[i]), 4), "own_ret_12": round(float(w.own_ret_12.iloc[i]), 4) if np.isfinite(w.own_ret_12.iloc[i]) else None}
                      for i in offs]
res["switch_ons"] = [pd.to_datetime(int(w.start_ts.iloc[i]), unit="s").strftime("%m-%d %H:%M") for i in ons]
base = w[(w.start_ts < 1793059200) & (w.active == 1)]
res["baseline_active_windows"] = {"mkt_ret_12_median": round(float(base.mkt_ret_12.median()), 4), "mkt_ret_12_p10": round(float(base.mkt_ret_12.quantile(.1)), 4),
                                  "own_ret_12_median": round(float(base.own_ret_12.median()), 4), "own_ret_12_p10": round(float(base.own_ret_12.quantile(.1)), 4)}
print(json.dumps(res, indent=1))
(ROOT / "research/reverse_engineering/directional-maker/results/iter5_markout.json").write_text(json.dumps(res, indent=1))

"""Iteration 3, family N2: is the BTC 5m on/off (which windows get >= 1 cluster maker fill) tied to
(a) what else the cluster trades at the time (own-state, descriptive only), or
(b) a public correlate not tried before: the taker mix of the clean BTC 5m tape in the previous hour
    (top-taker shares, HFT share, distinct takers, print sizes, buy share) and spot regime?
Window-level LightGBM fitted on BUILD windows, AUC on VALIDATE windows. Nothing at or after H.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from panel2 import OUT, WALLETS, H  # noqa: E402
from features2 import Spot  # noqa: E402

VAL0 = 1792108800
B0 = 1791504000


def fam(slug: str) -> str:
    import re
    s = re.sub(r"-\d+$", "", str(slug))
    if s.startswith("btc-updown-5m"):
        return "btc5m"
    if s.startswith("btc-updown-15m"):
        return "btc15m"
    if s.startswith("btc-updown-4h"):
        return "btc4h"
    if s.startswith("eth-updown-5m"):
        return "eth5m"
    if s.startswith("eth-updown-15m"):
        return "eth15m"
    if "-updown-5m" in s:
        return "alt5m"
    if "-updown-" in s:
        return "alt_other"
    return "other"


def main():
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[(w["end_ts"] <= H) & (w["start_ts"] >= B0)].sort_values("start_ts").reset_index(drop=True)
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk = fills[(fills["role"] == "maker") & (fills["side"] == "BUY")]
    on = set(mk["cid"])
    w["on"] = w["cid"].isin(on).astype(int)
    # (a) own activity elsewhere per slot (descriptive)
    acts = []
    for name in WALLETS:
        a = pd.read_parquet(OUT / f"activity_{name}.parquet", columns=["timestamp", "type", "slug"])
        a = a[(a["type"] == "TRADE") & (a["timestamp"] < H) & (a["timestamp"] >= B0)]
        acts.append(a)
    a = pd.concat(acts, ignore_index=True)
    a["fam"] = a["slug"].map(fam)
    a["slot"] = (a["timestamp"] // 300) * 300
    piv = a.pivot_table(index="slot", columns="fam", values="timestamp", aggfunc="count", fill_value=0)
    ws = w.set_index("start_ts")
    piv = piv.reindex(ws.index, fill_value=0)
    desc = {}
    for split, m in (("build", ws.index < VAL0), ("validate", ws.index >= VAL0)):
        on_m = ws["on"].to_numpy() == 1
        r = {}
        for c in [c for c in piv.columns if c != "btc5m"]:
            x = piv[c].to_numpy()[m]
            r[c] = {"mean_on": float(x[on_m[m]].mean()), "mean_off": float(x[~on_m[m]].mean()),
                    "share_slots_active_on": float((x[on_m[m]] > 0).mean()), "share_slots_active_off": float((x[~on_m[m]] > 0).mean())}
        desc[split] = r
    # (b) public taker mix in the previous hour (clean BTC 5m tape; cluster tx and wallets removed)
    cw = set(WALLETS.values())
    fl_tx = set(fills["tx"])
    top = None
    per = []
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        tk = pd.read_parquet(f, columns=["ts", "side", "size", "wallet", "tx"])
        tk = tk[~(tk["wallet"].isin(cw) | tk["tx"].isin(fl_tx))]
        tk = tk[tk["ts"] < H]
        tk["slot"] = (tk["ts"] // 300) * 300
        per.append(tk[["slot", "ts", "side", "size", "wallet"]])
    tk = pd.concat(per, ignore_index=True)
    del per
    bt = tk[tk["ts"] < VAL0]
    cnt = bt["wallet"].value_counts()
    top = set(cnt.index[:20])
    hft = set(cnt.index[cnt >= 5000])  # >= 5,000 BTC 5m prints in the BUILD week
    tk["top"] = tk["wallet"].isin(top)
    tk["hft"] = tk["wallet"].isin(hft)
    tk["big"] = tk["size"] >= 50
    tk["buy"] = tk["side"].astype(str) == "BUY"
    g = tk.groupby("slot").agg(n=("ts", "size"), top=("top", "sum"), hft=("hft", "sum"), big=("big", "sum"),
                               buy=("buy", "sum"), med=("size", "median"), nt=("wallet", "nunique"))
    g = g.reindex(np.arange(B0 - 3600, H, 300), fill_value=0)
    # rolling previous-hour (12 slots ending before the window's start) and the previous slot
    roll = g[["n", "top", "hft", "big", "buy"]].rolling(12, min_periods=1).sum().shift(1)
    feat = pd.DataFrame(index=g.index)
    feat["n1h"] = roll["n"]
    for c in ("top", "hft", "big", "buy"):
        feat[c + "_sh1h"] = roll[c] / roll["n"].replace(0, np.nan)
    feat["nt_prev"] = g["nt"].shift(1)
    feat["med_prev"] = g["med"].shift(1)
    feat["n_prev"] = g["n"].shift(1)
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < H]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    st = w["start_ts"].to_numpy()
    feat = feat.reindex(st)
    feat["vol1h"] = sp.sigma(st, 3600) * 1e4
    feat["vol4h"] = sp.sigma(st, 14400) * 1e4
    feat["ret1h"] = np.abs(np.log(sp.last(st) / sp.last(st - 3600))) * 1e4
    feat["hour_sin"] = np.sin(2 * np.pi * (st % 86400) / 86400)
    feat["hour_cos"] = np.cos(2 * np.pi * (st % 86400) / 86400)
    X = feat.reset_index(drop=True)
    y = w["on"].to_numpy()
    b = st < VAL0
    v = ~b
    res = {"desc_own_activity_elsewhere": desc, "val_on_share": float(y[v].mean()), "build_on_share": float(y[b].mean()),
           "n_hft_takers": len(hft)}
    params = dict(objective="binary", learning_rate=0.03, num_leaves=7, min_data_in_leaf=50, feature_fraction=0.8,
                  bagging_fraction=0.8, bagging_freq=1, lambda_l2=10.0, max_bin=63, verbose=-1, seed=7, num_threads=2)
    for name, cols in {"taker_mix": ["n1h", "top_sh1h", "hft_sh1h", "big_sh1h", "buy_sh1h", "nt_prev", "med_prev", "n_prev"],
                       "spot_regime": ["vol1h", "vol4h", "ret1h"],
                       "mix+spot": ["n1h", "top_sh1h", "hft_sh1h", "big_sh1h", "buy_sh1h", "nt_prev", "med_prev", "n_prev", "vol1h", "vol4h", "ret1h"],
                       "mix+spot+hour": list(X.columns)}.items():
        m = lgb.train(params, lgb.Dataset(X.loc[b, cols], y[b]), 200)
        p = m.predict(X.loc[v, cols])
        res[name] = {"val_auc": float(roc_auc_score(y[v], p)),
                     "imp": dict(sorted(zip(cols, m.feature_importance("gain").round(0).tolist()), key=lambda t: -t[1])[:5])}
    # univariate AUCs on VALIDATE (sign-free: max(auc, 1-auc) reported with sign)
    uni = {}
    for c in X.columns:
        x = X.loc[v, c].to_numpy()
        ok = np.isfinite(x)
        if ok.sum() > 100:
            uni[c] = round(float(roc_auc_score(y[v][ok], x[ok])), 3)
    res["univariate_val_auc"] = uni
    # the same within BUILD (does the relationship even exist there?)
    unib = {}
    for c in X.columns:
        x = X.loc[b, c].to_numpy()
        ok = np.isfinite(x)
        if ok.sum() > 100:
            unib[c] = round(float(roc_auc_score(y[b][ok], x[ok])), 3)
    res["univariate_build_auc"] = unib
    print(json.dumps({k: v for k, v in res.items() if k != "desc_own_activity_elsewhere"}, indent=1))
    print(json.dumps(desc["validate"], indent=0)[:1500])
    (HERE.parent / "results_iter3_onoff.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

"""Iteration 13 (X113 step 4): the taker LIMIT price against the archive touch at the decision clock on VALIDATE. Calldata sample
hours on 10-20 11:00 and 10-21 13:00 (calldata_sample.parquet: tx, salt, signed amounts); m = archive match ms of the tx; arrival
a = m - 150; share of taker BUY orders whose limit is within one tick (0.01) of o's archive best ask at a - Lambda (Lambda = 0, 30,
100, 180, 500 ms), exact match share, and the touch at the match itself (m) as the trivial anchor. Usage: python dcprice13.py ARCHIVE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
A = sys.argv[1]
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
cd = pd.read_parquet(f"{C}/calldata_sample.parquet", columns=["tx", "role", "maker", "token", "maker_amt", "taker_amt", "oside", "salt"])
cd = cd[cd.maker.str.lower().isin(CL) & (cd.role.astype(str).str.lower().str.startswith("t")) & (cd.oside.astype(str).isin(["0", "BUY", "buy"]) | (cd.oside == 0))]
cd["limit"] = cd.maker_amt.astype(float) / cd.taker_amt.astype(float)
res = {"taker_buy_orders_in_sample": int(len(cd))}
out = []
for day in ("2026-10-20", "2026-10-21"):
    tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    tc = pd.read_parquet(f"{A}/pm_touch_{day}.parquet"); tc["tokenId"] = tc.tokenId.astype(str)
    touch = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.bestAsk.to_numpy(float)) for k, g in tc.groupby("tokenId")}
    d = cd.copy(); d["m"] = d.tx.str.lower().map(mt); d = d[d.m.notna()]
    d["tok"] = d.token.astype(str)
    for L in (None, 0, 30, 100, 180, 500):
        col = "ask_m" if L is None else f"ask_{L}"
        v = np.full(len(d), np.nan)
        for t_, idx in d.groupby("tok").indices.items():
            if t_ in touch:
                T_, X_ = touch[t_]; tt = d.m.to_numpy(np.int64)[idx] - (0 if L is None else 150 + L)
                i = np.searchsorted(T_, tt, "right") - 1
                vv = X_[np.clip(i, 0, len(X_) - 1)]; vv = np.where(i < 0, np.nan, vv); v[idx] = vv
        d[col] = v
    d["day"] = day; out.append(d)
D = pd.concat(out, ignore_index=True)
res["matched"] = int(len(D))
for col in ["ask_m"] + [f"ask_{L}" for L in (0, 30, 100, 180, 500)]:
    ok = D[col].notna()
    e = (D.limit - D[col])[ok]
    res[col] = {"within_tick": round(float((e.abs() <= 0.0101).mean()), 4), "exact": round(float((e.abs() <= 0.0001).mean()), 4),
                "above_by_1c_plus": round(float((e >= 0.0099).mean()), 4), "n": int(ok.sum())}
res["by_wallet_ask_30"] = {CL[w]: round(float(((D.limit - D.ask_30).abs() <= 0.0101)[D.maker.str.lower() == w].mean()), 4) for w in CL}
json.dump(res, open(f"{R}/dcprice13.json", "w"), indent=1)
print(json.dumps(res))

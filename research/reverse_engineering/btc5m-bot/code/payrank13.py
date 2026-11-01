"""Iteration 13 (price component per wallet / per leg, X113 step 4 follow-up): the taker limit minus o's archive ask at arrival - 30 ms
(cents) for the calldata sample orders of 10-20 11:00 and 10-21 13:00, by wallet and by leg rank inside a fan-out event (operator
taker orders on the same token with archive match ms within 300 ms, ranked by match ms); and the within-tick share of per-wallet
pay-up anchors (ask + c_w). Usage: python payrank13.py ARCHIVE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
A = sys.argv[1]
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
cd = pd.read_parquet(f"{C}/calldata_sample.parquet", columns=["tx", "role", "maker", "token", "maker_amt", "taker_amt"])
cd = cd[cd.maker.str.lower().isin(CL) & (cd.role.astype(str).str.lower().str.startswith("t"))].copy()
cd["limit"] = cd.maker_amt.astype(float) / cd.taker_amt.astype(float)
out = []
for day in ("2026-10-20", "2026-10-21"):
    tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    tc = pd.read_parquet(f"{A}/pm_touch_{day}.parquet"); tc["tokenId"] = tc.tokenId.astype(str)
    touch = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.bestAsk.to_numpy(float)) for k, g in tc.groupby("tokenId")}
    d = cd.copy(); d["m"] = d.tx.str.lower().map(mt); d = d[d.m.notna()].copy(); d["tok"] = d.token.astype(str)
    v = np.full(len(d), np.nan)
    for t_, idx in d.groupby("tok").indices.items():
        if t_ in touch:
            T_, X_ = touch[t_]; tt = d.m.to_numpy(np.int64)[idx] - 180; i = np.searchsorted(T_, tt, "right") - 1
            v[idx] = np.where(i < 0, np.nan, X_[np.clip(i, 0, len(X_) - 1)])
    d["ask30"] = v; out.append(d)
D = pd.concat(out, ignore_index=True); D = D[D.ask30.notna()]
D["w"] = D.maker.str.lower().map(CL); D["prem"] = ((D.limit - D.ask30) * 100).round().astype(int)
D = D.sort_values(["tok", "m"]).reset_index(drop=True)
D["ev"] = ((D.tok != D.tok.shift()) | (D.m - D.m.shift() > 300)).cumsum()
D["rank"] = D.groupby("ev").cumcount(); D["legs"] = D.groupby("ev").ev.transform("size")
res = {"n": int(len(D))}
res["premium_by_wallet"] = {w: {str(k): round(float(v), 3) for k, v in g.prem.clip(-2, 4).value_counts(normalize=True).sort_index().items()} for w, g in D.groupby("w")}
res["mean_premium_by_rank"] = {str(r): [round(float(g.prem.clip(-5, 10).mean()), 3), int(len(g))] for r, g in D.groupby(D["rank"].clip(0, 3))}
res["mean_premium_single_vs_multi"] = {"single": round(float(D.prem[D.legs == 1].clip(-5, 10).mean()), 3), "multi": round(float(D.prem[D.legs > 1].clip(-5, 10).mean()), 3)}
res["by_wallet_rank"] = {f"{w}_{r}": [round(float(g.prem.clip(-5, 10).mean()), 3), int(len(g))] for (w, r), g in D.groupby(["w", D["rank"].clip(0, 2)])}
anchors = {"ask": {"DS": 0, "GF": 0, "XM": 0}, "ask_plus_cw": {"DS": 0, "GF": 1, "XM": 1}}
for nm, cw in anchors.items():
    pred = D.ask30 + D.w.map(cw) / 100.0
    ok = (D.limit - pred).abs() <= 0.0101
    res["within_tick_" + nm] = {"pool": round(float(ok.mean()), 4), **{w: round(float(ok[D.w == w].mean()), 4) for w in ("DS", "GF", "XM")}}
json.dump(res, open(f"{R}/payrank13.json", "w"), indent=1)
print(json.dumps(res))

"""Iteration 16 (X154 step 2, X162 step 3 partial): are XM's 'first legs' events whose earlier leg went to the operator's 4th / 5th
wallets (W4 / W5)? For each operator first leg (rank 0) of 10-20..22, a W4 / W5 TAKER BUY on the same window in [m0 - 300, m0) ms
(W4 / W5 txs from the data-api tapes, server ms from the public capture's trade rows), by lead wallet; placebo m0 - 3 s.
Usage: python w45lead16.py"""
import os, glob, json
import numpy as np, pandas as pd
S = os.environ["RE16_SCRATCH"]
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
win = pd.read_parquet(".cache/re/btc5m-bot/windows.parquet", columns=["cid", "start_ts"])
win = win[(win.start_ts >= 1792454400) & (win.start_ts < 1792713600)]
rows = []
for c in win.cid:
    fn = f"{S}/it16/tapes/{c}.parquet"
    if os.path.exists(fn):
        d = pd.read_parquet(fn, columns=["proxyWallet", "side", "transactionHash"])
        d = d[d.proxyWallet.str.lower().isin(W45)]
        if len(d):
            rows.append(d.assign(cid=c))
w = pd.concat(rows) if rows else pd.DataFrame(columns=["proxyWallet", "side", "transactionHash", "cid"])
w["tx"] = w.transactionHash.str.lower()
ms = []
for d in ("10-20", "10-21", "10-22"):
    t = pd.read_parquet(f"{S}/it13/hf_dl/pm_trades_2026-{d}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    t["tx"] = t.transactionHash.str.lower(); ms.append(t[t.tx.isin(set(w.tx))].groupby("tx").exchangeTimestampMs.min())
ms = pd.concat(ms)
w["m"] = w.tx.map(ms); w = w[w.m.notna()].drop_duplicates("tx")
idx = {c: np.sort(g.m.to_numpy()) for c, g in w.groupby("cid")}
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "m0", "rank", "start_ts"])
p = p[(p["rank"] == 0) & (p.start_ts >= 1792454400) & (p.start_ts < 1792713600)]
res = {"w45_txs_with_ms": int(len(w)), "by_wallet": w.proxyWallet.str.lower().value_counts().to_dict()}
for sh, tag in ((0, "m0"), (3000, "placebo_m0-3s")):
    out = {}
    for lead, g in p.groupby("wallet"):
        hit = 0
        for r in g.itertuples():
            a = idx.get(r.cid)
            if a is None:
                continue
            t = r.m0 - sh; i = np.searchsorted(a, t - 300); hit += int(i < len(a) and a[i] < t)
        out[lead] = {"n": int(len(g)), "share_with_w45_leg_in_prev_300ms": round(hit / len(g), 4)}
    res[tag] = out
print(json.dumps(res, indent=0))
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/w45lead16.json", "w"), indent=1)
# ---- gap from the last W4 / W5 leg to the XM first leg; what follows a W4 / W5 leg; same outcome?
tp = {}
for c in win.cid:
    fn = f"{S}/it16/tapes/{c}.parquet"
    if os.path.exists(fn):
        d = pd.read_parquet(fn, columns=["proxyWallet", "outcome", "transactionHash"])
        d = d[d.proxyWallet.str.lower().isin(W45)]
        for r in d.itertuples():
            tp[r.transactionHash.lower()] = (r.outcome == "Up")
w["up"] = w.tx.map(tp)
pa = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "start_ts"])
pa = pa[(pa.start_ts >= 1792454400) & (pa.start_ts < 1792713600)]
gaps = []; same = []
pp = p.merge(pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "m0", "rank", "up"]).drop_duplicates(["cid", "wallet", "m0", "rank"]), on=["cid", "wallet", "m0", "rank"], how="left")
for r in pp[pp.wallet == "XM"].itertuples():
    g = w[w.cid == r.cid]
    if not len(g):
        continue
    a = g.m.to_numpy(); j = np.where((a < r.m0) & (a >= r.m0 - 300))[0]
    if len(j):
        k = j[np.argmax(a[j])]; gaps.append(r.m0 - a[k]); same.append(int(bool(g.up.iloc[k]) == bool(r.up)))
res["xm_gap_from_w45_ms_quantiles"] = {q: float(np.quantile(gaps, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)} if gaps else None
res["xm_same_outcome_as_w45"] = round(float(np.mean(same)), 4) if same else None
# next operator leg (any of the 3 wallets) within 300 ms after a W4 / W5 leg
allm = pa.sort_values("m"); nxt = {"DS": 0, "GF": 0, "XM": 0, "none": 0}
byc = {c: g for c, g in allm.groupby("cid")}
for r in w.itertuples():
    g = byc.get(r.cid)
    if g is None:
        nxt["none"] += 1; continue
    a = g.m.to_numpy(); i = np.searchsorted(a, r.m, "right")
    if i < len(a) and a[i] - r.m <= 300:
        nxt[g.wallet.iloc[i]] += 1
    else:
        nxt["none"] += 1
res["next_leg_after_w45_within_300ms"] = nxt
print(json.dumps({k: res[k] for k in ("xm_gap_from_w45_ms_quantiles", "xm_same_outcome_as_w45", "next_leg_after_w45_within_300ms")}, indent=0))
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/w45lead16.json", "w"), indent=1)

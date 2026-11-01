"""Iteration 16 (X159 / X160 / X162 with W4 / W5 as slots): the deterministic priority rule over FIVE wallets (DS, GF, XM and the
operator's 4th / 5th wallets W4 0xd84403ef.., W5 0x03b4c58b..), visible occupancy = a taker match in (m - H, m), 10-20..22 (W4 / W5
taker legs from the data-api tapes with server ms from the public capture). Accuracy over the three studied wallets' legs and over all
legs, XM recall / precision, best priority order and slot length. Usage: python disp16b.py"""
import os, json, itertools
import numpy as np, pandas as pd
S = os.environ["RE16_SCRATCH"]
r16 = json.load(open("research/reverse_engineering/btc5m-bot/results/w45lead16.json"))
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908": "W4", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c": "W5"}
win = pd.read_parquet(".cache/re/btc5m-bot/windows.parquet", columns=["cid", "start_ts"])
win = win[(win.start_ts >= 1792454400) & (win.start_ts < 1792713600)]
rows = []
for c in win.cid:
    fn = f"{S}/it16/tapes/{c}.parquet"
    if os.path.exists(fn):
        d = pd.read_parquet(fn, columns=["proxyWallet", "side", "transactionHash"])
        d = d[d.proxyWallet.str.lower().isin(W45) & (d.side == "BUY")]
        if len(d):
            rows.append(d.assign(cid=c))
w = pd.concat(rows); w["tx"] = w.transactionHash.str.lower(); w["wallet"] = w.proxyWallet.str.lower().map(W45)
ms = []
for d in ("10-20", "10-21", "10-22"):
    t = pd.read_parquet(f"{S}/it13/hf_dl/pm_trades_2026-{d}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    t["tx"] = t.transactionHash.str.lower(); ms.append(t[t.tx.isin(set(w.tx))].groupby("tx").exchangeTimestampMs.min())
ms = pd.concat(ms); w["m"] = w.tx.map(ms); w = w[w.m.notna()].drop_duplicates("tx")
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["wallet", "m", "start_ts"])
p = p[(p.start_ts >= 1792454400) & (p.start_ts < 1792713600)]
o = pd.concat([p[["wallet", "m"]], w[["wallet", "m"]]]).sort_values("m").reset_index(drop=True)
W5 = ("DS", "GF", "XM", "W4", "W5")
mm = {x: np.sort(o.m[o.wallet == x].to_numpy()) for x in W5}
mv = o.m.to_numpy(); wv = o.wallet.to_numpy(); three = np.isin(wv, ["DS", "GF", "XM"])
res = {"legs": {x: int(len(mm[x])) for x in W5}, "rules": {}}
best = []
for H in (200, 300, 400):
    busy = {x: (np.searchsorted(mm[x], mv, "left") - np.searchsorted(mm[x], mv - H, "right")) > 0 for x in W5}
    for perm in itertools.permutations(W5):
        pred = np.full(len(o), perm[0], dtype=object); asg = np.zeros(len(o), bool)
        for x in perm:
            sel = ~busy[x] & ~asg; pred[sel] = x; asg |= sel
        acc_all = float((pred == wv).mean()); acc3 = float((pred[three] == wv[three]).mean())
        xr = float(((pred == "XM") & (wv == "XM")).sum() / max((wv == "XM").sum(), 1)); xp = float(((pred == "XM") & (wv == "XM")).sum() / max((pred == "XM").sum(), 1))
        best.append((acc_all, acc3, xr, xp, H, ">".join(perm)))
best.sort(key=lambda z: -z[0])
res["top_by_all_legs"] = [dict(acc_all=round(a, 4), acc_3wallets=round(b, 4), xm_recall=round(c, 4), xm_precision=round(d, 4), H=h, order=s) for a, b, c, d, h, s in best[:6]]
b3 = [z for z in best if z[5].startswith("DS>GF>XM")][:1] + [z for z in best if z[5] == "DS>GF>W4>XM>W5"][:3]
res["reference"] = [dict(acc_all=round(a, 4), acc_3wallets=round(b, 4), xm_recall=round(c, 4), xm_precision=round(d, 4), H=h, order=s) for a, b, c, d, h, s in b3]
print(json.dumps(res, indent=0))
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/disp16b.json", "w"), indent=1)

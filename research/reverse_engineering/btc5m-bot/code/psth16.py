"""Iteration 16 (X154 step 1 on other feeds): XM's feed fingerprint. Per carrier of operator FIRST legs (10-20..22), the PSTH of signed
price changes toward o on exchange-stamped trade feeds (Binance USD-M BTCUSDT trades, OKX BTC-USDT-SWAP trades, Binance spot trades) in
10-ms bins of m0 - T, placebo m0 - 3 s subtracted; peak lag and half-maximum width. A feed on which XM's peak is as sharp as DS's on
spot (half-max <= 130 ms) would be XM's trigger feed. Usage: python psth16.py"""
import os, json, gc
import numpy as np, pandas as pd

S = os.environ["RE16_SCRATCH"]
C = ".cache/re/btc5m-bot"
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["wallet", "up", "m0", "rank", "start_ts"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
fl = p[(p["rank"] == 0) & p.dd.isin(["10-20", "10-21", "10-22"])].reset_index(drop=True)
BIN, LO, HI = 10, 50, 1000; nb = (HI - LO) // BIN
lags = LO + BIN * np.arange(nb) + BIN / 2
W3 = ("DS", "GF", "XM")
FEEDS = {"usdm_trades": C + "/fut/{d0}.parquet", "okx_swap_trades": C + "/venues/okx/{d0}.parquet", "spot_trades": C + "/venues/bnspot/{d0}.parquet"}
res = {}
for feed, pat in FEEDS.items():
    acc = {w: np.zeros(nb) for w in W3}; acc_pl = {w: np.zeros(nb) for w in W3}; cnt = {w: 0 for w in W3}
    ok_any = False
    for d in ["10-20", "10-21", "10-22"]:
        d0 = int(pd.Timestamp(f"2026-{d}", tz="UTC").timestamp())
        fn = pat.format(d0=d0)
        if not os.path.exists(fn):
            continue
        t = pd.read_parquet(fn, columns=["T", "p"]).sort_values("T", kind="stable")
        T = t["T"].to_numpy(np.int64); P = t.p.to_numpy(float); del t
        dp = np.diff(P); sg = np.sign(dp); T1 = T[1:]; nz = sg != 0; T1, sg = T1[nz], sg[nz]
        ok_any = True
        g = fl[fl.dd == d]
        for w in W3:
            q = g[g.wallet == w]
            s_o = np.where(q.up.to_numpy() == 1, 1.0, -1.0)
            for base, A in ((q.m0.to_numpy(), acc), (q.m0.to_numpy() - 3000, acc_pl)):
                a = np.searchsorted(T1, base - HI, "left"); b = np.searchsorted(T1, base - LO, "left")
                for i in range(len(q)):
                    lg = base[i] - T1[a[i]:b[i]]; kk = ((lg - LO) // BIN).astype(int); okk = (kk >= 0) & (kk < nb)
                    np.add.at(A[w], kk[okk], sg[a[i]:b[i]][okk] * s_o[i])
            cnt[w] += len(q)
        del T, P, T1, sg; gc.collect()
    if not ok_any:
        res[feed] = "missing"; continue
    out = {}
    for w in W3:
        net = (acc[w] - acc_pl[w]) / max(cnt[w], 1)
        sm = pd.Series(net).rolling(3, center=True, min_periods=1).mean().to_numpy()
        k = int(np.argmax(sm)); above = np.where(sm >= sm[k] / 2)[0]
        out[w] = {"n": cnt[w], "peak_lag_ms": float(lags[k]), "peak": round(float(sm[k]), 4), "halfmax": [float(lags[above.min()]), float(lags[above.max()])],
                  "net_by_50ms": {int(LO + 50 * j): round(float(net[5 * j:5 * j + 5].sum()), 3) for j in range(nb // 5)}}
    res[feed] = out
    print(feed, {w: (out[w]["peak_lag_ms"], out[w]["halfmax"], out[w]["peak"]) for w in W3}, flush=True)
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/psth16.json", "w"), indent=1)

"""Iteration 17, E3 (pre-registered here, before running; brief 2026-11-01 step 4): an indicator screen with tools/indicators.py on the
operator's decision instants. Units: BTC 5m windows [start, start + 300). Decisions: first legs of DS / GF / XM at m0 - 180 ms (the
bot's posting instant; signing times are pre-sign times for this bot, so they are not decisions). Family (pre-registered): Binance
spot microprice on a 50-ms grid of the capture (Te = receive - 131 ms) -> jumps of 3 sigma over 1, 2 and 5 steps (50 / 100 / 250 ms)
and of 4 sigma over 2 steps; spot crossings of the window's strike (priceToBeat); bursts of other traders' Polymarket taker BUY prints
(server ms; operator txs excluded) over 1 s, 3 sigma. Signed tests use the event sign vs the decision side (Up +1). Screen on 10-19
(BH over the family on p_link), confirm the survivors once on 10-20. max_lag 2 s, bin 50 ms, n_null 300, swap null.
Usage: python e3_17.py"""
import os, sys, json
import numpy as np, pandas as pd, pyarrow.parquet as pq
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import indicators as ind
S = os.environ["RE16_SCRATCH"]
C = _ROOT + "/.cache/re/btc5m-bot"
pred = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "m0", "start_ts"])
ptb = pd.read_parquet(C + "/ptb.parquet").set_index("start").priceToBeat
excl = set(pd.read_parquet(C + "/fills.parquet", columns=["tx"]).tx.str.lower())


def day_inputs(day):
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
    p = pred[(pred.start_ts >= d0) & (pred.start_ts < d0 + 86400)]
    f1 = p[p.m == p.m0].drop_duplicates(["cid", "up", "m0"])
    dec = (f1.m0.to_numpy() - 180) / 1000.0; dsg = np.where(f1.up.to_numpy() == 1, 1.0, -1.0)
    starts = np.unique(p.start_ts.to_numpy().astype(np.int64)); units = np.column_stack([starts, starts + 300]).astype(float)
    t = ind.grid(d0, d0 + 86400, 0.05)
    mic = np.full(len(t), np.nan)
    for h0 in range(0, 24, 4):
        lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 4) * 3600) * 1000
        tb = pq.read_table(f"{S}/it13/hf_dl/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                           filters=[("type", "==", "book"), ("receivedTimestampMs", ">=", lo - 5000), ("receivedTimestampMs", "<", hi + 131)])
        Te = (tb.column("receivedTimestampMs").to_numpy().astype(np.int64) - 131) / 1000.0
        bp, bq, ap, aq = (tb.column(k).to_numpy().astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
        del tb
        mc = (bp * aq + ap * bq) / (bq + aq); o = np.argsort(Te, kind="stable")
        k = (t >= lo / 1000.0) & (t < hi / 1000.0)
        mic[k] = ind.asof(t[k], Te[o], mc[o])
        del Te, bp, bq, ap, aq, mc
    evs = {}
    for h, kk in ((1, 3.0), (2, 3.0), (5, 3.0), (2, 4.0)):
        evs[f"spot_jump_{h * 50}ms_{int(kk)}sig"] = ind.jumps(t, mic, horizon=h, k=kk, halflife=600)
    K = np.full(len(t), np.nan)
    for s_ in starts:
        if s_ in ptb.index:
            a, b = np.searchsorted(t, s_), np.searchsorted(t, s_ + 300)
            K[a:b] = ptb.loc[s_]
    evs["spot_strike_crossing"] = ind.crossings(t, mic - K, 0.0, refractory_s=1.0)
    tr = pd.read_parquet(f"{S}/it13/hf_dl/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tradeSide"])
    tr = tr[(tr.tradeSide == "BUY") & ~tr.transactionHash.str.lower().isin(excl)]
    ts = np.sort(tr.exchangeTimestampMs.to_numpy() / 1000.0)
    t1 = ind.grid(d0, d0 + 86400, 0.25)
    evs["pm_other_taker_burst_1s_3sig"] = (ind.burst(t1, ts, window_steps=4, k=3.0, halflife=240)[0], None)
    return dec, dsg, units, evs


res = {"preregistered": __doc__.split("Usage")[0].strip()}
dec, dsg, units, evs = day_inputs("2026-10-19")
kw = dict(max_lag_s=2.0, bin_s=0.05, n_null=300, decision_sign=dsg)
scr = ind.screen(dec, {k: v for k, v in evs.items()}, units, **kw)
res["screen_10-19"] = [{k: r.get(k) for k in ("name", "n_events", "peak_lag_s", "peak_lift", "shape_peak_lag_s", "shape_lift", "p_link", "q_bh", "signed_p_link", "signed_q_bh")} for r in scr]
print(json.dumps(res["screen_10-19"], default=str), flush=True)
surv = [r["name"] for r in scr if r.get("q_bh") is not None and r["q_bh"] < 0.05]
res["survivors"] = surv
dec2, dsg2, units2, evs2 = day_inputs("2026-10-20")
conf = {}
for nm in surv:
    e_ts, e_sg = evs2[nm]
    r = ind.event_study(dec2, e_ts, units2, max_lag_s=2.0, bin_s=0.05, n_null=300, decision_sign=dsg2, event_sign=e_sg)
    conf[nm] = {"n_events": int(len(e_ts)), "peak_lag_s": r["peak_lag_s"], "peak_lift": r["peak_lift"], "shape_peak_lag_s": r["shape_peak_lag_s"],
                "shape_lift": r["shape_lift"], "p_link": r["p_link"], "signed_p_link": r.get("signed", {}).get("p_link"), "signed_shape_z": r.get("signed", {}).get("shape_z")}
res["confirm_10-20"] = conf
print(json.dumps(conf, default=str), flush=True)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/e3_17.json", "w"), indent=1, default=str)

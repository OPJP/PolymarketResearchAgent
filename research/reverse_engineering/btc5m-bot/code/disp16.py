"""Iteration 16 (X160 = assumptions P1 steps 1 / 3, X159 = mechanics P4 partial, X154 = information P4 step 1 partial): is the carrying
wallet a PRIORITY-SLOT dispatcher with hidden occupancy (E1) or is XM a slower path for random decisions (E2)?
(a) Tick-lock PSTH per carrier: for every operator FIRST leg (rank 0) of 10-20..22, the signed rate of Binance spot microprice ticks
    toward o in 10-ms bins of m0 - Te (Te = capture receive - 131 ms, the exchange-equivalent clock of pre-registration 5), with a
    placebo at m0 - 3 s. E2 predicts XM's peak shifted by a constant or broadened; E1 a peak at the same lag as DS's.
(b) Deterministic priority rule over the operator's VISIBLE in-flight orders (matches in (m - H, m)): carrier accuracy for every
    priority order and H, per day, 10-17..22; base rates and the fills-only table.
(c) Hidden-occupancy proxy: maker-first operator order hashes (maker fills only, no taker fill) on the same (window, outcome) whose
    first maker fill comes within 60 s after a first leg, by carrier and by visible state.
Usage: python disp16.py"""
import os, sys, json, gc, itertools
import numpy as np, pandas as pd, pyarrow.parquet as pq

S = os.environ["RE16_SCRATCH"]
A = S + "/it13/hf_dl"
TRANSIT = 131
res = {}
p = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "m0", "rank", "ev", "osz", "start_ts"])
p["dd"] = pd.to_datetime(p.start_ts, unit="s").dt.strftime("%m-%d")
# ---------------- (b) priority rule on visible occupancy
o = p.sort_values("m").reset_index(drop=True)
W3 = ("DS", "GF", "XM")
mm = {w: np.sort(o.m[o.wallet == w].to_numpy()) for w in W3}
mv = o.m.to_numpy(); wv = o.wallet.to_numpy()
rb = {}
for H in (100, 150, 200, 250, 300, 400):
    busy = {w: (np.searchsorted(mm[w], mv, "left") - np.searchsorted(mm[w], mv - H, "right")) > 0 for w in W3}
    for perm in itertools.permutations(W3):
        pred = np.full(len(o), perm[0], dtype=object)
        assigned = np.zeros(len(o), bool)
        for w in perm:
            sel = ~busy[w] & ~assigned
            pred[sel] = w; assigned |= sel
        acc = float((pred == wv).mean())
        rb[f"H{H}|{''.join(x[0] for x in perm)}"] = round(acc, 4)
    st = np.select([~busy["DS"] & ~busy["GF"], busy["DS"] & ~busy["GF"], ~busy["DS"] & busy["GF"]], ["none", "DS", "GF"], "DS+GF")
    if H == 150:
        res["routing_table_H150"] = pd.crosstab(st, wv, normalize="index").round(3).to_dict("index")
        res["routing_n_H150"] = pd.Series(st).value_counts().to_dict()
        res["routing_by_day_none"] = pd.crosstab([o.dd, st], wv, normalize="index").round(3).xs("none", level=1).to_dict("index")
        res["routing_by_day_DSbusy"] = pd.crosstab([o.dd, st], wv, normalize="index").round(3).xs("DS", level=1).to_dict("index")
best = sorted(rb.items(), key=lambda kv: -kv[1])[:6]
res["priority_rule_best"] = dict(best); res["always_DS"] = round(float((wv == "DS").mean()), 4)
print("priority", best, res["always_DS"], flush=True)
# ---------------- (a) tick-lock PSTH of first legs, 10-20..22
fl = p[(p["rank"] == 0) & p.dd.isin(["10-20", "10-21", "10-22"])].reset_index(drop=True)
BIN = 10; LO, HI = 50, 1000
nb = (HI - LO) // BIN
psth = {w: np.zeros(nb) for w in W3}; psth_pl = {w: np.zeros(nb) for w in W3}; absr = {w: np.zeros(nb) for w in W3}
cnt = {w: 0 for w in W3}
for d in ["10-20", "10-21", "10-22"]:
    day = f"2026-{d}"
    g = fl[fl.dd == d]
    d0ms = int(pd.Timestamp(day, tz="UTC").timestamp()) * 1000
    for h0 in range(0, 24, 4):
        lo, hi = d0ms + h0 * 3600000, d0ms + (h0 + 4) * 3600000
        gg = g[(g.m0 >= lo) & (g.m0 < hi)]
        if not len(gg):
            continue
        t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                          filters=[("receivedTimestampMs", ">=", lo - 8000), ("receivedTimestampMs", "<", hi + 8000), ("type", "=", "book")])
        Tb = t.column("receivedTimestampMs").to_numpy().astype(np.int64)
        bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False).astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
        mic = (bp * aq + ap * bq) / (bq + aq)
        oo = np.argsort(Tb, kind="stable"); Tb, mic = Tb[oo], mic[oo]
        dm = np.diff(mic); Te = Tb[1:] - TRANSIT; sgn = np.sign(dm)
        nz = sgn != 0; Te, sgn = Te[nz], sgn[nz]
        del t, bp, bq, ap, aq, mic, dm; gc.collect()
        for w in W3:
            q = gg[gg.wallet == w]
            if not len(q):
                continue
            s_o = np.where(q.up.to_numpy() == 1, 1.0, -1.0)
            for base, acc in ((q.m0.to_numpy(), psth), (q.m0.to_numpy() - 3000, psth_pl)):
                a = np.searchsorted(Te, base - HI, "left"); b = np.searchsorted(Te, base - LO, "left")
                for i in range(len(q)):
                    sl = sgn[a[i]:b[i]]; lg = base[i] - Te[a[i]:b[i]]; kk = ((lg - LO) // BIN).astype(int); ok = (kk >= 0) & (kk < nb)
                    np.add.at(acc[w], kk[ok], sl[ok] * s_o[i])
                    if acc is psth:
                        np.add.at(absr[w], kk[ok], 1.0)
            cnt[w] += len(q)
        del Te, sgn; gc.collect()
    print(d, cnt, flush=True)
lags = LO + BIN * np.arange(nb) + BIN / 2
prof = {}
for w in W3:
    net = psth[w] / max(cnt[w], 1) - psth_pl[w] / max(cnt[w], 1)  # signed ticks toward o per leg per 10-ms bin, placebo-subtracted
    sm = pd.Series(net).rolling(3, center=True, min_periods=1).mean().to_numpy()
    kpk = int(np.argmax(sm))
    half = sm[kpk] / 2; above = np.where(sm >= half)[0]
    prof[w] = {"n": cnt[w], "peak_lag_ms": float(lags[kpk]), "peak_val": round(float(sm[kpk]), 4),
               "fwhm_lo": float(lags[above.min()]), "fwhm_hi": float(lags[above.max()]),
               "net_by_50ms": {int(LO + 50 * j): round(float(net[5 * j:5 * j + 5].sum()), 4) for j in range(nb // 5)},
               "rate_by_50ms": {int(LO + 50 * j): round(float(absr[w][5 * j:5 * j + 5].sum() / max(cnt[w], 1)), 3) for j in range(nb // 5)}}
res["psth_first_legs"] = prof
for w in W3:
    print(w, {k: v for k, v in prof[w].items() if k != "net_by_50ms" and k != "rate_by_50ms"}, flush=True)
    print("   net", prof[w]["net_by_50ms"], flush=True)
# ---------------- (c) hidden-occupancy proxy: maker-first operator order hashes
f = pd.read_parquet(".cache/re/btc5m-bot/fills.parquet", columns=["ts", "oh", "wallet", "role", "cid", "is_up", "start_ts", "shares"])
f = f[f.start_ts >= 1792454400 - 86400 * 3]
th = set(f.oh[f.role == "T"])
mf = f[(f.role == "M") & ~f.oh.isin(th)].groupby("oh").agg(t1=("ts", "min"), cid=("cid", "first"), up=("is_up", "first"), wallet=("wallet", "first"), sh=("shares", "sum")).reset_index()
res["maker_first_hashes"] = {"n": int(len(mf)), "by_wallet": mf.wallet.value_counts().to_dict()}
fl2 = p[(p["rank"] == 0) & p.dd.isin(["10-17", "10-18", "10-19", "10-20", "10-21", "10-22"])].copy()
idx = {(c, int(u), w): np.sort(g.t1.to_numpy()) for (c, u, w), g in mf.groupby(["cid", "up", "wallet"])}
for w in W3:
    v = np.zeros(len(fl2), bool)
    for i, r in enumerate(fl2.itertuples()):
        a = idx.get((r.cid, int(r.up), w))
        if a is not None:
            j = np.searchsorted(a, r.m0 / 1000.0 - 1.0); v[i] = j < len(a) and a[j] <= r.m0 / 1000.0 + 60
    fl2[f"mf_{w}"] = v
res["maker_first_within_60s_after_first_leg"] = fl2.groupby("wallet")[[f"mf_{w}" for w in W3]].mean().round(4).to_dict("index")
print(res["maker_first_within_60s_after_first_leg"], flush=True)
json.dump(res, open("research/reverse_engineering/btc5m-bot/results/disp16.json", "w"), indent=1, default=str)

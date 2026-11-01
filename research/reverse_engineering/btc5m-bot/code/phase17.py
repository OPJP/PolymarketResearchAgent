"""Iteration 17, PRE-REGISTRATION 13 (NOTES.md, written 09:53 UTC 11-01 before this runs): two-phase hazard target for the exposure
tracker. Reuses hazflow14's per-second frame (it14/hazflow14.parquet: h, y per (cid, rel) for 10-17..22) and its tracker harness
(track12.run, variant trk_a) on the 864 windows of 10-20..22, with the it16 taker tapes. mix14 (adopted, reference) vs mix17 (two
phases at 60 s, primary) and mix17b (three phases, reported only). Usage: python phase17.py TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track12

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
TD = sys.argv[1]
Hs = pd.read_parquet(os.environ["RE16_SCRATCH"] + "/it14/hazflow14.parquet")
FIT = {"2026-10-17", "2026-10-18", "2026-10-19"}
fit = Hs.day.isin(FIT).to_numpy()
c0 = float((Hs.h[fit] * Hs.y[fit]).sum() / (Hs.h[fit] ** 2).sum())
res = {"c_mix14_refit": round(c0, 4)}
for nm, edges in (("mix17", [60]), ("mix17b", [60, 180])):
    ph = np.digitize(Hs.rel.to_numpy(), edges)
    X = np.column_stack([Hs.h.to_numpy() * (ph == k) for k in range(len(edges) + 1)])
    cc = np.linalg.lstsq(X[fit], Hs.y.to_numpy()[fit], rcond=None)[0]
    Hs[f"nf_{nm}"] = X @ cc
    res[f"coef_{nm}"] = [round(float(x), 4) for x in cc]
vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf", "ask_u", "ask_d"]).merge(
    pd.read_parquet(f"{C}/it12/nf12b_val.parquet")[["cid", "rel", "nf12b"]], on=["cid", "rel"], how="left")
S = Hs[~fit].merge(vo, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
S["avg"] = 0.5 * (S.nf + S.nf12b.fillna(0)); S["mix14"] = 0.5 * S.avg + 0.5 * S.nfhaz
for nm in ("mix17", "mix17b"):
    S[nm] = 0.5 * S.avg + 0.5 * S[f"nf_{nm}"]
g = S.groupby("cid").agg(y=("y", "sum"), mix14=("mix14", "sum"), mix17=("mix17", "sum"), mix17b=("mix17b", "sum"))
res["window_net_r"] = {k: round(float(g.y.corr(g[k])), 4) for k in ("mix14", "mix17", "mix17b")}
res["window_net_spearman"] = {k: round(float(g.y.corr(g[k], method="spearman")), 4) for k in ("mix14", "mix17", "mix17b")}
print(json.dumps(res), flush=True)
winx = pd.read_parquet(f"{C}/windows.parquet").set_index("cid"); cids = S.cid.unique()
fl2 = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
fl2 = fl2[fl2.cid.isin(cids)]
mk_tx = set(fl2.loc[fl2.role == "M", "tx"].str.lower())
parts = [pd.read_parquet(f"{TD}/{c_}.parquet", columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"]).assign(cid=c_)
         for c_ in cids if os.path.exists(f"{TD}/{c_}.parquet")]
TA = pd.concat(parts, ignore_index=True); del parts
TA = TA[(TA.side == "BUY") & ~TA.proxyWallet.str.lower().isin(track12.CL)]
TA["rel"] = TA.timestamp - winx.loc[TA.cid, "start_ts"].to_numpy(); TA = TA[(TA.rel >= -2) & (TA.rel <= 305)]
TA["mk"] = TA.transactionHash.str.lower().isin(mk_tx); TA["up"] = TA.outcome == "Up"
TA = TA.sort_values(["cid", "up", "rel"], kind="stable")
tapes = {}
for (c_, o), dd in TA.groupby(["cid", "up"], sort=False):
    tapes.setdefault(c_, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
    tapes[c_][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
fl2["pay"] = np.where(fl2.is_up, fl2.up_payout, 1 - fl2.up_payout); fl2["pnl"] = fl2.shares * (fl2.pay - fl2.price) - fl2.fee_usd
Wp = {w: fl2[fl2.wallet == w].groupby("cid").pnl.sum().reindex(cids).fillna(0) for w in ("GF", "XM", "DS")}
Wp["pool"] = fl2.groupby("cid").pnl.sum().reindex(cids).fillna(0)
blocks = winx.loc[cids, "start_ts"].to_numpy() // 7200
half = winx.loc[cids, "start_ts"].to_numpy() < int(pd.Timestamp("2026-10-21 12:00", tz="UTC").timestamp())
res["n_windows"] = int(len(cids)); res["tapes_found"] = int(len(tapes))
for nm in ("mix14", "mix17", "mix17b"):
    v = S[["cid", "rel", "ask_u", "ask_d"]].copy(); v["nf"] = S[nm].to_numpy()
    T, fin = track12.run(winx, v, tapes, mk_tx, track12.VARIANTS["trk_a"])
    rp = T.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    o = {"fills": int(len(T)), "pnl_before_rebates": round(float(T.pnl.sum()), 1)}
    for w, wp in Wp.items():
        o[w] = [round(float(rp.corr(wp)), 4), round(float(rp.corr(wp, method="spearman")), 4)]
    rng = np.random.default_rng(14); ub = np.unique(blocks); bidx = {b: np.where(blocks == b)[0] for b in ub}
    x, yy = rp.to_numpy(), Wp["pool"].to_numpy(); bs = []
    for _ in range(1000):
        ii = np.concatenate([bidx[b] for b in rng.choice(ub, len(ub))]); bs.append(np.corrcoef(x[ii], yy[ii])[0, 1])
    o["pool_pearson_block_ci95"] = [round(float(np.quantile(bs, 0.025)), 4), round(float(np.quantile(bs, 0.975)), 4)]
    o["pool_halves"] = [round(float(np.corrcoef(x[h], yy[h])[0, 1]), 4) for h in (half, ~half)]
    o["pool_halves_spearman"] = [round(float(pd.Series(x[h]).corr(pd.Series(yy[h]), method="spearman")), 4) for h in (half, ~half)]
    res[f"tracker_trk_a_{nm}"] = o
    print(nm, json.dumps(o), flush=True)
a, b = res["tracker_trk_a_mix14"]["pool"], res["tracker_trk_a_mix17"]["pool"]
res["adopted_mix17"] = bool(b[0] > a[0] and b[1] > a[1])
json.dump(res, open(f"{R}/phase17.json", "w"), indent=1)
print("adopted", res["adopted_mix17"])

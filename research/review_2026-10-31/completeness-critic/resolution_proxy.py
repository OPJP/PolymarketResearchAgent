"""Which public spot feed reproduces Polymarket's Chainlink resolution best? For the 576 cached BTC-5m FIT/TEST windows,
priceToBeat (ptb) and finalPrice (final) are the Chainlink 60-s TWAP values recorded in gamma metadata (ptb.pkl from
the btc5m challenge). Proxy: 60-s TWAP of per-second prices over [start-60,start) and [end-60,end). Settlement-only use."""
import sys, json, pickle, zipfile, glob
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import numpy as np, pandas as pd
OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic"
CH = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster"
ptb = pickle.load(open(f"{CH}/ptb.pkl", "rb"))
frames = []
for f in sorted(glob.glob(f"{OUT}/dl_binance/*.zip")):
    z = zipfile.ZipFile(f)
    with z.open(z.namelist()[0]) as fh:
        frames.append(pd.read_csv(fh, header=None, usecols=[0, 4], names=["ot", "close"]))
B = pd.concat(frames).sort_values("ot").drop_duplicates("ot")
bser = pd.Series(B.close.to_numpy(float), index=(B.ot.to_numpy() // 1_000_000).astype(np.int64))
d = pickle.load(open(f"{CH}/slim.pkl", "rb"))
rows = []
for per in ("fit", "test"):
    kser = pd.Series(d[per]["spot_vals"], index=np.asarray(d[per]["spot_ev"]).astype(np.int64))
    kser = kser[~kser.index.duplicated(keep="last")].sort_index()
    for w in d[per]["windows"]:
        p = ptb.get(w.condition_id)
        if not p or p.get("ptb") is None or p.get("final") is None or w.up_payout is None:
            continue
        def twap(s, a, b):
            idx = np.arange(a, b); v = s.reindex(idx, method="ffill") if s.index.min() <= a else s.reindex(idx)
            return float(np.nanmean(v.to_numpy()))
        ks = kser.reindex(np.arange(w.start_ts - 400, w.end_ts + 1)).ffill()
        bs = bser.reindex(np.arange(w.start_ts - 400, w.end_ts + 1)).ffill()
        rows.append({"per": per, "cid": w.condition_id, "up": float(w.up_payout), "cl_ptb": p["ptb"], "cl_final": p["final"],
                     "k0": float(ks.loc[w.start_ts - 60:w.start_ts - 1].mean()), "k1": float(ks.loc[w.end_ts - 60:w.end_ts - 1].mean()),
                     "b0": float(bs.loc[w.start_ts - 60:w.start_ts - 1].mean()), "b1": float(bs.loc[w.end_ts - 60:w.end_ts - 1].mean()),
                     "klast0": float(ks.loc[w.start_ts - 1]), "klast1": float(ks.loc[w.end_ts - 1])})
R = pd.DataFrame(rows).dropna()
R["cl_up"] = (R.cl_final >= R.cl_ptb).astype(float)
out = {"windows": int(len(R)), "chainlink_fields_reproduce_payout": float((R.cl_up == R.up).mean())}
for nm, a, b in (("kraken_twap60", "k0", "k1"), ("binance_twap60", "b0", "b1"), ("kraken_last_trade", "klast0", "klast1")):
    pred = (R[b] >= R[a]).astype(float)
    dcl = R.cl_final - R.cl_ptb; dpx = R[b] - R[a]
    out[nm] = {"resolution_agreement": round(float((pred == R.up).mean()), 4),
               "mis_resolved": int((pred != R.up).sum()),
               "corr_window_move_vs_chainlink": round(float(np.corrcoef(dcl, dpx)[0, 1]), 4),
               "rmse_window_move_usd": round(float(np.sqrt(np.mean((dcl - dpx) ** 2))), 2)}
    for per in ("fit", "test"):
        m = R.per == per
        out[nm][f"agreement_{per}"] = round(float((pred[m] == R.up[m]).mean()), 4)
print(json.dumps(out, indent=1))
json.dump(out, open(f"{OUT}/resolution_proxy.json", "w"), indent=1)

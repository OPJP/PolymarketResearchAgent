"""Iteration 8, X30 step 3 (panel-assumptions iter6 P3; with the exact strike from X45): REVEALED-PREFERENCE fair value.
For every VALIDATE cluster taker order (first fill: price p_o, block second s) and every other trader's taker BUY print
(data-api tapes; cluster and cluster-maker txs removed), FV_k,L(o) = digital value of o with the exact strike K
(priceToBeat), index I = Binance spot close at s - 2 - L x exp(basis at the open), vol k x 5-min realized, TWAP variance
(tau - 40 before the last minute). A bot that buys only when FV_bot(o) > p_o + margin reveals (k, L) where the share of
its buys with FV - p > 0 is highest RELATIVE to other takers'. Also: does the best (k, L) reproduce the underdog tilt
(share of underdog buys that are 'value' vs favourite buys)? Writes results/revpref8.json. Usage: python revpref8.py TAPE_DIR"""
import os, sys, json, glob
import numpy as np, pandas as pd
from scipy.stats import norm
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
VAL0, H = 1792108800, 1792713600
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9",
      "0xd84403ef"}  # W4 prefix handled below


def main(tape_dir):
    f = pd.read_parquet(os.path.join(C, "fills.parquet"), columns=["ts", "wallet", "role", "oh", "price", "start_ts", "is_up", "cid", "tx"])
    f = f[(f.start_ts >= VAL0)]
    tk = f[f.role == "T"].sort_values("ts", kind="stable").groupby(["wallet", "oh"]).agg(ts=("ts", "first"), p=("price", "first"), up=("is_up", "first"),
                                                                                        st=("start_ts", "first"), cid=("cid", "first")).reset_index()
    ptb = pd.read_parquet(os.path.join(C, "ptb.parquet")).set_index("start").priceToBeat
    bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
    px = pd.Series(bn.close.values.astype(float), index=bn.sec.values.astype(np.int64)).sort_index()
    px = px[~px.index.duplicated()]
    full = px.reindex(np.arange(px.index.min(), px.index.max() + 1)).ffill()
    t0 = int(full.index[0]); P = full.values; R = np.r_[0.0, np.diff(np.log(P))]
    cR = np.cumsum(R); cR2 = np.cumsum(R ** 2); cP = np.cumsum(P)
    at = lambda arr, t: arr[np.asarray(t, np.int64) - t0]
    # other takers' BUY prints (seeded sample of windows to keep memory small)
    rng = np.random.default_rng(8)
    files = sorted(glob.glob(os.path.join(tape_dir, "*.parquet")))
    files = [files[i] for i in rng.choice(len(files), min(600, len(files)), replace=False)]
    makers_tx = set(f[f.role == "M"].tx)
    st_by_cid = f.groupby("cid").start_ts.first()
    oth = []
    for fp in files:
        d = pd.read_parquet(fp)
        if not len(d) or "side" not in d:
            continue
        cid = os.path.basename(fp)[:-8]
        if cid not in st_by_cid.index:
            continue
        d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(CL) & ~d.proxyWallet.str.lower().str.startswith("0xd84403ef") & ~d.transactionHash.isin(makers_tx)]
        st0 = int(st_by_cid[cid])
        d = d[(d.timestamp >= st0 + 2) & (d.timestamp < st0 + 298)]
        oth.append(pd.DataFrame({"ts": d.timestamp.to_numpy(np.int64), "p": d.price.to_numpy(float), "up": (d.outcome == "Up").to_numpy(), "st": st0}))
    oth = pd.concat(oth, ignore_index=True) if oth else pd.DataFrame(columns=["ts", "p", "up", "st"])
    out = {"cluster_orders": int(len(tk)), "other_prints": int(len(oth))}

    def fv(df, k, L):
        st = df.st.to_numpy(np.int64); s = df.ts.to_numpy(np.int64)
        K = st_ptb = ptb.reindex(st).to_numpy(float)
        om = (at(cP, st - 1) - at(cP, st - 61)) / 60.0
        I = at(P, s - 2 - L) * np.exp(np.log(K) - np.log(om))
        n = 300
        v1 = (at(cR2, s - 2) - at(cR2, s - 2 - n)) / n - ((at(cR, s - 2) - at(cR, s - 2 - n)) / n) ** 2
        sd = k * np.sqrt(np.maximum(v1, 1e-12))
        tau = (st + 300 - (s - 2 - L)).astype(float)
        var = np.where(tau > 60, sd ** 2 * (tau - 40), sd ** 2 * np.maximum(tau, 1) / 3)
        fu = norm.cdf(np.log(I / K) / np.maximum(np.sqrt(var), 1e-9))
        return np.where(df.up.to_numpy(bool), fu, 1 - fu)

    grid = []
    for k in (0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0):
        for L in (0, 2, 5, 10, 20):
            a = fv(tk, k, L) - tk.p.to_numpy(float); b = fv(oth, k, L) - oth.p.to_numpy(float)
            und = tk.p.to_numpy(float) < 0.5
            grid.append({"k": k, "L": L, "cluster_value_share": round(float(np.nanmean(a > 0)), 4), "others_value_share": round(float(np.nanmean(b > 0)), 4),
                         "excess": round(float(np.nanmean(a > 0) - np.nanmean(b > 0)), 4), "cluster_mean_gap_c": round(float(np.nanmean(a) * 100), 3),
                         "cluster_value_share_underdog": round(float(np.nanmean(a[und] > 0)), 4), "cluster_value_share_favourite": round(float(np.nanmean(a[~und] > 0)), 4)})
    grid.sort(key=lambda r: -r["excess"])
    out["grid_top"] = grid[:8]; out["grid_all"] = grid
    for r in grid[:8]:
        print(json.dumps(r))
    json.dump(out, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "revpref8.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])

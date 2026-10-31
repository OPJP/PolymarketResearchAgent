"""Iteration 7 (catalog X30 = panel-assumptions iter6 P3, steps 1-2): the UNDERDOG-TILT surface, a model-free signature of
a bot fair value that differs from the market's. VALIDATE (windows starting 10-16..10-23), development only.
Cluster taker orders (first fill as taker; price = VWAP of the order) vs OTHER traders' taker BUY prints (full taper tapes,
cluster wallets and cluster-maker transactions removed). Underdog = bought outcome priced < 0.5 (|p - 0.5| >= 0.02).
Bins: rel (60-s), |p - 0.5| (0.1 steps), size (cluster: >= 90 filled shares = big). Conditioning: the Up price change
over the previous 30 s from other traders' prints (|dp| < 0.02 = static, else moved).
Usage: python tilt7.py TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/tilt7.json"
VAL = (1792108800, 1792713600)
CL = ["0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"]


def main(tape_dir):
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "li", "ts", "tx", "oh", "wallet", "role", "shares", "price", "cid", "start_ts", "is_up"])
    f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])].sort_values(["block", "li"])
    f["usd"] = f.shares * f.price
    o = f.groupby(["wallet", "oh"], sort=False).agg(cid=("cid", "first"), is_up=("is_up", "first"), ts=("ts", "first"), role0=("role", "first"),
                                                    shares=("shares", "sum"), usd=("usd", "sum"), start=("start_ts", "first")).reset_index()
    o = o[o.role0 == "T"]
    o["p"] = o.usd / o.shares; o["rel"] = o.ts - o.start; o["big"] = o.shares >= 90
    makers_by_cid = f[f.role == "M"].groupby("cid").tx.agg(lambda s: set(s))
    oth = []; dpo = np.full(len(o), np.nan)
    o = o.reset_index(drop=True)
    for cid, gi in o.groupby("cid").groups.items():
        p = f"{tape_dir}/{cid}.parquet"
        if not os.path.exists(p):
            continue
        d = pd.read_parquet(p)
        if not len(d):
            continue
        st0 = int(o.start.iloc[gi[0]])
        d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(CL) & ~d.transactionHash.isin(list(makers_by_cid.get(cid, set())))].sort_values("timestamp")
        if not len(d):
            continue
        pu = np.where(d.outcome == "Up", d.price, 1 - d.price); tt = d.timestamp.to_numpy(np.int64)

        def up_at(t):
            i = np.searchsorted(tt, t, "right") - 1
            return np.where(i >= 0, pu[np.clip(i, 0, len(pu) - 1)], np.nan)
        rel = tt - st0
        dd = d.assign(rel=rel, p=d.price.to_numpy(), dp=up_at(tt - 1) - up_at(tt - 31))
        dd = dd[(dd.rel >= 0) & (dd.rel < 300)]
        oth.append(dd[["rel", "p", "size", "dp"]])
        ts = o.ts.to_numpy()[gi]
        dpo[gi] = up_at(ts - 1) - up_at(ts - 31)
    o["dp"] = dpo
    oth = pd.concat(oth)
    res = {"cluster_taker_orders": int(len(o)), "other_buy_prints": int(len(oth))}

    def surf(df, wcol=None):
        df = df[(df.p - 0.5).abs() >= 0.02].copy()
        df["und"] = df.p < 0.5
        df["rb"] = (df.rel // 60).clip(0, 4).astype(int) * 60
        df["db"] = pd.cut((df.p - 0.5).abs(), [0, 0.1, 0.2, 0.3, 0.4, 0.5], include_lowest=True)
        out = {}
        for (rb, db), g in df.groupby(["rb", "db"], observed=True):
            if len(g) < 30:
                continue
            w = g[wcol] if wcol else None
            out[f"{rb}-{rb + 60}|{db}"] = [round(float(np.average(g.und, weights=w) if w is not None else g.und.mean()), 3), int(len(g))]
        return out
    res["cluster_small"] = surf(o[~o.big])
    res["cluster_big"] = surf(o[o.big])
    res["others_count"] = surf(oth)
    res["others_size_weighted"] = surf(oth, "size")
    st = o[o.dp.abs() < 0.02]; mvd = o[o.dp.abs() >= 0.02]
    res["cluster_small_static30s"] = surf(st[~st.big]); res["cluster_small_moved30s"] = surf(mvd[~mvd.big])
    so = oth[oth.dp.abs() < 0.02]
    res["others_count_static30s"] = surf(so)
    # pooled summary at |p - 0.5| in [0.3, 0.4]
    def share(df, lo, hi):
        x = df[((df.p - 0.5).abs() >= lo) & ((df.p - 0.5).abs() < hi)]
        return [round(float((x.p < 0.5).mean()), 3), int(len(x))] if len(x) else None
    res["summary_dist_0.3_0.4"] = {"cluster_small": share(o[~o.big], 0.3, 0.4), "cluster_big": share(o[o.big], 0.3, 0.4), "cluster_small_static": share(st[~st.big], 0.3, 0.4),
                                   "cluster_small_moved": share(mvd[~mvd.big], 0.3, 0.4), "others": share(oth, 0.3, 0.4), "others_static": share(so, 0.3, 0.4)}
    res["summary_dist_0.02_0.1"] = {"cluster_small": share(o[~o.big], 0.02, 0.1), "others": share(oth, 0.02, 0.1)}
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("cluster_taker_orders", "other_buy_prints", "summary_dist_0.3_0.4", "summary_dist_0.02_0.1")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

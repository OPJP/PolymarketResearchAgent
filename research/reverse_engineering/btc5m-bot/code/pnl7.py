"""Iteration 7 (catalog X28 = panel-assumptions iter6 P1, strong form of X17): the PnL target as an ORDER-OVERLAP problem.
VALIDATE only (windows starting 2026-10-16..10-23), development data, nothing sealed.

1. Per-window PnL per wallet and pooled; split-half reliability (random halves of a wallet's own orders by order-hash
   parity); net-position share of the PnL variance.
2. Big orders (>= 90 filled shares, proxy of the 100-share size): their share of orders and of PnL variance, their
   correlation with the total and across siblings.
3. Oracle-decision replays (the wallet's OWN orders, window/outcome/price as executed):
   a. every order at a fixed 30 shares (the frozen replica's size);
   b. every order at its size class (small -> 30, big -> 100);
   c. (with tapes) the strict-fill model of final_rule._strict_backtest fed with the wallet's own taker decisions:
      fills only against OTHER traders' taker BUY prints on o at <= limit in [s + lo, s + hi] (several latency windows),
      size = its filled shares (oracle size) or 30.
Usage: python pnl7.py [TAPE_DIR]"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/pnl7.json"
VAL = (1792108800, 1792713600)
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
FEE = 0.07


def corr(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return None, None
    return round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)


def main(tape_dir=None):
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts", "tx", "li", "oh", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "rel", "is_up", "up_payout"])
    f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])].copy()
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= VAL[0]) & (win.end_ts <= VAL[1])]
    cids = win.cid.to_numpy()
    f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
    f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
    f["net"] = np.where(f.is_up, f.shares, -f.shares)
    f = f.sort_values(["block", "li"])
    res = {"n_fills": int(len(f)), "n_windows": int(len(cids))}
    # orders
    o = f.groupby(["wallet", "oh"], sort=False).agg(cid=("cid", "first"), is_up=("is_up", "first"), pay=("pay", "first"), ts0=("ts", "min"), rel0=("rel", "min"),
                                                    role0=("role", "first"), shares=("shares", "sum"), usdc=("price", lambda s: 0.0), fee=("fee_usd", "sum"),
                                                    pnl=("pnl", "sum"), pmax=("price", "max"), nf=("price", "size")).reset_index()
    o["usdc"] = f.assign(u=f.shares * f.price).groupby(["wallet", "oh"], sort=False).u.sum().to_numpy()
    o["vwap"] = o.usdc / o.shares
    o["big"] = o.shares >= 90
    o["half"] = o.oh.str[-1].apply(lambda c: int(c, 16) % 2)
    res["orders"] = int(len(o))
    res["big_share_of_orders"] = {w: round(float(g.big.mean()), 4) for w, g in o.groupby("wallet")}

    def per_window(df, val="pnl"):
        return df.groupby("cid")[val].sum().reindex(cids).fillna(0.0)

    out = {}
    for w in ["DS", "GF", "XM", "pool"]:
        ow = o if w == "pool" else o[o.wallet == w]
        fw = f if w == "pool" else f[f.wallet == w]
        tot = per_window(fw)
        r = {"orders": int(len(ow)), "pnl_sum": round(float(tot.sum()), 1), "pnl_sd_window": round(float(tot.std()), 2)}
        net = per_window(fw, "net")
        out_pay = win.set_index("cid").up_payout.reindex(cids).to_numpy()
        r["corr_pnl_vs_net_x_outcome"] = corr(tot, net.to_numpy() * (2 * out_pay - 1))
        r["split_half"] = corr(per_window(ow[ow.half == 0]), per_window(ow[ow.half == 1]))
        r["big_vs_total"] = corr(per_window(ow[ow.big]), tot)
        r["small_vs_total"] = corr(per_window(ow[~ow.big]), tot)
        r["big_share_var"] = round(float(per_window(ow[ow.big]).var() / tot.var()), 4)
        # oracle replays
        fee_ps = ow.fee / ow.shares
        r["oracle_30_shares"] = corr(per_window(ow.assign(p=30 * (ow.pay - ow.vwap) - 30 * fee_ps), "p"), tot)
        r["oracle_size_class_30_100"] = corr(per_window(ow.assign(p=np.where(ow.big, 100, 30) * (ow.pay - ow.vwap - fee_ps)), "p"), tot)
        r["oracle_taker_orders_only_true_size"] = corr(per_window(ow[ow.role0 == "T"]), tot)
        out[w] = r
    # cross-sibling big-order correlations
    pw = {w: per_window(o[(o.wallet == w) & o.big]) for w in ["DS", "GF", "XM"]}
    pt = {w: per_window(o[o.wallet == w]) for w in ["DS", "GF", "XM"]}
    out["siblings"] = {f"{a}-{b}": {"big": corr(pw[a], pw[b]), "total": corr(pt[a], pt[b])} for a, b in [("DS", "GF"), ("DS", "XM"), ("GF", "XM")]}
    res["by_wallet"] = out
    # VALIDATE halves (pre-registered: first / second half of the windows by start time)
    mid = np.median(win.start_ts)
    res["halves"] = {}
    for hname, sel in [("h1", win.start_ts < mid), ("h2", win.start_ts >= mid)]:
        cc = win.cid[sel].to_numpy()
        hh = {}
        for w in ["DS", "GF", "XM", "pool"]:
            ow = o if w == "pool" else o[o.wallet == w]
            fw = f if w == "pool" else f[f.wallet == w]
            tot = fw.groupby("cid").pnl.sum().reindex(cc).fillna(0)
            a = ow[ow.half == 0].groupby("cid").pnl.sum().reindex(cc).fillna(0); b = ow[ow.half == 1].groupby("cid").pnl.sum().reindex(cc).fillna(0)
            fee_ps = ow.fee / ow.shares
            p30 = ow.assign(p=30 * (ow.pay - ow.vwap - fee_ps)).groupby("cid").p.sum().reindex(cc).fillna(0)
            hh[w] = {"split_half": corr(a, b), "oracle_30": corr(p30, tot)}
        res["halves"][hname] = hh
    if tape_dir:
        res["strict_fill_oracle"] = strict_oracle(o, f, win, tape_dir)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1)[:6000])


def strict_oracle(o, f, win, tape_dir):
    """The wallet's own TAKER orders through the frozen strict-fill model (other traders' taker BUY prints on o at <= limit)."""
    cl_maker_tx = set(f.loc[f.role == "M", "tx"])
    wi = win.set_index("cid")
    tk = o[o.role0 == "T"].copy()
    tk["s0"] = (tk.ts0 - wi.start_ts.reindex(tk.cid).to_numpy()).astype(int)
    windows = {"[s+1,s+3]": (1, 3), "[s,s+2]": (0, 2), "[s-1,s+1]": (-1, 1), "[s+1,s+10]": (1, 10)}
    rows = {k: [] for k in windows}
    rows30 = {k: [] for k in windows}
    for cid, g in tk.groupby("cid", sort=False):
        p = f"{tape_dir}/{cid}.parquet"
        if not os.path.exists(p):
            continue
        d = pd.read_parquet(p)
        if not len(d) or "side" not in d:
            continue
        d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(CL) & ~d.transactionHash.isin(cl_maker_tx)]
        st0 = int(wi.at[cid, "start_ts"])
        d = d.assign(rel=d.timestamp - st0, up=(d.outcome == "Up"))
        for oc in (True, False):
            dd = d[d.up == oc].sort_values("rel", kind="stable")
            R = dd.rel.to_numpy(np.int64); P = dd.price.to_numpy(float); Z = dd["size"].to_numpy(float)
            gg = g[g.is_up == oc]
            for r in gg.itertuples():
                for k, (lo, hi) in windows.items():
                    for tgt, store in ((r.shares, rows), (30.0, rows30)):
                        left = tgt; pn = 0.0; sh_tot = 0.0
                        for j in range(np.searchsorted(R, r.s0 + lo, "left"), np.searchsorted(R, r.s0 + hi, "right")):
                            if P[j] <= r.pmax + 1e-9:
                                sh = min(left, Z[j]); left -= sh; sh_tot += sh
                                pn += sh * (r.pay - P[j]) - FEE * P[j] * (1 - P[j]) * sh
                                if left <= 0:
                                    break
                        store[k].append((r.wallet, cid, pn, sh_tot, tgt))
    cids = win.cid.to_numpy()
    fw = f
    out = {}
    for k in windows:
        for nm, store in (("true_size", rows), ("30", rows30)):
            T = pd.DataFrame(store[k], columns=["wallet", "cid", "pnl", "sh", "tgt"])
            res = {"fill_share": round(float(T.sh.sum() / T.tgt.sum()), 4)}
            for w in ["DS", "GF", "XM", "pool"]:
                tw = T if w == "pool" else T[T.wallet == w]
                ww = fw if w == "pool" else fw[fw.wallet == w]
                a = tw.groupby("cid").pnl.sum().reindex(cids).fillna(0); b = ww.groupby("cid").pnl.sum().reindex(cids).fillna(0)
                res[w] = corr(a, b)
            out[f"{k}_{nm}"] = res
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)

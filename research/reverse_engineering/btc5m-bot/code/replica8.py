"""Iteration 8 (X49 step 4 = panel-mechanics iter7 P1; X54 = panel-assumptions iter7 P1 step 5): the executable replica of
replica7 with a SIZE RULE DRIVEN BY THE REPLICA'S OWN SIMULATED BOOK (legitimate state of an executable rule).
Decisions as in replica7 (frozen it4b cell scores, presence p_o >= 0.30 -> BUY at the last implied ask; one open order per
(window, outcome); conventions (a) prints [s+1, s+3], busy 3 s; (b) prints [s, s+2], busy 2 s).
Size rules (all frozen before scoring; the net table is fitted on the BUILD calldata hours only):
  30        fixed 30 shares (replica7)
  pw        100 x p_o (replica7)
  net_tab   30 + 70 x P_BUILD(large | net bin), net = the replica's own filled shares on o minus o' known at s
            (fills of earlier decisions whose fill window has closed)
  net_thr   100 if the replica's net on o >= 0 else 30
  net_tab_x 30 + 70 x P_BUILD(large | net bin) x min(1, 2 p_o)
Usage: python replica8.py TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/replica8.json"
VAL = (1792108800, 1792713600)
CL = ["0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"]
FEE = 0.07
P_THRESH = 0.30
CONV = {"a_latency2s": (1, 3, 3), "b_decoded": (0, 2, 2)}
NET_BINS = [-1e9, -200, -60, -1e-9, 1e-9, 60, 200, 1e9]


def build_table():
    """P(large | operator net bin) on the BUILD calldata hours (pooled wallets); same state definition as size8.py."""
    b = pd.read_parquet(f"{C}/b1_orders_sample.parquet")
    b = b[np.isfinite(b.first_ts) & (b.first_ts < VAL[0])].copy()
    b["hr"] = (b.first_ts // 3600).astype(int)
    mins = b.groupby("hr")["size"].agg(lambda s: s.value_counts().index[s.value_counts().values >= 0.03 * len(s)].min())
    b["large"] = (b["size"] > b.hr.map(mins) + 1e-9).astype(int)
    b["s"] = (b.first_ts - b.start_ts).astype(int)
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["ts", "shares", "start_ts", "is_up"])
    f = f[f.start_ts.isin(set(b.start_ts))]
    f["s"] = (f.ts - f.start_ts).astype(int); f["su"] = f.shares * np.where(f.is_up, 1.0, -1.0)
    grp = {k: g for k, g in f.groupby("start_ts")}
    net = []
    for r in b.itertuples():
        g = grp.get(r.start_ts)
        tot = 0.0 if g is None else g.su.values[g.s.values <= r.s - 1].sum()
        net.append(tot * (1.0 if r.is_up else -1.0))
    b["nb"] = pd.cut(np.array(net), NET_BINS, labels=False)
    t = b.groupby("nb").large.mean().reindex(range(len(NET_BINS) - 1)).fillna(b.large.mean())
    return t.to_numpy(float), b.groupby("nb").large.size().to_dict()


def corr(a, b):
    return round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)


def main(tape_dir):
    tab, tab_n = build_table()
    print("BUILD P(large | net bin)", np.round(tab, 3).tolist(), tab_n, flush=True)
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])]
    f["pnl"] = f.shares * (np.where(f.is_up, f.up_payout, 1 - f.up_payout) - f.price) - f.fee_usd
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= VAL[0]) & (win.end_ts <= VAL[1])].set_index("cid")
    cids = win.index.to_numpy()
    sc = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "pu", "pd", "ask_u", "ask_d"])
    makers_by_cid = f[f.role == "M"].groupby("cid").tx.agg(lambda s: set(s))
    RULES = ["30", "pw", "net_tab", "net_thr", "net_tab_x"]
    acc = {(c, z): [] for c in CONV for z in RULES}
    for cid, g in sc.groupby("cid", sort=False):
        if cid not in win.index:
            continue
        p = f"{tape_dir}/{cid}.parquet"
        if not os.path.exists(p):
            continue
        d = pd.read_parquet(p)
        if not len(d) or "side" not in d:
            continue
        d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(CL) & ~d.transactionHash.isin(list(makers_by_cid.get(cid, set())))]
        st0 = int(win.at[cid, "start_ts"]); pay_up = float(win.at[cid, "up_payout"])
        rel = d.timestamp.to_numpy(np.int64) - st0; upm = (d.outcome == "Up").to_numpy()
        g = g.sort_values("rel")
        tape = {}
        for oc in (True, False):
            sel = upm == oc
            R = rel[sel]; P = d.price.to_numpy(float)[sel]; Z = d["size"].to_numpy(float)[sel]
            oo = np.argsort(R, kind="stable"); tape[oc] = (R[oo], P[oo], Z[oo])
        ss = g.rel.to_numpy(np.int64)
        dec = []
        for oc in (True, False):
            pr = (g.pu if oc else g.pd).to_numpy(float); ask = (g.ask_u if oc else g.ask_d).to_numpy(float)
            ok = (pr >= P_THRESH) & np.isfinite(ask) & (ask > 0.05) & (ask < 0.95)
            for j in np.where(ok)[0]:
                dec.append((int(ss[j]), oc, float(ask[j]), float(pr[j])))
        dec.sort(key=lambda x: (x[0], not x[1]))
        for conv, (lo, hi, busy_s) in CONV.items():
            for zn in RULES:
                busy = {True: -10 ** 9, False: -10 ** 9}
                pend = []  # (known_at, oc, shares)
                net_up = 0.0
                for s0, oc, a, pr in dec:
                    if s0 <= busy[oc]:
                        continue
                    busy[oc] = s0 + busy_s - 1
                    keep = []
                    for kt, o2, sh in pend:
                        if kt < s0:
                            net_up += sh if o2 else -sh
                        else:
                            keep.append((kt, o2, sh))
                    pend = keep
                    net_o = net_up if oc else -net_up
                    nb = int(np.digitize([net_o], NET_BINS[1:-1])[0])
                    if zn == "30":
                        tgt = 30.0
                    elif zn == "pw":
                        tgt = 100.0 * pr
                    elif zn == "net_tab":
                        tgt = 30.0 + 70.0 * tab[nb]
                    elif zn == "net_thr":
                        tgt = 100.0 if net_o >= 0 else 30.0
                    else:
                        tgt = 30.0 + 70.0 * tab[nb] * min(1.0, 2.0 * pr)
                    R, P, Z = tape[oc]
                    i0 = np.searchsorted(R, s0 + lo, "left"); i1 = np.searchsorted(R, s0 + hi, "right")
                    if i1 <= i0:
                        continue
                    pp = P[i0:i1]; zz = Z[i0:i1]; mk = pp <= a + 1e-9
                    pp, zz = pp[mk], zz[mk]
                    if not len(pp):
                        continue
                    cz = np.cumsum(zz)
                    take = np.clip(np.minimum(zz, tgt - (cz - zz)), 0, None)
                    sh = float(take.sum())
                    if sh <= 0:
                        continue
                    pay = pay_up if oc else 1 - pay_up
                    pend.append((s0 + hi, oc, sh))
                    acc[(conv, zn)].append((cid, float(np.sum(take * (pay - pp) - FEE * pp * (1 - pp) * take)), float(np.sum(take * pp)), sh))
    res = {"build_table": np.round(tab, 4).tolist(), "build_table_n": {str(k): int(v) for k, v in tab_n.items()}}
    for (conv, zn), rows in acc.items():
        T = pd.DataFrame(rows, columns=["cid", "pnl", "usd", "sh"])
        a = T.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
        r = {"fills": int(len(T)), "usd": round(float(T.usd.sum()), 1), "return_before_rebate": round(float(T.pnl.sum() / max(T.usd.sum(), 1e-9)), 4)}
        for w in ["DS", "GF", "XM", "pool"]:
            fw = f if w == "pool" else f[f.wallet == w]
            b = fw.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
            r[w] = corr(a, b)
        # halves by window start
        st = win.loc[cids, "start_ts"].to_numpy(); h = st < np.median(st)
        bp = f.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
        r["pool_halves"] = [corr(a[h], bp[h]), corr(a[~h], bp[~h])]
        res[f"{conv}_{zn}"] = r
        print(conv, zn, json.dumps(r), flush=True)
    json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])

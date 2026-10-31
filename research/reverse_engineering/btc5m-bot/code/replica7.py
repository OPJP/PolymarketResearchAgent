"""Iteration 7 (X28 step 4, first version): EXECUTABLE replica under the two pre-registered fill conventions, VALIDATE.
Decisions from the frozen iteration-4b cell scores (val_outcome_it4b.parquet: presence pu / pd per (window, second), last
implied asks at s - 1): at second s, for each outcome o with presence p_o >= P_THRESH (0.30, fixed in iteration 1), send a
BUY limit at ask_o. Size: fixed 30 shares, or presence-weighted (100 x p_o, i.e. expected-size sizing). One open order per
(window, outcome) at a time; busy for B s. Fills only against OTHER traders' taker BUY prints on o at <= limit:
(a) prints in [s+1, s+3] (latency >= 2 s, busy 3 s; the frozen convention), (b) prints in [s, s+2] (decoded latency, busy 2 s).
Per-window realized PnL (taker fee 0.07 p (1-p)) vs the wallet's actual per-window PnL, per wallet and pooled.
Usage: python replica7.py TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/replica7.json"
VAL = (1792108800, 1792713600)
CL = ["0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"]
FEE = 0.07
P_THRESH = 0.30
CONV = {"a_latency2s": (1, 3, 3), "b_decoded": (0, 2, 2)}


def corr(a, b):
    return round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)


def main(tape_dir):
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])]
    f["pnl"] = f.shares * (np.where(f.is_up, f.up_payout, 1 - f.up_payout) - f.price) - f.fee_usd
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= VAL[0]) & (win.end_ts <= VAL[1])].set_index("cid")
    cids = win.index.to_numpy()
    sc = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "pu", "pd", "ask_u", "ask_d"])
    makers_by_cid = f[f.role == "M"].groupby("cid").tx.agg(lambda s: set(s))
    acc = {(c, z): [] for c in CONV for z in ("30", "pw")}
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
        for oc in (True, False):
            sel = upm == oc
            R = rel[sel]; P = d.price.to_numpy(float)[sel]; Z = d["size"].to_numpy(float)[sel]
            oo = np.argsort(R, kind="stable"); R, P, Z = R[oo], P[oo], Z[oo]
            pr = (g.pu if oc else g.pd).to_numpy(float); ask = (g.ask_u if oc else g.ask_d).to_numpy(float); ss = g.rel.to_numpy(np.int64)
            ok = (pr >= P_THRESH) & np.isfinite(ask) & (ask > 0.05) & (ask < 0.95)
            pay = pay_up if oc else 1 - pay_up
            for conv, (lo, hi, busy_s) in CONV.items():
                busy = -10 ** 9
                for j in np.where(ok)[0]:
                    s0 = ss[j]
                    if s0 <= busy:
                        continue
                    busy = s0 + busy_s - 1
                    i0 = np.searchsorted(R, s0 + lo, "left"); i1 = np.searchsorted(R, s0 + hi, "right")
                    if i1 <= i0:
                        continue
                    pp = P[i0:i1]; zz = Z[i0:i1]; mk = pp <= ask[j] + 1e-9
                    pp, zz = pp[mk], zz[mk]
                    if not len(pp):
                        continue
                    cz = np.cumsum(zz)
                    for zn, tgt in (("30", 30.0), ("pw", 100.0 * pr[j])):
                        take = np.clip(np.minimum(zz, tgt - (cz - zz)), 0, None)
                        acc[(conv, zn)].append((cid, float(np.sum(take * (pay - pp) - FEE * pp * (1 - pp) * take)), float(np.sum(take * pp))))
    res = {}
    for (conv, zn), rows in acc.items():
        T = pd.DataFrame(rows, columns=["cid", "pnl", "usd"])
        a = T.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
        r = {"fills": int(len(T)), "usd": round(float(T.usd.sum()), 1), "return_before_rebate": round(float(T.pnl.sum() / max(T.usd.sum(), 1e-9)), 4)}
        for w in ["DS", "GF", "XM", "pool"]:
            fw = f if w == "pool" else f[f.wallet == w]
            b = fw.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
            r[w] = corr(a, b)
        res[f"{conv}_{zn}"] = r
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

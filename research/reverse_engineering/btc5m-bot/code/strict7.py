"""Iteration 7 (X28 step 3): ORACLE-DECISION ceiling of the frozen strict-fill model. The wallet's OWN taker decisions
(window, outcome, block second of the first fill s, limit = its highest fill price, size = its filled shares or 30) are
sent through final_rule._strict_backtest's fill model: fills only against OTHER traders' taker BUY prints on the same
outcome at <= limit with block ts in [s + lo, s + hi], at the print price, for min(print size, remaining). Per-window
PnL of these fills vs the wallet's actual per-window PnL (all its fills, taker and maker). VALIDATE, development only.
Usage: python strict7.py TAPE_DIR"""
import os, sys, json
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = _ROOT + "/research/reverse_engineering/btc5m-bot/results/strict7.json"
VAL = (1792108800, 1792713600)
CL = ["0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"]
FEE = 0.07
WINS = {"[s+1,s+3]": (1, 3), "[s-1,s+1]": (-1, 1), "[s,s+5]": (0, 5)}


def corr(a, b):
    return round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)


def main(tape_dir):
    f = pd.read_parquet(f"{C}/fills.parquet", columns=["block", "ts", "tx", "li", "oh", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    f = f[(f.start_ts >= VAL[0]) & (f.start_ts < VAL[1])].sort_values(["block", "li"])
    f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
    f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= VAL[0]) & (win.end_ts <= VAL[1])]
    cids = win.cid.to_numpy()
    g = f.groupby(["wallet", "oh"], sort=False)
    o = g.agg(cid=("cid", "first"), is_up=("is_up", "first"), pay=("pay", "first"), ts0=("ts", "first"), role0=("role", "first"),
              shares=("shares", "sum"), pmax=("price", "max"), start=("start_ts", "first")).reset_index()
    tk = o[o.role0 == "T"].copy()
    tk["s0"] = (tk.ts0 - tk.start).astype(np.int64)
    makers_by_cid = f[f.role == "M"].groupby("cid").tx.agg(lambda s: set(s))
    acc = {(k, nm): [] for k in WINS for nm in ("true", "30")}
    import time as _t; _t0 = _t.time()
    for _i, (cid, gg) in enumerate(tk.groupby("cid", sort=False)):
        if _i % 200 == 0:
            print("progress", _i, round(_t.time() - _t0, 1), flush=True)
        p = f"{tape_dir}/{cid}.parquet"
        if not os.path.exists(p):
            continue
        d = pd.read_parquet(p)
        if not len(d) or "side" not in d:
            continue
        d = d[(d.side == "BUY") & ~d.proxyWallet.str.lower().isin(CL) & ~d.transactionHash.isin(list(makers_by_cid.get(cid, set())))]
        st0 = int(gg.start.iloc[0])
        rel = (d.timestamp.to_numpy(np.int64) - st0); upm = (d.outcome == "Up").to_numpy()
        for oc in (True, False):
            sel = upm == oc
            R = rel[sel]; P = d.price.to_numpy(float)[sel]; Z = d["size"].to_numpy(float)[sel]
            oo = np.argsort(R, kind="stable"); R, P, Z = R[oo], P[oo], Z[oo]
            q = gg[gg.is_up == oc]
            if not len(q):
                continue
            s0 = q.s0.to_numpy(np.int64); pm = q.pmax.to_numpy(float); sh = q.shares.to_numpy(float); pay = q.pay.to_numpy(float); wal = q.wallet.to_numpy()
            for k, (lo, hi) in WINS.items():
                i0 = np.searchsorted(R, s0 + lo, "left"); i1 = np.searchsorted(R, s0 + hi, "right")
                for j in range(len(q)):
                    if i1[j] <= i0[j]:
                        acc[(k, "true")].append((wal[j], cid, 0.0, 0.0, sh[j])); acc[(k, "30")].append((wal[j], cid, 0.0, 0.0, 30.0))
                        continue
                    pp = P[i0[j]:i1[j]]; zz = Z[i0[j]:i1[j]]
                    mk = pp <= pm[j] + 1e-9
                    pp, zz = pp[mk], zz[mk]
                    cz = np.cumsum(zz)
                    for nm, tgt in (("true", sh[j]), ("30", 30.0)):
                        take = np.clip(np.minimum(zz, tgt - (cz - zz)), 0, None)
                        pn = float(np.sum(take * (pay[j] - pp) - FEE * pp * (1 - pp) * take))
                        acc[(k, nm)].append((wal[j], cid, pn, float(take.sum()), tgt))
    res = {"taker_orders": int(len(tk))}
    for (k, nm), rows in acc.items():
        T = pd.DataFrame(rows, columns=["wallet", "cid", "pnl", "sh", "tgt"])
        r = {"fill_share": round(float(T.sh.sum() / T.tgt.sum()), 4)}
        for w in ["DS", "GF", "XM", "pool"]:
            tw = T if w == "pool" else T[T.wallet == w]
            fw = f if w == "pool" else f[f.wallet == w]
            a = tw.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy(); b = fw.groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
            r[w] = corr(a, b)
        res[f"{k}_{nm}"] = r
    # upper reference: the same decisions filled in full at their own prices (no fill model), taker orders only
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

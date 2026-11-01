"""Iteration 11: ceiling of the strict-fill window replay. Same engine as code11/replay.py (L = 2, slack 2, trade-through,
full flow, delta 0 and 0.01, Q 500 and session size) but the side is an ORACLE: the cluster's terminal net side of the
window (maker BUY shares Up > Down), quoted for the whole window. If even this replay's per-window PnL correlates < 0.5
with the cluster's, no side rule can pass the outcome bar under strict fills. Aggregates only.
    python code11/replay_oracle.py
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as RP  # noqa: E402
C = RP.C
SPLIT_V = 1793059200


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return [round(float(np.corrcoef(a, b)[0, 1]), 3), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 3)]


def main():
    base, px = RP.load_spot()
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    W = W[(W.start_ts >= RP.LOT[0]) & (W.start_ts < RP.LOT[1])].set_index("cid")
    CW = pd.read_parquet(C / "it11" / "cluster_windows.parquet")
    mk = CW[CW.role == "maker"].groupby("cid").agg(pnl=("pnl", "sum"), up=("up", "sum"), dn=("dn", "sum"))
    onet = (mk.up > mk.dn).to_dict()
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh"])
    cl_tx = set(F.txh.str.lower())
    for n in ("bosona", "almach", "momoney"):
        cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
    out = []
    for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
        T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        T["in_cl"] = T.tx.str.lower().isin(cl_tx)
        T["own"] = T.wallet.str.lower().isin(set(RP.CLUSTER))
        T["price"] = RP.snap(T.price.to_numpy())
        for cid, g in T.groupby("cid"):
            if cid not in W.index or cid not in onet:
                continue
            ww = W.loc[cid]
            st, en, up_tok, pay_up = int(ww.start_ts), int(ww.end_ts), str(ww.up_token), float(ww.up_payout)
            g = g.sort_values("ts", kind="stable")
            ts = g.ts.to_numpy().astype(np.int64)
            is_up = g.asset.astype(str).to_numpy() == up_tok
            sell = g.side.to_numpy() == "SELL"
            pr, sz = g.price.to_numpy(), g["size"].to_numpy().astype(float)
            clean = ~g.in_cl.to_numpy()
            pu = np.where(is_up, pr, 1 - pr)
            d = np.arange(st + 1, en - RP.STOP)
            k = np.searchsorted(ts[clean], d, side="right") - 1
            mid_up = np.where(k >= 0, pu[clean][np.clip(k, 0, None)], np.nan)
            side_up = bool(onet[cid])
            kk = ts - 2 - 2 - 1 - (st + 1)
            fm = (kk >= 0) & (kk < len(d)) & ~g.own.to_numpy()
            for delta in (0.0, 0.01):
                q = RP.quote_price((mid_up if side_up else 1 - mid_up) - delta)
                qk = q[kk[fm]]
                iu, se, p_, s_ = is_up[fm], sell[fm], pr[fm], sz[fm]
                thr = ((iu == side_up) & se & (p_ < qk - 1e-9)) | ((iu != side_up) & ~se & (p_ > 1 - qk + 1e-9))
                vol = np.bincount(kk[fm][thr], weights=s_[thr], minlength=len(d))
                pay = pay_up if side_up else 1 - pay_up
                for qn, Q in (("q500", 500.0), ("qsess", 500.0 if RP.session(st) else 62.0)):
                    f_ = np.where(np.isfinite(q), np.minimum(Q, vol), 0.0)
                    out.append((cid, st, delta, qn, float((f_ * (pay - np.nan_to_num(q))).sum())))
    R = pd.DataFrame(out, columns=["cid", "st", "delta", "q", "pnl"])
    res = {}
    for (delta, qn), g in R.groupby(["delta", "q"]):
        g = g.set_index("cid").join(mk[["pnl"]].rename(columns={"pnl": "cl"}))
        rec = {}
        for sp, m in (("study", g.st < SPLIT_V), ("validate", g.st >= SPLIT_V)):
            rec[sp] = corr(g.pnl[m], g.cl[m])
        res[f"d{delta}_{qn}"] = rec
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / "iter11_replay_oracle.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

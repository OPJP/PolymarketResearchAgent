"""X137 (panel iter12 mechanics P3): the full-machine strict replay of code12/replay_machine.py with the pairing leg priced
at the tracer-measured depth instead of "at the market". Same engine (lot BTC 5m windows, cluster transactions removed
from the information set and the cluster's own taker orders from the flow, trade-through fills, slack 2, L = 2 s).
Pairing bid of |U - D| on the under-held outcome at (last clean print - 0.01 - depth); depth in {0 (iteration 12), 0.05,
0.11 (tracer median depth, X135)}; the main rung keeps its price; a print that trades through both the main rung and the
deeper pairing bid of the same outcome fills the main rung first. Main rules: posture, held. Scored against the cluster's
window PnL (maker fills) per half: Pearson / Spearman, total PnL and locked PnL (STUDY 10-23..26 case by case allowed,
VALIDATE 10-27..30 aggregate only).
    python code13/replay_pair_depth.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code11"))
sys.path.insert(0, str(HERE.parent / "code12"))
import replay as RP  # noqa: E402
from replay_machine_score import cluster_windows, corr  # noqa: E402

C = RP.C
DEPTHS = (None, 0.0, 0.05, 0.11)
MAINS = ("posture", "held")
L = 2
DELTA = 0.01
EPS = 1e-9


def run(nd, vol_up, vol_dn, pv_up, pv_dn, main_up_sig, Q, depth, lag, qu, qd, pqu, pqd, main):
    f_up, f_dn, p_up, p_dn = (np.zeros(nd) for _ in range(4))
    U = D = 0.0
    first = None
    for d in range(nd):
        j = d - lag
        if j >= 0:
            U += f_up[j] + p_up[j]
            D += f_dn[j] + p_dn[j]
            if first is None and (f_up[j] + p_up[j] + f_dn[j] + p_dn[j]) > 0:
                first = j
        if main == "posture" or first is None:
            m = main_up_sig[d]
        else:
            m = 1 if U > D else (0 if D > U else main_up_sig[d])
        bu = Q if (m == 1 and qu[d]) else 0.0
        bd = Q if (m == 0 and qd[d]) else 0.0
        if bu > 0 and vol_up[d] > 0:
            f_up[d] = min(bu, vol_up[d])
        if bd > 0 and vol_dn[d] > 0:
            f_dn[d] = min(bd, vol_dn[d])
        if depth is not None:
            if U > D and pqd[d]:
                p_dn[d] = min(U - D, max(pv_dn[d] - f_dn[d], 0.0))
            elif D > U and pqu[d]:
                p_up[d] = min(D - U, max(pv_up[d] - f_up[d], 0.0))
    return f_up, f_dn, p_up, p_dn


def main():
    t0 = time.time()
    base, px = RP.load_spot()
    v3 = RP.rv(px, 300)
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    W = W[(W.start_ts >= RP.LOT[0]) & (W.start_ts < RP.LOT[1])].set_index("cid")
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
            if cid not in W.index:
                continue
            ww = W.loc[cid]
            st, en, up_tok, pay_up = int(ww.start_ts), int(ww.end_ts), str(ww.up_token), ww.up_payout
            if pay_up is None or not np.isfinite(pay_up):
                continue
            pay_up = float(pay_up)
            g = g.sort_values("ts", kind="stable")
            ts = g.ts.to_numpy().astype(np.int64)
            is_up = g.asset.astype(str).to_numpy() == up_tok
            sell = g.side.to_numpy() == "SELL"
            buy = ~sell
            pr, sz = g.price.to_numpy(), g["size"].to_numpy().astype(float)
            clean = ~g.in_cl.to_numpy()
            own = g.own.to_numpy()
            pu = np.where(is_up, pr, 1 - pr)
            d = np.arange(st + 1, en - RP.STOP)
            nd = len(d)
            k = np.searchsorted(ts[clean], d, side="right") - 1
            mid_up = np.where(k >= 0, pu[clean][np.clip(k, 0, None)], np.nan)
            i0 = st - 60 - base
            if i0 < 400 or en - base >= len(px):
                continue
            K = float(px[i0:st - base].mean())
            si = d - 2 - base
            S = px[si]
            sig = 1.4 * v3[si] * np.sqrt(np.maximum(en - d, 1))
            with np.errstate(divide="ignore", invalid="ignore"):
                fair_up = ndtr(np.log(S / K) / np.where(sig > 0, sig, np.nan))
            ok = np.isfinite(mid_up) & np.isfinite(fair_up)
            main_up_sig = np.where(~ok, -1, np.where(fair_up > mid_up, 1, np.where(fair_up < mid_up, 0, -1))).astype(int)
            Q = 500.0 if bool(RP.session(st)) else 62.0
            q_up = RP.quote_price(mid_up - DELTA)
            q_dn = RP.quote_price((1 - mid_up) - DELTA)
            kk = ts - RP.SLACK - L - 1 - (st + 1)
            fm = (kk >= 0) & (kk < nd) & ~own
            kf, iuf, sef, buf, prf, szf = kk[fm], is_up[fm], sell[fm], buy[fm], pr[fm], sz[fm]

            def through(qa, qb):
                a, b = qa[kf], qb[kf]
                tu = (iuf & sef & (prf < a - EPS)) | (~iuf & buf & (prf > 1 - a + EPS))
                td = (~iuf & sef & (prf < b - EPS)) | (iuf & buf & (prf > 1 - b + EPS))
                return (np.bincount(kf[tu], weights=szf[tu], minlength=nd), np.bincount(kf[td], weights=szf[td], minlength=nd))
            vol_up, vol_dn = through(q_up, q_dn)
            vq_up = np.isfinite(q_up) & (q_up >= 0.001) & (q_up <= 0.999)
            vq_dn = np.isfinite(q_dn) & (q_dn >= 0.001) & (q_dn <= 0.999)
            for depth in DEPTHS:
                if depth is None:
                    p_qu, p_qd, pv_up, pv_dn = q_up, q_dn, vol_up, vol_dn
                else:
                    p_qu = RP.quote_price(mid_up - DELTA - depth)
                    p_qd = RP.quote_price((1 - mid_up) - DELTA - depth)
                    pv_up, pv_dn = through(p_qu, p_qd)
                pq_up = np.isfinite(p_qu) & (p_qu >= 0.001) & (p_qu <= 0.999)
                pq_dn = np.isfinite(p_qd) & (p_qd >= 0.001) & (p_qd <= 0.999)
                for mr in MAINS:
                    f_up, f_dn, p_up, p_dn = run(nd, vol_up, vol_dn, pv_up, pv_dn, main_up_sig, Q, depth, L + 1, vq_up, vq_dn, pq_up, pq_dn, mr)
                    U, D = f_up.sum() + p_up.sum(), f_dn.sum() + p_dn.sum()
                    cu = float((f_up * np.nan_to_num(q_up)).sum() + (p_up * np.nan_to_num(p_qu)).sum())
                    cd = float((f_dn * np.nan_to_num(q_dn)).sum() + (p_dn * np.nan_to_num(p_qd)).sum())
                    pnl = U * pay_up + D * (1 - pay_up) - cu - cd
                    P = min(U, D)
                    locked = P * (1 - (cu / U if U > 0 else 0) - (cd / D if D > 0 else 0)) if P > 0 else 0.0
                    out.append((cid, st, mr, -1.0 if depth is None else depth, float(pnl), float(U), float(D), float(locked)))
        print(pd.to_datetime(day, unit="s").date(), len(out), round(time.time() - t0, 1), flush=True)
        del T
    R = pd.DataFrame(out, columns=["cid", "st", "main", "depth", "pnl", "U", "D", "locked"])
    R.to_parquet(C / "it13" / "replay_pair_depth.parquet")
    pooled, _ = cluster_windows()
    res = {}
    for (mr, dp), g in R.groupby(["main", "depth"]):
        g = g.set_index("cid")
        j = g.join(pooled, rsuffix="_cl", how="inner")
        key = f"{mr}_{'nopair' if dp < 0 else 'depth_' + str(dp)}"
        r = {}
        for half, m in (("study", j.st < 1793059200), ("validate", j.st >= 1793059200)):
            x = j[m]
            r[half] = {"windows": int(len(x)), "corr_pnl": corr(x.pnl, x.pnl_cl), "replay_pnl": round(float(x.pnl.sum()), 1), "replay_locked": round(float(x.locked.sum()), 1),
                       "cluster_pnl": round(float(x.pnl_cl.sum()), 1), "cluster_locked": round(float(x.locked_cl.sum()), 1)}
        res[key] = r
    (HERE.parent / "results/iter13_replay_pair_depth.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

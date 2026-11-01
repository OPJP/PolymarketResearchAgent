"""Iteration 12, X126 (panel iter11 assumptions P1): replay the whole decoded window state machine, exit included.

Same strict-fill engine as code11/replay.py (data-api taker tape of every lot BTC 5m window, prints in cluster
transactions removed from the information set, the cluster's own taker orders removed from the flow, trade-through
fills only, a print stamped T counts at T - 2 (slack 2), the quote decided at d is live in (d + L, d + L + 1]).
New: the replay carries its own inventory (Up shares U, Down shares D, known with a lag of L + 1 s) and adds
  * the main rung: Q = session size (500 in the weekday 12-21 UTC session, else 62) per second at last clean print - 0.01
    on the main side; main rules: posture (Chainlink-stand-in digital, 1.4 x v300, vs the last clean print, every
    second), held (posture until the replay's first fill, then the outcome it holds more of), oracle_net (the
    cluster's terminal net side, all window; a ceiling, not a rule);
  * the pairing leg (pair = 1): while U != D, a bid of |U - D| on the under-held outcome at its last clean print - 0.01
    (X92: the cluster's pairing bids are sized to the imbalance and priced at the market);
  * the merge ~65 s before the end is cash-neutral for PnL (a pair pays 1 either way) and is not simulated.
Per window: PnL, U, D, costs, locked = min(U, D) x (1 - avg Up cost - avg Down cost), residual = PnL - locked.
Writes .cache/re/directional-maker/it12/machine_windows.parquet. Scoring: code12/replay_machine_score.py.
    python code12/replay_machine.py
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code11"))
import replay as RP  # noqa: E402

C = RP.C
OUT = C / "it12"
MAINS = ("posture", "held", "oracle_net")
PAIRS = (0, 1)
LATS = (2, 0)
DELTA = 0.01
TOUCH = len(sys.argv) > 1 and sys.argv[1] == "touch"  # exploratory: fills at the bid price too (first in queue)
EPS = -1e-9 if TOUCH else 1e-9


def run_window(nd, vol_up, vol_dn, main_up_sig, Q, pair, lag, qu, qd, oracle_up, main):
    """Sequential allocation of fills given per-second through-volumes. Returns arrays f_up, f_dn."""
    f_up = np.zeros(nd)
    f_dn = np.zeros(nd)
    U = 0.0
    D = 0.0
    first = None
    for d in range(nd):
        j = d - lag
        if j >= 0:
            U += f_up[j]
            D += f_dn[j]
            if first is None and (f_up[j] > 0 or f_dn[j] > 0):
                first = j
        if main == "posture":
            m = main_up_sig[d]  # 1 up, 0 down, -1 none
        elif main == "held":
            if first is None:
                m = main_up_sig[d]
            else:
                m = 1 if U > D else (0 if D > U else main_up_sig[d])
        else:
            m = 1 if oracle_up else 0
        bu = Q if (m == 1 and qu[d]) else 0.0
        bd = Q if (m == 0 and qd[d]) else 0.0
        if pair:
            if U > D and qd[d]:
                bd += U - D
            elif D > U and qu[d]:
                bu += D - U
        if bu > 0 and vol_up[d] > 0:
            f_up[d] = min(bu, vol_up[d])
        if bd > 0 and vol_dn[d] > 0:
            f_dn[d] = min(bd, vol_dn[d])
    return f_up, f_dn


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    base, px = RP.load_spot()
    v3 = RP.rv(px, 300)
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    W = W[(W.start_ts >= RP.LOT[0]) & (W.start_ts < RP.LOT[1])].set_index("cid")
    CW = pd.read_parquet(C / "it11" / "cluster_windows.parquet")
    mk = CW[CW.role == "maker"].groupby("cid").agg(up=("up", "sum"), dn=("dn", "sum"))
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
            sess = bool(RP.session(st))
            Q = 500.0 if sess else 62.0
            q_up = RP.quote_price(mid_up - DELTA)
            q_dn = RP.quote_price((1 - mid_up) - DELTA)
            vq_up = np.isfinite(q_up) & (q_up >= 0.001) & (q_up <= 0.999)
            vq_dn = np.isfinite(q_dn) & (q_dn >= 0.001) & (q_dn <= 0.999)
            for L in LATS:
                kk = ts - RP.SLACK - L - 1 - (st + 1)
                fm = (kk >= 0) & (kk < nd) & ~own
                kf, iuf, sef, buf, prf, szf = kk[fm], is_up[fm], sell[fm], buy[fm], pr[fm], sz[fm]
                qu, qd = q_up[kf], q_dn[kf]
                thr_up = (iuf & sef & (prf < qu - EPS)) | (~iuf & buf & (prf > 1 - qu + EPS))
                thr_dn = (~iuf & sef & (prf < qd - EPS)) | (iuf & buf & (prf > 1 - qd + EPS))
                vol_up = np.bincount(kf[thr_up], weights=szf[thr_up], minlength=nd)
                vol_dn = np.bincount(kf[thr_dn], weights=szf[thr_dn], minlength=nd)
                for main_r in MAINS:
                    if main_r == "oracle_net" and cid not in onet:
                        continue
                    for pair in PAIRS:
                        f_up, f_dn = run_window(nd, vol_up, vol_dn, main_up_sig, Q, pair, L + 1, vq_up, vq_dn,
                                                bool(onet.get(cid, False)), main_r)
                        U, D = f_up.sum(), f_dn.sum()
                        cu = float((f_up * np.nan_to_num(q_up)).sum())
                        cd = float((f_dn * np.nan_to_num(q_dn)).sum())
                        pnl = U * pay_up + D * (1 - pay_up) - cu - cd
                        P = min(U, D)
                        locked = P * (1 - (cu / U if U > 0 else 0) - (cd / D if D > 0 else 0)) if P > 0 else 0.0
                        out.append((cid, st, L, main_r, pair, float(pnl), float(U), float(D), cu, cd, float(locked)))
        print(pd.to_datetime(day, unit="s").date(), len(out), round(time.time() - t0, 1), flush=True)
        del T
    R = pd.DataFrame(out, columns=["cid", "st", "L", "main", "pair", "pnl", "U", "D", "cu", "cd", "locked"])
    R["resid"] = R.pnl - R.locked
    R.to_parquet(OUT / ("machine_windows_touch.parquet" if TOUCH else "machine_windows.parquet"))
    print("saved", len(R), round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    main()

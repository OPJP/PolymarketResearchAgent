"""Iteration 11 pivot (mechanics panel P1 = X106 / P4 = X109; catalog D3 / X64): the window as the unit of decision.

An executable state machine replays a ladder second by second against the public data-api taker tape of every BTC 5m
window of the released lot (STUDY 10-23..26 case by case, VALIDATE 10-27..30 aggregates only), with the examiner's
strict-fill conventions (EXAM_r1.md backtest):
  * decision second d (window open + 1 s .. end - STOP): information = clean prints stamped <= d (prints in any cluster
    transaction removed), Binance 1-s spot second d - 2 (a second is usable one second after it ends), strike K = mean
    Binance spot over [st - 60, st) (the basis to Chainlink cancels, as in code9/vol_hist.py);
  * the quote decided at d is live in (d + L, d + L + 1]; a print stamped T counts at T - SLACK (slack 2);
  * a BUY bid at q on token X fills only on a print that trades THROUGH it: a taker SELL of X below q or a taker BUY of
    the complement above 1 - q (complementary mint); fill per decision second = min(Q, through volume);
  * side rules: posture (Up iff the digital fair of Up, Phi(ln(S/K) / (1.4 v300 sqrt(tau))), exceeds the last clean
    Up print), two-sided, cheaper side, favourite, pick-off (the outcome the last Binance second moved against);
  * price: q = quote_price(last clean print of the token - delta), delta in {0, 0.01};
  * size Q per second: 1, 100, 500, session (500 in the weekday 12-21 UTC session, else 62);
  * fill flow: 'full' = every taker print except the cluster's own taker orders (the takers that hit the cluster are
    market demand a replay at a better price would have met first); 'clean' = prints in non-cluster transactions only.
The window's realized replay PnL = sum fills x (payout - q); its terminal net = Up shares - Down shares.

Writes .cache/re/directional-maker/it11/replay_windows.parquet (one row per window x config) and the cluster's window
table it11/cluster_windows.parquet. Prints nothing per VALIDATE window.
    python code11/replay.py
"""
import itertools
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache" / "re" / "directional-maker"
OUT = C / "it11"
OUT.mkdir(parents=True, exist_ok=True)
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
LOT = (1792713600, 1793404800)
STOP = 30
SLACK = 2
SIDES = ("posture", "two", "cheaper", "fav", "pickoff")
DELTAS = (0.0, 0.01)
LATS = (2, 0)
FLOWS = ("full", "clean")
QS = ("q1", "q100", "q500", "qsess")


def load_spot():
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).drop_duplicates("sec").sort_values("sec")
    base = int(s.sec.iloc[0])
    n = int(s.sec.iloc[-1]) - base + 1
    px = np.full(n, np.nan)
    px[s.sec.to_numpy() - base] = s.px.to_numpy()
    idx = np.where(~np.isnan(px), np.arange(n), 0)
    np.maximum.accumulate(idx, out=idx)
    return base, px[idx]


def rv(px, L):
    lp = np.log(px)
    r = np.diff(lp, prepend=lp[0])
    cs = np.concatenate([[0.0], np.cumsum(r * r)])
    i = np.arange(len(r))
    lo = np.maximum(i + 1 - L, 0)
    return np.sqrt((cs[i + 1] - cs[lo]) / np.maximum(i + 1 - lo, 1))


def quote_price(x):
    x = np.asarray(x, dtype=float)
    q01 = np.floor(x / 0.01 + 1e-9) * 0.01
    q001 = np.floor(x / 0.001 + 1e-9) * 0.001
    return np.where((q001 < 0.04) | (q001 > 0.96), q001, q01)


def snap(p):
    p = np.asarray(p, dtype=float)
    return np.where((p < 0.04) | (p > 0.96), np.round(p, 3), np.round(p, 2))


def session(ts):
    t = pd.to_datetime(ts, unit="s")
    return (t.dayofweek < 5) & (t.hour >= 12) & (t.hour < 21)


def main():
    t0 = time.time()
    base, px = load_spot()
    v3 = rv(px, 300)
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    W = W[(W.start_ts >= LOT[0]) & (W.start_ts < LOT[1])].set_index("cid")
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet")
    F = F[F.cid.isin(W.index) & (F.side == "BUY")].copy()
    F["txh"] = F.txh.str.lower()
    cl_tx = set(F.txh)
    for n in ("bosona", "almach", "momoney"):
        g = pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"])
        cl_tx |= set(g.transactionHash.str.lower())
    # cluster window table (maker BUY fills; all BUY fills)
    F["is_up"] = [str(t) == str(W.at[c, "up_token"]) for t, c in zip(F.token_id, F.cid)]
    F["pay"] = np.where(F.is_up, W.loc[F.cid, "up_payout"].to_numpy(), 1 - W.loc[F.cid, "up_payout"].to_numpy())
    F["pnl"] = F.shares * (F.pay - F.price)
    F["sh_up"] = np.where(F.is_up, F.shares, 0.0)
    F["sh_dn"] = np.where(F.is_up, 0.0, F.shares)
    rows = []
    for (cid, wal, role), g in F.groupby(["cid", "wallet", "role"]):
        g = g.sort_values("ts", kind="stable")
        rows.append(dict(cid=cid, wallet=CLUSTER.get(wal, wal), role=role, pnl=g.pnl.sum(), up=g.sh_up.sum(), dn=g.sh_dn.sum(),
                         usd=float((g.shares * g.price).sum()), n=len(g), first_up=int(g.is_up.iloc[0]), first_ts=int(g.ts.iloc[0])))
    CW = pd.DataFrame(rows)
    CW.to_parquet(OUT / "cluster_windows.parquet")
    print("cluster windows", len(CW), round(time.time() - t0, 1), flush=True)
    out = []
    days = sorted(set((W.start_ts // 86400 * 86400).astype(int)))
    for day in days:
        T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        T["in_cl"] = T.tx.str.lower().isin(cl_tx)
        T["own_taker"] = T.wallet.str.lower().isin(set(CLUSTER))
        T["price"] = snap(T.price.to_numpy())
        for cid, g in T.groupby("cid"):
            if cid not in W.index:
                continue
            ww = W.loc[cid]
            st, en, up_tok, pay_up = int(ww.start_ts), int(ww.end_ts), str(ww.up_token), ww.up_payout
            if pay_up is None or not np.isfinite(pay_up):
                continue
            g = g.sort_values("ts", kind="stable")
            ts = g.ts.to_numpy().astype(np.int64)
            is_up = (g.asset.astype(str).to_numpy() == up_tok)
            sell = g.side.to_numpy() == "SELL"
            buy = ~sell
            pr = g.price.to_numpy()
            sz = g["size"].to_numpy().astype(float)
            in_cl = g.in_cl.to_numpy()
            own_t = g.own_taker.to_numpy()
            pu = np.where(is_up, pr, 1 - pr)
            clean = ~in_cl
            d = np.arange(st + 1, en - STOP)
            nd = len(d)
            cts, cpu = ts[clean], pu[clean]
            k = np.searchsorted(cts, d, side="right") - 1
            mid_up = np.where(k >= 0, cpu[np.clip(k, 0, None)], np.nan)
            i0 = st - 60 - base
            if i0 < 400 or en - base >= len(px):
                continue
            K = float(px[i0:st - base].mean())
            si = d - 2 - base
            S = px[si]
            sig = 1.4 * v3[si] * np.sqrt(np.maximum(en - d, 1))
            with np.errstate(divide="ignore", invalid="ignore"):
                fair_up = ndtr(np.log(S / K) / np.where(sig > 0, sig, np.nan))
            dpx = px[si] - px[si - 1]
            sess = bool(session(st))
            sides = {
                "posture": (fair_up > mid_up, fair_up < mid_up),
                "two": (np.isfinite(mid_up), np.isfinite(mid_up)),
                "cheaper": (mid_up < 0.5, mid_up > 0.5),
                "fav": (mid_up > 0.5, mid_up < 0.5),
                "pickoff": (dpx < 0, dpx > 0),
            }
            ok_mid = np.isfinite(mid_up)
            post_frac_up = float(np.nanmean((fair_up > mid_up)[ok_mid])) if ok_mid.any() else np.nan
            j_first = np.argmax(ok_mid) if ok_mid.any() else -1
            entry_post_up = int(fair_up[j_first] > mid_up[j_first]) if j_first >= 0 and np.isfinite(fair_up[j_first]) else -1
            base_row = dict(cid=cid, st=st, day=day, sess=int(sess), pay_up=float(pay_up), post_frac_up=post_frac_up,
                            entry_post_up=entry_post_up, n_prints=int(len(ts)))
            for L in LATS:
                kk = ts - SLACK - L - 1 - (st + 1)
                inr = (kk >= 0) & (kk < nd)
                for flow in FLOWS:
                    fm = inr & ~own_t & (clean if flow == "clean" else True)
                    kf, iuf, sef, buf, prf, szf = kk[fm], is_up[fm], sell[fm], buy[fm], pr[fm], sz[fm]
                    for delta in DELTAS:
                        q_up = quote_price(mid_up - delta)
                        q_dn = quote_price((1 - mid_up) - delta)
                        vq_up = np.isfinite(q_up) & (q_up >= 0.001) & (q_up <= 0.999)
                        vq_dn = np.isfinite(q_dn) & (q_dn >= 0.001) & (q_dn <= 0.999)
                        for touch in ((False, True) if delta > 0 else (False,)):
                            eps = -1e-9 if touch else 1e-9
                            qu, qd = q_up[kf], q_dn[kf]
                            thr_up = (iuf & sef & (prf < qu - eps)) | (~iuf & buf & (prf > 1 - qu + eps))
                            thr_dn = (~iuf & sef & (prf < qd - eps)) | (iuf & buf & (prf > 1 - qd + eps))
                            vol_up = np.bincount(kf[thr_up], weights=szf[thr_up], minlength=nd)
                            vol_dn = np.bincount(kf[thr_dn], weights=szf[thr_dn], minlength=nd)
                            for side in SIDES:
                                a_up, a_dn = sides[side]
                                a_up = a_up & vq_up
                                a_dn = a_dn & vq_dn
                                for qn in QS:
                                    Q = {"q1": 1.0, "q100": 100.0, "q500": 500.0, "qsess": 500.0 if sess else 62.0}[qn]
                                    f_up = np.where(a_up, np.minimum(Q, vol_up), 0.0)
                                    f_dn = np.where(a_dn, np.minimum(Q, vol_dn), 0.0)
                                    su, sd_ = f_up.sum(), f_dn.sum()
                                    if su + sd_ > 0:
                                        pnl = float((f_up * (pay_up - np.nan_to_num(q_up))).sum() + (f_dn * ((1 - pay_up) - np.nan_to_num(q_dn))).sum())
                                        iu_ = np.nonzero(f_up > 0)[0]
                                        id_ = np.nonzero(f_dn > 0)[0]
                                        fu_ = iu_[0] if len(iu_) else 10 ** 9
                                        fd_ = id_[0] if len(id_) else 10 ** 9
                                        first_up = int(fu_ < fd_) if fu_ != fd_ else -1
                                        usd = float((f_up * np.nan_to_num(q_up)).sum() + (f_dn * np.nan_to_num(q_dn)).sum())
                                    else:
                                        pnl, first_up, usd = 0.0, -1, 0.0
                                    out.append((cid, L, flow, delta, int(touch), side, qn, pnl, float(su), float(sd_), first_up, usd))
            out_base = base_row
            out.append(("__base__", out_base))
        print(pd.to_datetime(day, unit="s").date(), len(out), round(time.time() - t0, 1), flush=True)
        del T
    bases = [r[1] for r in out if r[0] == "__base__"]
    recs = [r for r in out if r[0] != "__base__"]
    R = pd.DataFrame(recs, columns=["cid", "L", "flow", "delta", "touch", "side", "q", "pnl", "up", "dn", "first_up", "usd"])
    B = pd.DataFrame(bases)
    R.to_parquet(OUT / "replay_windows.parquet")
    B.to_parquet(OUT / "replay_window_base.parquet")
    print("saved", len(R), len(B), round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    main()

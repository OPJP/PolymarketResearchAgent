"""directional-maker iteration 14, X154 (panel iter13 mechanics P4 step 2): the order life-cycle in the strict replay.

Live 10-31 15-18 (mechanics panel check 1): 79% of cluster orders end partially filled and the remainder is cancelled
~165 ms after the last fill (re-posted at the remainder size in 2.8%): each order serves one taker batch. Variant of
code11/replay.py (same inputs, posture side, last clean print - 0.01, session size, L 2 s, slack 2, all prints but
the cluster's own taker orders): per decision second the quote fills at most ONE taker print (the first print of that
second that reaches it) instead of the second's whole through-volume. Strict (trade-through) and at-touch fills; side =
the posture (frozen R7 replay) or the oracle window side (the cluster's terminal net maker side, a ceiling).
Window PnL correlation with the cluster's maker window PnL: STUDY (10-23..26) and VALIDATE (10-27..30, aggregate).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/replay_batch.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code11"))
from replay import load_spot, rv, quote_price, snap, session, CLUSTER, LOT, STOP, SLACK  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT_V = 1793059200


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return [round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)]


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
    CW = pd.read_parquet(C / "it11" / "cluster_windows.parquet")
    mkw = CW[CW.role == "maker"].groupby("cid").agg(pnl=("pnl", "sum"), up=("up", "sum"), dn=("dn", "sum"))
    oracle_up = (mkw.up > mkw.dn).to_dict()
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
            sell = g.side.to_numpy() == "SELL"; buy = ~sell
            pr = g.price.to_numpy(); sz = g["size"].to_numpy().astype(float)
            clean = ~g.in_cl.to_numpy(); own_t = g.own_taker.to_numpy()
            pu = np.where(is_up, pr, 1 - pr)
            d = np.arange(st + 1, en - STOP); nd = len(d)
            cts, cpu = ts[clean], pu[clean]
            k = np.searchsorted(cts, d, side="right") - 1
            mid_up = np.where(k >= 0, cpu[np.clip(k, 0, None)], np.nan)
            i0 = st - 60 - base
            if i0 < 400 or en - base >= len(px):
                continue
            K = float(px[i0:st - base].mean())
            si = d - 2 - base
            sig = 1.4 * v3[si] * np.sqrt(np.maximum(en - d, 1))
            with np.errstate(divide="ignore", invalid="ignore"):
                fair_up = ndtr(np.log(px[si] / K) / np.where(sig > 0, sig, np.nan))
            sess = bool(session(st)); Q = 500.0 if sess else 62.0
            orc = oracle_up.get(cid)
            sides = {"posture": (fair_up > mid_up, fair_up < mid_up)}
            if orc is not None:
                sides["oracle"] = (np.full(nd, bool(orc)), np.full(nd, not bool(orc)))
            kk = ts - SLACK - 2 - 1 - (st + 1)
            fm = (kk >= 0) & (kk < nd) & ~own_t
            kf, iuf, sef, buf, prf, szf = kk[fm], is_up[fm], sell[fm], buy[fm], pr[fm], sz[fm]
            q_up = quote_price(mid_up - 0.01); q_dn = quote_price((1 - mid_up) - 0.01)
            vq_up = np.isfinite(q_up) & (q_up >= 0.001) & (q_up <= 0.999)
            vq_dn = np.isfinite(q_dn) & (q_dn >= 0.001) & (q_dn <= 0.999)
            for touch in (False, True):
                eps = -1e-9 if touch else 1e-9
                qu, qd = q_up[kf], q_dn[kf]
                thr_up = (iuf & sef & (prf < qu - eps)) | (~iuf & buf & (prf > 1 - qu + eps))
                thr_dn = (~iuf & sef & (prf < qd - eps)) | (iuf & buf & (prf > 1 - qd + eps))
                vol = {}
                for nm, thr in (("up", thr_up), ("dn", thr_dn)):
                    vol[nm + "_sum"] = np.bincount(kf[thr], weights=szf[thr], minlength=nd)
                    kk1, first = np.unique(kf[thr], return_index=True)
                    v1 = np.zeros(nd); v1[kk1] = szf[thr][first]
                    vol[nm + "_batch1"] = v1
                for side, (a_up, a_dn) in sides.items():
                    a_up = a_up & vq_up; a_dn = a_dn & vq_dn
                    for cap in ("sum", "batch1"):
                        f_up = np.where(a_up, np.minimum(Q, vol["up_" + cap]), 0.0)
                        f_dn = np.where(a_dn, np.minimum(Q, vol["dn_" + cap]), 0.0)
                        pnl = float((f_up * (pay_up - np.nan_to_num(q_up))).sum() + (f_dn * ((1 - pay_up) - np.nan_to_num(q_dn))).sum())
                        usd = float((f_up * np.nan_to_num(q_up)).sum() + (f_dn * np.nan_to_num(q_dn)).sum())
                        out.append((cid, st, int(touch), side, cap, pnl, usd, float(f_up.sum()), float(f_dn.sum())))
        print(pd.to_datetime(day, unit="s").date(), len(out), round(time.time() - t0, 1), flush=True)
        del T
    R = pd.DataFrame(out, columns=["cid", "st", "touch", "side", "cap", "pnl", "usd", "up", "dn"])
    R.to_parquet(C / "it14_replay_batch.parquet")
    res = {}
    for (touch, side, cap), g in R.groupby(["touch", "side", "cap"]):
        g = g.set_index("cid"); rec = {}
        for sp, m in (("study", g.st < SPLIT_V), ("validate", g.st >= SPLIT_V)):
            ids = g.index[m]
            cl = mkw.pnl.reindex(ids).dropna()
            rp = g.pnl.reindex(cl.index).fillna(0.0)
            rec[sp] = {"window_corr_pearson_spearman": corr(rp, cl), "windows": int(len(cl)),
                       "replay_pnl": round(float(g.pnl[m].sum()), 1), "replay_usd": round(float(g.usd[m].sum()), 1),
                       "replay_return": round(float(g.pnl[m].sum() / max(g.usd[m].sum(), 1e-9)), 4),
                       "cluster_pnl": round(float(cl.sum()), 1)}
        res[f"{'touch' if touch else 'strict'}_{side}_{cap}"] = rec
    (HERE.parent / "results" / "iter14_replay_batch.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

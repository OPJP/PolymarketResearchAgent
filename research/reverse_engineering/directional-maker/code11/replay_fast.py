"""Iteration 11: the window replay on a FAST clock (exploratory, not the examiner's latency convention). Prints of each
lot BTC 5m window are put in execution order (block second, then the position inside the block where the block was
fetched for R7-price, else the data-api row order). The replay's quote before print j uses only earlier prints (the last
clean print before j as the mid) and Binance spot second ts_j - 3 (completed before the earliest match time of a print
stamped ts_j); print j fills it if it trades THROUGH the quote (strict), fill = min(Q, size). Side rules: posture, two-sided,
oracle (the cluster's terminal net side). Quotes from the open to 30 s before the end; delta 0 / 0.01; session size.
This measures how much of the cluster's window PnL a fast (per-trade) executable copy of the decoded quote reproduces.
Aggregates only for VALIDATE.
    python code11/replay_fast.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as RP  # noqa: E402

C = RP.C
SPLIT_V = 1793059200


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return [round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)]


def main():
    base, px = RP.load_spot()
    v3 = RP.rv(px, 300)
    W = pd.read_parquet(C / "exam" / "windows_5m.parquet")
    W = W[(W.start_ts >= RP.LOT[0]) & (W.start_ts < RP.LOT[1])].set_index("cid")
    CW = pd.read_parquet(C / "it11" / "cluster_windows.parquet")
    mk = CW[CW.role == "maker"].groupby("cid").agg(pnl=("pnl", "sum"), up=("up", "sum"), dn=("dn", "sum"))
    onet = (mk.up > mk.dn).to_dict()
    BL = pd.read_parquet(C / "it11" / "inblock_blocks_all.parquet", columns=["bts", "h", "pos"])
    pos = dict(zip(BL.h, BL.pos))
    del BL
    F = pd.read_parquet(C / "exam" / "fills_holdout.parquet", columns=["txh"])
    cl_tx = set(F.txh.str.lower())
    for n in ("bosona", "almach", "momoney"):
        cl_tx |= set(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["transactionHash"]).transactionHash.str.lower())
    out = []
    for day in sorted(set((W.start_ts // 86400 * 86400).astype(int))):
        T = pd.read_parquet(C / "exam" / f"taker5m_day_{day}.parquet", columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        T["tx"] = T.tx.str.lower()
        T["rowpos"] = np.arange(len(T))
        T["p"] = T.tx.map(pos).fillna(-1).astype(np.int64)
        T["in_cl"] = T.tx.isin(cl_tx)
        T["own"] = T.wallet.str.lower().isin(set(RP.CLUSTER))
        T["price"] = RP.snap(T.price.to_numpy())
        for cid, g in T.groupby("cid"):
            if cid not in W.index:
                continue
            ww = W.loc[cid]
            st, en, up_tok, pay_up = int(ww.start_ts), int(ww.end_ts), str(ww.up_token), float(ww.up_payout)
            i0 = st - 60 - base
            if i0 < 400 or en - base >= len(px):
                continue
            K = float(px[i0:st - base].mean())
            key = np.where(g.p.to_numpy() >= 0, g.p.to_numpy(), 10 ** 6 + g.rowpos.to_numpy())
            o = np.lexsort((key, g.ts.to_numpy()))
            g = g.iloc[o]
            ts = g.ts.to_numpy().astype(np.int64)
            is_up = g.asset.astype(str).to_numpy() == up_tok
            sell = g.side.to_numpy() == "SELL"
            pr, sz = g.price.to_numpy(), g["size"].to_numpy().astype(float)
            clean = ~g.in_cl.to_numpy()
            own = g.own.to_numpy()
            pu = np.where(is_up, pr, 1 - pr)
            # last clean print strictly before j (in execution order)
            idx = np.where(clean, np.arange(len(g)), -1)
            last_incl = np.maximum.accumulate(idx)
            prev = np.concatenate([[-1], last_incl[:-1]])
            mid_up = np.where(prev >= 0, pu[np.clip(prev, 0, None)], np.nan)
            si = ts - 3 - base
            S = px[si]
            sig = 1.4 * v3[si] * np.sqrt(np.maximum(en - ts, 1))
            with np.errstate(divide="ignore", invalid="ignore"):
                fair_up = ndtr(np.log(S / K) / np.where(sig > 0, sig, np.nan))
            live = (ts > st) & (ts <= en - RP.STOP) & np.isfinite(mid_up) & ~own
            sess = RP.session(st)
            Q = 500.0 if sess else 62.0
            for side in ("posture", "two", "oracle"):
                if side == "posture":
                    a_up, a_dn = fair_up > mid_up, fair_up < mid_up
                elif side == "two":
                    a_up = a_dn = np.ones(len(g), bool)
                else:
                    if cid not in onet:
                        continue
                    a_up = np.full(len(g), bool(onet[cid]))
                    a_dn = ~a_up
                for delta in (0.0, 0.01):
                    q_up = RP.quote_price(mid_up - delta)
                    q_dn = RP.quote_price((1 - mid_up) - delta)
                    thr_up = live & a_up & (((is_up & sell) & (pr < q_up - 1e-9)) | ((~is_up & ~sell) & (pr > 1 - q_up + 1e-9)))
                    thr_dn = live & a_dn & (((~is_up & sell) & (pr < q_dn - 1e-9)) | ((is_up & ~sell) & (pr > 1 - q_dn + 1e-9)))
                    f_up = np.where(thr_up, np.minimum(Q, sz), 0.0)
                    f_dn = np.where(thr_dn, np.minimum(Q, sz), 0.0)
                    pnl = float((f_up * (pay_up - np.nan_to_num(q_up))).sum() + (f_dn * ((1 - pay_up) - np.nan_to_num(q_dn))).sum())
                    usd = float((f_up * np.nan_to_num(q_up)).sum() + (f_dn * np.nan_to_num(q_dn)).sum())
                    out.append((cid, st, side, delta, pnl, usd, float(f_up.sum()), float(f_dn.sum())))
        print(pd.to_datetime(day, unit="s").date(), len(out), flush=True)
    R = pd.DataFrame(out, columns=["cid", "st", "side", "delta", "pnl", "usd", "up", "dn"])
    R.to_parquet(C / "it11" / "replay_fast.parquet")
    res = {}
    for (side, delta), g in R.groupby(["side", "delta"]):
        g = g.set_index("cid").join(mk.rename(columns={"pnl": "cl", "up": "cup", "dn": "cdn"}), how="inner")
        rec = {}
        for sp, m in (("study", g.st < SPLIT_V), ("validate", g.st >= SPLIT_V)):
            gg = g[m]
            net_ok = (gg.up != gg.dn)
            rec[sp] = {"corr": corr(gg.pnl, gg.cl), "windows": int(len(gg)), "return": round(float(gg.pnl.sum() / max(gg.usd.sum(), 1e-9)), 4),
                       "net_side_agree": round(float(((gg.up > gg.dn) == (gg.cup > gg.cdn))[net_ok].mean()), 4)}
        res[f"{side}_d{delta}"] = rec
    print(json.dumps(res, indent=1))
    (HERE.parent / "results" / "iter11_replay_fast.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

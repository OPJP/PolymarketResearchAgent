"""Iteration 19, X191 'Who else' (brief E2 step 'who else'; pre-registration 24, written 11-01 ~14:30 UTC before the run): which other
Polymarket wallets show the operator's Globex-hours pre-reaction mass? Evidence of a shared input and of its timing only, never a rule
input. Takes: non-operator taker BUY prints of the VALIDATE window tapes (it16/tapes, data-api, proxyWallet) on 10-17..22, timed by the
capture's server-ms trade rows (min exchangeTimestampMs per (tx, token)); operator wallets (DS / GF / XM / W4 / W5) and every tx that
contains an operator fill excluded. Events: knee19b's isolated Binance spot microprice jumps. Per wallet and session: same-minus-opposite
takes in [0, 230) ms (early) and [230, 320) ms (reaction) after the jump; E = early / reaction. Reported: wallets with reaction excess
>= 15 in both sessions, ranked by E_open - E_closed, with the operator's own values as the reference (E 0.96 / 0.39).
Usage: python who19.py FRAME_DIR HF_DIR TAPE_DIR"""
import os, sys, json, gc, glob
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knee19b import events
from dc_exam14 import globex_open_ms

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
OPW = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9",
       "0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}


def main():
    D, A, TD = sys.argv[1], sys.argv[2], sys.argv[3]
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts"])
    op_tx = set(pd.read_parquet(f"{C}/fills.parquet", columns=["tx"]).tx.str.lower())
    days = ["2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]
    acc = {}  # wallet -> [early_open, peak_open, early_closed, peak_closed, n_takes]
    for day in days:
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
        cids = win[(win.start_ts >= d0) & (win.start_ts < d0 + 86400)].cid.tolist()
        parts = []
        for cc in cids:
            fn = f"{TD}/{cc}.parquet"
            if os.path.exists(fn):
                t = pd.read_parquet(fn, columns=["proxyWallet", "side", "asset", "outcome", "transactionHash"])
                parts.append(t[t.side == "BUY"])
        tp = pd.concat(parts, ignore_index=True); del parts
        tp["w"] = tp.proxyWallet.str.lower(); tp["tx"] = tp.transactionHash.str.lower()
        tp = tp[~tp.w.isin(OPW) & ~tp.tx.isin(op_tx)]
        tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradeSide"])
        tr = tr[tr.tradeSide == "BUY"]
        ms = tr.assign(tx=tr.transactionHash.str.lower(), asset=tr.tokenId.astype(str)).groupby(["tx", "asset"]).exchangeTimestampMs.min()
        del tr
        tp["asset"] = tp.asset.astype(str)
        tp = tp.join(ms, on=["tx", "asset"], how="inner").drop_duplicates(["tx", "asset", "w"])
        tp["y"] = np.where(tp.outcome == "Up", 1, -1)
        M = tp.exchangeTimestampMs.to_numpy(np.int64); Y = tp.y.to_numpy(); Wc, Wn = pd.factorize(tp.w)
        o = np.argsort(M, kind="stable"); M, Y, Wc = M[o], Y[o], Wc[o]
        n_w = len(Wn); E = np.zeros((n_w, 5))
        np.add.at(E[:, 4], Wc, 1.0)
        for h0 in range(0, 24, 6):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 6) * 3600) * 1000
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                              filters=[("receivedTimestampMs", ">=", lo - 70000), ("receivedTimestampMs", "<", hi + 2000), ("type", "=", "book")])
            Tb = t.column("receivedTimestampMs").to_numpy() - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False).astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); oo = np.argsort(Tb, kind="stable"); Tb, mic = Tb[oo], mic[oo]
            del t, bp, bq, ap, aq; gc.collect()
            te, se, iso = events(Tb, mic, lo - 60000, hi)
            k = (te >= lo) & (iso == 1); te, se = te[k], se[k]
            op_ = globex_open_ms(te)
            a = np.searchsorted(M, te, "left"); b = np.searchsorted(M, te + 320, "left")
            for i in np.where(b > a)[0]:
                lag = M[a[i]:b[i]] - te[i]; sg = np.where(Y[a[i]:b[i]] == se[i], 1.0, -1.0); wc = Wc[a[i]:b[i]]
                col = 0 if op_[i] else 2
                e1 = lag < 230
                np.add.at(E[:, col], wc[e1], sg[e1]); np.add.at(E[:, col + 1], wc[~e1], sg[~e1])
            del Tb, mic; gc.collect()
        for j, w in enumerate(Wn):
            v = acc.setdefault(w, np.zeros(5)); v += E[j]
        print(day, len(tp), n_w, flush=True)
        del tp; gc.collect()
    rows = []
    for w, v in acc.items():
        rows.append((w, *v))
    T = pd.DataFrame(rows, columns=["wallet", "early_open", "peak_open", "early_closed", "peak_closed", "takes"])
    T["E_open"] = T.early_open / T.peak_open.where(T.peak_open > 0); T["E_closed"] = T.early_closed / T.peak_closed.where(T.peak_closed > 0)
    T["dE"] = T.E_open - T.E_closed
    elig = T[(T.peak_open >= 15) & (T.peak_closed >= 15)].sort_values("dE", ascending=False)
    tot = T[["early_open", "peak_open", "early_closed", "peak_closed"]].sum()
    res = {"prereg": "24", "wallets": int(len(T)), "eligible": int(len(elig)),
           "crowd_total": {"E_open": round(float(tot.early_open / tot.peak_open), 3), "E_closed": round(float(tot.early_closed / tot.peak_closed), 3)},
           "operator_reference": {"E_open": 0.96, "E_closed": 0.388},
           "top_by_dE": elig.head(15).round(3).to_dict("records"),
           "eligible_with_E_open_ge_0.8_and_E_closed_le_0.5": int(((elig.E_open >= 0.8) & (elig.E_closed <= 0.5)).sum()),
           "eligible_dE_quantiles": {q: round(float(elig.dE.quantile(q)), 3) for q in (0.1, 0.5, 0.9)} if len(elig) else None}
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(f"{R}/who19.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

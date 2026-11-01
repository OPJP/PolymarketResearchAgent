"""Iteration 19 (diagnostic, not a claim; written 11-01 ~14:50 UTC before the run): knee19e's baseline E (|z| > 3, isolation 2 s) per
capture DAY and per wallet in Globex-open hours, against the dc14 side accuracy per day (the iteration-18 assumptions panel's 10-22
anomaly: is the day with the weakest Binance-knee side the day with the most pre-Binance decisions?). Usage: python knee19f.py FRAME_DIR HF_DIR"""
import os, sys, json, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knee19e import events
from dc_exam14 import globex_open_ms
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["up", "m", "m0", "rank", "day", "wallet", "p_dc14_spot_own"])
    acc_day = P[P.wallet.isin(["DS", "GF", "XM"])].assign(ok=lambda x: (x.p_dc14_spot_own > 0.5).astype(int) == x.up)
    acc_day["open"] = globex_open_ms(acc_day.m.to_numpy(np.int64))
    F = P[(P["rank"] == 0) & P.wallet.isin(["DS", "GF", "XM"])].reset_index(drop=True)
    M0 = F.m0.to_numpy(np.int64); Y0 = np.where(F.up.to_numpy() == 1, 1, -1)
    out = {}
    for day in sorted(F.day.unique()):
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp()); e = np.zeros(4)
        for h0 in range(0, 24, 6):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 6) * 3600) * 1000
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                              filters=[("receivedTimestampMs", ">=", lo - 70000), ("receivedTimestampMs", "<", hi + 2000), ("type", "=", "book")])
            Tb = t.column("receivedTimestampMs").to_numpy() - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False).astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); o = np.argsort(Tb, kind="stable"); Tb, mic = Tb[o], mic[o]
            del t, bp, bq, ap, aq; gc.collect()
            if len(Tb) < 1000:
                continue
            te, se, iso = events(Tb, mic, lo - 60000, hi, 3.0, 2000)
            k_ = (te >= lo) & iso; te, se = te[k_], se[k_]; opn = globex_open_ms(te)
            sel = np.where((M0 >= lo - 1000) & (M0 < hi + 1000))[0]; o2 = np.argsort(M0[sel]); ms_, ys_ = M0[sel][o2], Y0[sel][o2]
            a = np.searchsorted(ms_, te, "left"); b = np.searchsorted(ms_, te + 320, "left")
            for i in np.where(b > a)[0]:
                lag = ms_[a[i]:b[i]] - te[i]; sg = np.where(ys_[a[i]:b[i]] == se[i], 1.0, -1.0); c0 = 0 if opn[i] else 2
                e[c0] += sg[lag < 230].sum(); e[c0 + 1] += sg[lag >= 230].sum()
            del Tb, mic; gc.collect()
        ad = acc_day[acc_day.day == day]
        out[day] = {"E_open": round(e[0] / e[1], 3) if e[1] > 0 else None, "E_closed": round(e[2] / e[3], 3) if e[3] > 0 else None,
                    "excess_open_early_peak": [e[0], e[1]], "dc14_acc_open": round(float(ad.ok[ad.open].mean()), 4) if ad.open.any() else None,
                    "dc14_acc_closed": round(float(ad.ok[~ad.open].mean()), 4) if (~ad.open).any() else None}
        print(day, out[day], flush=True)
    json.dump(out, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/knee19f.json", "w"), indent=1)


if __name__ == "__main__":
    main()

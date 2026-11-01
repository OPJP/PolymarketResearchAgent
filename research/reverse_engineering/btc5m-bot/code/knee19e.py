"""Iteration 19, X191 robustness (pre-registration 16e, written 11-01 ~14:40 UTC before the run): sensitivity and placebo of the E
statistic (knee19b / 16c) for operator first legs on 10-17..22.
Variants: (a) baseline |z| > 3, isolation 2 s (replicates 16c); (b) |z| > 4; (c) isolation 4 s; (d) PLACEBO: the operator's first
legs shifted by -3 s and +3 s (same events), where no reaction exists, so the excess in both bands and the session difference should
vanish. Reported: E_open, E_closed and the excess counts per variant. The Globex reading requires E_open > E_closed in (a)-(c) and no
structure in (d).
Usage: python knee19e.py FRAME_DIR HF_DIR"""
import os, sys, json, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knee19b import at
from dc_exam14 import globex_open_ms

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"


def events(Tb, mic, lo, hi, zthr, iso_ms):
    G = np.arange(lo, hi, 10, dtype=np.int64)
    lm = np.log(at(Tb, mic, G))
    r = np.full(len(G), np.nan); r[10:] = lm[10:] - lm[:-10]
    sd = pd.Series(r[::10]).rolling(600, min_periods=300).std().shift(1).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        z = r / np.repeat(sd, 10)[: len(G)]
    big = np.isfinite(z) & (np.abs(z) > zthr); mid = np.isfinite(z) & (np.abs(z) > 2.0)
    cand = np.where(big)[0]
    ev, last = [], -10 ** 9
    for i in cand:
        if i - last > 30:
            ev.append(i)
        last = i
    ev = np.asarray(ev, np.int64)
    cm = np.concatenate([[0], np.cumsum(mid)])
    w = iso_ms // 10
    pre = cm[np.clip(ev - 30, 0, None)] - cm[np.clip(ev - w, 0, None)]
    pre2 = cm[ev] - cm[np.clip(ev - 30, 0, None)]
    return G[ev], np.sign(z[ev]).astype(int), (pre == 0) & (pre2 <= 3)


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["up", "m0", "rank", "day", "wallet"])
    P = P[(P["rank"] == 0) & P.wallet.isin(["DS", "GF", "XM"])].reset_index(drop=True)
    M0 = P.m0.to_numpy(np.int64); Y0 = np.where(P.up.to_numpy() == 1, 1, -1)
    VAR = {"a_base": (3.0, 2000, 0), "b_z4": (4.0, 2000, 0), "c_iso4s": (3.0, 4000, 0), "d_placebo_minus3s": (3.0, 2000, -3000), "d_placebo_plus3s": (3.0, 2000, 3000)}
    acc = {k: np.zeros(4) for k in VAR}  # early_open, peak_open, early_closed, peak_closed
    nev = {k: [0, 0] for k in VAR}
    for day in sorted(P.day.unique()):
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
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
            cache = {}
            for vn, (zt, iw, sh) in VAR.items():
                key = (zt, iw)
                if key not in cache:
                    te, se, iso = events(Tb, mic, lo - 60000, hi, zt, iw)
                    k_ = (te >= lo) & iso; cache[key] = (te[k_], se[k_])
                te, se = cache[key]
                opn = globex_open_ms(te)
                M = M0 + sh; sel = np.where((M >= lo - 1000) & (M < hi + 1000))[0]
                o2 = np.argsort(M[sel], kind="stable"); ms_, ys_ = M[sel][o2], Y0[sel][o2]
                a = np.searchsorted(ms_, te, "left"); b = np.searchsorted(ms_, te + 320, "left")
                nev[vn][0] += int(opn.sum()); nev[vn][1] += int((~opn).sum())
                for i in np.where(b > a)[0]:
                    lag = ms_[a[i]:b[i]] - te[i]; sg = np.where(ys_[a[i]:b[i]] == se[i], 1.0, -1.0)
                    c0 = 0 if opn[i] else 2
                    acc[vn][c0] += sg[lag < 230].sum(); acc[vn][c0 + 1] += sg[lag >= 230].sum()
            del Tb, mic; gc.collect()
        print(day, flush=True)
    res = {"prereg": "16e"}
    for vn, v in acc.items():
        res[vn] = {"events_open_closed": nev[vn], "excess_early_peak_open": [v[0], v[1]], "excess_early_peak_closed": [v[2], v[3]],
                   "E_open": round(v[0] / v[1], 3) if v[1] > 0 else None, "E_closed": round(v[2] / v[3], 3) if v[3] > 0 else None,
                   "per_1000_events_early_peak_open": [round(1000 * v[0] / max(nev[vn][0], 1), 2), round(1000 * v[1] / max(nev[vn][0], 1), 2)],
                   "per_1000_events_early_peak_closed": [round(1000 * v[2] / max(nev[vn][1], 1), 2), round(1000 * v[3] / max(nev[vn][1], 1), 2)]}
        print(vn, res[vn], flush=True)
    json.dump(res, open(f"{R}/knee19e.json", "w"), indent=1)


if __name__ == "__main__":
    main()

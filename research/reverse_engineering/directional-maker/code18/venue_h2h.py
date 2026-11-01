"""iteration 18, T21 (exploratory, in sample on the two 11-01 full-depth blocks already used; it motivates the
pre-registered T14 and replaces nothing): law E2's futures branch computed on each venue's mid (Binance USD-M bookTicker,
Bybit linear best mid, OKX swap ticker mid, Coinbase ticker mid, Binance spot aggTrade) with the same rule (move >= $2
over [t - 500, t - 50] ms on the venue's own stamps), the publish branch unchanged (Binance futures-only innovation)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import event_law as el  # noqa: E402
import lag_floor as lf  # noqa: E402


def main():
    E0, M0 = el.fut_mid(el.FIT[0] - 120, el.FIT[1] + 60)
    secs, cl, P = el.publishes(*el.FIT)
    X = el.design(E0, M0, secs)
    y = np.array([cl[s] - cl[s - 1] for s in secs])
    ok = np.all(np.isfinite(X), axis=1)
    beta, *_ = np.linalg.lstsq(np.c_[np.ones(ok.sum()), X[ok]], y[ok], rcond=None)
    out = {}
    for name in ("freeze_1101_0700_0915", "confirm_1101_0915_1200"):
        a, b, qf = el.BLOCKS[name]
        q = pd.read_parquet(el.C / qf)
        q = q[(q.s >= a * 1000) & (q.s < b * 1000) & (q.p >= 0.10) & (q.p <= 0.90) & q.dz.isin([500.0, 1000.0])].sort_values("s").reset_index(drop=True)
        t = q.s.to_numpy(np.int64)
        yv = (q.sd == 1).to_numpy(float)
        F = q.F.to_numpy(float)
        mp = q.mid_prev.to_numpy(float)
        post = np.where(np.isfinite(F) & np.isfinite(mp), (F > mp).astype(float), np.nan)
        E, M = el.fut_mid(a - 120, b + 60)
        sc, clb, Pb = el.publishes(a, b)
        Xb = el.design(E, M, sc)
        yb = np.array([clb[s] - clb[s - 1] for s in sc])
        okb = np.all(np.isfinite(Xb), axis=1)
        u = yb - np.where(okb, np.c_[np.ones(len(Xb)), np.nan_to_num(Xb)] @ beta, np.nan)
        o = np.argsort([Pb[s] for s in sc])
        Pm = np.array([Pb[s] for s in sc], np.int64)[o]
        um = u[o]
        pub = np.full(len(t), np.nan)
        for k, tk in enumerate(t):
            j = np.searchsorted(Pm, tk, side="right") - 1
            while j >= 0 and Pm[j] > tk - 150:
                if np.isfinite(um[j]) and abs(um[j]) >= 1.0:
                    pub[k] = float(um[j] > 0)
                    break
                j -= 1
        okp = np.isfinite(post)
        rec = {"posts": int(okp.sum()), "posture": round(float((post[okp] == yv[okp]).mean()), 4)}
        for feed in ("dm_bnf", "dm_byb", "dm_okx", "dm_cb", "dm_bns"):
            pts = lf.points(feed, a - 5, b + 5)
            if len(pts) < 100:
                rec[feed] = {"note": "no data"}
                continue
            ts_ = np.array([p_[0] for p_ in pts], np.int64)
            vs_ = np.array([p_[1] for p_ in pts], float)
            dF = el.at(ts_, vs_, t - 50) - el.at(ts_, vs_, t - 500)
            mv = np.isfinite(dF) & (np.abs(dF) >= 2.0)
            law = np.where(np.isfinite(pub), pub, np.where(mv, (dF > 0).astype(float), post))
            br = mv & ~np.isfinite(pub) & okp
            rec[feed] = {"E2_all": round(float((law[okp] == yv[okp]).mean()), 4), "branch_posts": int(br.sum()),
                         "branch_acc": round(float((law[br] == yv[br]).mean()), 4) if br.any() else None}
        out[name] = rec
    (HERE.parent / "results" / "iter18_venue_h2h.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

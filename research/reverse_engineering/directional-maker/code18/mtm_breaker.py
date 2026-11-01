"""iteration 18, T22 = X207 light (pre-registered in NOTES.md 13:48 UTC 11-01; own state, reported as such): do the BTC 5m
switch-offs follow a rolling realised loss? Realised PnL per BTC 5m window (cluster BUY trades, exact outcomes from the
cluster's REDEEM rows, settlement only) booked at window end + 60 s; rolling 2-h and 6-h sums (pooled over the three
accounts) at time t from windows booked before t. Events: every BTC 5m off stretch >= 60 min in 08-02..10-22 (16);
placebos: up to 20 times per event at the same hour-of-week in other weeks with the module on in the previous 15 min.
Statistic: AUC of -PnL separating events from placebos, label-permutation p (2,000). Reading: AUC >= 0.75 with p < 0.01 ->
a loss breaker (own state); else not shown."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pnl_by_ratio as pr  # noqa: E402

CACHE = pr.C
T0, T1 = 1785628800, 1792713600


def main():
    A = pr.trades()
    rd = []
    for w in pr.CLW:
        for f in (CACHE / f"activity_{w}.parquet", CACHE / "exam" / f"activity_{w}.parquet"):
            a = pd.read_parquet(f, columns=["type", "outcomeIndex", "size", "usdcSize", "slug"])
            rd.append(a[(a.type == "REDEEM") & a.slug.str.startswith("btc-updown-5m-")])
    hh = pd.read_parquet(CACHE / "it12" / "hist_btc.parquet", columns=["type", "outcomeIndex", "size", "usdcSize", "slug"])
    rd.append(hh[(hh.type == "REDEEM") & hh.slug.astype(str).str.startswith("btc-updown-5m-")])
    R_ = pd.concat(rd, ignore_index=True)
    R_ = R_[(R_["size"] > 1) & R_.outcomeIndex.isin([0, 1])].copy()
    R_["st"] = R_.slug.astype(str).str.rsplit("-", n=1).str[1].astype(int)
    R_["upw"] = np.where(R_.outcomeIndex == 0, R_.usdcSize / R_["size"] > 0.5, R_.usdcSize / R_["size"] < 0.5).astype(float)
    vote = R_.groupby("st").upw.mean()
    exact = {int(k): float(v > 0.5) for k, v in vote.items() if abs(v - 0.5) > 0.25}
    A = A[A.st.isin(set(exact))].copy()
    A["pay"] = np.where(A.outcomeIndex == 0, A.st.map(exact), 1 - A.st.map(exact))
    A["pnl"] = A.pay * A["size"] - A.usdcSize
    wp = A.groupby("st").pnl.sum()
    book_t = wp.index.to_numpy(np.int64) + 360
    cs = np.r_[0.0, np.cumsum(wp.to_numpy())]

    def roll(t, L):
        j = np.searchsorted(book_t, t, side="left")
        i = np.searchsorted(book_t, t - L, side="left")
        return cs[j] - cs[i]
    on_w = set(A.st.astype(int).unique()) | set(pr.trades().st.astype(int).unique())
    g = np.arange(T0, T1, 300)
    on = np.array([int(t) in on_w for t in g])
    ev = []
    i = 0
    while i < len(g):
        if not on[i]:
            j = i
            while j < len(g) and not on[j]:
                j += 1
            if j - i >= 12 and i >= 3:
                ev.append(int(g[i]))
            i = j
        else:
            i += 1
    on3 = {int(g[k]) for k in range(3, len(g)) if on[k - 3:k].all()}
    rng = np.random.default_rng(0)
    pl = []
    for t in ev:
        c = [t + 7 * 86400 * k for k in range(-12, 13) if k != 0 and (t + 7 * 86400 * k) in on3]
        pl += list(rng.choice(c, size=min(20, len(c)), replace=False)) if c else []
    out = {"events": len(ev), "placebos": len(pl), "events_utc": [pd.Timestamp(t, unit="s").strftime("%m-%d %H:%M") for t in ev]}
    for L in (7200, 21600):
        xe = np.array([roll(t, L) for t in ev])
        xp = np.array([roll(int(t), L) for t in pl])
        y = np.r_[np.ones(len(xe)), np.zeros(len(xp))]
        s = -np.r_[xe, xp]
        auc = roc_auc_score(y, s)
        perm = [roc_auc_score(rng.permutation(y), s) for _ in range(2000)]
        out[f"roll_{L // 3600}h"] = {"auc": round(float(auc), 3), "p_perm": float((np.sum(np.array(perm) >= auc) + 1) / 2001),
                                     "event_median_pnl": round(float(np.median(xe)), 1), "placebo_median_pnl": round(float(np.median(xp)), 1)}
        out[f"roll_{L // 3600}h"]["reading_met"] = bool(auc >= 0.75 and out[f"roll_{L // 3600}h"]["p_perm"] < 0.01)
    (HERE.parent / "results" / "iter18_mtm_breaker.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

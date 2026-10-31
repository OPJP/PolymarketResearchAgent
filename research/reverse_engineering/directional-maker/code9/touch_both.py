"""Iteration 9: quote-bound or taker-bound side? For every match-clock fill of 10-31 12:00-18:00 (side_D), the shared
recorder's latest top-of-book record before the match ms gives the size at the touch on both outcomes (Up bid = best
bid, Down bid = 1 - best ask with the ask size). A touch size >= 500 marks a cluster-class rung there (88% of filled
exact-500 orders are the cluster's). If both outcomes carry >= 500 at the touch, the taker chooses which one fills; if
only one does, the quote does. Reports the shares and the posture accuracy in each case. Development, descriptive."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

C = ROOT / ".cache/re/directional-maker/it9"
A, B = 1793448000, 1793469600


def main():
    D = pd.read_parquet(C / f"side_D_{A}_{B}.parquet")
    w = pd.concat([F._windows(A - 900, B), F._windows15(A - 900, B)], ignore_index=True)
    w["up_token"] = w.up_token.astype(str)
    key = {(int(s), int(e)): u for s, e, u in zip(w.start_ts, w.end_ts, w.up_token)}
    toks = set(key.values())
    bk = {}
    for r in F._iter_live_xq(A - 60, B, toks):
        if r.get("k") == "q" and str(r.get("a")) in toks:
            b_, o_ = r.get("b") or [], r.get("o") or []
            if b_ and o_:
                bb = max(b_, key=lambda x: float(x[0]))
                ba = min(o_, key=lambda x: float(x[0]))
                bk.setdefault(str(r["a"]), []).append((int(r.get("s") or r.get("t")), float(bb[0]), float(bb[1]), float(ba[0]), float(ba[1])))
    bk = {t: np.array(sorted(v)) for t, v in bk.items()}
    sp = pd.read_parquet(C / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    rows = []
    for r in D.itertuples(index=False):
        u = key.get((int(r.st), int(r.en)))
        if u is None or u not in bk:
            continue
        a_ = bk[u]
        i = np.searchsorted(a_[:, 0], r.T, side="left") - 1
        if i < 0 or r.T - a_[i, 0] > 5000:
            continue
        up_bid_sz, dn_bid_sz = a_[i, 2], a_[i, 4]
        own = up_bid_sz if r.is_up == 1 else dn_bid_sz
        oth = dn_bid_sz if r.is_up == 1 else up_bid_sz
        k = int(r.T // 1000) - 1 - b0
        v300 = np.sqrt((cs[k + 1] - cs[k + 1 - 300]) / 300)
        v3600 = np.sqrt((cs[k + 1] - cs[k + 1 - 3600]) / 3600)
        tau = max(r.en - r.T / 1000, 1.0)
        x = np.log(r.cl / r.K)
        y = r.is_up == 1
        rows.append(dict(own=own, oth=oth, frz=(norm.cdf(x / (1.4 * v300 * np.sqrt(tau))) > r.mid_up) == y,
                         slow=(norm.cdf(x / (v3600 * np.sqrt(tau))) > r.mid_up) == y, burst=v300 / v3600 > 1.5))
    T = pd.DataFrame(rows)
    out = {"fills": int(len(T))}
    for thr in (500, 250):
        cls = np.select([(T.own >= thr) & (T.oth >= thr), (T.own >= thr), (T.oth >= thr)], ["both", "only_bought", "only_other"], "neither")
        rec = {}
        for c in ("both", "only_bought", "only_other", "neither"):
            k = cls == c
            rec[c] = {"share": round(float(k.mean()), 3), "frozen": round(float(T.frz[k].mean()), 3) if k.any() else None,
                      "slow": round(float(T.slow[k].mean()), 3) if k.any() else None,
                      "burst_share": round(float(T.burst[k].mean()), 3) if k.any() else None}
        one = (cls == "only_bought") | (cls == "only_other")
        rec["quote_side_predictor_when_one_sided"] = round(float((cls[one] == "only_bought").mean()), 3) if one.any() else None
        out[f"touch_size_ge_{thr}"] = rec
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_touch_both.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

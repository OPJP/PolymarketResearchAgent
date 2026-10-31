"""Iteration 8, panel iter7 information I7-2 (X60) step 1 (live, development block 10-31 12:18-16:53 UTC): the BTC 15m
book as a trigger of the 5m sellers. For 5m windows that end on a 15m boundary (aligned: both settle on the same closing
TWAP-60), the 15m mid implies a closing-mean m = ln K15 + s Phi^-1(mid15) (s = sigma sqrt(tau), sigma = 1.4 x 300-s Binance
1-s vol), hence P5_implied = Phi((m - ln K5) / s). gap = P5_implied - mid5 (Up terms). Placebo: the same formula in the
non-aligned 5m windows (different settlement times). Measures, per second: corr(gap, net taker Up-buying in the 5m book over
the next 3 s), and P(next 5m clean print sells Up) by gap sign; cluster fills (code8/fill_side.py rows, 14:06-16:30): the
share of Up fills by gap sign. Shared recorder 'q' (mids) and 'x' (trades) through final_rule's tolerant reader.
    python code8/x60_cross.py 1793449080 1793466000
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def main(a, b):
    w5 = F._windows(a - 300, b + 300)
    w15 = F._windows15(a - 900, b + 900)
    w = pd.concat([w5, w15], ignore_index=True)
    w["up_token"], w["down_token"] = w.up_token.astype(str), w.down_token.astype(str)
    ptb = F._ptb_any(w)
    ups = set(w.up_token)
    tok2up = {**dict(zip(w.up_token, w.up_token)), **dict(zip(w.down_token, w.up_token))}
    mids, trades = {}, []
    for r in F._iter_live_xq(a, b, ups):
        if r.get("k") == "q" and str(r.get("a")) in ups:
            bq, oq = r.get("b") or [], r.get("o") or []
            if bq and oq:
                mids.setdefault(str(r["a"]), []).append((int(r.get("s") or r["t"]), (max(float(x[0]) for x in bq) + min(float(x[0]) for x in oq)) / 2))
        elif r.get("k") == "x":
            t = str(r.get("a"))
            if t in tok2up:
                up_tok = tok2up[t]
                is_up = t == up_tok
                d = str(r.get("d", "")).upper()[:1]
                buy_up = (is_up and d == "B") or ((not is_up) and d == "S")
                trades.append((up_tok, int(r.get("s") or r["t"]), float(r.get("z") or 0), 1 if buy_up else -1, str(r.get("h", "")).lower()))
    M = {t: (np.array([x[0] for x in v]), np.array([x[1] for x in v])) for t, v in mids.items()}
    for t in M:
        o = np.argsort(M[t][0], kind="stable")
        M[t] = (M[t][0][o], M[t][1][o])
    X = pd.DataFrame(trades, columns=["up", "s", "z", "dirn", "h"]).sort_values("s")
    secs, px = zip(*F._binance_rest_seconds(a - 400, b + 10))
    secs, px = np.array(secs, dtype=np.int64), np.array(px)
    r1 = np.r_[0.0, np.diff(np.log(px))]
    up_of = {(int(s), int(e)): u for u, s, e in zip(w.up_token, w.start_ts, w.end_ts)}
    rows = []
    for (st, en), u5 in up_of.items():
        if en - st != 300 or u5 not in M or st < a or en > b:
            continue
        st15 = st - (st % 900)
        u15 = up_of.get((st15, st15 + 900))
        if u15 is None or u15 not in M:
            continue
        K5, K15 = ptb.get(("5m", st)), ptb.get(("15m", st15))
        if K5 is None or K15 is None:
            continue
        aligned = (en == st15 + 900)
        x5 = X[X.up == u5]
        xs, xz, xd = x5.s.to_numpy(), x5.z.to_numpy(), x5.dirn.to_numpy()
        for t in range(st + 5, en - 30):
            T = t * 1000
            i5 = np.searchsorted(M[u5][0], T, side="right") - 1
            i15 = np.searchsorted(M[u15][0], T, side="right") - 1
            j = np.searchsorted(secs, t)
            if i5 < 0 or i15 < 0 or j < 300:
                continue
            m5, m15 = M[u5][1][i5], M[u15][1][i15]
            if not (0.03 < m5 < 0.97 and 0.03 < m15 < 0.97):
                continue
            sig = np.std(r1[j - 300:j]) * 1.4
            tau = en - t if aligned else st15 + 900 - t
            s_ = sig * np.sqrt(max(tau, 1))
            m = np.log(K15) + s_ * norm.ppf(m15)
            s5 = sig * np.sqrt(max(en - t, 1))
            p5 = norm.cdf((m - np.log(K5)) / (s5 if aligned else s_))
            nxt = (xs >= T) & (xs < T + 3000)
            k = np.searchsorted(xs, T, side="left")
            rows.append(dict(aligned=int(aligned), st=st, t=t, gap=p5 - m5, net3=float((xz[nxt] * xd[nxt]).sum()),
                             next_dir=int(xd[k]) if k < len(xd) and xs[k] < T + 3000 else 0))
    D = pd.DataFrame(rows)
    out = {"seconds": int(len(D)), "aligned_seconds": int(D.aligned.sum())}
    for al, g in D.groupby("aligned"):
        nm = "aligned" if al else "placebo_nonaligned"
        big = g[g.gap.abs() > 0.02]
        nd = big[big.next_dir != 0]
        out[nm] = {"n": int(len(g)), "gap_q": g.gap.quantile([.1, .5, .9]).round(3).to_dict(),
                   "corr_gap_net_upbuy_3s": round(float(np.corrcoef(g.gap, g.net3)[0, 1]), 4),
                   "next_print_buys_up_when_gap_pos": round(float((nd.next_dir[nd.gap > 0] > 0).mean()), 3) if (nd.gap > 0).any() else None,
                   "next_print_buys_up_when_gap_neg": round(float((nd.next_dir[nd.gap < 0] > 0).mean()), 3) if (nd.gap < 0).any() else None,
                   "n_big": int(len(big))}
    # cluster fills (14:06-16:30) vs the gap at their match ms, aligned windows
    fs = pd.read_parquet(C / "it6" / "fill_side_1793455600_1793464202.parquet")
    fs = fs[fs.fam == "5m"].copy()
    fs["t"] = fs["T"] // 1000
    J = fs.merge(D[["st", "t", "gap", "aligned"]], on=["st", "t"], how="inner")
    if len(J):
        out["cluster_fills"] = {str(al): {"n": int(len(g)), "up_share_gap_pos": round(float(g.up[g.gap > 0].mean()), 3) if (g.gap > 0).any() else None,
                                           "up_share_gap_neg": round(float(g.up[g.gap < 0].mean()), 3) if (g.gap < 0).any() else None,
                                           "side_acc_sign_gap": round(float(((g.gap > 0) == (g.up == 1)).mean()), 3),
                                           "side_acc_posture": round(float(((g.e_cl > 0) == (g.up == 1)).mean()), 3)}
                                for al, g in J.groupby("aligned")}
    (HERE.parent / "results" / f"iter8_x60_cross_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))

"""Iteration 9, check of the decision count (ins9b): is P(a resting lost race gets a maker fill) like the cluster's remainder
refill rate pi_rem = 0.458? Anonymous analogue from my unthrottled book (btc5m_clob_raw2, 10-31 development block): every size
increment of exactly 30 / 60 / 100 shares on o's BID side at a price L that was o's ask within the previous 300 ms (a lost-race
insertion, as in subs6). Its fate: FILLED if a trade at that level (a taker SELL of o at L, or a taker BUY of the other outcome
at 1 - L) comes before the level loses that size without a trade; CANCEL if the level loses it first; EXPIRED after 10 s.
Usage: python pianon9.py START END OUT_JSON"""
import os, sys, json
from collections import deque
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L

SIZES = (30.0, 60.0, 100.0)


def main(a, b, out):
    books = {}; hist = {}; pend = {}; q = deque(); done = []

    def close(key, fate, s):
        lst = pend.get(key)
        if not lst:
            return
        for it in lst:
            if it["fate"] is None:
                it["fate"] = fate; it["t_end"] = s; done.append(it)
        pend[key] = []
    for r in L.recs("btc5m_clob_raw2", a - 300, b + 30):
        k = r.get("k")
        if k == "f":
            if r.get("u") == 1:
                mm = int(r["m"]); books[mm] = {"B": {round(p, 4): z for p, z in r["b"]}, "S": {round(p, 4): z for p, z in r["o"]}}
            continue
        if k == "x":
            mm = int(r["m"]); s = int(r["s"]); u = int(r.get("u") or 0); p = round(float(r["p"]), 4); d = r.get("d")
            if u == 1 and d == "SELL":
                close((mm, "B", p), "filled", s)
            elif u == 0 and d == "BUY":
                close((mm, "B", round(1 - p, 4)), "filled", s)
            elif u == 1 and d == "BUY":
                close((mm, "S", p), "filled", s)
            elif u == 0 and d == "SELL":
                close((mm, "S", round(1 - p, 4)), "filled", s)
            continue
        if k != "p":
            continue
        mm = int(r["m"]); sd = r["d"]; p = round(float(r["p"]), 4); s = int(r["s"])
        bk = books.setdefault(mm, {"B": {}, "S": {}})[sd]
        prev = bk.get(p, 0.0); new = float(r["z"] or 0.0)
        if new == 0:
            bk.pop(p, None)
        else:
            bk[p] = new
        delta = new - prev
        key = (mm, sd, p)
        lst = pend.get(key)
        if lst and delta < -0.5:
            keep = []
            for it in lst:
                if it["fate"] is None and new < it["base"] + it["z"] - 0.01:
                    it["fate"] = "cancel"; it["t_end"] = s; done.append(it)
                elif it["fate"] is None:
                    keep.append(it)
            pend[key] = keep
        h = hist.setdefault(mm, deque(maxlen=400))
        if a * 1000 <= s < b * 1000 and delta > 0.5 and any(abs(delta - z) < 0.011 for z in SIZES):
            hit = False
            for x in reversed(h):
                if x[0] < s - 300:
                    break
                if sd == "B" and x[2] is not None and abs(x[2] - p) < 1e-9:
                    hit = True; break
                if sd == "S" and x[1] is not None and abs(x[1] - p) < 1e-9:
                    hit = True; break
            if hit:
                it = {"s": s, "m": mm, "side": sd, "p": p, "z": round(delta, 2), "base": prev, "fate": None, "t_end": None}
                pend.setdefault(key, []).append(it); q.append(it)
        h.append((s, r.get("bb"), r.get("ba")))
        while q and q[0]["s"] < s - 10000:
            it = q.popleft()
            if it["fate"] is None:
                it["fate"] = "expired_10s"; it["t_end"] = s; done.append(it)
    D = pd.DataFrame(done)
    res = {"insertions": int(len(D)), "fate": D.fate.value_counts(normalize=True).round(4).to_dict(),
           "by_size": {str(z): g.fate.value_counts(normalize=True).round(4).to_dict() for z, g in D.groupby("z")},
           "filled_share_excl_expired": round(float((D.fate == "filled").sum() / max((D.fate != "expired_10s").sum(), 1)), 4)}
    for f_ in ("cancel", "filled"):
        g = D[D.fate == f_]
        if len(g):
            res[f"life_ms_q_{f_}"] = [float(x) for x in np.percentile((g.t_end - g.s).astype(float), [10, 50, 90])]
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])

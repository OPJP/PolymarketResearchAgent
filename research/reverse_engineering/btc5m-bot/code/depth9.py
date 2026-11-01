"""Iteration 9 (panel iter8 mechanics P2): does the VISIBLE Polymarket depth at the decision set the pay-up level and the size?
For every cluster taker-first order of 10-31 14:14-17:55 with calldata (size Z, limit L) and a match ms m in my unthrottled
book (btc5m_clob_raw2), the ask ladder of o at m - 50 ms (Up asks = Up 'S' levels; Down asks = Up bids mirrored, 1 - p),
rebuilt from snapshots + every near-touch change (within 2 c of the touch). Then:
  price: share of PAY-UP orders (L > touch) with L == the cheapest level whose cumulative depth covers Z ("depth cover"), vs
         touch + 1 c; and for touch orders, whether the touch depth covered Z;
  size:  within-wallet AUC of P(large) (Z >= 90) from the touch size, the depth within 1 c and 2 c of the touch.
Usage: python depth9.py START END OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9
from sklearn.metrics import roc_auc_score

C = L.C


def main(a, b, out):
    o, fills = ins9.load_orders(a, b)
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna() & o.Z.notna()].copy(); o["mstart"] = o.mstart.astype(int); o["Lx"] = o.Lim.fillna(o.px0)
    # match ms from the raw feed trades
    txms = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        if r.get("k") == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    o["m0"] = o.tx0.str.lower().map(txms)
    T = o[(o["first"] == "T") & o.m0.notna()].copy()
    T["q"] = (T.m0 - 50).astype(np.int64)
    queries = {}
    for i, r in enumerate(T.itertuples()):
        queries.setdefault(int(r.mstart), []).append((int(r.q), i, bool(r.is_up)))
    for k in queries:
        queries[k].sort()
    ptr = {k: 0 for k in queries}
    books = {}
    snap = [None] * len(T)

    def take(mm, up):
        bk = books.get(mm)
        if bk is None:
            return None
        if up:
            lv = sorted(bk["S"].items())[:6]
        else:
            lv = sorted(((round(1 - p, 4), z) for p, z in bk["B"].items()))[:6]
        return lv
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        k = r.get("k")
        if k not in ("f", "p"):
            continue
        mm = int(r["m"]); s = int(r["s"])
        if mm in queries:
            qs = queries[mm]; j = ptr[mm]
            while j < len(qs) and qs[j][0] <= s:
                snap[qs[j][1]] = take(mm, qs[j][2]); j += 1
            ptr[mm] = j
        if k == "f":
            if r.get("u") == 1:
                books[mm] = {"B": {round(p, 4): z for p, z in r["b"]}, "S": {round(p, 4): z for p, z in r["o"]}}
        else:
            bk = books.setdefault(mm, {"B": {}, "S": {}})[r["d"]]
            p = round(float(r["p"]), 4); z = float(r["z"] or 0.0)
            if z == 0:
                bk.pop(p, None)
            else:
                bk[p] = z
    rows = []
    for (r, sn) in zip(T.itertuples(), snap):
        if not sn:
            continue
        touch = sn[0][0]; cum = np.cumsum([z for p, z in sn]); prices = [p for p, z in sn]
        cover = next((p for p, c in zip(prices, cum) if c >= r.Z - 1e-6), np.nan)
        d1 = sum(z for p, z in sn if p <= touch + 0.0101); d2 = sum(z for p, z in sn if p <= touch + 0.0201)
        rows.append((r.w, r.Z, r.Lx, touch, sn[0][1], d1, d2, cover, r.shT))
    D = pd.DataFrame(rows, columns=["w", "Z", "L", "touch", "tz", "d1", "d2", "cover", "shT"])
    D["payup"] = D.L > D.touch + 1e-6
    D["below"] = D.L < D.touch - 1e-6
    res = {"n_taker_first_with_book": int(len(D)), "payup_share": round(float(D.payup.mean()), 4),
           "limit_below_touch_share": round(float(D.below.mean()), 4)}
    P = D[D.payup]
    res["payup"] = {"n": int(len(P)), "L==depth_cover": round(float((np.abs(P.L - P.cover) < 1e-6).mean()), 4),
                    "L==touch+1c": round(float((np.abs(P.L - P.touch - 0.01) < 1e-6).mean()), 4),
                    "L>=depth_cover": round(float((P.L >= P.cover - 1e-6).mean()), 4),
                    "touch_covered_Z": round(float((P.tz >= P.Z - 1e-6).mean()), 4),
                    "L_minus_touch_c": ((P.L - P.touch) * 100).round().clip(0, 5).value_counts().sort_index().to_dict(),
                    "by_wallet": {w: [round(float((np.abs(g.L - g.cover) < 1e-6).mean()), 4), int(len(g))] for w, g in P.groupby("w")}}
    Tt = D[~D.payup & ~D.below]
    res["touch_orders"] = {"n": int(len(Tt)), "touch_covered_Z": round(float((Tt.tz >= Tt.Z - 1e-6).mean()), 4),
                           "cover_would_need_payup": round(float((Tt.cover > Tt.touch + 1e-6).mean()), 4)}
    # pay-up predicted by "touch does not cover Z": precision / recall
    pred = D.tz < D.Z - 1e-6
    res["payup_vs_touch_not_covering"] = {"P(payup | touch < Z)": round(float(D.payup[pred].mean()), 4), "n_pred": int(pred.sum()),
                                          "P(payup | touch >= Z)": round(float(D.payup[~pred].mean()), 4), "n_not": int((~pred).sum())}
    # size: within-wallet AUC of large from depth
    D["large"] = D.Z >= 90
    sz = {}
    for w, g in D.groupby("w"):
        if g.large.nunique() < 2:
            continue
        sz[w] = {"n": int(len(g)), "large_share": round(float(g.large.mean()), 4)}
        for f in ("tz", "d1", "d2"):
            sz[w][f"auc_{f}"] = round(float(roc_auc_score(g.large, g[f])), 4)
        sz[w]["P(payup|large)"] = round(float(g.payup[g.large].mean()), 4); sz[w]["P(payup|small)"] = round(float(g.payup[~g.large].mean()), 4)
    res["size_from_depth"] = sz
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])

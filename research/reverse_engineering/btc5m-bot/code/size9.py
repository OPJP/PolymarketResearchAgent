"""Iteration 9: is the LARGE size a public, decision-level function of the fee-aware edge (fee9) at the decision instant?
Taker-first cluster orders of 10-31 14:55-17:55 with calldata size Z (large = Z >= 90) and the match ms m0 (raw feed). At the
last 100-ms grid point at or before m0 - 50 of the same window (stale9 grids A, B, C; lab feeds): V_1 = 100 Delta_o move - cost,
gain, cost, the tick toward o over [t - 500, t), |ask - 0.5|, rel. Within-wallet AUC of large for each, and pooled.
Usage: python size9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, ins9, fee9
from sklearn.metrics import roc_auc_score

C = L.C


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    o, _ = ins9.load_orders(1793458456, 1793469300)
    tokmap = {}; txms = {}
    for r in L.recs("btc5m_clob_raw2", 1793458456 - 600, 1793469300 + 400):
        k = r.get("k")
        if k == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
        elif k == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna() & o.Z.notna() & (o["first"] == "T")].copy()
    o["m0"] = o.tx0.str.lower().map(txms); o = o[o.m0.notna()].copy(); o["Lx"] = o.Lim.fillna(o.px0)
    rows = []
    for nm in ("A", "B", "C"):
        a, b = stale9.IV[nm]
        gd, tk, S = stale9.grid(a, b, lost)
        t = gd["t"]; st = gd["st"]
        acc = np.zeros(len(t)); n = np.zeros(len(t))
        from lag7 import mv
        for key in stale9.BTCK:
            if key in S:
                r_ = mv(S, key, t - 600, t - 100); acc += np.nan_to_num(r_); n += np.isfinite(r_)
        move = np.where(n > 0, acc / np.maximum(n, 1), np.nan)
        sub = o[(o.m0 >= a * 1000) & (o.m0 < b * 1000)]
        for r in sub.itertuples():
            j = np.searchsorted(t, r.m0 - 50, "right") - 1
            while j >= 0 and st[j] != r.mstart and t[j] > r.m0 - 3000:
                j -= 1
            if j < 0 or st[j] != r.mstart:
                continue
            D = gd[bool(r.is_up)]; sg = 1.0 if r.is_up else -1.0
            ask = D["ask"][j]; mid = D["mid"][j]
            if not (np.isfinite(ask) and np.isfinite(mid) and np.isfinite(move[j])):
                continue
            mo = min(max(mid, 0.01), 0.99)
            dl = norm.pdf(norm.ppf(mo)) / (stale9.SIG * np.sqrt(gd["tau"][j]))
            gain = 100 * dl * sg * move[j]; cost = 100 * ((ask - mo) + 0.035 * ask * (1 - ask))
            rows.append((r.w, r.Z, gain - cost, gain, cost, sg * gd["tick"][j], abs(ask - 0.5), r.m0 / 1000 - r.mstart, ask, r.Lx > ask + 1e-6))
    R = pd.DataFrame(rows, columns=["w", "Z", "V", "gain", "cost", "tick", "dist", "rel", "ask", "payup"])
    R["large"] = R.Z >= 90
    res = {"n": int(len(R)), "large": int(R.large.sum())}
    for w, g in list(R.groupby("w")) + [("pooled", R)]:
        if g.large.nunique() < 2:
            continue
        res[w] = {"n": int(len(g)), "n_large": int(g.large.sum())}
        for f_ in ("V", "gain", "cost", "tick", "dist", "rel", "ask"):
            res[w][f"auc_{f_}"] = round(float(roc_auc_score(g.large, g[f_])), 4)
        res[w]["P(large|V>0)"] = [round(float(g.large[g.V > 0].mean()), 4) if (g.V > 0).any() else None, int((g.V > 0).sum())]
        res[w]["P(large|V<=0)"] = round(float(g.large[g.V <= 0].mean()), 4)
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

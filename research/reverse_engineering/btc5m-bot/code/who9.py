"""Iteration 9 (panel iter8 information P3, part; assumptions P1 'signature if false'): WHO took the ask of o that the
cluster's lost races were aimed at? For every maker-first cluster order classified as a lost race (ins9b: the limit was o's ask
within 300 ms / 1 s before its insertion), the trades BUYING o at the order's limit L in [s_ins - 1000, s_ins + 20] ms of my
unthrottled feed (btc5m_clob_raw2 'x' records, server ms, tx hash): the taker is the CLUSTER (tx is one of its taker txs) or
ANOTHER trader. By wallet and size (XM's 60-share class), with the lag from that trade to the insertion.
Usage: python who9.py START END OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L

C = L.C
EX = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}


def main(a, b, out):
    M = pd.read_parquet(C + "/it9/ins9b_M.parquet")
    d = pd.read_parquet(C + "/it9/own_1231_12_18.parquet")
    d["role"] = np.where(d.cp.isin(EX), "T", "M"); d["w"] = d.owner.map(L.W)
    dt = d[d.role == "T"].reset_index(drop=True); dt["txl"] = dt.tx.str.lower(); ctx = dt.groupby("txl").w.first().to_dict()
    tr = []
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        if r.get("k") == "x" and r.get("d") == "BUY":
            tr.append((int(r["s"]), int(r["m"]), int(r.get("u") or 0), round(float(r["p"]), 4), float(r["z"]), (r.get("h") or "").lower()))
    T = pd.DataFrame(tr, columns=["s", "m", "u", "p", "z", "h"])
    T["who"] = T.h.map(ctx).fillna("other")
    keyed = {k: g.sort_values("s") for k, g in T.groupby(["m", "u", "p"])}
    rows = []
    for r in M.itertuples():
        g = keyed.get((int(r.mstart), int(bool(r.is_up)), round(float(r.L), 4)))
        if g is None:
            rows.append((r.w, r.Z, r.rcls, "none", np.nan)); continue
        s = g.s.to_numpy()
        k = (s >= r.s_ins - 1000) & (s <= r.s_ins + 20)
        if not k.any():
            rows.append((r.w, r.Z, r.rcls, "none", np.nan)); continue
        gg = g[k]
        # the latest trade before the insertion
        j = gg.iloc[-1]
        who = j.who
        rows.append((r.w, r.Z, r.rcls, who if who != r.w else "self", r.s_ins - j.s))
    R = pd.DataFrame(rows, columns=["w", "Z", "rcls", "taker", "lag"])
    R["taker_c"] = np.where(R.taker.isin(["DS", "GF", "XM", "self"]), "cluster", R.taker)
    res = {}
    for nm, g in (("all_lost", R[R.rcls.isin(["lost_300", "lost_1000"])]), ("lost_300", R[R.rcls == "lost_300"]),
                  ("passive_2s", R[R.rcls == "passive_2s"])):
        res[nm] = {"n": int(len(g)), "taker": g.taker_c.value_counts(normalize=True).round(4).to_dict(),
                   "by_wallet": {w: gg.taker.value_counts(normalize=True).round(3).to_dict() for w, gg in g.groupby("w")},
                   "lag_ms_q_cluster": [float(x) for x in np.nanpercentile(g[g.taker_c == "cluster"].lag, [10, 50, 90])] if (g.taker_c == "cluster").any() else None,
                   "lag_ms_q_other": [float(x) for x in np.nanpercentile(g[g.taker_c == "other"].lag, [10, 50, 90])] if (g.taker_c == "other").any() else None}
    g = R[(R.w == "XM") & (R.Z == 60) & R.rcls.isin(["lost_300", "lost_1000"])]
    res["XM60_lost"] = {"n": int(len(g)), "taker": g.taker.value_counts(normalize=True).round(4).to_dict(),
                        "lag_ms_q": [float(x) for x in np.nanpercentile(g.lag, [10, 50, 90])] if g.lag.notna().any() else None}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])

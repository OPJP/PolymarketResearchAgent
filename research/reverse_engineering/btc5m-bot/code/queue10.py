"""Iteration 10 (X73 step 5, panel iter9 information P1): is the race a FIFO queue in the 150-ms delay buffer?
Each cluster decision arrives at a = m - D (won race, taker-first order matched at m) or a = s_ins - D (lost race placed on the book
unmatched at s_ins, located in it9/ins9b_M). Orders of other takers on the same outcome that arrived in [a - D, a) are AHEAD in the
queue; they are matched in [a, a + D). Count them from the crowd's matches (non-operator taker BUYs of o in every recorded BTC 5m
match tx of 10-31 14:55-17:55, calldata it9/cd9 + it10/cdall10, match ms from it10/txms10): k_ahead = crowd matches on o in
[a, a + D) and their shares. Compare won vs lost races: P(won | k_ahead = 0 / 1 / 2+), and the ahead shares vs the cluster
order's size. Also the crowd matches in [a - D, a) (orders that arrived before a - D: already gone before the cluster's view).
Usage: python queue10.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9

C = L.C
A, B = 1793458500, 1793469300
D = 150
OPS = set(L.W) | {"0xd84403efd50b49a1d8a7181627e00307e6ea5908"}


def main(out):
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", A - 600, B + 60):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    tm = pd.read_parquet(C + "/it10/txms10.parquet"); mt = dict(zip(tm.tx, tm.m))
    cd = pd.concat([pd.read_parquet(C + "/it9/cd9.parquet"), pd.read_parquet(C + "/it10/cdall10.parquet")], ignore_index=True)
    cd["m"] = cd.tx.str.lower().map(mt)
    cr = cd[(cd.role == "T") & ~cd.maker.isin(OPS) & (cd.oside == 0) & cd.m.notna()].drop_duplicates(["tx", "maker", "token"]).copy()
    cr["st"] = cr.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[0]); cr["up"] = cr.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[1])
    cr = cr[cr.st.notna()]
    cr["sh"] = cr.taker_amt.astype(float)
    crg = {k: (np.sort(g.m.to_numpy(np.int64)), g.sort_values("m").sh.to_numpy(float)) for k, g in cr.groupby(["st", "up"])}
    o, _ = ins9.load_orders(A, B)
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy()
    o["m0"] = o.tx0.str.lower().map(mt)
    won = o[(o["first"] == "T") & o.m0.notna()]
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet"); Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])]
    ev = pd.concat([pd.DataFrame({"st": won.mstart.astype(int), "up": won.is_up.astype(bool), "a": won.m0.astype(np.int64) - D, "won": True, "Z": won.Z.astype(float), "w": won.w}),
                    pd.DataFrame({"st": Mi.mstart.astype(int), "up": Mi.is_up.astype(bool), "a": Mi.s_ins.astype(np.int64) - D, "won": False, "Z": Mi.Z.astype(float), "w": Mi.w})], ignore_index=True)
    k_ahead = np.zeros(len(ev)); sh_ahead = np.zeros(len(ev)); k_before = np.zeros(len(ev))
    for i, (st, up, a) in enumerate(zip(ev.st.to_numpy(), ev.up.to_numpy(), ev.a.to_numpy(np.int64))):
        g = crg.get((float(st), bool(up))) or crg.get((int(st), bool(up)))
        if g is None:
            continue
        ms, sh = g
        j0 = np.searchsorted(ms, a, "left"); j1 = np.searchsorted(ms, a + D, "left"); jb = np.searchsorted(ms, a - D, "left")
        k_ahead[i] = j1 - j0; sh_ahead[i] = sh[j0:j1].sum(); k_before[i] = j0 - jb
    ev["k_ahead"] = k_ahead; ev["sh_ahead"] = sh_ahead; ev["k_before"] = k_before
    res = {"decisions": int(len(ev)), "won": int(ev.won.sum()), "lost_located": int((~ev.won).sum()), "crowd_buys": int(len(cr))}
    res["P(won | k_ahead)"] = {lab: [round(float(ev.won[s].mean()), 4), int(s.sum())] for lab, s in
                               (("0", ev.k_ahead == 0), ("1", ev.k_ahead == 1), ("2+", ev.k_ahead >= 2))}
    res["P(won | crowd matches in [a - D, a))"] = {lab: [round(float(ev.won[s].mean()), 4), int(s.sum())] for lab, s in
                                                   (("0", ev.k_before == 0), ("1+", ev.k_before >= 1))}
    res["k_ahead_mean_won_vs_lost"] = [round(float(ev.k_ahead[ev.won].mean()), 3), round(float(ev.k_ahead[~ev.won].mean()), 3)]
    res["P(k_ahead >= 1) won vs lost"] = [round(float((ev.k_ahead[ev.won] >= 1).mean()), 4), round(float((ev.k_ahead[~ev.won] >= 1).mean()), 4)]
    res["by_wallet P(won | k_ahead 0 / 1+)"] = {w: [round(float(g.won[g.k_ahead == 0].mean()), 4) if (g.k_ahead == 0).any() else None,
                                                  round(float(g.won[g.k_ahead >= 1].mean()), 4) if (g.k_ahead >= 1).any() else None, int(len(g))] for w, g in ev.groupby("w")}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

"""Iteration 11 (panel iter10 mechanics P2 = X93, first step): how deterministic is a race on the RECORDED book, as a function of
the arrival-time error a replica would make? For every live decision of 10-31 14:55-17:55 (won race: taker-first order, limit L,
arrival a = match - 150; lost race: located maker-first insertion, a = insertion - 150), the recorded o-ask (btc5m_clob_raw2
touch) at the would-be match time a + 150 + delta for delta < 0 only (an EARLIER arrival sees the real book, before the wallet's
own order touched it; a later one would need the unobservable counterfactual of the liquidity the wallet took). Flip rate:
won races with ask(a + 150 + delta) > L (an earlier replica would have missed), lost races with ask(a + 150 + delta) <= L (an
earlier replica would have won), delta in -10 .. -150 ms; and the same with a symmetric jitter |delta| <= sigma on the lost
races (whose book after a + 150 is real: the wallet did not take anything). Also P(won) for near-ties: another cluster or crowd
taker arrival on o within 5 ms of a vs clear arrivals (an engine lottery inside the hold would show here).
Usage: python race11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9, gate8

C = L.C
A, B = 1793458500, 1793469300
OPS = set(L.W) | {"0xd84403efd50b49a1d8a7181627e00307e6ea5908"}


def r4(x):
    return round(float(x), 4)


def main(out):
    o, _ = ins9.load_orders(A, B)
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", A - 600, B + 60):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    tm = pd.read_parquet(C + "/it10/txms10.parquet"); mt = dict(zip(tm.tx, tm.m))
    o["st"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.st.notna()].copy(); o["m0"] = o.tx0.str.lower().map(mt)
    T = o[(o["first"] == "T") & o.m0.notna() & o.Lim.notna()]
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet"); Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])]
    D = pd.concat([pd.DataFrame({"st": T.st.astype(int), "up": T.up.astype(bool), "a": T.m0.astype(np.int64) - 150, "L": T.Lim.astype(float), "won": True, "w": T.w}),
                   pd.DataFrame({"st": Mi.mstart.astype(int), "up": Mi.is_up.astype(bool), "a": Mi.s_ins.astype(np.int64) - 150, "L": Mi.L.astype(float), "won": False, "w": Mi.w})], ignore_index=True)
    R = gate8.raw_touch("btc5m_clob_raw2", A, B)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    deltas = np.array([-1, -5, -10, -25, -50, -75, -100, -150, -200, -300])
    ok = np.zeros((len(D), len(deltas)), float) * np.nan
    pos = np.zeros((len(D), 7)) * np.nan  # lost races: ask at a + 150 + d for d = +10..+150 (real book; the wallet took nothing)
    dpos = np.array([1, 10, 25, 50, 75, 100, 150])
    for i, (st, up, a, Lm) in enumerate(zip(D.st.to_numpy(), D.up.to_numpy(), D.a.to_numpy(np.int64), D.L.to_numpy(float))):
        x = tch.get(int(st))
        if x is None:
            continue
        rs, bb, ba = x
        def ask(t):
            j = np.searchsorted(rs, t, "right") - 1
            v = np.where(j >= 0, (ba if up else 1 - bb)[np.clip(j, 0, None)], np.nan)
            return np.round(v, 4)
        ok[i] = ask(a + 150 + deltas) <= Lm + 1e-6
        pos[i] = ask(a + 150 + dpos) <= Lm + 1e-6
    won = D.won.to_numpy(bool)
    res = {"decisions": int(len(D)), "won": int(won.sum()), "lost": int((~won).sum())}
    res["won: P(ask <= L at match + delta) for earlier arrivals"] = {int(d): r4(np.nanmean(ok[won, k])) for k, d in enumerate(deltas)}
    res["lost: P(ask <= L at a + 150 + delta) for earlier arrivals (would have won)"] = {int(d): r4(np.nanmean(ok[~won, k])) for k, d in enumerate(deltas)}
    res["lost: P(ask <= L at a + 150 + delta) for later arrivals"] = {int(d): r4(np.nanmean(pos[~won, k])) for k, d in enumerate(dpos)}
    # flip probability under a uniform earlier-arrival error of up to sigma (won and lost pooled, earlier side only)
    for sig in (10, 25, 50, 100, 150):
        ks = [k for k, d in enumerate(deltas) if -sig <= d < 0]
        fw = 1 - np.nanmean(ok[won][:, ks]); fl = np.nanmean(ok[~won][:, ks])
        res.setdefault("flip_rate_earlier_arrival_up_to_sigma", {})[sig] = {"won_flip": r4(fw), "lost_flip": r4(fl),
                                                                            "pooled": r4((fw * won.sum() + fl * (~won).sum()) / len(D))}
    # near-ties: another operator decision arrival on the same outcome within 5 ms
    D = D.sort_values(["st", "up", "a"]).reset_index(drop=True)
    gap = D.groupby(["st", "up"]).a.diff().abs()
    gap2 = D.groupby(["st", "up"]).a.diff(-1).abs()
    near = (np.fmin(gap.fillna(1e9), gap2.fillna(1e9)) <= 5).to_numpy()
    res["P(won) operator near-tie (another operator arrival within 5 ms) vs clear"] = [r4(D.won[near].mean()) if near.any() else None, int(near.sum()),
                                                                                      r4(D.won[~near].mean()), int((~near).sum())]
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

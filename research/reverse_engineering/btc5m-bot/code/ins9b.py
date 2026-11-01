"""Iteration 9, follow-up of ins9.py: refined classification of the cluster's maker-first orders by the ask path of o BEFORE
the insertion (a lost race = the limit was o's ask at some instant in [s - W, s - 20] ms, W = 300 / 1000 ms: a taker order that
arrived after the ask left; passive = the limit was never at o's ask in the 2 s before the insertion), the same "view age"
profile for won races (limit == ask of o at m - d), votes by refined class (8 lab series), and the implied decision count.
Usage: python ins9b.py START END OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9

C = L.C


def stream_touch(a, b):
    touch = {}; txms = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        k = r.get("k")
        if k == "p" and r.get("bb") is not None and r.get("ba") is not None:
            t = touch.setdefault(int(r["m"]), [])
            if not t or t[-1][1] != r["bb"] or t[-1][2] != r["ba"]:
                t.append((int(r["s"]), float(r["bb"]), float(r["ba"])))
        elif k == "f" and r.get("u") == 1 and r.get("b") and r.get("o"):
            bb = max(p for p, z in r["b"]); ba = min(p for p, z in r["o"])
            touch.setdefault(int(r["m"]), []).append((int(r["s"]), float(bb), float(ba)))
        elif k == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    return {m: np.array(sorted(v), float) for m, v in touch.items()}, txms


def ask_path(T, s, up, lo, hi):
    """o's ask at every touch change in [s - lo, s - hi] plus the value in force at s - lo."""
    i0 = np.searchsorted(T[:, 0], s - lo, "left") - 1; i1 = np.searchsorted(T[:, 0], s - hi, "left") - 1
    i0 = max(i0, 0)
    seg = T[i0:i1 + 1]
    if not len(seg):
        return np.array([])
    return seg[:, 2] if up else 1 - seg[:, 1]


def main(a, b, out):
    M = pd.read_parquet(C + "/it9/ins9_M.parquet")
    M = M[M.found].copy()
    o, fills = ins9.load_orders(a, b)
    touch, txms = stream_touch(a, b)
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy(); o["mstart"] = o.mstart.astype(int); o["Lx"] = o.Lim.fillna(o.px0)
    o["m0"] = o.tx0.str.lower().map(txms)
    res = {}
    # refined classes for M-first orders
    cls = []
    for r in M.itertuples():
        T = touch.get(int(r.mstart))
        if T is None:
            cls.append(("na", np.nan, np.nan)); continue
        p300 = ask_path(T, r.s_ins, r.is_up, 300, 20); p1000 = ask_path(T, r.s_ins, r.is_up, 1000, 20)
        p2000 = ask_path(T, r.s_ins, r.is_up, 2000, 0)
        at300 = bool(len(p300) and np.any(p300 <= r.L + 1e-6)); at1000 = bool(len(p1000) and np.any(p1000 <= r.L + 1e-6))
        never = bool(len(p2000) and np.all(p2000 > r.L + 1e-6))
        c = "lost_300" if at300 else ("lost_1000" if at1000 else ("passive_2s" if never else "other"))
        mn = float(np.min(p2000)) if len(p2000) else np.nan
        cls.append((c, mn, float(p2000[-1]) if len(p2000) else np.nan))
    M["rcls"] = [c for c, _, _ in cls]; M["min_ask2s"] = [x for _, x, _ in cls]; M["ask_at_ins"] = [x for _, _, x in cls]
    M["gap_to_min_ask_c"] = ((M.min_ask2s - M.L) * 100).round(2)
    res["M_first_refined"] = {"n": int(len(M)), "class": M.rcls.value_counts().to_dict(),
                              "class_unambiguous": M[M.ncand == 1].rcls.value_counts().to_dict(),
                              "class_by_wallet_size": {f"{w}_{int(z) if z == z else 'na'}": g.rcls.value_counts().to_dict()
                                                       for (w, z), g in M.groupby(["w", M.Z.fillna(-1)]) if len(g) >= 10},
                              "passive_2s_gap_to_min_ask_c": M[M.rcls == "passive_2s"].gap_to_min_ask_c.clip(0, 6).value_counts().sort_index().to_dict(),
                              "passive_2s_vs_bid100_c": M[M.rcls == "passive_2s"].vs_bid_c.clip(-4, 4).value_counts().sort_index().to_dict()}
    # view age of won races: share with limit == o's ask at m0 - d (and >= ask)
    won = o[(o["first"] == "T") & o.m0.notna()]
    prof = {}
    for d in (20, 50, 100, 150, 200, 300, 500, 1000):
        eq = []
        for r in won.itertuples():
            T = touch.get(int(r.mstart))
            if T is None:
                continue
            i = np.searchsorted(T[:, 0], r.m0 - d, "left") - 1
            if i < 0:
                continue
            ask = T[i, 2] if r.is_up else 1 - T[i, 1]
            eq.append((abs(ask - r.Lx) < 1e-6, r.Lx >= ask - 1e-6))
        eq = np.array(eq)
        prof[str(d)] = [round(float(eq[:, 0].mean()), 4), round(float(eq[:, 1].mean()), 4), int(len(eq))]
    res["won_race_limit_vs_ask_at_m_minus_d"] = {"cols": ["limit==ask", "limit>=ask", "n"], **prof}
    # M-first: same profile at s_ins - d
    prof = {}
    for d in (20, 50, 100, 150, 200, 300, 500, 1000):
        eq = []
        for r in M.itertuples():
            T = touch.get(int(r.mstart))
            if T is None:
                continue
            i = np.searchsorted(T[:, 0], r.s_ins - d, "left") - 1
            if i < 0:
                continue
            ask = T[i, 2] if r.is_up else 1 - T[i, 1]
            eq.append((abs(ask - r.L) < 1e-6, r.L >= ask - 1e-6))
        eq = np.array(eq)
        prof[str(d)] = [round(float(eq[:, 0].mean()), 4), round(float(eq[:, 1].mean()), 4), int(len(eq))]
    res["M_first_limit_vs_ask_at_ins_minus_d"] = {"cols": ["limit==ask", "limit>=ask", "n"], **prof}
    # votes by refined class
    ser = ins9.load_venues(a, b)
    rng = np.random.default_rng(19)
    vres = {}
    for c, g in list(M.groupby("rcls")) + [("XM60_all", M[(M.w == "XM") & (M.Z == 60)]), ("XM60_passive_2s", M[(M.w == "XM") & (M.Z == 60) & (M.rcls == "passive_2s")]),
                                          ("DSGF_passive_2s", M[(M.w != "XM") & (M.rcls == "passive_2s")])]:
        if not len(g):
            continue
        tt = g.s_ins.to_numpy(np.int64); up = g.is_up.to_numpy(bool)
        v, cv = ins9.vote_at(ser, tt)
        vres[c] = ins9.summarize_vote(v, cv, up, c)
        pl = tt + (rng.choice([-1, 1], len(tt)) * rng.uniform(5000, 60000, len(tt))).astype(np.int64)
        vp, cvp = ins9.vote_at(ser, pl)
        vres[c]["placebo"] = ins9.summarize_vote(vp, cvp, up, c)["agree_on_voted"]
        # earlier window: the bot saw the tick earlier if its order is late
        v2, cv2 = ins9.vote_at(ser, tt, 1000, 200)
        vres[c]["vote_1000_200"] = ins9.summarize_vote(v2, cv2, up, c)["agree_on_voted"]
    res["vote_by_refined_class"] = vres
    # decisions per filled order with the refined lost-race count
    pi = 0.4583
    nT = int((o["first"] == "T").sum())
    lost = int(M.rcls.isin(["lost_300", "lost_1000"]).sum()); passive = int((M.rcls == "passive_2s").sum()); other = int((M.rcls == "other").sum() + (M.rcls == "na").sum())
    nM_all = int((o["first"] == "M").sum()); unk = nM_all - lost - passive - other
    for nm, lost_n in (("lost_300+1000", lost), ("lost_300+1000+other", lost + other)):
        fl = lost_n / max(lost_n + passive, 1)
        Ml = lost_n + fl * unk
        D = nT + Ml / pi + (nM_all - Ml)
        res.setdefault("decisions", {})[nm] = {"T_first": nT, "M_lost": round(Ml, 1), "M_rest": round(nM_all - Ml, 1),
                                               "decisions": round(D, 1), "q": round(float(len(o) / D), 4)}
    M.to_parquet(C + "/it9/ins9b_M.parquet")
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:7000])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])

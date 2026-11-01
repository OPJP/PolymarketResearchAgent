"""Iteration 9 (PIVOT: the decision record from the book; panel iter8 assumptions P1 + P2, mechanics P3 step 1, information P3
part). Unit of decision = the BOOK INSERTION of a cluster order, not the race-winning match.

For every cluster order of 10-31 14:14-17:55 UTC (development block 12-18) with a maker fill, from on-chain fills (order hash,
role, tx) + V2 calldata (original size Z, limit L, signing ms) + my unthrottled book (btc5m_clob_raw2, server ms):
  * M-first orders (first fill is a maker fill): the insertion = the latest size increment of exactly Z at (o, L) in the Up
    book (BUY Up at L -> bid L; BUY Down at L -> Up ask at 1 - L) before the first maker fill (<= 136 s); classified by the
    ask of o SEEN 50-300 ms before the insertion: limit >= ask seen = LOST RACE (submitted to take, the ask left first);
    limit < ask seen = PASSIVE QUOTE (distance to the bid recorded).
  * MT orders (taker first, remainder R = Z - taker shares): the remainder's insertion at the match is the truth set for the
    insertion finder (found within [m0 - 100, m0 + 300] ms?).
  * P(remainder refills) = pi_rem from on-chain fills + calldata (T-first orders with R > 0).
  * Lab vote (8 series: Binance USD-M bf, spot bs, OKX ok, Bybit by; BTC + ETH/1.235; microprice; [s-600, s-100) ms; tick
    > 0.002 bp) at: won races (taker matches m0), lost-race insertions, passive insertions, and placebo instants (+-5..60 s).
  * Gate check: change of o's ask over [s - 500, s) at won races vs lost-race insertions (is "the hazard doubles when o's ask
    falls" a race-outcome filter?).
  * Decisions per filled order: q = P(fill | decision) = (T + M_lost) / (T + M_lost / pi_rem).
Usage: python ins9.py START END OUT_JSON"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L

C = L.C
EX = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}
W = L.W
VEN = ("bf", "bs", "ok", "by")
ETH_SCALE = 1.235
TICK = 0.002


def load_orders(a, b):
    d = pd.read_parquet(C + "/it9/own_1231_12_18.parquet")
    d = d[(d.ts >= a - 200) & (d.ts < b + 200)].copy()
    d["role"] = np.where(d.cp.isin(EX), "T", "M")
    d["w"] = d.owner.map(W)
    d["sh"] = d.tamt / 1e6; d["px"] = (d.mamt / d.tamt).round(4)
    d = d.sort_values(["block", "li"])
    cds = [pd.read_parquet(f) for f in glob.glob(C + "/post/cd*.parquet")]
    if os.path.exists(C + "/it9/cd9.parquet"):
        cds.append(pd.read_parquet(C + "/it9/cd9.parquet"))
    cd = pd.concat(cds, ignore_index=True)
    cd = cd[cd.maker.isin(list(W))].copy()
    cd["token"] = cd.token.astype(str)
    cd["Z"] = cd.taker_amt.astype(float); cd["Lim"] = (cd.maker_amt.astype(float) / cd.taker_amt.astype(float)).round(4)
    cd = cd.drop_duplicates(["tx", "maker", "token", "role", "Z", "Lim", "sign_ms"])
    key = cd.groupby(["tx", "maker", "token", "role"]).agg(Z=("Z", "first"), Lim=("Lim", "first"), sign_ms=("sign_ms", "first"),
                                                          ncd=("Z", "size")).reset_index()
    d["token"] = d.token.astype(str)
    d = d.merge(key, left_on=["tx", "owner", "token", "role"], right_on=["tx", "maker", "token", "role"], how="left")
    g = d.groupby("oh", sort=False)
    o = g.agg(w=("w", "first"), token=("token", "first"), ts0=("ts", "min"), first=("role", "first"),
              hasT=("role", lambda x: (x == "T").any()), hasM=("role", lambda x: (x == "M").any()),
              shT=("sh", lambda x: 0.0), Z=("Z", "first"), Lim=("Lim", "first"), sign_ms=("sign_ms", "first"),
              px0=("px", "first")).reset_index()
    shT = d[d.role == "T"].groupby("oh").sh.sum(); shM = d[d.role == "M"].groupby("oh").sh.sum()
    o["shT"] = o.oh.map(shT).fillna(0.0); o["shM"] = o.oh.map(shM).fillna(0.0)
    tx0 = d.groupby("oh").tx.first(); o["tx0"] = o.oh.map(tx0)
    txM = d[d.role == "M"].groupby("oh").tx.first(); o["txM"] = o.oh.map(txM)
    o = o[(o.ts0 >= a) & (o.ts0 < b)]
    return o, d


def stream_book(a, b, targets):
    """targets: set of (m, side, price) levels whose size history is kept. Returns tok map, touch arrays per window,
    level histories, trade ms by tx hash (min server ms), all trades (s, m, u, p, z, d)."""
    tok = {}
    books = {}; touch = {}; lev = {k: [] for k in targets}; txms = {}; trades = []
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        k = r.get("k")
        if k == "S":
            tok[str(r["u"])] = (int(r["m"]), True); tok[str(r["d"])] = (int(r["m"]), False)
        elif k == "f":
            if r.get("u") == 1:
                mm = int(r["m"])
                books[mm] = {"B": {round(p, 4): z for p, z in r["b"]}, "S": {round(p, 4): z for p, z in r["o"]}}
                bb = max(books[mm]["B"], default=np.nan); ba = min(books[mm]["S"], default=np.nan)
                touch.setdefault(mm, []).append((int(r["s"]), bb, ba))
        elif k == "p":
            mm = int(r["m"]); sd = r["d"]; p = round(float(r["p"]), 4)
            bk = books.setdefault(mm, {"B": {}, "S": {}})[sd]
            prev = bk.get(p, 0.0); new = float(r["z"] or 0.0)
            if new == 0:
                bk.pop(p, None)
            else:
                bk[p] = new
            key = (mm, sd, p)
            if key in lev:
                lev[key].append((int(r["s"]), new, new - prev))
            if r.get("bb") is not None and r.get("ba") is not None:
                t = touch.setdefault(mm, [])
                if not t or t[-1][1] != r["bb"] or t[-1][2] != r["ba"]:
                    t.append((int(r["s"]), float(r["bb"]), float(r["ba"])))
        elif k == "x":
            h = (r.get("h") or "").lower()
            if h:
                txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
            trades.append((int(r["s"]), int(r["m"]), int(r.get("u") or 0), float(r["p"]), float(r["z"]), r.get("d"), h))
    touch = {mm: np.array(sorted(v), float) for mm, v in touch.items()}
    return tok, touch, lev, txms, trades


def at_touch(T, s):
    """(bb, ba) of the Up book at the last change strictly before s."""
    i = np.searchsorted(T[:, 0], s, "left") - 1
    if i < 0:
        return np.nan, np.nan
    return T[i, 1], T[i, 2]


def load_venues(a, b):
    rows = {}
    for r in L.recs("btc5m_venues2", a - 5, b + 5):
        v = r.get("v")
        if v in VEN and r.get("b") and r.get("a"):
            rows.setdefault((v, r["y"]), []).append((r.get("E") or 0, r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    ser = {}
    off = None
    if ("bf", "BTC") in rows:
        x = np.array(rows[("bf", "BTC")], float); off = float(np.median(x[:, 1] - x[:, 0]))
    for key, lst in rows.items():
        x = np.array(lst, float)
        T = x[:, 0] if key[0] != "bs" and np.all(x[:, 0] > 0) else x[:, 1] - (off or 0)
        o = np.argsort(T, kind="stable"); x = x[o]; T = T[o].astype(np.int64)
        mic = (x[:, 2] * x[:, 5] + x[:, 4] * x[:, 3]) / np.maximum(x[:, 3] + x[:, 5], 1e-12)
        ser[key] = (T, mic, ETH_SCALE if key[1] == "ETH" else 1.0)
    return ser


def vote_at(ser, tt, w0=600, w1=100):
    tt = np.asarray(tt, np.int64)
    Q = []
    for key in sorted(ser):
        T, mic, sc = ser[key]
        i0 = np.searchsorted(T, tt - w0, "right") - 1; i1 = np.searchsorted(T, tt - w1, "right") - 1
        r = (mic[np.clip(i1, 0, len(mic) - 1)] / mic[np.clip(i0, 0, len(mic) - 1)] - 1) * 1e4 / sc
        r[(i0 < 0) | (tt < T[0] + 3000) | (tt > T[-1] - 500)] = np.nan
        Q.append(r)
    Q = np.vstack(Q)
    cov = np.isfinite(Q).any(axis=0)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > TICK), axis=0)
    return vote, cov


def summarize_vote(vote, cov, up, name):
    k = cov & (vote != 0)
    ok = (vote > 0) == up
    st = np.abs(vote)
    out = {"n": int(len(up)), "covered": int(cov.sum()), "voted_share": round(float(k.sum() / max(cov.sum(), 1)), 4),
           "agree_on_voted": round(float(ok[k].mean()), 4) if k.any() else None,
           "by_strength": {}}
    for lo, hi, nm in ((1, 1, "1"), (2, 2, "2"), (3, 4, "3-4"), (5, 99, "5+")):
        s = k & (st >= lo) & (st <= hi)
        if s.any():
            out["by_strength"][nm] = [round(float(ok[s].mean()), 4), int(s.sum())]
    return out


def main(a, b, out_path):
    o, fills = load_orders(a, b)
    print("orders", len(o), o["first"].value_counts().to_dict(), "with calldata", int(o.Z.notna().sum()), flush=True)
    # token -> window/outcome from the subscriptions of the raw feed (first pass is cheap: S records only)
    targets = set()
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 400):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0])
    o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy()
    o["mstart"] = o.mstart.astype(int)
    o["Lx"] = o.Lim.fillna(o.px0)
    for r in o.itertuples():
        side = "B" if r.is_up else "S"; p = round(r.Lx if r.is_up else 1 - r.Lx, 4)
        targets.add((r.mstart, side, p))
    print("targets", len(targets), flush=True)
    tok, touch, lev, txms, trades = stream_book(a, b, targets)
    print("book streamed: windows", len(touch), "tx ms", len(txms), "trades", len(trades), flush=True)
    o["m0"] = o.tx0.str.lower().map(txms)
    o["m1"] = o.txM.str.lower().map(txms)
    res = {"interval": [a, b], "orders": int(len(o)), "first_role": o["first"].value_counts().to_dict(),
           "calldata_share": round(float(o.Z.notna().mean()), 4)}
    # ---- remainders: pi_rem (P(any maker fill | remainder > 0)) for T-first orders with calldata
    tf = o[(o["first"] == "T") & o.Z.notna()].copy()
    tf["R"] = (tf.Z - tf.shT - (tf.shM * 0)).round(4)
    rem = tf[tf.R > 0.5]
    res["T_first"] = {"n": int(len(tf)), "with_remainder": int(len(rem)), "remainder_share": round(float(len(rem) / max(len(tf), 1)), 4),
                      "pi_rem": round(float(rem.hasM.mean()), 4) if len(rem) else None,
                      "pi_rem_by_wallet": {w: [round(float(g.hasM.mean()), 4), int(len(g))] for w, g in rem.groupby("w")}}
    # ---- truth set for the insertion finder: MT remainders inserted at the match
    found_mt = []
    for r in rem[rem.m0.notna()].itertuples():
        side = "B" if r.is_up else "S"; p = round(r.Lx if r.is_up else 1 - r.Lx, 4)
        h = lev.get((r.mstart, side, p), [])
        hit = [s for s, z, dz in h if abs(dz - r.R) < 0.02 and r.m0 - 100 <= s <= r.m0 + 400]
        found_mt.append((r.oh, r.w, len(hit) > 0, (hit[0] - r.m0) if hit else np.nan))
    fm = pd.DataFrame(found_mt, columns=["oh", "w", "found", "lag"])
    res["truth_remainder_insertion"] = {"n": int(len(fm)), "found_share": round(float(fm.found.mean()), 4) if len(fm) else None,
                                        "lag_ms_q": [float(x) for x in np.nanpercentile(fm.lag, [10, 50, 90])] if fm.found.any() else None}
    # ---- M-first orders: insertion, classification
    mf = o[(o["first"] == "M") & o.m1.notna()].copy()
    rows = []
    for r in mf.itertuples():
        side = "B" if r.is_up else "S"; p = round(r.Lx if r.is_up else 1 - r.Lx, 4)
        h = lev.get((r.mstart, side, p), [])
        Z = r.Z if r.Z == r.Z else None
        cands = [(s, z, dz) for s, z, dz in h if r.m1 - 136000 <= s <= r.m1 + 50 and dz > 0.5 and
                 ((Z is not None and abs(dz - Z) < 0.02) or (Z is None and abs(dz - round(dz)) < 0.02 and dz >= r.shM - 0.02))]
        if r.sign_ms == r.sign_ms:
            cands = [c for c in cands if c[0] >= r.sign_ms - 2000]
        if not cands:
            rows.append((r.oh, r.w, r.is_up, r.Lx, Z, r.mstart, r.m1, np.nan, 0) + (np.nan,) * 10)
            continue
        s_ins = cands[-1][0]
        T = touch.get(r.mstart)
        vals = []
        for dl in (50, 100, 150, 300):
            bb, ba = at_touch(T, s_ins - dl) if T is not None else (np.nan, np.nan)
            ask = ba if r.is_up else 1 - bb; bid = bb if r.is_up else 1 - ba
            vals += [ask, bid]
        bb5, ba5 = at_touch(T, s_ins - 500) if T is not None else (np.nan, np.nan)
        ask500 = ba5 if r.is_up else 1 - bb5
        rows.append((r.oh, r.w, r.is_up, r.Lx, Z, r.mstart, r.m1, s_ins, len(cands)) + tuple(vals) + (ask500, r.sign_ms))
    cols = ["oh", "w", "is_up", "L", "Z", "mstart", "m1", "s_ins", "ncand", "ask50", "bid50", "ask100", "bid100", "ask150", "bid150",
            "ask300", "bid300", "ask500", "sign_ms"]
    M = pd.DataFrame(rows, columns=cols)
    M["found"] = M.s_ins.notna()
    M["gap_ins_fill_s"] = (M.m1 - M.s_ins) / 1000
    M["cls"] = np.where(~M.found, "not_found", np.where(M.L >= M.ask100 - 1e-6, "lost_race", "passive"))
    M["below_ask_c"] = ((M.ask100 - M.L) * 100).round(2)
    M["vs_bid_c"] = ((M.L - M.bid100) * 100).round(2)
    res["M_first"] = {"n": int(len(M)), "found_share": round(float(M.found.mean()), 4),
                      "ambiguous_share(>1 cand)": round(float((M.ncand > 1).mean()), 4),
                      "class": M.cls.value_counts().to_dict(),
                      "class_by_wallet": {w: g.cls.value_counts().to_dict() for w, g in M.groupby("w")},
                      "class_by_wallet_size": {f"{w}_{int(z) if z == z else 'na'}": g.cls.value_counts().to_dict()
                                               for (w, z), g in M.groupby(["w", M.Z.fillna(-1)]) if len(g) >= 10},
                      "lost_race_at_other_lags": {f"L>=ask{dl}": round(float((M[M.found].L >= M[M.found][f"ask{dl}"] - 1e-6).mean()), 4)
                                                  for dl in (50, 150, 300)},
                      "passive_below_ask_c_q": [float(x) for x in np.nanpercentile(M[M.cls == "passive"].below_ask_c, [10, 50, 90])] if (M.cls == "passive").any() else None,
                      "passive_vs_bid_c": M[M.cls == "passive"].vs_bid_c.clip(-5, 5).value_counts().sort_index().to_dict() if (M.cls == "passive").any() else None,
                      "gap_ins_to_fill_s_q": {c: [float(x) for x in np.nanpercentile(g.gap_ins_fill_s, [10, 50, 90])] for c, g in M[M.found].groupby("cls")},
                      "ins_minus_sign_s_q": {c: [float(x) for x in np.nanpercentile((g.s_ins - g.sign_ms) / 1000, [10, 50, 90])]
                                             for c, g in M[M.found & M.sign_ms.notna()].groupby("cls")}}
    # ---- votes at instants
    ser = load_venues(a, b)
    rng = np.random.default_rng(9)
    won = o[(o["first"] == "T") & o.m0.notna()]
    sets = {"won_race_match": (won.m0.to_numpy(np.int64), won.is_up.to_numpy(bool), won.w.to_numpy())}
    for c in ("lost_race", "passive"):
        g = M[M.cls == c]
        sets[f"{c}_insertion"] = (g.s_ins.to_numpy(np.int64), g.is_up.to_numpy(bool), g.w.to_numpy())
    g = M[M.found]
    sets["M_first_at_first_fill"] = (g.m1.to_numpy(np.int64), g.is_up.to_numpy(bool), g.w.to_numpy())
    vres = {}
    for nm, (tt, up, ww) in sets.items():
        if not len(tt):
            continue
        v, cv = vote_at(ser, tt)
        vres[nm] = summarize_vote(v, cv, up, nm)
        pl = tt + (rng.choice([-1, 1], len(tt)) * rng.uniform(5000, 60000, len(tt))).astype(np.int64)
        vp, cvp = vote_at(ser, pl)
        vres[nm]["placebo"] = summarize_vote(vp, cvp, up, nm + "_placebo")["agree_on_voted"]
        vres[nm]["by_wallet"] = {}
        for w in ("DS", "GF", "XM"):
            s = ww == w
            if s.any():
                sv = summarize_vote(v[s], cv[s], up[s], nm)
                vres[nm]["by_wallet"][w] = [sv["agree_on_voted"], sv["voted_share"], int(s.sum())]
    # XM 60-share passive subset
    g = M[(M.w == "XM") & (M.Z == 60)]
    if len(g):
        v, cv = vote_at(ser, g.s_ins.fillna(0).to_numpy(np.int64)) if g.found.any() else (None, None)
        if v is not None:
            vres["XM60_insertion"] = summarize_vote(v[g.found.to_numpy()], cv[g.found.to_numpy()], g.is_up.to_numpy(bool)[g.found.to_numpy()], "xm60")
    res["vote"] = vres
    # ---- gate check: o's ask change over [s-500, s-100) at won races vs lost-race insertions
    def ask_change(tt, up, ms):
        out = []
        for t_, u_, m_ in zip(tt, up, ms):
            T = touch.get(int(m_))
            if T is None:
                out.append(np.nan); continue
            bb1, ba1 = at_touch(T, t_ - 100); bb0, ba0 = at_touch(T, t_ - 500)
            out.append((ba1 - ba0) if u_ else -((bb1) - (bb0)))
        return np.array(out)
    ws = won.m0.to_numpy(np.int64); wu = won.is_up.to_numpy(bool); wm = won.mstart.to_numpy()
    ca = ask_change(ws, wu, wm)
    lr = M[M.cls == "lost_race"]
    cl = ask_change(lr.s_ins.to_numpy(np.int64), lr.is_up.to_numpy(bool), lr.mstart.to_numpy())
    def dist(x):
        x = x[np.isfinite(x)]
        return {"n": int(len(x)), "fell": round(float((x < -0.0049).mean()), 4), "unch": round(float((np.abs(x) <= 0.0049).mean()), 4),
                "rose": round(float((x > 0.0049).mean()), 4)} if len(x) else None
    res["gate_ask_change_500_100"] = {"won_race": dist(ca), "lost_race_insertion": dist(cl)}
    # ---- decisions per filled order
    nT = int((o["first"] == "T").sum()); nMl = int((M.cls == "lost_race").sum()); nMp = int((M.cls == "passive").sum())
    nMn = int((M.cls == "not_found").sum()) + int(((o["first"] == "M") & o.m1.isna()).sum())
    pi = res["T_first"]["pi_rem"]
    if pi:
        # not-found M-first orders split pro rata between lost and passive
        fl = nMl / max(nMl + nMp, 1)
        Ml = nMl + fl * nMn
        D = nT + Ml / pi + (nMp + (1 - fl) * nMn)
        q = (nT + Ml + nMp + (1 - fl) * nMn) / D
        res["decisions"] = {"T_first": nT, "M_lost": nMl, "M_passive": nMp, "M_unclassified": nMn, "pi_rem": pi,
                            "decisions_est": round(float(D), 1), "filled_orders": int(len(o)), "q_fill_per_decision": round(float(q), 4),
                            "q_by_wallet": {}}
        for w in ("DS", "GF", "XM"):
            ow = o[o.w == w]; Mw = M[M.w == w]
            nTw = int((ow["first"] == "T").sum()); nMlw = int((Mw.cls == "lost_race").sum()); nMpw = int((Mw.cls == "passive").sum())
            nMnw = int((Mw.cls == "not_found").sum()) + int(((ow["first"] == "M") & ow.m1.isna()).sum())
            piw = res["T_first"]["pi_rem_by_wallet"].get(w, [pi])[0] or pi
            flw = nMlw / max(nMlw + nMpw, 1); Mlw = nMlw + flw * nMnw
            Dw = nTw + Mlw / piw + nMpw + (1 - flw) * nMnw
            res["decisions"]["q_by_wallet"][w] = round(float((nTw + Mlw + nMpw + (1 - flw) * nMnw) / max(Dw, 1)), 4)
    M.to_parquet(C + "/it9/ins9_M.parquet")
    json.dump(res, open(out_path, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:6000])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])

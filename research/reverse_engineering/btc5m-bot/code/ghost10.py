"""Iteration 10 (panel iter9 mechanics P1 = X77 and assumptions P5 = X86): does every cluster decision leave a book trace, and
how many decisions are invisible (unfilled lost races = ghost orders)?

Book pass over btc5m_clob_raw2 (my unthrottled BTC 5m book, 10-31 development block; near-touch 2 c, quotes coalesced to 30 ms):
every positive size increment on a level, with its base (the level's size before), whether the level was o's ask within the
previous 300 ms (the lost-race geometry: a BUY o at L resting on o's bid where L was o's ask), and its fate:
  filled   = a trade at the level after the insertion (queue front if base == 0),
  cancel   = the level loses exactly the inserted size (or empties) with no trade at the level within 100 ms,
  censored = neither within 10 s (includes levels that left the recorded 2-c band).
Truth sets: (i) T-first cluster remainders (calldata Z - taker shares) looked up at (o, L) within [m0 - 100, m0 + 400] ms,
split into later-filled and never-filled (X86); (ii) located M-first insertions (ins9b_M). Crowd reference: old-ask insertions of
non-menu sizes. Ghost estimate: life-floor mixture (cluster cancels have a ~100-ms floor, the crowd's median is ~70 ms).
Venue move at an insertion: Binance USD-M BTC microprice toward o over [s - 800, s - 200) ms (the decision ~150 ms before the
book placement under the 150-ms taker delay, plus the bot's ~100-200-ms reaction).
Usage: python ghost10.py START END OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9
from lag7 import micro_series, mv

C = L.C
MENU = (30.0, 60.0, 100.0)
OUTD = C + "/it10"


def book_pass(a, b):
    books = {}; touch = {}; P = []; D = []; X = []; tokmap = {}
    for r in L.recs("btc5m_clob_raw2", a - 600, b + 60):
        k = r.get("k")
        if k == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
            continue
        if k == "f":
            if r.get("u") == 1:
                mm = int(r["m"])
                books[mm] = {"B": {round(p, 4): z for p, z in r["b"]}, "S": {round(p, 4): z for p, z in r["o"]}}
                if r["b"] and r["o"]:
                    touch.setdefault(mm, []).append((int(r["s"]), max(p for p, z in r["b"]), min(p for p, z in r["o"])))
            continue
        if k == "x":
            X.append((int(r["s"]), int(r["m"]), int(r.get("u") or 0), round(float(r["p"]), 4), float(r["z"]), r.get("d"),
                      (r.get("h") or "").lower()))
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
        dz = new - prev
        if dz > 0.005:
            P.append((s, mm, sd == "B", p, round(dz, 4), prev))
        elif dz < -0.005:
            D.append((s, mm, sd == "B", p, round(dz, 4), new))
        if r.get("bb") is not None and r.get("ba") is not None:
            t = touch.setdefault(mm, [])
            if not t or t[-1][1] != r["bb"] or t[-1][2] != r["ba"]:
                t.append((s, float(r["bb"]), float(r["ba"])))
    P = pd.DataFrame(P, columns=["s", "m", "bid", "p", "z", "base"])
    D = pd.DataFrame(D, columns=["s", "m", "bid", "p", "dz", "new"])
    X = pd.DataFrame(X, columns=["s", "m", "u", "p", "z", "d", "h"])
    touch = {m: np.array(sorted(v), float) for m, v in touch.items()}
    return P, D, X, touch, tokmap


def trade_levels(X):
    """map each trade to the mirrored Up-book level it consumed: (m, bid side?, price)."""
    up = X.u == 1; buy = X.d == "BUY"
    lvl_bid = (up & ~buy) | (~up & buy)
    price = np.where(up, X.p, (1 - X.p).round(4))
    return pd.DataFrame({"s": X.s, "m": X.m, "bid": lvl_bid, "p": np.round(price, 4), "z": X.z, "h": X.h})


def fates(P, D, T, horizon=10000, tol=100):
    """fate of every increment in P (rows of P must be insertions to evaluate)."""
    Dg = {k: (g.s.to_numpy(np.int64), g.dz.to_numpy(float), g.new.to_numpy(float)) for k, g in D.groupby(["m", "bid", "p"])}
    Tg = {k: (g.s.to_numpy(np.int64), g.h.to_numpy()) for k, g in T.groupby(["m", "bid", "p"])}
    fate = []; tend = []; fh = []
    for r in P.itertuples(index=False):
        key = (r.m, r.bid, r.p)
        s0 = r.s; z = r.z
        tc = None
        dd = Dg.get(key)
        tt = Tg.get(key)
        if dd is not None:
            ds, dz, dn = dd
            i0 = np.searchsorted(ds, s0, "right"); i1 = np.searchsorted(ds, s0 + horizon, "right")
            for j in range(i0, i1):
                if abs(dz[j] + z) <= 0.02 or dn[j] <= 0.005 or (r.base <= 0.005 and dn[j] < z - 0.01):
                    # no trade at the level within tol ms -> a cancel
                    if tt is not None:
                        ts_, _ = tt
                        k0 = np.searchsorted(ts_, ds[j] - tol, "left"); k1 = np.searchsorted(ts_, ds[j] + tol, "right")
                        if k1 > k0:
                            continue
                    tc = ds[j]
                    break
        tf = None; hf = ""
        if tt is not None:
            ts_, hs = tt
            k0 = np.searchsorted(ts_, s0 - 30, "left")
            if k0 < len(ts_) and ts_[k0] <= s0 + horizon:
                tf = ts_[k0]; hf = hs[k0]
        if tf is not None and (tc is None or tf <= tc + tol):
            fate.append("filled" if r.base <= 0.005 else "filled_q"); tend.append(tf); fh.append(hf)
        elif tc is not None:
            fate.append("cancel"); tend.append(tc); fh.append("")
        else:
            fate.append("censored"); tend.append(s0 + horizon); fh.append("")
    out = P.copy()
    out["fate"] = fate; out["t_end"] = tend; out["fill_h"] = fh
    out["life"] = out.t_end - out.s
    return out


def old_ask_flag(P, touch, w=300):
    flag = np.zeros(len(P), bool); at_bb = np.zeros(len(P), bool)
    for m, idx in P.groupby("m").groups.items():
        T = touch.get(int(m))
        if T is None:
            continue
        sub = P.loc[idx]
        s = sub.s.to_numpy(np.int64); p = sub.p.to_numpy(float); bid = sub.bid.to_numpy(bool)
        i0 = np.searchsorted(T[:, 0], s - w, "left") - 1; i1 = np.searchsorted(T[:, 0], s, "left") - 1
        res = np.zeros(len(sub), bool); top = np.zeros(len(sub), bool)
        for j in range(len(sub)):
            if i1[j] < 0:
                continue
            seg = T[max(i0[j], 0):i1[j] + 1]
            if bid[j]:
                res[j] = np.any(np.abs(seg[:, 2] - p[j]) < 1e-6)
                top[j] = p[j] >= T[i1[j], 1] - 1e-6
            else:
                res[j] = np.any(np.abs(seg[:, 1] - p[j]) < 1e-6)
                top[j] = p[j] <= T[i1[j], 2] + 1e-6
        pos = P.index.get_indexer(idx)
        flag[pos] = res; at_bb[pos] = top
    return flag, at_bb


def qd(x, qs=(5, 10, 25, 50, 75, 90)):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return [round(float(v), 1) for v in np.percentile(x, qs)] if len(x) else None


def main(a, b, out):
    os.makedirs(OUTD, exist_ok=True)
    P, D, X, touch, tokmap = book_pass(a, b)
    print("book pass: increments", len(P), "decrements", len(D), "trades", len(X), flush=True)
    T = trade_levels(X)
    P = P[(P.s >= a * 1000) & (P.s < b * 1000)].reset_index(drop=True)
    P["oldask"], P["at_top"] = old_ask_flag(P, touch)
    P["menu"] = P.z.round(2).isin(MENU)
    P["integer"] = (P.z - P.z.round()).abs() < 0.011
    cand = P[P.oldask].reset_index(drop=True)
    print("old-ask increments", len(cand), "menu", int(cand.menu.sum()), flush=True)
    F = fates(cand, D, T)
    # cluster orders and truth sets
    o, fills = ins9.load_orders(a, b)
    txms = X.groupby("h").s.min()
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy(); o["mstart"] = o.mstart.astype(int); o["Lx"] = o.Lim.fillna(o.px0)
    o["m0"] = o.tx0.str.lower().map(txms)
    cdx = pd.read_parquet(C + "/it9/cd9.parquet", columns=["tx", "maker", "role"])
    cl_maker_tx = set(cdx[cdx.maker.isin(list(L.W)) & (cdx.role == "M")].tx.str.lower())
    cl_tx = set(cdx.tx.str.lower())
    # level lookup for all increments (not only old-ask) for the remainder truth set
    Pg = {k: (g.s.to_numpy(np.int64), g.z.to_numpy(float), g.index.to_numpy()) for k, g in P.groupby(["m", "bid", "p"])}
    res = {"interval": [a, b], "increments": int(len(P)), "old_ask_increments": int(len(cand)),
           "old_ask_menu": int(cand.menu.sum())}
    tf = o[(o["first"] == "T") & o.Z.notna() & o.m0.notna()].copy()
    tf["R"] = (tf.Z - tf.shT).round(4)
    rem = tf[tf.R > 0.5].copy()
    hit_idx = []
    for r in rem.itertuples():
        key = (r.mstart, bool(r.is_up), round(r.Lx if r.is_up else 1 - r.Lx, 4))
        g = Pg.get(key)
        j = -1
        if g is not None:
            ss, zz, ii = g
            k = np.where((np.abs(zz - r.R) <= 0.02) & (ss >= r.m0 - 100) & (ss <= r.m0 + 400))[0]
            if len(k):
                j = int(ii[k[0]])
        hit_idx.append(j)
    rem["pidx"] = hit_idx; rem["found"] = rem.pidx >= 0
    hits = sorted({j for j in hit_idx if j >= 0})
    Fh = fates(P.iloc[hits], D, T) if hits else P.iloc[:0].assign(fate=[], t_end=[], fill_h=[], life=[])
    Fh.index = hits
    rem["fate"] = [Fh.fate.at[j] if j >= 0 else None for j in rem.pidx]
    rem["life"] = [Fh.life.at[j] if j >= 0 else np.nan for j in rem.pidx]
    rem["lag"] = [P.s.iat[j] - r.m0 if j >= 0 else np.nan for j, r in zip(rem.pidx, rem.itertuples())]
    rem["never_filled"] = ~rem.hasM
    def remsum(g):
        return {"n": int(len(g)), "found": round(float(g.found.mean()), 4) if len(g) else None,
                "fate_of_found": g[g.found].fate.value_counts().to_dict(),
                "lag_ms_q10_50_90": qd(g[g.found].lag, (10, 50, 90)),
                "cancel_life_ms_q5_10_25_50_75_90": qd(g[g.found & (g.fate == "cancel")].life)}
    res["X86_remainders"] = {"never_filled": remsum(rem[rem.never_filled]), "filled_later": remsum(rem[~rem.never_filled]),
                             "never_filled_by_wallet": {w: remsum(g) for w, g in rem[rem.never_filled].groupby("w")},
                             "never_filled_by_size": {str(int(z)): remsum(g) for z, g in rem[rem.never_filled].groupby("Z") if len(g) >= 10},
                             "never_filled_by_R_menu": {str(k): remsum(g) for k, g in rem[rem.never_filled].groupby(rem[rem.never_filled].R.round(2).isin(MENU))}}
    # known cluster insertions among the old-ask candidates (exclude them from the ghost pool)
    known = set()
    for j in rem[rem.found].pidx:
        r = P.iloc[int(j)]; known.add((int(r.s), int(r.m), bool(r.bid), float(r.p)))
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet")
    Mi = Mi[Mi.s_ins.notna()]
    for r in Mi.itertuples():
        known.add((int(r.s_ins), int(r.mstart), bool(r.is_up), round(r.L if r.is_up else 1 - r.L, 4)))
    F["known_cluster"] = [(int(s), int(m), bool(bd), float(p)) in known for s, m, bd, p in zip(F.s, F.m, F.bid, F.p)]
    F["fill_cluster_maker_tx"] = F.fill_h.isin(cl_maker_tx)
    F["fill_cluster_any_tx"] = F.fill_h.isin(cl_tx)
    # venue move toward o at the insertion
    S = micro_series("btc5m_venues2", a, b)
    if ("bf", "BTC") in S:
        r_ = mv(S, ("bf", "BTC"), F.s.to_numpy(np.int64) - 800, F.s.to_numpy(np.int64) - 200)
        F["move"] = np.where(F.bid, r_, -r_)  # bid side = BUY Up; ask side = BUY Down
    else:
        F["move"] = np.nan
    F.to_parquet(OUTD + "/ghost_cand.parquet")
    rem.drop(columns=[c for c in rem.columns if rem[c].dtype == object and c not in ("w", "fate", "token", "oh")], errors="ignore").to_parquet(OUTD + "/rem10.parquet")
    # life distributions
    def lifes(g):
        c = g[g.fate == "cancel"]
        return {"n": int(len(g)), "fate": g.fate.value_counts(normalize=True).round(4).to_dict(),
                "cancel_life_q5_10_25_50_75_90": qd(c.life), "P(life<90|cancel)": round(float((c.life < 90).mean()), 4) if len(c) else None,
                "P(life>=150|cancel)": round(float((c.life >= 150).mean()), 4) if len(c) else None}
    U = F[~F.known_cluster]
    res["life"] = {"known_cluster_old_ask": lifes(F[F.known_cluster]),
                   "unknown_menu": lifes(U[U.menu]), "unknown_menu_by_size": {str(z): lifes(g) for z, g in U[U.menu].groupby(U[U.menu].z.round(0))},
                   "crowd_ref_nonmenu_integer": lifes(U[~U.menu & U.integer & (U.z >= 5) & (U.z <= 200)]),
                   "crowd_ref_nonmenu_all": lifes(U[~U.menu]),
                   "unknown_menu_filled_by_noncluster_tx": int(((U.fate == "filled") & U.menu & ~U.fill_cluster_any_tx).sum()),
                   "unknown_menu_filled_by_cluster_maker_tx": int(((U.fate == "filled") & U.menu & U.fill_cluster_maker_tx).sum())}
    # ghost estimate by the life-floor mixture, per size and move bin
    nf = rem[rem.never_filled & rem.found & (rem.fate == "cancel")]
    f_cl = float((nf.life < 90).mean()) if len(nf) else 0.05
    ref = U[~U.menu & U.integer & (U.z >= 5) & (U.z <= 200) & (U.fate == "cancel")]
    f_cr = float((ref.life < 90).mean()) if len(ref) else 0.6
    def ghosts(g):
        c = g[g.fate == "cancel"]
        N = len(c); n90 = int((c.life < 90).sum())
        Ncl = (f_cr * N - n90) / max(f_cr - f_cl, 1e-6)
        return {"cancels": N, "life<90": n90, "ghost_cluster_est": round(float(np.clip(Ncl, 0, N)), 1),
                "censored": int((g.fate == "censored").sum())}
    res["mixture"] = {"f_cluster_life<90": round(f_cl, 4), "n_cluster_ref": int(len(nf)), "f_crowd_life<90": round(f_cr, 4), "n_crowd_ref": int(len(ref))}
    Um = U[U.menu]
    res["ghost_est"] = {"all_menu": ghosts(Um), "by_size": {str(z): ghosts(g) for z, g in Um.groupby(Um.z.round(0))},
                        "by_move_bp": {}}
    bins = [(-99, 0.002), (0.002, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 99)]
    for lo, hi in bins:
        g = Um[(Um.move >= lo) & (Um.move < hi)]
        kc = F[F.known_cluster & (F.move >= lo) & (F.move < hi)]
        res["ghost_est"]["by_move_bp"][f"{lo}..{hi}"] = dict(ghosts(g), known_cluster_old_ask=int(len(kc)))
    nT = int((o["first"] == "T").sum())
    res["counts"] = {"T_first_orders": nT, "M_first_located": int(len(Mi)), "filled_orders": int(len(o))}
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:7000])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])

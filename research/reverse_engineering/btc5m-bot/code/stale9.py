"""Iteration 9 (panel iter8 mechanics P1, strong form of X13): is the decision gated by a STALE-QUOTE EDGE measured since o's
touch last changed? (the selectivity question left by ins9b: ~1.45 decisions per filled order, so the 92% of high-hazard
instants without a match are mostly instants where the bot did NOT decide).

100-ms grid (rel 5..285 s) on development intervals of 10-31 (lab feeds: btc5m_clob_raw2 touch, btc5m_venues2 microprices,
clob_crypto trades). For outcome o at t:
  anchor a = last change of o's best-ask price (variant: of o's bid or ask), age cap 10 s;
  dS = mean over the BTC series (bf, bs, ok, by) of 1e4 ln(S(t - 250) / S(a - 250))  [bp, the bot's ~250-ms view];
  Delta_o = phi(Phi^-1(mid_o(a))) / (sigma sqrt(tau)), sigma = 0.67 bp / sqrt(s) (DVOL ~38%), tau = s to the window end;
  E_o = mid_o(a) + sgn_o * k * Delta_o * dS - ask_o(t)   [cents], k in {0.5, 1, 2} chosen on the fit interval.
Labels: (i) a cluster taker match on o in [t + 100, t + 600) (as the frozen hazard); (ii) a DECISION = match or lost-race
insertion (ins9b classes lost_300 / lost_1000) on o in [t + 100, t + 600).
Models (logistic, fit on interval A, scored on B and C, never refit): BASE (Polymarket activity: trades, touch changes, age,
price level), FULL (BASE + six-series tick terms, the frozen design), E-only, BASE + E, FULL + E. Window-block bootstrap of
the FULL+E - FULL gain. Hazard by E bins. Side on weak / no-vote won races: argmax_o E_o(m - 50).
Usage: python stale9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed, gate8, ins9
from lag7 import micro_series, mv, px_at
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
OWN = C + "/it9/own_1231_12_18.parquet"
IV = {"A": (1793458500, 1793462640), "B": (1793462640, 1793464380), "C": (1793464380, 1793469300)}  # 14:55-16:04, 16:04-16:33, 16:33-17:55 UTC
SIG = 0.67
BTCK = (("bf", "BTC"), ("bs", "BTC"), ("ok", "BTC"), ("by", "BTC"))


def grid(a, b, lost):
    d = live6.own_taker(OWN, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].sort_values("m").drop_duplicates(["tx", "token"])
    tk = tk[(tk.m >= a * 1000) & (tk.m < b * 1000)]
    S = micro_series("btc5m_venues2", a, b); keys = sorted(S)
    R = gate8.raw_touch("btc5m_clob_raw2", a, b)
    wins = sorted({tok[t][1] for t in tok})
    G = []
    for st in wins:
        if sealed.is_sealed(st, "btc5m-bot"):
            continue
        g = np.arange((st + 5) * 1000, (st + 285) * 1000, 100, dtype=np.int64)
        g = g[(g >= a * 1000 + 5000) & (g < b * 1000)]
        G.append(np.c_[g, np.full(len(g), st)])
    G = np.vstack(G); t = G[:, 0]; st = G[:, 1]
    allc = np.zeros(len(t)); oka = np.zeros(len(t), bool)
    for key in keys:
        r = mv(S, key, t - 500, t); oka |= np.isfinite(r); allc += np.nan_to_num(r)
    out = {"t": t, "st": st}
    for o in (True, False):
        out[o] = {k: np.full(len(t), np.nan) for k in ("ask", "ask5", "age", "a_ask", "a_any", "mid_a_ask", "mid_a_any", "mid")}
    for s0, rg in R.groupby("m"):
        sel = np.where(st == s0)[0]
        if not len(sel):
            continue
        rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float); bb = rg.bb.to_numpy(float)
        mid = (ba + bb) / 2
        tt = t[sel]
        i = np.searchsorted(rs, tt, "right") - 1; i5 = np.searchsorted(rs, tt - 500, "right") - 1
        ok_ = i >= 0
        chU = np.r_[True, np.diff(ba) != 0]; chD = np.r_[True, np.diff(bb) != 0]; chA = chU | chD
        for o, ch, askv in ((True, chU, ba), (False, chD, 1 - bb)):
            idx_ch = np.where(ch)[0]; idx_any = np.where(chA)[0]
            j = np.searchsorted(rs[idx_ch], tt, "right") - 1; ja = np.searchsorted(rs[idx_any], tt, "right") - 1
            ic = idx_ch[np.clip(j, 0, None)]; ia = idx_any[np.clip(ja, 0, None)]
            D = out[o]
            D["ask"][sel] = np.where(ok_, askv[np.clip(i, 0, None)], np.nan)
            D["ask5"][sel] = np.where(i5 >= 0, askv[np.clip(i5, 0, None)], np.nan)
            D["a_ask"][sel] = np.where(j >= 0, rs[ic], np.nan); D["a_any"][sel] = np.where(ja >= 0, rs[ia], np.nan)
            mo = mid if o else 1 - mid
            D["mid_a_ask"][sel] = np.where(j >= 0, mo[ic], np.nan); D["mid_a_any"][sel] = np.where(ja >= 0, mo[ia], np.nan)
            D["mid"][sel] = np.where(ok_, mo[np.clip(i, 0, None)], np.nan)
            D["age"][sel] = tt - D["a_ask"][sel]
    # venue move since the anchor (capped at 10 s), BTC series mean, the bot's 250-ms view
    def dS_since(anchor):
        an = np.maximum(np.nan_to_num(anchor, nan=0), t - 10000)
        acc = np.zeros(len(t)); n = np.zeros(len(t))
        for key in BTCK:
            if key not in S:
                continue
            r = mv(S, key, an - 250, t - 250)
            acc += np.nan_to_num(r); n += np.isfinite(r)
        return np.where(n > 0, acc / np.maximum(n, 1), np.nan)
    for o in (True, False):
        out[o]["dS_ask"] = dS_since(out[o]["a_ask"]); out[o]["dS_any"] = dS_since(out[o]["a_any"])
    # labels
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool); sm_all = tk.start.to_numpy()
    lo = lost[(lost.s_ins >= a * 1000) & (lost.s_ins < b * 1000)]
    for o in (True, False):
        for nm, (mm, ss) in (("y_match", (m[up == o], sm_all[up == o])),
                             ("y_dec", (np.r_[m[up == o], lo.s_ins.to_numpy(np.int64)[lo.is_up.to_numpy(bool) == o]],
                                        np.r_[sm_all[up == o], lo.mstart.to_numpy()[lo.is_up.to_numpy(bool) == o]]))):
            od = np.argsort(mm); mm = mm[od]; ss = ss[od]
            y = np.zeros(len(t), bool)
            i0 = np.searchsorted(mm, t + 100, "left"); i1 = np.searchsorted(mm, t + 600, "left")
            for jj in np.where(i1 > i0)[0]:
                y[jj] = (ss[i0[jj]:i1[jj]] == st[jj]).any()
            out[o][nm] = y
    tr = trades[~trades.tx.isin(set(tk.tx))].copy()
    tr["start"] = tr.token.map(lambda x: tok.get(x, (None, -1))[1])
    nb = np.zeros(len(t))
    for s0, gg in tr.groupby("start"):
        ms = np.sort(gg.s_ms.to_numpy(np.int64)); sel = st == s0
        nb[sel] = np.searchsorted(ms, t[sel], "left") - np.searchsorted(ms, t[sel] - 1000, "left")
    out["act"] = nb; out["tick"] = allc; out["oka"] = oka
    out["tau"] = np.clip(st + 300 - t / 1000, 5, 300)
    return out, tk, S


def stack(gd, k_mult=1.0, anchor="ask"):
    rows = []
    for o, sg in ((True, 1.0), (False, -1.0)):
        D = gd[o]
        keep = gd["oka"] & np.isfinite(D["ask"]) & np.isfinite(D["ask5"]) & (D["ask"] > 0.03) & (D["ask"] < 0.97) & np.isfinite(D[f"mid_a_{anchor}"]) & np.isfinite(D[f"dS_{anchor}"])
        mida = np.clip(D[f"mid_a_{anchor}"], 0.01, 0.99)
        delta = norm.pdf(norm.ppf(mida)) / (SIG * np.sqrt(gd["tau"]))
        E = (mida + sg * k_mult * delta * D[f"dS_{anchor}"] - D["ask"]) * 100
        rows.append(pd.DataFrame({"y_match": D["y_match"][keep], "y_dec": D["y_dec"][keep], "tick": sg * gd["tick"][keep],
                                  "rp": np.sign(np.round((D["ask"][keep] - D["ask5"][keep]) * 100)), "age": D["age"][keep],
                                  "act": gd["act"][keep], "ask": D["ask"][keep], "E": E[keep], "st": gd["st"][keep], "o": o, "t": gd["t"][keep]}))
    return pd.concat(rows, ignore_index=True)


def X_of(df, kind):
    act = df.act.to_numpy(float); rp = df.rp.to_numpy(float); la = np.log1p(np.nan_to_num(df.age.to_numpy(float), nan=1e5) / 100)
    ask = df.ask.to_numpy(float); tick = df.tick.to_numpy(float); E = df.E.to_numpy(float)
    base = np.c_[act, np.log1p(act), rp == 0, rp > 0, rp < 0, la, np.abs(ask - 0.5)]
    full = np.c_[base, tick, np.abs(tick), np.clip(tick, 0, None), np.clip(tick, 0, None) * (rp == 0), np.clip(tick, 0, None) * (rp > 0), la * (tick > 0.02)]
    Ef = np.c_[np.clip(E, -10, 10), np.clip(E, 0, 10), E > 0, E > 0.5, E > 1, E > 2, np.clip(E, -10, 10) * la]
    return {"base": base, "full": full, "E": Ef, "base+E": np.c_[base, Ef], "full+E": np.c_[full, Ef]}[kind].astype(float)


def fit_score(tr, te, kind, ycol):
    Xa, Xb = X_of(tr, kind), X_of(te, kind)
    mu, sd = Xa.mean(0), Xa.std(0) + 1e-9
    lr = LogisticRegression(max_iter=3000, C=1.0).fit((Xa - mu) / sd, tr[ycol])
    return lr.predict_proba((Xb - mu) / sd)[:, 1]


def boot_gain(y, p1, p0, blocks, n=1000, seed=5):
    ub, inv = np.unique(blocks, return_inverse=True)
    rng = np.random.default_rng(seed); g = []
    idxs = [np.where(inv == i)[0] for i in range(len(ub))]
    for _ in range(n):
        pick = rng.integers(0, len(ub), len(ub)); ii = np.concatenate([idxs[p] for p in pick])
        if y[ii].min() == y[ii].max():
            continue
        g.append(roc_auc_score(y[ii], p1[ii]) - roc_auc_score(y[ii], p0[ii]))
    return [round(float(x), 4) for x in np.percentile(g, [2.5, 50, 97.5])]


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet")
    lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    G = {}; TK = {}; SS = {}
    for nm, (a, b) in IV.items():
        G[nm], TK[nm], SS[nm] = grid(a, b, lost)
        print(nm, "grid", len(G[nm]["t"]), flush=True)
    res = {"intervals": IV, "sigma_bp": SIG}
    # choose k and anchor on A (univariate AUC of E for the decision label)
    best = None; ch = {}
    for anchor in ("ask", "any"):
        for k in (0.5, 1.0, 2.0):
            dA = stack(G["A"], k, anchor)
            au = roc_auc_score(dA.y_dec, dA.E); ch[f"{anchor}_k{k}"] = round(float(au), 4)
            if best is None or au > best[0]:
                best = (au, anchor, k)
    res["choice_on_A_univariate_auc_E_ydec"] = ch; res["chosen"] = {"anchor": best[1], "k": best[2]}
    dfs = {nm: stack(G[nm], best[2], best[1]) for nm in IV}
    for nm, df in dfs.items():
        res.setdefault("univariate_auc_E", {})[nm] = {"y_match": round(float(roc_auc_score(df.y_match, df.E)), 4),
                                                      "y_dec": round(float(roc_auc_score(df.y_dec, df.E)), 4),
                                                      "n": int(len(df)), "pos_match": int(df.y_match.sum()), "pos_dec": int(df.y_dec.sum())}
        bins = pd.cut(df.E, [-100, -2, -1, 0, 0.5, 1, 2, 4, 100])
        tab = df.groupby(bins, observed=False).agg(p_match=("y_match", "mean"), p_dec=("y_dec", "mean"), n=("y_dec", "size"))
        res.setdefault("hazard_by_E_cents", {})[nm] = {str(i): [round(float(r.p_match), 4), round(float(r.p_dec), 4), int(r.n)] for i, r in tab.iterrows()}
    # models fit on A, scored on B and C
    for ycol in ("y_match", "y_dec"):
        for te in ("B", "C"):
            sc = {}
            P = {}
            for kind in ("base", "full", "E", "base+E", "full+E"):
                P[kind] = fit_score(dfs["A"], dfs[te], kind, ycol)
                sc[kind] = round(float(roc_auc_score(dfs[te][ycol], P[kind])), 4)
            y = dfs[te][ycol].to_numpy(); blk = dfs[te].st.to_numpy()
            sc["gain_fullE_vs_full_CI"] = boot_gain(y, P["full+E"], P["full"], blk)
            sc["gain_full_vs_base_CI"] = boot_gain(y, P["full"], P["base"], blk)
            sc["gain_baseE_vs_base_CI"] = boot_gain(y, P["base+E"], P["base"], blk)
            res.setdefault("models_fit_A", {})[f"{ycol}_on_{te}"] = sc
    # side of weak / no-vote won races by argmax E at m - 50
    sides = {}
    for nm in ("A", "B", "C"):
        tk = TK[nm]; gd = G[nm]
        m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool); stt = tk.start.to_numpy()
        ser = ins9.load_venues(*IV[nm])
        v, cv = ins9.vote_at(ser, m)
        # E at m - 50 for both outcomes: nearest grid point at or before m - 50 in the same window
        tt = gd["t"]; sts = gd["st"]
        Eo = {}
        for o, sg in ((True, 1.0), (False, -1.0)):
            D = gd[o]
            mida = np.clip(D[f"mid_a_{best[1]}"], 0.01, 0.99)
            delta = norm.pdf(norm.ppf(mida)) / (SIG * np.sqrt(gd["tau"]))
            Eo[o] = (mida + sg * best[2] * delta * D[f"dS_{best[1]}"] - D["ask"]) * 100
        pe = []
        for mi, si in zip(m, stt):
            j = np.searchsorted(tt, mi - 50, "right") - 1
            # walk back to the same window
            while j >= 0 and sts[j] != si and tt[j] > mi - 2000:
                j -= 1
            if j < 0 or sts[j] != si or not (np.isfinite(Eo[True][j]) and np.isfinite(Eo[False][j])):
                pe.append(np.nan)
            else:
                pe.append(1.0 if Eo[True][j] > Eo[False][j] else (-1.0 if Eo[True][j] < Eo[False][j] else np.nan))
        pe = np.array(pe)
        strength = np.abs(v)
        for lab, kk in (("no_vote", cv & (v == 0)), ("weak_1", cv & (strength == 1)), ("weak_2", cv & (strength == 2)), ("strong_3+", cv & (strength >= 3))):
            k2 = kk & np.isfinite(pe)
            sides.setdefault(nm, {})[lab] = [round(float(((pe[k2] > 0) == up[k2]).mean()), 4) if k2.any() else None, int(k2.sum())]
    res["side_argmax_E_at_m_minus_50"] = sides
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:8000])


if __name__ == "__main__":
    main(sys.argv[1])

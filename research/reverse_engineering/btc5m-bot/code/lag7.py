"""Iteration 7 (catalog X31 = panel-assumptions iter6 P4, and D2 hazard at matching-engine ms): is the perp microprice
tick the TRIGGER or a CORRELATE of the bot's taker decisions? Development blocks only (10-31 12:00-18:00 so far).
Matches = cluster taker fills with a recorded match ms (shared clob_crypto trade record with the same tx hash).
Quote series = the sized top of book of FEED (Binance USD-M / spot, Bybit, OKX, Hyperliquid; BTC and ETH, ETH scaled to BTC
units by 1.235), microprice = (bid x ask size + ask x bid size) / (bid size + ask size).
1. LAG PROFILE: side agreement of the ten-series vote (sign of microprice moves > 0.002 bp) in 100-ms bins
   [m + k, m + k + 100) for k in [-3000, +3000), and of the composite move (sum over series), vs placebo times.
2. HAZARD / SPECIFICITY on a 100-ms grid of all covered times inside BTC 5m windows (rel 5-285 s): the composite move
   over [t - 500, t) (Binance USD-M BTC + ETH microprice), and the label "a cluster taker match on outcome o in
   [t + 100, t + 600)"; P(match | |move| bin) and the AUC of the signed move toward o (presence trigger strength),
   against the market-activity baseline (Polymarket trades on the window in [t - 1000, t)).
3. SIZE vs trigger strength (where calldata of the match tx exists): large-size share by |composite move| bin.
Usage: python lag7.py OWN_PARQUET START END FEED [CALLDATA_PARQUET]"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6
import sealed
from sklearn.metrics import roc_auc_score


def micro_series(feed, a, b):
    rows = {}
    for r in L.recs(feed, a - 60, b):
        v = r.get("v")
        if v in ("bf", "by", "ok", "bs", "hl") and r.get("b") and r.get("a"):
            rows.setdefault((v, r["y"]), []).append((r.get("E") or 0, r["t"], r["b"], r.get("B") or 0, r["a"], r.get("A") or 0))
    off = None
    if ("bf", "BTC") in rows:
        x = np.array(rows[("bf", "BTC")], float); off = float(np.median(x[:, 1] - x[:, 0]))
    S = {}
    for key, lst in sorted(rows.items()):
        x = np.array(lst, float)
        T = x[:, 0] if key[0] != "bs" else x[:, 1] - (off or 0)
        o = np.argsort(T, kind="stable"); x = x[o]; T = T[o].astype(np.int64)
        mic = (x[:, 2] * x[:, 5] + x[:, 4] * x[:, 3]) / np.maximum(x[:, 3] + x[:, 5], 1e-12)
        S[key] = (T, mic, 1.235 if key[1] == "ETH" else 1.0)
    return S


def px_at(T, p, t):
    i = np.searchsorted(T, t, "right") - 1
    out = p[np.clip(i, 0, len(p) - 1)].astype(float)
    out[i < 0] = np.nan
    return out


def mv(S, key, t0, t1):
    T, p, sc = S[key]
    a, b = px_at(T, p, t0), px_at(T, p, t1)
    r = (b / a - 1) * 1e4 / sc
    ins = (t0 > T[0] + 3000) & (t1 < T[-1] - 200)
    r[~ins] = np.nan
    return r


def main(own_path, a, b, feed, cd_path=None):
    d = live6.own_taker(own_path, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()].sort_values("m").drop_duplicates(["tx", "token"])
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    S = micro_series(feed, a, b)
    keys = sorted(S)
    rng = np.random.default_rng(11)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    res = {"interval": [a, b], "feed": feed, "matches": int(len(m)), "series": [f"{k[0]}_{k[1]}" for k in keys]}
    # 1. lag profile
    prof = []
    for k0 in range(-3000, 3000, 100):
        Q = np.vstack([mv(S, key, m + k0, m + k0 + 100) for key in keys]); Qp = np.vstack([mv(S, key, pl + k0, pl + k0 + 100) for key in keys])
        vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0); votep = np.nansum(np.sign(Qp) * (np.abs(Qp) > 0.002), axis=0)
        cov = np.isfinite(Q).any(axis=0)
        kk = cov & (vote != 0); kp = cov & (votep != 0)
        comp = np.nansum(Q, axis=0)
        prof.append({"k": k0, "cover": round(float(kk.sum() / max(cov.sum(), 1)), 3), "agree": round(float(((vote[kk] > 0) == up[kk]).mean()), 3) if kk.any() else None,
                     "placebo_agree": round(float(((votep[kp] > 0) == up[kp]).mean()), 3) if kp.any() else None,
                     "mean_signed_comp_bp": round(float(np.nanmean(np.where(up, 1, -1)[cov] * comp[cov])), 4) if cov.any() else None, "n": int(cov.sum())})
    res["lag_profile_100ms"] = prof
    # 2. hazard on a 100-ms grid inside windows
    wins = sorted({tok[t][1] for t in tok})
    grid = []
    for st in wins:
        if sealed.is_sealed(st, "btc5m-bot"):
            continue
        g = np.arange((st + 5) * 1000, (st + 285) * 1000, 100, dtype=np.int64)
        g = g[(g >= a * 1000) & (g < b * 1000)]
        grid.append(np.c_[g, np.full(len(g), st)])
    if not grid:
        return res
    G = np.vstack(grid); t = G[:, 0]; st = G[:, 1]
    main_keys = [k for k in keys if k[0] == "bf"]
    comp = np.zeros(len(t)); okm = np.zeros(len(t), bool)
    for key in main_keys:
        r = mv(S, key, t - 500, t)
        okm |= np.isfinite(r); comp += np.nan_to_num(r)
    allc = np.zeros(len(t)); oka = np.zeros(len(t), bool)
    for key in keys:
        r = mv(S, key, t - 500, t)
        oka |= np.isfinite(r); allc += np.nan_to_num(r)
    # labels: match on Up / Down in [t + 100, t + 600)
    lab = {}
    for o in (True, False):
        mm = np.sort(m[up == o]); sm = tk.start.to_numpy()[up == o][np.argsort(m[up == o])]
        y = np.zeros(len(t), bool)
        i0 = np.searchsorted(mm, t + 100, "left"); i1 = np.searchsorted(mm, t + 600, "left")
        has = i1 > i0
        # same window only
        for j in np.where(has)[0]:
            y[j] = (sm[i0[j]:i1[j]] == st[j]).any()
        lab[o] = y
    # market-activity baseline: other traders' Polymarket trades on the window in [t - 1000, t)
    tr = trades.copy()
    tr = tr[~tr.tx.isin(set(tk.tx))]
    tr["start"] = tr.token.map(lambda x: tok.get(x, (None, -1))[1]) if "token" in tr else -1
    nb = np.zeros(len(t))
    if "token" in tr:
        for s0, gg in tr.groupby("start"):
            ms = np.sort(gg.s_ms.to_numpy(np.int64))
            sel = st == s0
            nb[sel] = np.searchsorted(ms, t[sel], "left") - np.searchsorted(ms, t[sel] - 1000, "left")
    keep = okm
    out = {"grid_points": int(keep.sum()), "base_rate_up": round(float(lab[True][keep].mean()), 5), "base_rate_down": round(float(lab[False][keep].mean()), 5)}
    rows = []
    for o, sg in ((True, 1.0), (False, -1.0)):
        y = lab[o][keep]
        x = sg * comp[keep]; xa = sg * allc[keep]
        rows.append((y, x, xa, nb[keep]))
    y = np.r_[rows[0][0], rows[1][0]]; x = np.r_[rows[0][1], rows[1][1]]; xa = np.r_[rows[0][2], rows[1][2]]; nbb = np.r_[rows[0][3], rows[1][3]]
    out["auc_signed_move_bf"] = round(float(roc_auc_score(y, x)), 4)
    out["auc_signed_move_all10"] = round(float(roc_auc_score(y, xa)), 4)
    out["auc_market_activity_trades_1s"] = round(float(roc_auc_score(y, nbb)), 4)
    from sklearn.linear_model import LogisticRegression
    half = np.arange(len(y)) % 2 == 0  # interleaved halves (grid order is time order within windows)
    X1 = np.c_[nbb, np.log1p(nbb)]; X2 = np.c_[nbb, np.log1p(nbb), xa, np.abs(xa), np.clip(xa, 0, None)]
    for nm, X in (("activity", X1), ("activity+move", X2)):
        lr = LogisticRegression(max_iter=1000).fit(X[half], y[half])
        out[f"auc_{nm}_halfsplit"] = round(float(roc_auc_score(y[~half], lr.predict_proba(X[~half])[:, 1])), 4)
    bins = [-100, -0.5, -0.1, -0.02, 0.02, 0.1, 0.5, 100]
    cb = pd.cut(xa, bins)
    out["hazard_by_signed_move_all10_bp"] = {str(k): [round(float(y[cb == k].mean()), 5), int((cb == k).sum())] for k in cb.categories}
    res["hazard"] = out
    # 3. size vs strength
    if cd_path and os.path.exists(cd_path):
        cd = pd.read_parquet(cd_path)
        cd = cd[(cd.role == "T") & cd.maker.str.lower().isin(set(L.W))]
        cd = cd.assign(size=cd.taker_amt).drop_duplicates("tx").set_index("tx")
        tk2 = tk.assign(size=tk.tx.map(cd["size"])).dropna(subset=["size"])
        if len(tk2):
            m2 = tk2.m.to_numpy(np.int64); up2 = tk2.is_up.to_numpy(bool)
            c2 = np.zeros(len(m2))
            for key in keys:
                c2 += np.nan_to_num(mv(S, key, m2 - 600, m2 - 100))
            sg = np.where(up2, 1, -1) * c2
            tk2["large"] = tk2["size"] >= 100
            tk2["strength"] = sg
            b2 = pd.cut(np.abs(c2), [-1, 0.01, 0.1, 0.5, 1, 100])
            res["size_vs_strength"] = {"n": int(len(tk2)), "large_share": round(float(tk2.large.mean()), 4),
                                       "by_abs_move_bp": {str(k): [round(float(tk2.large[b2 == k].mean()), 4), int((b2 == k).sum())] for k in b2.categories},
                                       "auc_abs_move_for_large": round(float(roc_auc_score(tk2.large, np.abs(c2))), 4) if tk2.large.nunique() == 2 else None,
                                       "by_wallet": {w: round(float(g.large.mean()), 4) for w, g in tk2.groupby("wal")}}
    return res


if __name__ == "__main__":
    own_path, a, b, feed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    cd = sys.argv[5] if len(sys.argv) > 5 else None
    res = main(own_path, a, b, feed, cd)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", f"lag7_{a}.json")
    json.dump(res, open(out, "w"), indent=1)
    s = dict(res); prof = s.pop("lag_profile_100ms", [])
    print(json.dumps(s, indent=1)[:4000])
    for p in prof:
        if -1500 <= p["k"] <= 1500:
            print(p)

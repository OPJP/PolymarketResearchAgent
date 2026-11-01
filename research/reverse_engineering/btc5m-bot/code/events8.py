"""Iteration 8, X54 (panel-assumptions iter7 P1, multi-leg events) and X55 (panel-assumptions iter7 P2, wallets as slots).
Live development matches (cluster on-chain fills, match ms = server ms of the trade by tx hash; development blocks only).
1. Refractory: per wallet, gaps between its consecutive distinct matches (taker and maker), and same- vs cross-wallet pairs.
2. Events: cluster TAKER matches on the same window and outcome, each < 300 ms after the previous; legs, wallets.
3. Intensity: P(legs >= 2) and the event's filled shares vs features at the first leg's ms: |vote| and the signed ten-series
   composite toward o over [m - 600, m - 100), the Binance USD-M BTC move toward o over [m - 350, m - 250), the ask change of
   o over [m - 600, m - 100) (raw book), other traders' trades in [m - 1000, m), |p - 0.5|, rel. Univariate AUCs and an
   interleaved half-split logistic against the activity-only model.
Usage: python events8.py OWN A B VFEED CFEED"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
from lag7 import micro_series, mv
from gate8 import raw_touch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score


def main(own, a, b, vf, cf):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    d = d[d.token.isin(tok.keys())].copy()
    d["start"] = d.token.map(lambda t: tok[t][1]); d["is_up"] = d.token.map(lambda t: tok[t][2])
    d = d[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in d.start], bool)]
    d["m"] = d.tx.map(mt)
    d = d[d.m.notna() & (d.m >= a * 1000 + 5000) & (d.m < b * 1000)]
    d["sh"] = d.tamt / 1e6
    res = {"interval": [a, b]}
    # 1. refractory per wallet (distinct tx per wallet)
    ref = {}
    allm = d.drop_duplicates(["tx", "wal"]).sort_values("m")
    for w, g in allm.groupby("wal"):
        gaps = np.diff(g.m.to_numpy(np.int64))
        if len(gaps) < 5:
            continue
        ref[w] = {"n": int(len(g)), "min_ms": int(gaps.min()), "p1": int(np.percentile(gaps, 1)), "p5": int(np.percentile(gaps, 5)),
                  "share_lt_100": round(float((gaps < 100).mean()), 4), "share_lt_200": round(float((gaps < 200).mean()), 4)}
    M = allm.m.to_numpy(np.int64); Wl = allm.wal.to_numpy()
    same = cross = same100 = cross100 = 0
    for i in range(len(M)):
        j = i + 1
        while j < len(M) and M[j] - M[i] < 300:
            if Wl[j] == Wl[i]:
                same += 1; same100 += int(M[j] - M[i] < 100)
            else:
                cross += 1; cross100 += int(M[j] - M[i] < 100)
            j += 1
    shares = allm.wal.value_counts(normalize=True)
    res["refractory"] = ref
    res["pairs_lt300"] = {"same_wallet": same, "cross_wallet": cross, "same_lt100": same100, "cross_lt100": cross100,
                          "independence_same_share": round(float((shares ** 2).sum()), 3)}
    # 2. events on taker matches
    tk = d[d.role == "T"].drop_duplicates(["tx", "token"]).sort_values("m").reset_index(drop=True)
    ev = np.zeros(len(tk), int); e = -1; last = {}
    for i, r in enumerate(tk.itertuples()):
        k = (r.start, r.is_up)
        if k in last and r.m - last[k][0] < 300:
            ev[i] = last[k][1]
        else:
            e += 1; ev[i] = e
        last[k] = (r.m, ev[i])
    tk["ev"] = ev
    E = tk.groupby("ev").agg(m=("m", "min"), up=("is_up", "first"), start=("start", "first"), legs=("tx", "nunique"), wals=("wal", "nunique"),
                             sh=("sh", "sum"), first_wal=("wal", "first"), price=("mamt", "first"), tam=("tamt", "first")).reset_index()
    E["p"] = (E.price / E.tam).clip(0, 1)
    res["events"] = {"n_matches": int(len(tk)), "n_events": int(len(E)), "legs_dist": E.legs.value_counts().sort_index().head(6).to_dict(),
                     "multi_wallet_share_of_multileg": round(float((E.wals[E.legs >= 2] >= 2).mean()), 3) if (E.legs >= 2).any() else None}
    # 3. intensity features at the first leg
    m = E.m.to_numpy(np.int64); up = E.up.to_numpy(bool); sg = np.where(up, 1.0, -1.0)
    S = micro_series(vf, a, b); keys = sorted(S)
    Q = np.vstack([mv(S, k, m - 600, m - 100) for k in keys]); cov = np.isfinite(Q).any(axis=0)
    vote = np.nansum(np.sign(Q) * (np.abs(Q) > 0.002), axis=0) * sg
    comp = np.nansum(Q, axis=0) * sg
    bfb = mv(S, ("bf", "BTC"), m - 350, m - 250) * sg if ("bf", "BTC") in S else np.zeros(len(m))
    R = raw_touch(cf, a, b)
    dask = np.full(len(m), np.nan)
    for s0, rg in R.groupby("m"):
        sel = np.where(E.start.to_numpy() == s0)[0]
        if not len(sel):
            continue
        rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float); bb = rg.bb.to_numpy(float)
        def at(x, tt):
            i = np.searchsorted(rs, tt, "right") - 1
            o = x[np.clip(i, 0, None)].astype(float); o[i < 0] = np.nan
            return o
        uu = up[sel]
        a1 = np.where(uu, at(ba, m[sel] - 100), 1 - at(bb, m[sel] - 100)); a0 = np.where(uu, at(ba, m[sel] - 600), 1 - at(bb, m[sel] - 600))
        dask[sel] = a1 - a0
    tr = trades[~trades.tx.isin(set(d.tx))].copy()
    tr["start"] = tr.token.map(lambda x: tok.get(x, (None, -1))[1])
    act = np.zeros(len(m))
    for s0, gg in tr.groupby("start"):
        ms = np.sort(gg.s_ms.to_numpy(np.int64)); sel = E.start.to_numpy() == s0
        act[sel] = np.searchsorted(ms, m[sel], "left") - np.searchsorted(ms, m[sel] - 1000, "left")
    rel = m / 1000 - E.start.to_numpy()
    F = pd.DataFrame({"absvote": np.abs(vote), "vote_toward": vote, "comp_toward": comp, "abs_comp": np.abs(comp), "bf_btc_350_250": np.nan_to_num(bfb),
                      "dask_o": np.nan_to_num(dask), "act": act, "absp": np.abs(E.p - 0.5), "rel": rel})
    y = (E.legs >= 2).to_numpy(int)
    res["intensity"] = {"share_multileg": round(float(y.mean()), 3), "n": int(len(y))}
    uni = {}
    for c in F.columns:
        try:
            uni[c] = round(float(roc_auc_score(y, F[c])), 3)
        except ValueError:
            pass
    res["intensity"]["univariate_auc_multileg"] = uni
    half = np.arange(len(y)) % 2 == 0
    for nm, cols in (("activity", ["act", "absp", "rel"]), ("activity+trigger", list(F.columns))):
        X = F[cols].to_numpy(float)
        lr = LogisticRegression(max_iter=2000).fit(X[half], y[half])
        lr2 = LogisticRegression(max_iter=2000).fit(X[~half], y[~half])
        res["intensity"][f"auc_halfsplit_{nm}"] = [round(float(roc_auc_score(y[~half], lr.predict_proba(X[~half])[:, 1])), 3),
                                                   round(float(roc_auc_score(y[half], lr2.predict_proba(X[half])[:, 1])), 3)]
    # P(multileg) by |comp| bins
    cb = pd.cut(np.abs(comp), [-1, 0.01, 0.1, 0.5, 1, 100])
    res["intensity"]["p_multileg_by_abs_comp_bp"] = {str(k): [round(float(y[cb == k].mean()), 3), int((cb == k).sum())] for k in cb.categories}
    # event shares vs strength (filled shares, a size proxy without calldata)
    res["intensity"]["auc_event_shares_ge_100_by_abs_comp"] = round(float(roc_auc_score(E.sh >= 100, np.abs(comp)) if (E.sh >= 100).nunique() == 2 else np.nan), 3)
    return res


if __name__ == "__main__":
    own, a, b, vf, cf = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
    res = main(own, a, b, vf, cf)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", f"events8_{a}.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=0, default=str)[:3000])

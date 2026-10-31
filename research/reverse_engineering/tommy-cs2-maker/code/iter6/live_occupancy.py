"""Iteration 6, X70 step 1-2 (information panel iter5 P1) + X80 step 1 (assumptions panel iter5 P1): is the wallet's
resting ladder a FAST public function of the live book?

10-31 14:50-18:00 development block (BUILD-live), server clock, level_events_dev.parquet (7 dev-unit CS2 token-0
books, both sides; own levels by fingerprint with the wallet's actual maker sizes per market, whole cents, capped by
the level size). Dense label: at sample times every 1 s per (book, side), for each whole-cent level from others' best
+2c down to others' best -8c ("down" = worse for that side), y = an own order rests there.
Features at t - 100 ms (book state) and windows ending at t - 100 ms, no own state:
  gap (cents behind others' best), others' size at the level, others' size strictly better than the level,
  others' spread (cents), non-own cancels on the side within 2c of others' best in the last 200 / 1,000 ms,
  others'-best changes in the last 500 ms, seconds since others' best last changed, seconds since the last trade.
Models (logistic and LightGBM, fit on the first half of the block, scored on the second half): G = gap only;
F = all public features; AUC and the gain of F over G. Report also the AUC of G restricted to sides where the wallet
has any own level (its quoting state, own state, diagnostic).
Output: results/live_occupancy.json
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
STEP = 1000.0
LEVELS = list(range(-2, 9))  # cents behind others' best (negative = better than others)


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["a"] = cd.token_id.astype(str).map(t0map)
    wm = cd[(cd.idx >= 0) & (cd.maker == WALLET) & cd.a.notna()]
    own_sizes = {a: set(np.round(g.shares.to_numpy(float), 2)) | {100.0} for a, g in wm.groupby("a")}
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values(["a", "s"]).reset_index(drop=True)
    E["own"] = [bool(w) and (round(float(z), 2) in own_sizes.get(a, {100.0})) for a, z, w in zip(E.a, E["size"], E.whole)]
    rows = []
    for (a, side), g in E.groupby(["a", "side"]):
        sgn = 1.0 if side == "BUY" else -1.0
        lvl = {}
        own = defaultdict(float)
        S = g.s.to_numpy(float); P = g.p.to_numpy(float); Z = g.z.to_numpy(float); D = g.d.to_numpy(float)
        K = g.kind.to_numpy(); O = g.own.to_numpy()
        # other-side best is in the other group; approximate the spread from this book's opposite side later (skip)
        nonown_cancel_t = S[(K == "cancel") & ~O]
        nonown_cancel_p = P[(K == "cancel") & ~O]
        trade_t = S[K == "cons"]
        ob_hist_t, ob_hist_v = [], []
        t_next = S[0] + 5000.0
        i = 0
        n = len(g)
        snap_queue = []
        while i < n:
            s = S[i]
            # take snapshots for sample times t whose state time (t - 100) is before this event
            while t_next - 100.0 < s:
                ob = None
                for p, z in lvl.items():
                    if z - own.get(p, 0.0) > 0.5 and (ob is None or sgn * (p - ob) > 1e-9):
                        ob = p
                if ob is not None:
                    st = t_next - 100.0
                    j = np.searchsorted(ob_hist_t, st, side="right")
                    last_change = ob_hist_t[j - 1] if j > 0 else -1e18
                    nchg = j - np.searchsorted(ob_hist_t, st - 500.0)
                    c_lo2 = np.searchsorted(nonown_cancel_t, st - 200.0); c_hi = np.searchsorted(nonown_cancel_t, st)
                    c_lo10 = np.searchsorted(nonown_cancel_t, st - 1000.0)
                    near2 = np.abs(nonown_cancel_p[c_lo2:c_hi] - ob) <= 0.0201
                    near10 = np.abs(nonown_cancel_p[c_lo10:c_hi] - ob) <= 0.0201
                    jt = np.searchsorted(trade_t, st)
                    last_tr = trade_t[jt - 1] if jt > 0 else -1e18
                    better_size = 0.0
                    lv_sizes = {}
                    for p, z in lvl.items():
                        lv_sizes[round(p, 2)] = (z - own.get(p, 0.0), own.get(p, 0.0))
                    for L in LEVELS:
                        price = round(ob - sgn * L / 100.0, 2)
                        if price <= 0.0 or price >= 1.0:
                            continue
                        oth, mine = lv_sizes.get(price, (0.0, 0.0))
                        ahead = sum(max(v[0], 0.0) for pp, v in lv_sizes.items() if sgn * (pp - price) > 1e-9)
                        rows.append((a, side, t_next, L, int(mine > 0.5), max(oth, 0.0), ahead, int(near2.sum()),
                                     int(near10.sum()), int(nchg), min((st - last_change) / 1000.0, 600.0),
                                     min((st - last_tr) / 1000.0, 600.0), ob))
                t_next += STEP
            p, z, d, k, o = P[i], Z[i], D[i], K[i], O[i]
            before = None
            for pp, zz in lvl.items():
                if zz - own.get(pp, 0.0) > 0.5 and (before is None or sgn * (pp - before) > 1e-9):
                    before = pp
            lvl[p] = z
            if z <= 1e-9:
                lvl.pop(p, None)
            if k == "add" and o:
                own[p] += abs(d)
            elif k == "cancel" and o:
                own[p] = max(0.0, own[p] - abs(d))
            if p in own:
                own[p] = min(own[p], lvl.get(p, 0.0))
            after = None
            for pp, zz in lvl.items():
                if zz - own.get(pp, 0.0) > 0.5 and (after is None or sgn * (pp - after) > 1e-9):
                    after = pp
            if after is not None and (before is None or abs(after - before) > 1e-9):
                ob_hist_t.append(s); ob_hist_v.append(after)
            i += 1
    R = pd.DataFrame(rows, columns=["a", "side", "t", "gap", "y", "oth_at", "oth_ahead", "canc200", "canc1000",
                                    "chg500", "since_chg", "since_trade", "ob"])
    R["lo_ahead"] = np.log1p(R.oth_ahead)
    R["lo_at"] = np.log1p(R.oth_at)
    R["obdev"] = (R.ob - 0.5).abs()
    half = R.t.median()
    tr, va = R[R.t < half], R[R.t >= half]
    res = {"rows": int(len(R)), "base_rate": round(float(R.y.mean()), 3),
           "presence_by_gap": R.groupby("gap").y.mean().round(3).to_dict()}
    G = ["gap"]
    F = ["gap", "lo_at", "lo_ahead", "canc200", "canc1000", "chg500", "since_chg", "since_trade", "obdev"]
    for nm, cols in (("G_gap_only", G), ("F_public_fast", F)):
        Xtr = pd.get_dummies(tr[cols].assign(gap=tr.gap.astype(str)), columns=["gap"]) if True else tr[cols]
        Xva = pd.get_dummies(va[cols].assign(gap=va.gap.astype(str)), columns=["gap"]).reindex(columns=Xtr.columns, fill_value=0)
        lr = LogisticRegression(max_iter=3000).fit(Xtr, tr.y)
        res[nm + "_logit_auc"] = round(float(roc_auc_score(va.y, lr.predict_proba(Xva)[:, 1])), 3)
    try:
        import lightgbm as lgb
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_bin=63, min_child_samples=50, verbose=-1)
        m.fit(tr[F], tr.y)
        res["F_public_fast_lgbm_auc"] = round(float(roc_auc_score(va.y, m.predict_proba(va[F])[:, 1])), 3)
        res["F_lgbm_importance"] = dict(zip(F, [int(v) for v in m.feature_importances_]))
        m2 = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_bin=63, min_child_samples=50, verbose=-1)
        m2.fit(tr[G], tr.y)
        res["G_gap_only_lgbm_auc"] = round(float(roc_auc_score(va.y, m2.predict_proba(va[G])[:, 1])), 3)
    except Exception as e:  # noqa: BLE001
        res["lgbm_error"] = str(e)
    # leave-one-book-out (books = token-0 markets): does the slow-book-shape model generalize across markets?
    try:
        import lightgbm as lgb
        aucs = {}
        for bk in sorted(R.a.unique()):
            trb, vab = R[R.a != bk], R[R.a == bk]
            if vab.y.nunique() < 2:
                continue
            mm = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_bin=63, min_child_samples=50, verbose=-1)
            mm.fit(trb[F], trb.y)
            aucs[str(bk)[:8]] = round(float(roc_auc_score(vab.y, mm.predict_proba(vab[F])[:, 1])), 3)
            mg = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_bin=63, min_child_samples=50, verbose=-1)
            mg.fit(trb[G], trb.y)
            aucs[str(bk)[:8] + "_gap_only"] = round(float(roc_auc_score(vab.y, mg.predict_proba(vab[G])[:, 1])), 3)
        res["leave_one_book_out_auc"] = aucs
    except Exception as e:  # noqa: BLE001
        res["lobo_error"] = str(e)
    # own quoting state (diagnostic): sides where the wallet has any own level at the sample
    anyown = R.groupby(["a", "side", "t"]).y.transform("max")
    va2 = va[anyown.loc[va.index] == 1]
    tr2 = tr[anyown.loc[tr.index] == 1]
    lr = LogisticRegression(max_iter=3000).fit(pd.get_dummies(tr2.gap.astype(str)), tr2.y)
    res["G_given_quoting_side_auc_diag"] = round(float(roc_auc_score(va2.y, lr.predict_proba(pd.get_dummies(va2.gap.astype(str)).reindex(columns=pd.get_dummies(tr2.gap.astype(str)).columns, fill_value=0))[:, 1])), 3)
    (RES / "live_occupancy.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

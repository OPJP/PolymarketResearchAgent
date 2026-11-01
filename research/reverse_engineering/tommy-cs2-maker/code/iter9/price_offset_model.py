"""Iteration 9 (X124 follow-up: the knockout shows the PRICE LEVEL carries the per-market margin): which public,
point-in-time state predicts the wallet's maker price offset from the last print? Unit = every wallet maker order
(unique salt / signing ms) of 16-22 Oct (CS2 + Dota), BUILD = game start < 10-21, VALIDATE = 10-21..22.
Target k = round(100 x (price - round(last print, 2))) clipped to [-10, +3] (the in-play tick is 1 cent).
Public features (taker tapes, prints with block time <= sign - 1 s; the wallet's own transactions excluded):
  last-print aggressor class for the token (taker bought it / sold it), age of the last print, price level, momentum
  over 10 / 60 / 300 s, high - low over 60 s, prints and volume in 10 / 60 s, distinct takers in 60 s, takes by group P
  and group G in 5 / 30 s on the token or its complement, game elapsed minutes, map vs match, Dota flag.
Own-state variant adds the wallet's own net inventory in the token (shares of this token minus the complement, from its
fills with block time <= sign - 1 s).
Model: LightGBM multiclass on BUILD (max_bin 63); decision = argmax_k P(k-1) + P(k) + P(k+1) (optimal for within one
tick). Baselines: k = 0 (last print) and the best constant offset fitted on BUILD. Report within one tick on VALIDATE
and feature importances. Output: results/price_offset_model.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0 = 1792540800
KMIN, KMAX = -10, 3


def main():
    sg = json.load(open(RES / "selection_groupP.json"))
    GP = set(sg["members"])
    GG = {w for w, v in sg["candidates"].items() if not v["member"] and (v["build_grid_share"] or 0) >= 0.2}
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "cid", "oi", "price", "shares", "sign_ms", "salt", "fill", "bts", "gs_ts", "smt", "event"])
    a["maker"] = a.maker.str.lower()
    wtx = set(a.loc[a.maker == W, "tx"])
    wo = a[(a.maker == W) & (a.idx >= 0)].drop_duplicates(["salt", "sign_ms"])
    wo = wo[(wo.sign_ms > 1.79e12) & wo.cid.notna()]
    wf = a[(a.maker == W)][["cid", "oi", "fill", "bts"]].dropna()
    rows = []
    for cid, g in wo.groupby("cid"):
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["timestamp", "price", "size", "side", "outcomeIndex", "proxyWallet", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        if len(d) < 5:
            continue
        ts = d.timestamp.to_numpy(float)
        oi_ = d.outcomeIndex.astype(int).to_numpy()
        sd = d.side.to_numpy()
        pr = d.price.astype(float).to_numpy()
        sz = d["size"].astype(float).to_numpy()
        tk = d.proxyWallet.str.lower().to_numpy()
        p0 = np.where(oi_ == 0, pr, 1 - pr)
        isP, isG = np.isin(tk, list(GP)), np.isin(tk, list(GG))
        # direction of each print for token 0: +1 if it is a buy of token 0 (taker BUY o0 or SELL o1), else -1
        dir0 = np.where(((oi_ == 0) & (sd == "BUY")) | ((oi_ == 1) & (sd == "SELL")), 1, -1)
        cs = np.cumsum(sz)
        ff = wf[wf.cid == cid].sort_values("bts")
        fts = ff.bts.to_numpy(float)
        fsg = np.cumsum(np.where(ff.oi.to_numpy() == 0, ff.fill.to_numpy(float), -ff.fill.to_numpy(float)))
        gs = float(g.gs_ts.iloc[0])
        for r in g.itertuples():
            t = r.sign_ms / 1000 - 1.0
            k = np.searchsorted(ts, t, side="right") - 1
            if k < 0:
                continue
            z = int(r.oi)
            sgn = 1 if z == 0 else -1
            lpz = p0[k] if z == 0 else 1 - p0[k]

            def pz(tt):
                j = np.searchsorted(ts, tt, side="right") - 1
                return (p0[j] if z == 0 else 1 - p0[j]) if j >= 0 else lpz
            lo10, lo60 = np.searchsorted(ts, t - 10), np.searchsorted(ts, t - 60)
            lo5, lo30 = np.searchsorted(ts, t - 5), np.searchsorted(ts, t - 30)
            seg = slice(lo60, k + 1)
            pzseg = (p0[seg] if z == 0 else 1 - p0[seg])
            j = np.searchsorted(fts, t, side="right") - 1
            inv = (fsg[j] * sgn) if j >= 0 else 0.0
            rows.append({
                "cid": cid, "gs": gs, "price": float(r.price), "lp": round(float(lpz), 2), "z": z,
                "agg_buy_ours": int(dir0[k] * sgn > 0), "lp_age": float(t - ts[k]), "lvl": float(lpz),
                "mom10": float(lpz - pz(t - 10)), "mom60": float(lpz - pz(t - 60)), "mom300": float(lpz - pz(t - 300)),
                "hl60": float(pzseg.max() - pzseg.min()) if len(pzseg) else 0.0,
                "n10": int(k + 1 - lo10), "n60": int(k + 1 - lo60), "v60": float(cs[k] - (cs[lo60 - 1] if lo60 > 0 else 0.0)),
                "tk60": int(len(set(tk[seg]))),
                "gP5_ours": int((isP[lo5:k + 1] & (dir0[lo5:k + 1] * sgn > 0)).sum()), "gP5_comp": int((isP[lo5:k + 1] & (dir0[lo5:k + 1] * sgn < 0)).sum()),
                "gP30_ours": int((isP[lo30:k + 1] & (dir0[lo30:k + 1] * sgn > 0)).sum()), "gP30_comp": int((isP[lo30:k + 1] & (dir0[lo30:k + 1] * sgn < 0)).sum()),
                "gG30_ours": int((isG[lo30:k + 1] & (dir0[lo30:k + 1] * sgn > 0)).sum()), "gG30_comp": int((isG[lo30:k + 1] & (dir0[lo30:k + 1] * sgn < 0)).sum()),
                "flow60": float((dir0[seg] * sgn * sz[seg]).sum()),
                "elapsed_min": float((t - gs) / 60), "is_map": int(r.smt == "child_moneyline"), "dota": int(str(r.event).startswith("dota2")),
                "own_inv": float(inv)})
    X = pd.DataFrame(rows)
    X["k"] = np.clip(np.round((X.price - X.lp) * 100), KMIN, KMAX).astype(int)
    X["split"] = np.where(X.gs < VAL0, "build", "validate")
    pub = ["agg_buy_ours", "lp_age", "lvl", "mom10", "mom60", "mom300", "hl60", "n10", "n60", "v60", "tk60", "gP5_ours", "gP5_comp",
           "gP30_ours", "gP30_comp", "gG30_ours", "gG30_comp", "flow60", "elapsed_min", "is_map", "dota"]
    b, v = X[X.split == "build"], X[X.split == "validate"]
    res = {"orders": int(len(X)), "build": int(len(b)), "validate": int(len(v)),
           "k_dist_validate": {int(kk): round(float(c), 4) for kk, c in v.k.value_counts(normalize=True).sort_index().items()}}

    def within(kpred, kt):
        return float((np.abs(np.asarray(kpred) - np.asarray(kt)) <= 1).mean())
    res["baseline_last_print_k0"] = within(np.zeros(len(v)), v.k)
    consts = list(range(KMIN + 1, KMAX))
    cb = max(consts, key=lambda c: within(np.full(len(b), c), b.k))
    res["baseline_best_constant"] = {"k": int(cb), "validate": within(np.full(len(v), cb), v.k)}
    import lightgbm as lgb
    classes = np.arange(KMIN, KMAX + 1)
    for name, feats in (("public", pub), ("public_plus_own_inventory", pub + ["own_inv"])):
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_bin=63, min_child_samples=50,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)
        m.fit(b[feats], b.k - KMIN)
        P = np.zeros((len(v), len(classes)))
        P[:, m.classes_] = m.predict_proba(v[feats])
        S = P.copy()
        S[:, 1:] += P[:, :-1]
        S[:, :-1] += P[:, 1:]
        kp = classes[np.argmax(S, axis=1)]
        imp = sorted(zip(feats, m.booster_.feature_importance("gain")), key=lambda x: -x[1])
        res[name] = {"validate_within_tick": within(kp, v.k), "pred_k_dist": {int(kk): int(c) for kk, c in pd.Series(kp).value_counts().sort_index().items()},
                     "top_gain": [[f, round(float(gv), 1)] for f, gv in imp[:10]]}
        for nm, sel in (("cs2", v.dota == 0), ("dota", v.dota == 1)):
            res[name][f"validate_{nm}"] = within(kp[sel.to_numpy()], v.k[sel])
    X.to_parquet(OUT / "price_offset_rows.parquet", index=False)
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "price_offset_model.json", "w"), indent=1)


if __name__ == "__main__":
    main()

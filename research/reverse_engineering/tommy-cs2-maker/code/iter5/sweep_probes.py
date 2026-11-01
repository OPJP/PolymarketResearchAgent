"""Iteration 5, mechanics panel iter4 P2 (X56): sweep probes, an uncensored on-chain label of the resting ladder.

Probe = a FULLY consumed price level of a multi-level sweep by another taker, in play (16-22 Oct, the wallet's 229
markets, full matched-order record). Under price-time priority every order resting at a fully consumed level is filled,
so y = 1 iff the wallet had a maker order resting at that bid-equivalent price on token Z at the match time (no fill
censoring). The last (partially consumed) level of each sweep is not a probe.
Point-in-time features at m - 2 s (from public txs WITHOUT any wallet order; the probe tx itself is never a feature):
  quote state: d = probe price - others' last observed best bid on Z (cents); pair = others' best bid on Z + on Z';
  activity:    log1p public prints in [m-12, m-2] and [m-62, m-2] s, minutes since game start, price level p, |p-0.5|;
  own state (reported separately): the wallet's net shares on Z minus Z' from its fills before m - 2 s.
Models (logistic and LightGBM, BUILD fit, VALIDATE AUC with an event-block bootstrap of the gain over the activity-only
model): A = activity; Q = activity + quote state; QO = Q + own state. Band rule: P(y | d bucket) from BUILD.
Output: results/sweep_probes.json; probes in .cache/re/tommy-cs2-maker/probes.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter4"))
from queue_replay import load_record  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0, H = 1792540800, 1792713600
LAT = 2000.0


def build():
    cd, gs = load_record()
    cd = cd[cd.m.notna()].copy()
    rows = []
    for cid, g in cd.groupby("cid"):
        gsm = float(gs.get(cid, 0)) * 1000.0
        g = g.sort_values(["m", "tx", "idx"])
        tx = g.tx.to_numpy(); idx = g.idx.to_numpy(); side = g.side.to_numpy().astype(int); oi = g.oi.to_numpy().astype(int)
        pr = g.price.to_numpy(float); fl = g.fill.to_numpy(float); mm = g.m.to_numpy(float); mk = g.maker.to_numpy()
        cut = np.flatnonzero(tx[1:] != tx[:-1]) + 1
        ob = [None, None]
        pend = []
        prints = []  # match times of public txs without wallet orders
        inv = np.zeros(2)
        wfill = []  # (m, z_token, shares) wallet fills (maker and taker) for own state
        for lo, hi in zip(np.r_[0, cut], np.r_[cut, len(g)]):
            ti = np.flatnonzero(idx[lo:hi] == -1)
            if len(ti) == 0:
                continue
            t = lo + ti[0]
            m = mm[t]
            while pend and pend[0][0] <= m - LAT:
                _, zz, val = pend.pop(0)
                ob[zz] = val
            z = int(oi[t]) if side[t] == 1 else 1 - int(oi[t])
            ms = np.arange(lo, hi)[idx[lo:hi] >= 0]
            has_w = bool((mk[lo:hi] == WALLET).any())
            beq = np.where((side[ms] == 0) & (oi[ms] == z), pr[ms], np.where((side[ms] == 1) & (oi[ms] != z), 1 - pr[ms], np.nan))
            ok = np.isfinite(beq)
            # own fills (state for later probes)
            for r in range(lo, hi):
                if mk[r] == WALLET and side[r] == 0:
                    wfill.append((m, int(oi[r]), fl[r]))
            if m >= gsm + 60000 and mk[t] != WALLET and ok.sum() >= 2:
                b = np.round(beq[ok], 3)
                lv = np.unique(b)[::-1]
                if len(lv) >= 2:
                    wb = set(np.round(beq[ok & (mk[ms] == WALLET)], 3))
                    pts = np.array(prints)
                    n10 = int(((pts >= m - 12000) & (pts < m - 2000)).sum()) if len(pts) else 0
                    n60 = int(((pts >= m - 62000) & (pts < m - 2000)).sum()) if len(pts) else 0
                    if wfill:
                        wf = np.array(wfill)
                        sel = wf[:, 0] < m - 2000
                        own = float(np.sum(np.where(wf[sel, 1] == z, wf[sel, 2], -wf[sel, 2])))
                    else:
                        own = 0.0
                    for k, p in enumerate(lv[:-1]):
                        rows.append((cid, gsm / 1000.0, tx[t], m, z, float(p), k, int(p in wb),
                                     (p - ob[z]) * 100 if ob[z] is not None else np.nan,
                                     (ob[0] + ob[1]) if (ob[0] is not None and ob[1] is not None) else np.nan,
                                     n10, n60, (m - gsm) / 60000.0, own, str(mk[t]).lower()))
            if not has_w:
                prints.append(m)
                if ok.any():
                    pend.append((m, z, float(np.nanmax(beq[ok]))))
    P = pd.DataFrame(rows, columns=["cid", "gs", "tx", "m", "z", "p", "k", "y", "d_touch", "pair", "n10", "n60", "elapsed", "own_net", "taker"])
    P.to_parquet(OUT / "probes.parquet", index=False)
    return P


def main():
    p = OUT / "probes.parquet"
    P = pd.read_parquet(p) if (p.exists() and "--rebuild" not in sys.argv) else build()
    P["split"] = np.where(P.gs < VAL0, "BUILD", "VALIDATE")
    P["absmid"] = np.abs(P.p - 0.5)
    P["l10"], P["l60"] = np.log1p(P.n10), np.log1p(P.n60)
    P["dq"] = P.d_touch.fillna(-99).clip(-10, 5)
    P["d_known"] = P.d_touch.notna().astype(int)
    P["pairf"] = P.pair.fillna(0.97)
    P["own_c"] = np.sign(P.own_net) * np.log1p(np.abs(P.own_net))
    res = {"n_probes": P.split.value_counts().to_dict(), "base_rate": P.groupby("split").y.mean().round(4).to_dict(),
           "sweeps": P.groupby("split").tx.nunique().to_dict()}
    A = ["l10", "l60", "elapsed", "p", "absmid"]
    Q = A + ["dq", "d_known", "pairf"]
    QO = Q + ["own_c"]
    b, v = P[P.split == "BUILD"], P[P.split == "VALIDATE"]
    out = {}
    try:
        import lightgbm as lgb
    except Exception:  # noqa: BLE001
        lgb = None
    scores = {}
    for nm, cols in (("A_activity", A), ("Q_quote", Q), ("QO_quote_own", QO)):
        m = LogisticRegression(max_iter=3000).fit(b[cols], b.y)
        sl = m.predict_proba(v[cols])[:, 1]
        out[nm] = {"logit_val_auc": round(float(roc_auc_score(v.y, sl)), 4)}
        if lgb is not None:
            g = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, max_bin=63, min_child_samples=50, verbose=-1)
            g.fit(b[cols], b.y)
            sg = g.predict_proba(v[cols])[:, 1]
            out[nm]["gbm_val_auc"] = round(float(roc_auc_score(v.y, sg)), 4)
            out[nm]["gbm_importance"] = dict(zip(cols, [int(x) for x in g.feature_importances_]))
            scores[nm] = sg
        else:
            scores[nm] = sl
    # event-block bootstrap of the gain Q - A (GBM)
    ev = v.cid.to_numpy()
    uniq = np.unique(ev)
    rng = np.random.default_rng(0)
    gains = []
    yv = v.y.to_numpy()
    grp = {c: np.flatnonzero(ev == c) for c in uniq}
    for _ in range(1000):
        pick = rng.choice(uniq, len(uniq))
        ii = np.concatenate([grp[c] for c in pick])
        if yv[ii].min() == yv[ii].max():
            continue
        gains.append(roc_auc_score(yv[ii], scores["Q_quote"][ii]) - roc_auc_score(yv[ii], scores["A_activity"][ii]))
    gains = np.array(gains)
    out["gain_Q_minus_A"] = {"point": round(float(roc_auc_score(yv, scores["Q_quote"]) - roc_auc_score(yv, scores["A_activity"])), 4),
                             "ci95": [round(float(np.quantile(gains, 0.025)), 4), round(float(np.quantile(gains, 0.975)), 4)],
                             "p_le0": round(float((gains <= 0).mean()), 4), "block": "market"}
    # explicit band rule: P(y | d bucket) from BUILD
    def bucket(d):
        x = np.round(d.clip(-6, 0).to_numpy(float))
        lab = np.array(["unknown" if np.isnan(q) else str(int(q)) for q in x], dtype=object)
        lab[(d > 0.5).to_numpy()] = "above"
        return lab
    b_b, v_b = bucket(b.d_touch), bucket(v.d_touch)
    rate = pd.Series(b.y.to_numpy()).groupby(b_b).mean()
    sv = pd.Series(v_b).map(rate).fillna(b.y.mean()).to_numpy()
    out["band_rule"] = {"build_rate_by_d": {k: round(float(x), 4) for k, x in rate.items()},
                        "build_n_by_d": pd.Series(b_b).value_counts().to_dict(),
                        "val_auc": round(float(roc_auc_score(v.y, sv)), 4)}
    res["models"] = out
    (RES / "sweep_probes.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

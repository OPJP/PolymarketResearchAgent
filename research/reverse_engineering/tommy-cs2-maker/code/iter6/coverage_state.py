"""Iteration 6, X72 (information panel iter5 P3): is the wallet's per-match intermittency (presence among the informed
3c+ bursts persists within a market and is independent across markets) a real on / off input state, or composition
(price level, market type, game time, reversal structure)?

Census bursts (census_bursts.parquet, 16-22 Oct, development data); present = wallet-led or wallet-near; wallet-late
dropped. Covariates per burst: price level of the bought token at t0 - 1 s (public last print, wallet txs excluded),
map vs match market, game-time bin, reversal flag (the previous burst in the same market within 120 s was on the other
token), same-team flag.
Statistics per split: (a) P(present | previous burst in the market within 120 s present) - P(present | previous
absent); (b) number of runs within markets.
Nulls (2,000 draws each): (i) labels permuted within market; (ii) within market x price bin (0.1) x reversal flag x
game-time bin (3) strata; (iii) the same strata pooled across markets of the same event type (map / match) only (no
market term): composition-only null.
Also a logistic model of presence on the covariates (BUILD fit, VALIDATE AUC) with and without the lagged previous
label (the on / off state as a public-observable lag would be own-state-free only if the previous label is public; it
is a wallet take, so it is reported as a diagnostic of persistence only).
Output: results/coverage_state.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
VAL0 = 1792540800
rng = np.random.default_rng(72)


def stats(df):
    """df sorted by cid, t0; columns pres, prev_pres, prev_gap."""
    pres = df.pres.to_numpy()
    same_cid = np.r_[False, df.cid.to_numpy()[1:] == df.cid.to_numpy()[:-1]]
    prev = np.r_[0, pres[:-1]]
    m = same_cid & (df.prev_gap.to_numpy() <= 120)
    a = pres[m & (prev == 1)].mean() if (m & (prev == 1)).any() else np.nan
    b = pres[m & (prev == 0)].mean() if (m & (prev == 0)).any() else np.nan
    runs = int((pres[1:] != pres[:-1])[same_cid[1:]].sum() + df.cid.nunique())
    return float(a - b), runs


def relag(df, pres):
    d = df.copy()
    d["pres"] = pres
    same_cid = np.r_[False, d.cid.to_numpy()[1:] == d.cid.to_numpy()[:-1]]
    d["prev_pres"] = np.where(same_cid, np.r_[np.nan, pres[:-1].astype(float)], np.nan)
    return d


def main():
    B = pd.read_parquet(OUT / "census_bursts.parquet")
    B = B[B.label != "wallet-late"].copy()
    B["pres"] = B.label.isin(["wallet-led", "wallet-near"]).astype(int)
    o = pd.read_parquet(OUT / "orders.parquet")
    smt = dict(zip(o.cid, o.smt)) if "smt" in o.columns else {}
    pm = pd.read_parquet(OUT / "per_market.parquet", columns=["cid", "smt"])
    smt.update(dict(zip(pm.cid, pm.smt)))
    B["is_match"] = (B.cid.map(smt) == "moneyline").astype(int)
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"])
    wtx = set(ca.tx)
    lv = []
    for cid, g in B.groupby("cid"):
        tp = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not tp.exists():
            lv.append(pd.Series(np.nan, index=g.index))
            continue
        d = pd.read_parquet(tp, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        t = d.timestamp.to_numpy(float)
        p0 = np.where(d.outcomeIndex.to_numpy(int) == 0, d.price.to_numpy(float), 1 - d.price.to_numpy(float))
        j = np.searchsorted(t, g.t0.to_numpy(float) - 1, side="right") - 1
        pr = np.where(j >= 0, p0[np.clip(j, 0, None)], np.nan)
        pr = np.where(g.oi.to_numpy() == 0, pr, 1 - pr)
        lv.append(pd.Series(pr, index=g.index))
    B["plev"] = pd.concat(lv)
    B = B.sort_values(["cid", "t0"]).reset_index(drop=True)
    B["prev_gap"] = B.t0 - B.groupby("cid").t0.shift(1)
    B["prev_oi"] = B.groupby("cid").oi.shift(1)
    B["rev"] = ((B.prev_gap <= 120) & (B.prev_oi != B.oi)).astype(int)
    B["same"] = ((B.prev_gap <= 120) & (B.prev_oi == B.oi)).astype(int)
    B["gtime"] = (B.t0 - B.gs) / 3600.0
    B["gtb"] = pd.cut(B["gtime"], [-1, 0.75, 1.75, 99], labels=False)
    B["pb"] = np.clip((B.plev.fillna(0.5) * 10).astype(int), 0, 9)
    B["prev_gap"] = B.prev_gap.fillna(1e9)
    res = {}
    for sp, x in (("BUILD", B[B.gs < VAL0]), ("VALIDATE", B[B.gs >= VAL0])):
        x = x.reset_index(drop=True)
        x = relag(x, x.pres.to_numpy())
        obs_d, obs_r = stats(x)
        out = {"n": int(len(x)), "present_share": round(float(x.pres.mean()), 3),
               "obs_persistence_diff": round(obs_d, 3), "obs_runs": obs_r}
        strata = {"within_market": [x.cid],
                  "within_market_x_price_x_reversal_x_gametime": [x.cid, x.pb, x.rev, x.gtb],
                  "composition_only_no_market": [x.is_match, x.pb, x.rev, x.gtb]}
        for nm, keys in strata.items():
            grp = pd.Series(list(zip(*[k.to_numpy() for k in keys]))).astype(str) if len(keys) > 1 else keys[0].astype(str)
            idx_by = [np.flatnonzero(grp.to_numpy() == gval) for gval in grp.unique()]
            nd, nr = [], []
            p = x.pres.to_numpy().copy()
            for _ in range(2000):
                q = p.copy()
                for ii in idx_by:
                    if len(ii) > 1:
                        q[ii] = q[rng.permutation(ii)]
                d2, r2 = stats(relag(x, q))
                nd.append(d2); nr.append(r2)
            nd, nr = np.array(nd), np.array(nr)
            out[nm] = {"null_diff_median": round(float(np.median(nd)), 3), "p_diff": round(float((nd >= obs_d).mean()), 4),
                       "null_runs_median": float(np.median(nr)), "p_runs": round(float((nr <= obs_r).mean()), 4)}
        # presence by reversal / same-team / price level
        out["present_by_prev"] = {"reversal_120s": round(float(x[x.rev == 1].pres.mean()), 3),
                                  "same_team_120s": round(float(x[x.same == 1].pres.mean()), 3),
                                  "no_prev_120s": round(float(x[(x.rev == 0) & (x.same == 0)].pres.mean()), 3),
                                  "n": [int((x.rev == 1).sum()), int((x.same == 1).sum()), int(((x.rev == 0) & (x.same == 0)).sum())]}
        res[sp] = out
    # public-covariate model (no lag of the wallet's own label): BUILD fit, VALIDATE AUC
    feats = ["is_match", "rev", "same", "gtime"]
    B["pdev"] = (B.plev.fillna(0.5) - 0.5).abs()
    B["plev_f"] = B.plev.fillna(0.5)
    B["lmove"] = np.log(B.move10.clip(lower=0.03))
    B["lusd"] = np.log1p(B.usd)
    F = feats + ["pdev", "plev_f", "lmove", "lusd", "n_orders"]
    tr, va = B[B.gs < VAL0], B[B.gs >= VAL0]
    lr = LogisticRegression(max_iter=2000).fit(tr[F], tr.pres)
    res["public_covariate_model"] = {"features": F, "validate_auc": round(float(roc_auc_score(va.pres, lr.predict_proba(va[F])[:, 1])), 3),
                                     "coef": dict(zip(F, np.round(lr.coef_[0], 3).tolist()))}
    B2 = relag(B, B.pres.to_numpy())
    B2["lag_pres_120"] = np.where(B2.prev_gap <= 120, B2.prev_pres.fillna(0), 0.0)
    F2 = F + ["lag_pres_120"]
    tr2, va2 = B2[B2.gs < VAL0], B2[B2.gs >= VAL0]
    lr2 = LogisticRegression(max_iter=2000).fit(tr2[F2], tr2.pres)
    res["with_lagged_own_label_diagnostic"] = {"validate_auc": round(float(roc_auc_score(va2.pres, lr2.predict_proba(va2[F2])[:, 1])), 3),
                                               "coef_lag": round(float(lr2.coef_[0][-1]), 3)}
    (RES / "coverage_state.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

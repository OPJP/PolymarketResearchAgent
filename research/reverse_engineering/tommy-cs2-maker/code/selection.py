"""Selection (component 1): which CS2 match / map-winner markets the wallet trades.
Universe: every CS2 moneyline + child_moneyline market with gameStartTime in [MAKER_START, H) (plus the Dota 2 markets
it traded are outside the CS2 universe: reported as coverage). Label: wallet has >= 1 fill in the market.
Rules (fitted on BUILD = gs < SPLIT, scored on VALIDATE):
  S_meta   league rate (BUILD target encoding, k=5 shrinkage toward the tier rate), listing metadata only;
  B_act    activity baseline: pre-game prints / volume / distinct takers in [gs-1h, gs) of the market's event;
Threshold pre-registered: smallest score threshold whose BUILD lift >= 3; report VALIDATE AUC, recall, lift."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, RES, TAPES, WALLET, SPLIT, MAKER_START, auc  # noqa: E402

def frame(d0=MAKER_START, d1=H, traded=None):
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[u.smt.isin(["moneyline", "child_moneyline"]) & (u.gs_ts >= d0) & (u.gs_ts < d1)].copy()
    u["gs_ts"] = u["gs_ts"].astype("int64")
    if traded is None:
        traded = set(pd.read_parquet(OUT / "orders.parquet", columns=["cid"])["cid"])
    u["y"] = u.cid.isin(traded).astype(int)
    pre_n, pre_v, pre_w = [], [], []
    for cid, gs in zip(u.cid, u.gs_ts):
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists():
            pre_n.append(np.nan); pre_v.append(np.nan); pre_w.append(np.nan); continue
        d = pd.read_parquet(p, columns=["timestamp", "price", "size", "proxyWallet"])
        d = d[(d.timestamp >= gs - 3600) & (d.timestamp < gs) & (d.proxyWallet != WALLET)]
        pre_n.append(len(d)); pre_v.append(float((d.price.astype(float) * d["size"].astype(float)).sum())); pre_w.append(d.proxyWallet.nunique())
    u["pre_n"], u["pre_v"], u["pre_w"] = pre_n, pre_v, pre_w
    ev = u.groupby("event_slug")[["pre_n", "pre_v", "pre_w"]].transform("sum")
    u["e_pre_n"], u["e_pre_v"], u["e_pre_w"] = ev["pre_n"], ev["pre_v"], ev["pre_w"]
    u["tier"] = pd.to_numeric(u.league_tier, errors="coerce")
    return u

def league_rate(b, v, k=5.0):
    prior = b.y.mean()
    tr = b.groupby("tier").y.mean()
    lg = b.groupby("league").y.agg(["sum", "size"])
    v = v.copy()
    tier_rate = v.tier.map(tr).fillna(prior)
    s = v.league.map(lg["sum"]); n = v.league.map(lg["size"])
    v["s_meta"] = ((s.fillna(0) + k * tier_rate) / (n.fillna(0) + k)).astype(float)
    return v

def thr_metrics(sb, yb, sv, yv, lift_min=3.0):
    base_b = yb.mean(); best = None
    for t in np.unique(sb)[::-1]:
        sel = sb >= t
        if sel.sum() == 0: continue
        lift = yb[sel].mean() / base_b
        if lift >= lift_min: best = t
    if best is None: return {"thr": None}
    sel = sv >= best; base = yv.mean()
    prec = yv[sel].mean() if sel.sum() else float("nan")
    return {"thr": float(best), "val_recall": round(float(yv[sel].sum() / yv.sum()), 3), "val_lift": round(float(prec / base), 2), "val_selected": int(sel.sum())}

def main():
    u = frame()
    b, v = u[u.gs_ts < SPLIT], u[u.gs_ts >= SPLIT]
    v = league_rate(b, v); bb = league_rate(b, b)  # in-sample for threshold (note: optimistic on BUILD)
    res = {"universe_build": len(b), "universe_val": len(v), "pos_build": int(b.y.sum()), "pos_val": int(v.y.sum())}
    res["S_meta"] = {"val_auc": round(auc(v.s_meta, v.y), 4)} | thr_metrics(bb.s_meta.to_numpy(), bb.y.to_numpy(), v.s_meta.to_numpy(), v.y.to_numpy())
    for f in ["e_pre_n", "e_pre_v", "e_pre_w"]:
        res[f"B_{f}"] = {"val_auc": round(auc(v[f].fillna(0), v.y), 4)} | thr_metrics(b[f].fillna(0).to_numpy(), b.y.to_numpy(), v[f].fillna(0).to_numpy(), v.y.to_numpy())
    # combined logistic: activity baseline vs activity + meta
    from sklearn.linear_model import LogisticRegression
    def X(d, cols): return np.column_stack([np.log1p(d[c].fillna(0).to_numpy()) if c.startswith("e_pre") else d[c].to_numpy() for c in cols])
    bl = league_rate(b, b)
    for name, cols in (("B_act_logit", ["e_pre_n", "e_pre_v", "e_pre_w"]), ("S_meta_act_logit", ["e_pre_n", "e_pre_v", "e_pre_w", "s_meta"])):
        m = LogisticRegression(max_iter=2000).fit(X(bl, cols), bl.y)
        sv = m.predict_proba(X(v, cols))[:, 1]; sb = m.predict_proba(X(bl, cols))[:, 1]
        res[name] = {"val_auc": round(auc(sv, v.y), 4)} | thr_metrics(sb, bl.y.to_numpy(), sv, v.y.to_numpy())
    json.dump(res, open(RES / "results/selection.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()

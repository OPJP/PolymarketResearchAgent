"""Iteration 7, panel iter6 information I1 (X43; reopens X42): score the Chainlink input on the historical lot.

Inputs: code7/fetch_cl.py grid (Chainlink stamped at every bin start - 3 s for the pre-registered sample windows),
Gamma priceToBeat (code7/fetch_ptb.py), the lot panels (.cache/re/directional-maker/exam/panel_day_*.parquet, R2/R3
features + labels), the frozen R3 models (code/presence3_*.txt).
Fit on the STUDY sample (10-23..26), report on the VALIDATE sample (10-27..30) in aggregate only.

  .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code7/i1_cl_hist.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[4]
CODE = ROOT / "research/reverse_engineering/directional-maker/code"
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT))
import final_rule as fr  # noqa: E402
from train2 import PARAMS, ROUNDS, side_metrics  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
OUT = ROOT / "research/reverse_engineering/directional-maker/results"
S0, V0, V1 = 1792713600, 1793059200, 1793404800
TW = 60
CLF = ["gap_s", "edge_cl_s", "dcl10_s", "z_cl_s", "fair_cl_s"]


def cl_series(path=None):
    g = pd.read_parquet(path or (C / "cl/cl_grid.parquet")).dropna(subset=["open"])
    a = pd.Series(g["open"].to_numpy(), index=g["tau"].astype(np.int64).to_numpy())
    b = pd.Series(g["close"].to_numpy(), index=(g["tau"].astype(np.int64) + 300).to_numpy())
    s = pd.concat([a, b])
    s = s[~s.index.duplicated()]
    return s.sort_index()


def sample_windows():
    out = []
    for d in [S0 + 86400 * k for k in range(8)]:
        for i in range(0, 288, 8):
            out += [d + 300 * i, d + 300 * (i + 1)]
    return set(out)


def add_cl(p: pd.DataFrame, cl: pd.Series, ptb: dict, lag: int = 3) -> pd.DataFrame:
    """Chainlink features at each bin start t from the value stamped t - lag (and t - lag - 10)."""
    t = (p["start_ts"] + p["rel"]).to_numpy(np.int64)
    st = p["start_ts"].to_numpy(np.int64)
    end = st + 300
    v = cl.reindex(t - lag).to_numpy()
    v13 = cl.reindex(t - lag - 10).to_numpy()
    k = np.array([ptb.get(s, np.nan) for s in st])
    sig = p["sig"].to_numpy() / 1e4
    # closing TWAP = mean of CL stamped [end-61, end-2]; known part = grid values stamped in [end-61, t-lag]
    known = np.full(len(p), np.nan)
    rel = p["rel"].to_numpy()
    for r in np.unique(rel):
        if r < 240:
            continue
        m = rel == r
        offs = [o for o in range(300 - 61 + ((10 - lag - 239) % 10), int(r) - lag + 1, 10) if o >= 239]
        if offs:
            known[m] = np.nanmean(np.stack([cl.reindex(st[m] + o).to_numpy() for o in offs]), axis=0)
    r_rem = np.clip(st + 298 - (t - lag), 0, TW).astype(float)
    ts = end - TW
    before = (t < ts) | np.isnan(known)
    var_b = np.clip(ts - t, 0, None) + TW / 3.0
    mean_in = ((TW - r_rem) * np.nan_to_num(known) + r_rem * v) / TW
    sd_in = (r_rem / TW) * np.sqrt(np.maximum(r_rem, 1e-9) / 3.0)
    mean = np.where(before, v, mean_in)
    sdu = np.where(before, np.sqrt(var_b), sd_in)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (mean - k) / (v * sig * sdu)
    fu = stats.norm.cdf(z)
    up = p["side_up"].to_numpy() == 1
    sg = np.where(up, 1.0, -1.0)
    p["fair_cl_s"] = np.where(up, fu, 1 - fu).astype(np.float32)
    p["z_cl_s"] = np.clip(z * sg, -8, 8).astype(np.float32)
    p["edge_cl_s"] = (p["fair_cl_s"] - p["last_s"]).astype(np.float32)
    p["gap_s"] = (p["fair_cl_s"] - p["fair_s"]).astype(np.float32)
    with np.errstate(invalid="ignore", divide="ignore"):
        p["dcl10_s"] = (np.log(v / v13) * 1e4 * sg).astype(np.float32)
    p["cl_ok"] = np.isfinite(v) & np.isfinite(k)
    return p


def logit(x):
    x = np.clip(np.asarray(x, float), 1e-6, 1 - 1e-6)
    return np.log(x / (1 - x))


def block_boot(y, a, b, blocks, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    ub = np.unique(blocks)
    idx = {u: np.where(blocks == u)[0] for u in ub}
    out = []
    for _ in range(n):
        pick = rng.choice(ub, len(ub), replace=True)
        ii = np.concatenate([idx[u] for u in pick])
        yy = y[ii]
        if yy.sum() == 0 or yy.sum() == len(yy):
            continue
        out.append(fr._auc(yy, a[ii]) - fr._auc(yy, b[ii]))
    out = np.asarray(out)
    return {"mean": float(out.mean()), "lo95": float(np.quantile(out, 0.025)), "hi95": float(np.quantile(out, 0.975)),
            "p_le0": float(np.mean(out <= 0))}


def load_panel(days=range(S0, V1, 86400)):
    import lightgbm as lgb
    p = pd.concat([pd.read_parquet(C / f"exam/panel_day_{d}.parquet") for d in days], ignore_index=True)
    p = fr._add_clock(p)
    for nm in ("rule", "activity"):
        m = lgb.Booster(model_file=str(CODE / f"presence3_{nm}.txt"))
        p["p_" + nm] = m.predict(p[fr.FEATS[nm]])
    return p


def main():
    import lightgbm as lgb
    from sklearn.linear_model import LogisticRegression
    cl = cl_series()
    pt = pd.read_parquet(C / "cl/ptb_lot.parquet")
    ptb = dict(zip(pt["start_ts"].astype(np.int64), pt["ptb"]))
    samp = sample_windows()
    p = load_panel()
    vv = p.start_ts >= V0
    res = {"full_lot_check": {"validate_auc_r3": fr._auc(p.loc[vv, "y"], p.loc[vv, "p_rule"]),
                              "validate_auc_activity": fr._auc(p.loc[vv, "y"], p.loc[vv, "p_activity"])}}
    p = p[p["start_ts"].isin(samp)].copy()
    p = add_cl(p, cl, ptb)
    res["coverage"] = {"bins": int(len(p)), "cl_ok": float(p["cl_ok"].mean())}
    p = p[p["cl_ok"]].copy()
    tr, va = p[p.start_ts < V0].copy(), p[p.start_ts >= V0].copy()
    res["n"] = {"study_bins": int(len(tr)), "study_windows": int(tr.cid.nunique()), "study_pos": int(tr.y.sum()),
                "valid_bins": int(len(va)), "valid_windows": int(va.cid.nunique()), "valid_pos": int(va.y.sum())}
    res["gap_describe"] = {"study_abs_gap_median": float(np.median(np.abs(tr.gap_s))),
                           "study_abs_gap_p90": float(np.quantile(np.abs(tr.gap_s), 0.9)),
                           "corr_fair_cl_fair_bn": float(np.corrcoef(tr.fair_cl_s, tr.fair_s)[0, 1])}
    res["univariate_valid"] = {c: fr._auc(va.y, va[c].fillna(0).to_numpy()) for c in
                               ["edge_s", "edge_cl_s", "fair_s", "fair_cl_s", "gap_s", "dcl10_s", "p_rule", "p_activity"]}
    res["univariate_study"] = {c: fr._auc(tr.y, tr[c].fillna(0).to_numpy()) for c in
                               ["edge_s", "edge_cl_s", "fair_s", "fair_cl_s", "gap_s", "dcl10_s", "p_rule", "p_activity"]}
    out = {}
    blocks = (va["start_ts"] // 7200).to_numpy()
    for base in ("rule", "activity"):
        Xtr = np.column_stack([logit(tr["p_" + base])] + [tr[c].fillna(0).to_numpy() for c in CLF])
        Xva = np.column_stack([logit(va["p_" + base])] + [va[c].fillna(0).to_numpy() for c in CLF])
        lr0 = LogisticRegression(C=1.0, max_iter=2000).fit(Xtr[:, :1], tr.y)
        lr = LogisticRegression(C=1.0, max_iter=2000).fit(Xtr, tr.y)
        s0, s1 = lr0.predict_proba(Xva[:, :1])[:, 1], lr.predict_proba(Xva)[:, 1]
        out[base] = {"auc_base": fr._auc(va.y, s0), "auc_base+cl": fr._auc(va.y, s1),
                     "coef": dict(zip(["logit_p"] + CLF, np.round(lr.coef_[0], 4).tolist())),
                     "intercept": float(lr.intercept_[0]),
                     "boot_gain": block_boot(va.y.to_numpy(), s1, s0, blocks, n=1000)}
        va["s_" + base + "_cl"] = s1
        va["s_" + base] = s0
    res["stack"] = out
    res["side_valid"] = {"r3": side_metrics(va, "p_rule"), "r5_stack": side_metrics(va, "s_rule_cl"),
                         "activity": side_metrics(va, "p_activity"), "activity+cl": side_metrics(va, "s_activity_cl"),
                         "edge_cl": side_metrics(va.assign(q=va.edge_cl_s.fillna(0)), "q"),
                         "edge_bn": side_metrics(va.assign(q=va.edge_s.fillna(0)), "q")}
    fa = fr.FEATS["rule"]
    abl = {}
    for nm, feats in (("r3feats", fa), ("r3feats+cl", fa + CLF), ("activity", fr.FEATS["activity"]),
                      ("activity+cl", fr.FEATS["activity"] + CLF)):
        prm = dict(PARAMS, min_data_in_leaf=200, verbose=-1)
        m = lgb.train(prm, lgb.Dataset(tr[feats], tr["y"]), ROUNDS)
        va["g_" + nm] = m.predict(va[feats])
        abl[nm] = fr._auc(va.y, va["g_" + nm])
        if nm.endswith("+cl"):
            abl[nm + "_imp"] = dict(sorted(zip(feats, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:8])
    res["ablation_lgbm_study_fit"] = abl
    res["per_day_valid"] = {str(int(d)): {"r3": fr._auc(g.y, g.p_rule), "r5": fr._auc(g.y, g.s_rule_cl)}
                            for d, g in va.groupby(va.start_ts // 86400 * 86400)}
    # B3 on the lot: cluster maker BUY fill prices vs the Chainlink and Binance fairs of their bin (both at the bin start)
    try:
        from polyrea.analysis.updown import windows_from_markets
        from polyrea.workflows.updown_study import fetch_windows
        sl = sorted({f"btc-updown-5m-{int(s)}" for s in p.start_ts.unique()})
        ws = windows_from_markets(fetch_windows(sl))
        tok = {}
        for x in ws:
            tok[str(x.up_token)] = (x.start_ts, 1)
            tok[str(x.down_token)] = (x.start_ts, 0)
        f = pd.read_parquet(C / "exam/fills_holdout.parquet")
        f = f[(f.role == "maker") & (f.side == "BUY")].copy()
        f["k"] = [tok.get(str(t)) for t in f.token_id]
        f = f[f.k.notna()].copy()
        f["start_ts"] = [k[0] for k in f.k]
        f["side_up"] = [k[1] for k in f.k]
        f["rel"] = ((f.ts - f.start_ts) // 10 * 10).astype(int)
        key = p[["start_ts", "rel", "side_up", "fair_cl_s", "fair_s", "last_s"]]
        m = f.merge(key, on=["start_ts", "rel", "side_up"], how="inner")
        b3 = {}
        for nm, g in (("study", m[m.start_ts < V0]), ("validate", m[m.start_ts >= V0])):
            mid = g[(g.fair_s > 0.1) & (g.fair_s < 0.9)]
            b3[nm] = {"fills": int(len(g)), "mad_cl": float(np.median(np.abs(g.price - g.fair_cl_s))),
                      "mad_bn": float(np.median(np.abs(g.price - g.fair_s))),
                      "corr_cl": float(np.corrcoef(g.price, g.fair_cl_s)[0, 1]), "corr_bn": float(np.corrcoef(g.price, g.fair_s)[0, 1]),
                      "mid_fills": int(len(mid)), "mid_mad_cl": float(np.median(np.abs(mid.price - mid.fair_cl_s))),
                      "mid_mad_bn": float(np.median(np.abs(mid.price - mid.fair_s))),
                      "share_closer_to_cl": float(np.mean(np.abs(g.price - g.fair_cl_s) < np.abs(g.price - g.fair_s)))}
        res["b3_fill_price"] = b3
    except Exception as ex:  # noqa: BLE001
        res["b3_fill_price"] = {"error": repr(ex)[:300]}
    OUT.joinpath("iter7_i1_cl_hist.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float)[:7000])


if __name__ == "__main__":
    main()

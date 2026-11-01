"""R5 (iteration 7; adopted by the pre-registered criterion: on the VALIDATE sample presence AUC 0.6997 vs R3 0.6923,
2-h block-bootstrap gain +0.0075 [+0.0016, +0.0131]): R3's presence score stacked with Chainlink features (the
settlement stream), fitted (logistic) on the STUDY sample (154 windows of 10-23..26). Features at each bin start t use the Chainlink BTC/USD value stamped t - CL_LAG (and t - CL_LAG - 10),
Gamma priceToBeat (fixed at the window start) and R3's own volatility input (panel column 'sig').

fair_cl_s : digital P(closing TWAP-60 >= priceToBeat) from Chainlink, with the known part of the closing TWAP in the
            last minute (TWAP = mean of the values stamped [end-61, end-2]); side s
z_cl_s    : the z-score of that digital, signed by side, clipped to +-8
edge_cl_s : fair_cl_s - last clean print on s
gap_s     : fair_cl_s - R3's Binance fair_s
dcl10_s   : 10-s Chainlink log change (bp), signed by side
p_R5 = sigmoid(R5_INTERCEPT + R5_COEF . [logit(p_R3), gap_s, edge_cl_s, dcl10_s, z_cl_s, fair_cl_s]) (NaN -> 0)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

CL_LAG = 3
TW = 60
R5_FEATS = ["gap_s", "edge_cl_s", "dcl10_s", "z_cl_s", "fair_cl_s"]
R5_INTERCEPT = 0.7244311641234775   # STUDY-sample logistic fit, code7/i1_cl_hist.py (results/iter7_i1_cl_hist.json)
R5_COEF = [1.2305, 1.2574, -0.7608, 0.0454, 0.0743, -0.6915]  # logit(p_R3), gap_s, edge_cl_s, dcl10_s, z_cl_s, fair_cl_s


def stamps_needed(panel: pd.DataFrame) -> np.ndarray:
    t = (panel["start_ts"] + panel["rel"]).to_numpy(np.int64)
    st = panel["start_ts"].to_numpy(np.int64)
    extra = np.concatenate([st + o for o in range(247, 300, 10)])
    return np.unique(np.concatenate([t - CL_LAG, t - CL_LAG - 10, extra]))


def add_cl(p: pd.DataFrame, cl: pd.Series, ptb: dict, lag: int = CL_LAG) -> pd.DataFrame:
    t = (p["start_ts"] + p["rel"]).to_numpy(np.int64)
    st = p["start_ts"].to_numpy(np.int64)
    end = st + 300
    v = cl.reindex(t - lag).to_numpy()
    v13 = cl.reindex(t - lag - 10).to_numpy()
    k = np.array([ptb.get(s, np.nan) for s in st], dtype=float)
    sig = p["sig"].to_numpy() / 1e4
    known = np.full(len(p), np.nan)
    rel = p["rel"].to_numpy()
    for r in np.unique(rel):
        if r < 240:
            continue
        m = rel == r
        offs = [o for o in range(247, int(r) - lag + 1, 10)]
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


def score(p: pd.DataFrame, p_r3: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(p_r3, float), 1e-6, 1 - 1e-6)
    z = R5_INTERCEPT + R5_COEF[0] * np.log(x / (1 - x))
    for c, f in zip(R5_COEF[1:], R5_FEATS):
        z = z + c * np.nan_to_num(p[f].to_numpy(float))
    return 1 / (1 + np.exp(-z))

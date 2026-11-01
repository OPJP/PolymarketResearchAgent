"""Iteration 12: a new per-second NET-FLOW model (nf12) for the exposure tracker. Target: the cluster's signed net share
flow at block second s of the window (Up +, Down -). Features (PIT, as cells.py: spot closes <= s-2, others' prints <= s-1):
the cell base features of the Up cell, the tape features of both outcomes, and NEW slow path features (pre-open M1 / M2,
move since open, lagged minutes, 2 / 5 / 15-min moves, exact-strike z from Gamma priceToBeat, previous window's outcome
from the published priceToBeat pair, ask sum). No own state (inv_* / avg_* / pair_if_buy dropped). Fit on BUILD
(10-09..16) only; predictions on VALIDATE saved to .cache/re/btc5m-bot/it12/nf12_val.parquet."""
import os, sys, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd, lightgbm as lgb
from scipy.special import ndtr
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = f"{C}/it12"; os.makedirs(OUT, exist_ok=True)
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
CODE = os.path.dirname(os.path.abspath(__file__))
VAL0, H = 1792108800, 1792713600
SPOT = ["rel", "tau", "sig", "z", "fv", "r1", "rn1", "r2", "rn2", "r3", "rn3", "r5", "rn5", "r10", "rn10", "r20", "rn20", "r30", "rn30", "r60", "rn60", "absr1", "mxf3", "mxa3", "mxf10", "mxa10"]
TAPE = ["has_tape", "m_last", "age_last", "ask_o", "age_ask", "bid_o", "age_bid", "vwap10", "vwap30", "n1", "n2", "n5", "n30", "vol30", "flow1", "flow2", "flow5", "flow30", "sp_since", "gap_m", "gap_ask", "gap_vw", "spread", "dm5", "dm10", "dm30", "dgap5", "dgap10"]
DT = ["ask_o", "age_ask", "bid_o", "age_bid", "flow1", "flow5", "flow30", "dm5", "dm10", "dm30", "gap_m", "gap_ask", "spread"]
SLOW_PTB = ["M1", "M2", "since_open", "since_open_n", "lag1", "lag2", "r120", "r300", "r900", "z_ptb", "fv_ptb", "prev_up", "ask_sum", "ask_diff", "fv_gap_u", "fv_gap_d"]
SLOW_SPOT = ["M1", "M2", "since_open", "since_open_n", "lag1", "lag2", "r120", "r300", "r900", "prev_up_spot", "ask_sum", "ask_diff", "fvc_gap_u", "fvc_gap_d"]
VARIANT = os.environ.get("NF12_VARIANT", "ptb")  # "ptb" (nf12) or "spot" (nf12b: computable inside final_rule from its spot index)
SLOW = SLOW_PTB if VARIANT == "ptb" else SLOW_SPOT
SUF = "" if VARIANT == "ptb" else ("m" if VARIANT == "mkt" else "b")
MKT_FEATS = ["rel", "tau"] + TAPE + ["D_" + c for c in DT] + ["ask_sum", "ask_diff"]  # market-activity-only co-occurrence baseline (no spot / venue input)
PARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=63, min_data_in_leaf=400, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=12)
ROUNDS = 400


def slow_feats(df, px, s0, ptb):
    """df has cid, start_ts, rel, sig (x1e5), tau; px = Binance 1-s closes indexed from s0 (close of second t usable from t+2)."""
    lp = np.log(px)
    L = lambda t: lp[np.clip(t - s0, 0, len(lp) - 1)]
    st = df.start_ts.to_numpy(np.int64); s = st + df.rel.to_numpy(np.int64); q = s - 2
    sig = df.sig.to_numpy(float) / 1e5; tau = np.maximum(df.tau.to_numpy(float), 1)
    o = {}
    o["M1"] = (L(st - 62) - L(st - 302)) * 1e4
    o["M2"] = (L(np.minimum(st - 2, q)) - L(st - 62)) * 1e4
    o["since_open"] = (L(q) - L(st - 2)) * 1e4
    o["since_open_n"] = (L(q) - L(st - 2)) / (sig * np.sqrt(np.maximum(df.rel.to_numpy(float), 1)))
    o["lag1"] = (L(q - 60) - L(q - 120)) * 1e4
    o["lag2"] = (L(q - 120) - L(q - 180)) * 1e4
    o["r120"] = (L(q) - L(q - 120)) * 1e4
    o["r300"] = (L(q) - L(q - 300)) * 1e4
    o["r900"] = (L(q) - L(q - 900)) * 1e4
    k = ptb.reindex(df.start_ts.to_numpy()).to_numpy(float)
    kprev = ptb.reindex(df.start_ts.to_numpy() - 300).to_numpy(float)
    z = (L(q) - np.log(k)) / (sig * np.sqrt(tau))
    o["z_ptb"] = np.where(df.rel.to_numpy() >= 1, z, np.nan)
    o["fv_ptb"] = ndtr(o["z_ptb"])
    o["prev_up"] = np.where(np.isfinite(k) & np.isfinite(kprev), np.sign(k - kprev), np.nan)
    tw = np.array([lp[np.clip(np.arange(t - 60, t) - s0, 0, len(lp) - 1)].mean() for t in np.unique(st)])
    twp = np.array([lp[np.clip(np.arange(t - 360, t - 300) - s0, 0, len(lp) - 1)].mean() for t in np.unique(st)])
    pu = pd.Series(np.sign(tw - twp), index=np.unique(st))
    o["prev_up_spot"] = pu.reindex(st).to_numpy(float)
    return pd.DataFrame({kk: np.asarray(v, np.float32) for kk, v in o.items()}, index=df.index)


def pair_frame(d, px, s0, ptb):
    """Up/Down cell rows of one period -> one row per (cid, rel) with the nf12 features."""
    up = d[d.is_up].sort_values(["cid", "rel"]).reset_index(drop=True)
    dn = d[~d.is_up].sort_values(["cid", "rel"]).reset_index(drop=True)
    assert (up.cid.to_numpy() == dn.cid.to_numpy()).all() and (up.rel.to_numpy() == dn.rel.to_numpy()).all()
    X = up[["cid", "start_ts"] + SPOT + TAPE].copy()
    for c in DT:
        X["D_" + c] = dn[c].to_numpy(np.float32)
    X = pd.concat([X, slow_feats(X, px, s0, ptb)], axis=1)
    X["ask_sum"] = (X.ask_o + X.D_ask_o).astype(np.float32)
    X["ask_diff"] = (X.ask_o - X.D_ask_o).astype(np.float32)
    X["fv_gap_u"] = (X.fv_ptb - X.ask_o).astype(np.float32)
    X["fv_gap_d"] = ((1 - X.fv_ptb) - X.D_ask_o).astype(np.float32)
    X["fvc_gap_u"] = (X.fv - X.ask_o).astype(np.float32)
    X["fvc_gap_d"] = ((1 - X.fv) - X.D_ask_o).astype(np.float32)
    return X


def load(px, s0, ptb, fl):
    parts = []
    for fn in sorted(os.listdir(f"{C}/cells")):
        d = pd.read_parquet(f"{C}/cells/{fn}", columns=["cid", "start_ts", "is_up"] + SPOT + TAPE)
        parts.append(pair_frame(d, px, s0, ptb)); del d
    X = pd.concat(parts, ignore_index=True); del parts
    g = fl[(fl.rel >= 0) & (fl.rel < 300)]
    y = (g.shares * np.where(g.is_up, 1.0, -1.0)).groupby([g.cid, g.rel.astype(np.int64)]).sum()
    idx = pd.MultiIndex.from_arrays([X.cid.to_numpy(), X.rel.to_numpy().astype(np.int64)])
    X["y"] = y.reindex(idx).fillna(0).to_numpy(np.float32)
    for w in ("GF", "XM", "DS"):
        gw = g[g.wallet == w]
        yw = (gw.shares * np.where(gw.is_up, 1.0, -1.0)).groupby([gw.cid, gw.rel.astype(np.int64)]).sum()
        X["y" + w] = yw.reindex(idx).fillna(0).to_numpy(np.float32)
    return X


def main():
    t0 = time.time()
    b = pd.read_parquet(f"{C}/binance_1s.parquet")
    s0 = int(b.sec.min()); px = b.set_index("sec").close.reindex(np.arange(s0, int(b.sec.max()) + 1)).ffill().to_numpy(float)
    pt = pd.read_parquet(f"{C}/ptb.parquet")
    ptb = pt.set_index("start").priceToBeat.astype(float)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["wallet", "shares", "cid", "rel", "is_up", "start_ts"])
    X = load(px, s0, ptb, fl)
    print("rows", len(X), "load s", round(time.time() - t0), flush=True)
    feats = SPOT + TAPE + ["D_" + c for c in DT] + SLOW if VARIANT != "mkt" else MKT_FEATS
    tr = (X.start_ts < VAL0).to_numpy(); va = ((X.start_ts >= VAL0) & (X.start_ts < H)).to_numpy()
    res = {}
    preds = pd.DataFrame({"cid": X.cid[va].to_numpy(), "rel": X.rel[va].to_numpy()})
    for tgt, nm in ((("y", "nf12"), ("yGF", "nf12_GF"), ("yXM", "nf12_XM"), ("yDS", "nf12_DS")) if VARIANT == "ptb" else (("y", "nf12" + SUF),)):
        dtr = lgb.Dataset(X.loc[tr, feats], X.loc[tr, tgt], free_raw_data=True)
        m = lgb.train(PARAMS, dtr, num_boost_round=ROUNDS)
        m.save_model(f"{CODE}/model_it12_{nm}.txt")
        preds[nm] = m.predict(X.loc[va, feats], num_threads=4).astype(np.float32)
        if nm in ("nf12", "nf12b", "nf12m"):
            imp = pd.Series(m.feature_importance("gain"), index=feats).sort_values(ascending=False)
            res["importance_gain_top25"] = {k: round(float(v / imp.sum()), 4) for k, v in imp.head(25).items()}
            res["importance_slow_share"] = round(float(imp[[c for c in SLOW if c in feats]].sum() / imp.sum()), 4)
        print(nm, "trained", round(time.time() - t0), flush=True)
    preds.to_parquet(f"{OUT}/nf12{SUF}_val.parquet")
    if VARIANT != "ptb":
        preds["nf12"] = preds["nf12" + SUF]
    vX = X[va]
    net = vX.groupby("cid").y.sum()
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf"])
    nf4 = vo.groupby("cid").nf.sum().reindex(net.index)
    p12 = preds.groupby("cid").nf12.sum().reindex(net.index)
    res["validate_window_net_corr"] = {"nf_it4b": round(float(net.corr(nf4)), 4), "nf12": round(float(net.corr(p12)), 4),
                                       "avg": round(float(net.corr(0.5 * nf4 + 0.5 * p12)), 4), "corr_nf4_nf12": round(float(nf4.corr(p12)), 4)}
    for w in (("GF", "XM", "DS") if VARIANT == "ptb" else ()):
        nw = vX.groupby("cid")["y" + w].sum()
        res["validate_window_net_corr"][w] = {"pooled_nf12": round(float(nw.corr(p12)), 4),
                                              "own_nf12_" + w: round(float(nw.corr(preds.groupby("cid")["nf12_" + w].sum().reindex(net.index))), 4),
                                              "nf_it4b": round(float(nw.corr(nf4)), 4)}
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{R}/nf12{SUF}.json", "w"), indent=1)


if __name__ == "__main__":
    main()

"""Iteration 9 (X83 groundwork, first per-family presence beyond BTC 5m/15m): BTC hourly markets (Binance-settled) of
10-16..10-30, unit = (market, side s, 10-s bin t in [0, 3600)), label = >= 1 cluster BUY trade on s in [t, t+10) (activity;
all roles, the cluster's taker share is small). Point-in-time features at st + t from the clean data-api tape (prints in
any cluster transaction removed), Binance 1-s spot and the clock. Fit on BUILD 10-16..22 + STUDY 10-23..26, score on
VALIDATE 10-27..30 (aggregate only), activity-only baseline with the same model class and rounds; 2-h block bootstrap of
the gain. Exploratory: not part of the frozen rule."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
VAL = 1793059200


def main(famname="btc_hourly", L=3600):
    import lightgbm as lgb
    a = pd.read_parquet(C / "spot_btc_1s.parquet")
    b = pd.read_parquet(C / "exam" / "spot_btc_1s.parquet")
    s = pd.concat([a, b]).drop_duplicates("sec").sort_values("sec")
    base = int(s.sec.iloc[0])
    px = np.full(int(s.sec.iloc[-1]) - base + 1, np.nan)
    px[s.sec.to_numpy() - base] = s.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    mk = pd.read_parquet(C / "fam" / f"{famname}_markets.parquet")
    T = pd.read_parquet(C / "fam" / f"{famname}_tapes.parquet")
    parts = []
    for n in ("bosona", "almach", "momoney"):
        for p in (C / f"activity_{n}.parquet", C / "exam" / f"activity_{n}.parquet"):
            parts.append(pd.read_parquet(p, columns=["timestamp", "type", "conditionId", "asset", "side", "outcome", "price", "size", "transactionHash"]))
    act = pd.concat(parts).drop_duplicates()
    act = act[act.type == "TRADE"]
    T = T[~T.tx.str.lower().isin(set(act.transactionHash.str.lower()))].sort_values("ts")
    buys = act[act.side == "BUY"]
    rows = []
    tg = dict(tuple(T.groupby("cid")))
    bg = dict(tuple(buys.groupby("conditionId")))
    for r in mk.itertuples(index=False):
        cid, st, en = r.conditionId, int(r.st), int(r.en)
        g = bg.get(cid)
        tp = tg.get(cid)
        if g is None or tp is None or len(tp) < 20:
            continue
        up_tok = next((str(a_) for o, a_ in zip(g.outcome, g.asset) if str(o).lower() == "up"), None)
        if up_tok is None:
            continue
        pts = tp.ts.to_numpy()
        isup = tp.asset.astype(str).to_numpy() == up_tok
        sell = tp.side.astype(str).to_numpy() == "SELL"
        z = tp["size"].to_numpy(float)
        pup = np.where(isup, tp.price.to_numpy(float), 1 - tp.price.to_numpy(float))
        # flow that fills a maker BUY of Up: taker SELL Up or BUY Down; of Down: SELL Down or BUY Up
        f_up = np.cumsum(np.where((isup & sell) | (~isup & ~sell), z, 0.0))
        f_dn = np.cumsum(np.where((~isup & sell) | (isup & ~sell), z, 0.0))
        tb = st + np.arange(0, L, 10)
        K = px[st - 1 - base]
        i = tb - 1 - base
        S = px[i]
        v300 = np.sqrt((cs[i + 1] - cs[i + 1 - 300]) / 300)
        v3600 = np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600)
        tau = np.maximum(en - tb, 1.0)
        fair_up = norm.cdf(np.log(S / K) / (v3600 * np.sqrt(tau)))
        j = np.searchsorted(pts, tb, side="left") - 1  # prints strictly before the bin start
        last_up = np.where(j >= 0, pup[np.maximum(j, 0)], np.nan)
        age = np.where(j >= 0, tb - pts[np.maximum(j, 0)], 9999.0)

        def cnt(L):
            return (np.searchsorted(pts, tb, side="left") - np.searchsorted(pts, tb - L, side="left")).astype(float)

        def flow(fc, L):
            hi = np.searchsorted(pts, tb, side="left") - 1
            lo = np.searchsorted(pts, tb - L, side="left") - 1
            return np.where(hi >= 0, fc[np.maximum(hi, 0)], 0.0) - np.where(lo >= 0, fc[np.maximum(lo, 0)], 0.0)
        n10, n30, n120 = cnt(10), cnt(30), cnt(120)
        bts = g.timestamp.to_numpy()
        bup = (g.outcome.astype(str).str.lower() == "up").to_numpy()
        tt = pd.to_datetime(st, unit="s")
        for side_up in (1, 0):
            yb = np.zeros(len(tb), dtype=np.int8)
            sel = bts[bup == bool(side_up)]
            k = ((sel - st) // 10).astype(int)
            k = k[(k >= 0) & (k < len(tb))]
            yb[k] = 1
            last_s = last_up if side_up else 1 - last_up
            fair_s = fair_up if side_up else 1 - fair_up
            fl = flow(f_up if side_up else f_dn, 30)
            fo = flow(f_dn if side_up else f_up, 30)
            rows.append(pd.DataFrame({"st": st, "rel": tb - st, "s_up": side_up, "y": yb, "n10": n10, "n30": n30, "n120": n120,
                                      "flow_s30": fl, "flow_o30": fo, "last": last_s, "age": age, "tau": tau,
                                      "fair": fair_s, "edge": fair_s - last_s, "z": np.log(S / K) / (v3600 * np.sqrt(tau)) * (1 if side_up else -1),
                                      "vr": v300 / v3600, "v3600": v3600 * 1e4,
                                      "hour": tt.hour, "dow": tt.day_of_week, "us": int(tt.day_of_week < 5 and 12 <= tt.hour < 21)}))
    P = pd.concat(rows, ignore_index=True)
    ACT = ["rel", "s_up", "n10", "n30", "n120", "flow_s30", "flow_o30", "last", "age", "tau"]
    ALL = ACT + ["fair", "edge", "z", "vr", "v3600", "hour", "dow", "us"]
    tr, te = P[P.st < VAL], P[P.st >= VAL].copy()
    prm = dict(objective="binary", num_leaves=15, min_data_in_leaf=100, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=9,
               feature_fraction=0.9)
    out = {"bins_fit": int(len(tr)), "bins_val": int(len(te)), "pos_fit": float(tr.y.mean()), "pos_val": float(te.y.mean()),
           "markets_fit": int(tr.st.nunique()), "markets_val": int(te.st.nunique())}
    sc = {}
    for nm, cols in (("activity", ACT), ("rule", ALL), ("rule_no_clock", ACT + ["fair", "edge", "z", "vr", "v3600"])):
        m_ = lgb.train(prm, lgb.Dataset(tr[cols], tr.y), 300)
        sc[nm] = m_.predict(te[cols])
        out[nm] = round(float(roc_auc_score(te.y, sc[nm])), 4)
        if nm == "rule":
            imp = dict(zip(cols, m_.feature_importance("gain")))
            out["importance_rule"] = {k: round(float(v / sum(imp.values())), 3) for k, v in sorted(imp.items(), key=lambda kv: -kv[1])[:10]}
    blk = (te.st.to_numpy() + te.rel.to_numpy()) // 7200
    ub, inv = np.unique(blk, return_inverse=True)
    rng = np.random.default_rng(9)
    g_ = []
    yv = te.y.to_numpy()
    for _ in range(300):
        pick = rng.integers(0, len(ub), len(ub))
        idx = np.concatenate([np.where(inv == k)[0] for k in pick])
        if yv[idx].min() == yv[idx].max():
            continue
        g_.append(roc_auc_score(yv[idx], sc["rule"][idx]) - roc_auc_score(yv[idx], sc["activity"][idx]))
    out["gain_rule_minus_activity"] = round(out["rule"] - out["activity"], 4)
    out["gain_ci95_2h_blocks"] = [round(float(np.quantile(g_, 0.025)), 4), round(float(np.quantile(g_, 0.975)), 4)]
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / f"iter9_{famname}_presence.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "btc_hourly", int(sys.argv[2]) if len(sys.argv) > 2 else 3600)

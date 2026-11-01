"""Examiner r1, leakage audit of the decision-clock routes (dc_exam14 side features; dc_hazard14 hazard features used by the PnL target):
corrupt every capture value after the route's own cut and require identical features / predictions, with the FROZEN functions
dc_exam14.features and dc_hazard14._feats (called unchanged). Sample: 300 cluster taker orders of the first lot chunk drawn with seed
20261101 from the order list (tx hashes; listing-free since the orders are the unit), and 40 (window, outcome) hazard tracks.
Usage: python trunc_dc.py OUT_JSON"""
import os, sys, json, glob, pickle
ARGS = sys.argv[1:]
ROOT = os.getcwd(); CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"; sys.path.insert(0, CODE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
import dc_exam14 as dx, dc_hazard14 as hz
from an_side import cap_rows

EX = f"{ROOT}/.cache/exam/btc5m-bot"
rng = np.random.default_rng(20261101); noise = np.random.default_rng(7)


def main(out_json):
    d = sorted(glob.glob(f"{EX}/chunks/1792713600_*"))[0]
    a, b = map(int, os.path.basename(d).split("_"))
    fills = pd.read_parquet(f"{d}/fills.parquet"); win = pd.read_parquet(f"{d}/windows_all.parquet")
    win = win[(win.start_ts >= a) & (win.start_ts < b)]
    tr = cap_rows("polymarket", (a - 70) * 1000, (b + 400) * 1000, ["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSide"])
    bt = cap_rows("btc", (a - 80) * 1000, (b + 400) * 1000, ["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price", "quantity", "isBuyerMaker"])
    mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    f = fills[fills.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy(); f["m"] = f.tx.str.lower().map(mt); f = f[f.m.notna()]
    f = f.iloc[np.sort(rng.choice(len(f), min(300, len(f)), replace=False))]
    bk = bt[bt.type == "book"].sort_values("receivedTimestampMs", kind="stable"); td = bt[bt.type == "trade"].sort_values("exchangeTimestampMs", kind="stable")
    Tb = bk.receivedTimestampMs.to_numpy(np.int64); Tt = td.exchangeTimestampMs.to_numpy(np.int64)
    def mm(bp, bq, ap, aq):
        return (bp * aq + ap * bq) / (bq + aq), (bp + ap) / 2
    bp, bq, ap, aq = (bk[k].to_numpy(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity")); pt = td.price.to_numpy(float)
    mic, mid = mm(bp, bq, ap, aq)
    mdl = lgb.Booster(model_file=dx.MODEL); FN = mdl.feature_name()
    res = {"side_orders": int(len(f)), "side_identical": 0, "side_prob_max_abs_diff": 0.0}
    for m_, st in zip(f.m.to_numpy(np.int64), f.start_ts.to_numpy(np.int64)):
        X = m_ - dx.C_EX_MS
        F0 = dx.features(np.array([m_]), np.array([st]), Tb, mic, mid, Tt, pt)
        cb = Tb >= X + dx.TRANSIT_MS; ct = Tt >= X
        mic2 = mic.copy(); mid2 = mid.copy(); pt2 = pt.copy()
        mic2[cb] *= 1 + noise.normal(0, 0.001, cb.sum()); mid2[cb] *= 1 + noise.normal(0, 0.001, cb.sum()); pt2[ct] *= 1 + noise.normal(0, 0.001, ct.sum())
        F1 = dx.features(np.array([m_]), np.array([st]), Tb, mic2, mid2, Tt, pt2)
        same = np.allclose(F0[FN].to_numpy(float), F1[FN].to_numpy(float), equal_nan=True, rtol=0, atol=0)
        res["side_identical"] += int(same)
        res["side_prob_max_abs_diff"] = max(res["side_prob_max_abs_diff"], float(abs(mdl.predict(F0[FN])[0] - mdl.predict(F1[FN])[0])))
    # hazard features at bin ends e (the PnL target h(s) sums bins with e in [s-2, s-1)); cut: spot book (receive - 131) and trades >= e,
    # others' Polymarket prints >= e + 50 ms (the route's own stated horizons)
    mf = lgb.Booster(model_file=hz.MODEL_FULL); FH = mf.feature_name()
    excl = set(fills.tx.str.lower())
    t2 = tr.assign(h=tr.transactionHash.str.lower(), tokenId=tr.tokenId.astype(str))
    t2 = t2[~t2.h.isin(excl)].sort_values("exchangeTimestampMs", kind="stable")
    bt2 = bt.copy()
    Tb_, mic_, mid_, Tt_, cf_ = hz._spot(bt2)
    byt = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.tradePrice.to_numpy(float), g.tradeSide.to_numpy()) for k, g in t2.groupby("tokenId")}
    W = win.sample(min(20, len(win)), random_state=20261101)
    nh, ident, mx = 0, 0, 0.0
    for r in W.itertuples():
        st = int(r.start_ts) * 1000
        for up in (1, 0):
            for e in np.sort(rng.choice(np.arange(st + 5000, st + 270000, 50), 5, replace=False)):
                ee = np.array([e])
                F0 = hz._feats(r, up, ee, Tb_, mic_, mid_, Tt_, cf_, byt)
                c1 = Tb_ >= e; mic2 = mic_.copy(); mid2 = mid_.copy(); mic2[c1] *= 1 + noise.normal(0, 0.001, c1.sum()); mid2[c1] *= 1 + noise.normal(0, 0.001, c1.sum())
                cf2 = cf_.copy(); j = np.searchsorted(Tt_, e, "left"); cf2[j + 1:] += noise.normal(0, 5, len(cf2) - j - 1)
                byt2 = {k: (T_, np.where(T_ >= e + 50, noise.uniform(0.01, 0.99, len(T_)), P_), np.where(T_ >= e + 50, noise.choice(["BUY", "SELL"], len(T_)), S_)) for k, (T_, P_, S_) in byt.items()}
                F1 = hz._feats(r, up, ee, Tb_, mic2, mid2, Tt_, cf2, byt2)
                x0 = np.column_stack([F0[k] for k in FH]); x1 = np.column_stack([F1[k] for k in FH])
                ok = np.allclose(x0, x1, equal_nan=True, rtol=0, atol=0); ident += int(ok); nh += 1
                mx = max(mx, float(abs(mf.predict(x0)[0] - mf.predict(x1)[0])))
    res.update({"hazard_bins": nh, "hazard_identical": ident, "hazard_prob_max_abs_diff": mx})
    json.dump(res, open(out_json, "w"), indent=1); print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(ARGS[0])

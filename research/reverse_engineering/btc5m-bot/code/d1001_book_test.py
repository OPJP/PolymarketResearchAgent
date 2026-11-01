"""Iteration 5: do venue ORDER BOOKS (top of book: mid moves, size imbalance, microprice) explain the bot's side in the
seconds where no BTC trade series and no ETH trade moved? Mechanism test on 2026-10-01 00:00-08:00 UTC (BUILD side, < H),
the only pre-H day with free public top-of-book history (Tardis free first-day-of-month datasets).
All features are point-in-time at the horizon X = (s-1)*1000 ms for block second s (data in 100-ms buckets < X).
Output: research/reverse_engineering/btc5m-bot/results_book_test_iter5.json"""
import os, sys, json
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
D = _ROOT + "/.cache/re/btc5m-bot/d1001"
RES = _ROOT + "/research/reverse_engineering/btc5m-bot/results_book_test_iter5.json"
DAY0 = 1790812800
TRD = ["bnf", "byb", "okx", "bns", "bys", "oks"]  # six BTC trade series (as in iterations 3-4)
BOOK = ["bnf", "byb", "okx", "bns", "eth"]
ETH_BETA = 1.235  # ETH bp per BTC bp over 3 s (BUILD slope, iteration 4)


def series(name, cols):
    d = pd.read_parquet(f"{D}/{name}.parquet")
    b0 = DAY0 * 10
    n = int(d.b.max() - b0 + 1)
    out = {}
    for c in cols:
        a = np.full(n, np.nan)
        a[(d.b - b0).to_numpy()] = d[c].to_numpy(float)
        if c in ("p", "bid", "ask", "bq", "aq"):
            a = pd.Series(a).ffill().to_numpy()
        else:
            a = np.nan_to_num(a)
        out[c] = a
    return out


def at(a, idx):
    """value of the forward-filled bucket series just before bucket idx (i.e. data with T < idx*100 ms)."""
    j = np.clip(idx - 1, 0, len(a) - 1)
    return a[j]


def agree(x, side, mask=None):
    m = (x != 0) & np.isfinite(x)
    if mask is not None:
        m &= mask
    n = int(m.sum())
    if n == 0:
        return {"n": 0}
    acc = float((np.sign(x[m]) == side[m]).mean())
    return {"n": n, "agree": round(acc, 4), "z": round((acc - 0.5) / np.sqrt(0.25 / n), 1)}


def main():
    f = pd.read_parquet(f"{D}/fills.parquet")
    f = f[f.side == 0]
    g = f.groupby(["cid", "ts"]).agg(nup=("is_up", "sum"), n=("is_up", "size"), taker=("role", lambda r: (r == "T").any()),
                                    rel=("rel", "first")).reset_index()
    g["ndn"] = g.n - g.nup
    one = g[(g.nup == 0) | (g.ndn == 0)].copy()
    one = one[(one.ts >= DAY0 + 120)]
    side = np.where(one.nup > 0, 1.0, -1.0)
    s = one.ts.to_numpy(np.int64)
    B = (s - 1 - DAY0) * 10  # horizon bucket index (relative to DAY0)
    res = {"period": "2026-10-01 00:00-08:00 UTC (BUILD side)", "fills": int(len(f)), "one_sided_seconds": int(len(one)),
           "taker_share": round(float(one.taker.mean()), 4)}
    F = {}
    # trade moves (bp) over [s-4, s-1) and [s-3, s-2), PIT
    for v in TRD + ["eth"]:
        t = series(f"{v}_trd", ["p", "sv"])
        p1, p4, p2, p3 = at(t["p"], B), at(t["p"], B - 30), at(t["p"], B - 10), at(t["p"], B - 20)
        F[f"t_{v}_3s"] = 1e4 * np.log(p1 / p4)
        F[f"t_{v}_seg32"] = 1e4 * np.log(p2 / p3)
        F[f"t_{v}_1s"] = 1e4 * np.log(p1 / p2)
        cs = np.cumsum(t["sv"])
        F[f"t_{v}_ofi3"] = at(cs, B) - at(cs, B - 30)
        if v == "bnf":
            # future futures move after the horizon (non-PIT, diagnostics only)
            F["fut_next2"] = 1e4 * np.log(at(t["p"], B + 20) / p1)
            F["fut_s_s2"] = 1e4 * np.log(at(t["p"], B + 30) / at(t["p"], B + 10))
    for v in BOOK:
        q = series(f"{v}_book", ["bid", "ask", "bq", "aq", "n"])
        mid = (q["bid"] + q["ask"]) / 2
        imb = (q["bq"] - q["aq"]) / (q["bq"] + q["aq"])
        micro = (q["bid"] * q["aq"] + q["ask"] * q["bq"]) / (q["bq"] + q["aq"])
        F[f"b_{v}_mid3"] = 1e4 * np.log(at(mid, B) / at(mid, B - 30))
        F[f"b_{v}_mid1"] = 1e4 * np.log(at(mid, B) / at(mid, B - 10))
        F[f"b_{v}_imb"] = at(imb, B)
        F[f"b_{v}_imb_avg1"] = np.mean([at(imb, B - k) for k in range(10)], axis=0)
        F[f"b_{v}_micro"] = 1e4 * (at(micro, B) / at(mid, B) - 1)
        F[f"b_{v}_imb_pl60"] = at(imb, B - 600)  # placebo: 60 s earlier
        F[f"b_{v}_spread"] = 1e4 * (at(q["ask"], B) - at(q["bid"], B)) / at(mid, B)
        nupd = np.cumsum(q["n"]); F[f"b_{v}_nupd3"] = at(nupd, B) - at(nupd, B - 30)
    F = {k: np.asarray(v, float) for k, v in F.items()}
    mx6 = np.max(np.abs(np.vstack([F[f"t_{v}_3s"] for v in TRD])), axis=0)
    eth_eq = np.abs(F["t_eth_3s"]) / ETH_BETA
    nomove = mx6 <= 0.1
    nomove_eth = nomove & (eth_eq <= 0.1)
    taker = one.taker.to_numpy(bool)
    res["share_no_btc_move"] = round(float(nomove.mean()), 4)
    res["share_no_btc_no_eth_move"] = round(float(nomove_eth.mean()), 4)
    # 1) single-signal agreement by segment
    segs = {"all": None, "no_btc_move": nomove, "no_btc_no_eth_move": nomove_eth, "moving": ~nomove, "taker": taker,
            "no_btc_no_eth_taker": nomove_eth & taker}
    sig = ["t_bnf_3s", "t_eth_3s", "fut_next2", "fut_s_s2"] + [f"b_{v}_{k}" for v in BOOK for k in ("mid3", "mid1", "imb", "imb_avg1", "micro", "imb_pl60")]
    res["agreement"] = {sg: {k: agree(F[k], side, m) for k in sig} for sg, m in segs.items()}
    # composite book signals
    imb_mean = np.nanmean(np.vstack([F[f"b_{v}_imb_avg1"] for v in ["bnf", "byb", "okx", "bns"]]), axis=0)
    micro_mean = np.nanmean(np.vstack([F[f"b_{v}_micro"] for v in ["bnf", "byb", "okx", "bns"]]), axis=0)
    midmx = np.vstack([F[f"b_{v}_mid3"] for v in ["bnf", "byb", "okx", "bns"]])
    mid_mx = midmx[np.nanargmax(np.abs(np.nan_to_num(midmx)), axis=0), np.arange(midmx.shape[1])]
    for nm, x in (("imb_mean4", imb_mean), ("micro_mean4", micro_mean), ("mid_mx4", mid_mx)):
        res["agreement"].setdefault("composites", {})[nm] = {sg: agree(x, side, m) for sg, m in segs.items()}
    # strong imbalance bins in no-move seconds
    bins = {}
    for lo, hi in ((0, 0.2), (0.2, 0.5), (0.5, 0.8), (0.8, 1.01)):
        m = nomove_eth & (np.abs(imb_mean) >= lo) & (np.abs(imb_mean) < hi)
        bins[f"{lo}-{hi}"] = agree(imb_mean, side, m)
    res["no_move_by_abs_imb_mean4"] = bins
    # does the book explain the bot's predictive power for the next move in no-move seconds?
    fut = F["fut_next2"]
    m = nomove_eth & (fut != 0)
    res["no_move_next2_bot_side"] = agree(fut * 1.0, side, m)
    res["no_move_next2_book_imb"] = agree(np.sign(imb_mean) * np.sign(fut), np.ones_like(fut), m & (imb_mean != 0))
    # 2) grouped-CV logistic side model: trade features vs trade + book features
    tf = [k for k in F if k.startswith("t_")]
    bf = [k for k in F if k.startswith("b_") and not k.endswith("pl60")]
    X_t = np.nan_to_num(np.vstack([F[k] for k in tf]).T)
    X_b = np.nan_to_num(np.vstack([F[k] for k in tf + bf]).T)
    bf_byb = [k for k in bf if k.startswith("b_byb_")]
    X_y = np.nan_to_num(np.vstack([F[k] for k in tf + bf_byb]).T)
    y = (side > 0).astype(int)
    groups = one.cid.to_numpy()
    out = {}
    for nm, X in (("trades_only", X_t), ("trades_plus_bybit_book", X_y), ("trades_plus_book", X_b)):
        X = np.clip(X / (np.std(X, axis=0) + 1e-9), -6, 6)
        pred = np.zeros(len(y))
        for tr, te in GroupKFold(5).split(X, y, groups):
            mdl = LogisticRegression(C=0.5, max_iter=2000).fit(X[tr], y[tr])
            pred[te] = mdl.predict_proba(X[te])[:, 1]
        hit = (pred > 0.5) == (y == 1)
        out[nm] = {"all": round(float(hit.mean()), 4), "no_btc_no_eth_move": round(float(hit[nomove_eth].mean()), 4),
                   "moving": round(float(hit[~nomove].mean()), 4), "taker": round(float(hit[taker].mean()), 4), "maker_only": round(float(hit[~taker].mean()), 4)}
        out[nm + "_pred"] = pred
    a, b_ = (out["trades_only_pred"] > 0.5) == (y == 1), (out["trades_plus_book_pred"] > 0.5) == (y == 1)
    from scipy.stats import binomtest
    n01, n10 = int((~a & b_).sum()), int((a & ~b_).sum())
    res["cv_logit"] = {k: v for k, v in out.items() if not k.endswith("_pred")}
    res["cv_logit"]["mcnemar"] = {"book_only_right": n01, "trades_only_right": n10, "p": float(binomtest(n01, n01 + n10).pvalue) if n01 + n10 else None}
    json.dump(res, open(RES, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("one_sided_seconds", "taker_share", "share_no_btc_move", "share_no_btc_no_eth_move", "cv_logit")}, indent=0))
    for sg in ("all", "no_btc_no_eth_move", "no_btc_no_eth_taker"):
        print(sg, {k: (v.get("agree"), v.get("n")) for k, v in res["agreement"][sg].items()})
    print("composites", json.dumps(res["agreement"]["composites"]))
    print("bins", res["no_move_by_abs_imb_mean4"])
    print("next2", res["no_move_next2_bot_side"], res["no_move_next2_book_imb"])


if __name__ == "__main__":
    main()

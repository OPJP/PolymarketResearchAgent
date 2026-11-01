"""Iteration 19, X195 (information panel iter18 P2): CLOCK-FREE side route, in time and out of time.

PRE-REGISTRATION 17 (written 11-01 ~13:25 UTC, before the first run). Only exchange-stamped Binance spot TRADES (T, p, q, isBuyerMaker)
and Polymarket server-ms matches enter; no receive clock anywhere. Orders: operator (DS / GF / XM) taker BUY orders, one per
(tx, wallet, token); m = the matching-engine ms (capture trade rows by tx hash in time, dcfit14_pred.m; the live lab's CLOB trade
records' server ms 's' out of time, post17 / oot17's construction). Anchor X = m - 260 ms (the frozen C_EX_MS; no scan, never later
than the physics floor). Features: last-trade log return over [X - K, X) in bp and signed aggressive quantity (taker buy +, taker sell -)
over [X - K, X), K = 100 / 250 / 500 / 1000 / 2000 ms, trade count over [X - 250, X), rel = (m - 180) / 1000 - start_ts.
Model: LightGBM (binary, 31 leaves, lr 0.05, 300 rounds, min_data_in_leaf 100, max_bin 63, seed 19), fitted on the 10-17..19 orders,
frozen, scored once on 10-20..22 (in time) and once on 11-01 06:00-09:30 (out of time; 30 development windows, every window asserted
not sealed). Bars (claims): per-order accuracy >= 0.80 in time AND out of time. Reported (not claims): first legs, per wallet, halves,
placebo anchors m -/+ 3 s, Globex session split in time, c = 230 / 300 variants refitted the same way.
Usage: python oot19.py FRAME_DIR HF_DIR IT17_DIR"""
import os, sys, json, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq
import lightgbm as lgb
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live, sealed
from knee19 import session

R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
KS = (100, 250, 500, 1000, 2000)
PARAMS = {"objective": "binary", "num_leaves": 31, "learning_rate": 0.05, "min_data_in_leaf": 100, "max_bin": 63, "seed": 19, "verbose": -1,
          "feature_fraction": 0.9, "bagging_fraction": 0.8, "bagging_freq": 1}
ROUNDS = 300


def _atl(T, X, tt):
    i = np.searchsorted(T, tt, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def feats(m, st, T, p, sq, c):
    X = np.asarray(m, np.int64) - c
    F = {"rel": (np.asarray(m, np.int64) - 180) / 1000.0 - np.asarray(st, float)}
    x0 = _atl(T, p, X)
    cq = np.concatenate([[0.0], np.cumsum(sq)])
    for K in KS:
        F[f"r_{K}"] = ((x0 / _atl(T, p, X - K) - 1) * 1e4).astype(np.float32)
        F[f"v_{K}"] = (cq[np.searchsorted(T, X, "left")] - cq[np.searchsorted(T, X - K, "left")]).astype(np.float32)
    F["n_250"] = (np.searchsorted(T, X, "left") - np.searchsorted(T, X - 250, "left")).astype(np.float32)
    return pd.DataFrame(F)


def capture_trades(A, day):
    t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "exchangeTimestampMs", "price", "quantity", "isBuyerMaker"], filters=[("type", "=", "trade")])
    T = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False).astype(np.int64)
    p = t.column("price").to_numpy(zero_copy_only=False).astype(float); q = t.column("quantity").to_numpy(zero_copy_only=False).astype(float)
    mk = t.column("isBuyerMaker").to_numpy(zero_copy_only=False).astype(bool)
    o = np.argsort(T, kind="stable")
    return T[o], p[o], np.where(mk, -q, q)[o]


def build(P, A, c):
    out = []
    for day in sorted(P.day.unique()):
        T, p, sq = capture_trades(A, day)
        d = P[P.day == day]
        F = feats(d.m.to_numpy(np.int64), d.start_ts.to_numpy(), T, p, sq, c)
        Fm = feats(d.m.to_numpy(np.int64) - 3000, d.start_ts.to_numpy(), T, p, sq, c); Fm["rel"] = F["rel"] - 3.0
        Fp = feats(d.m.to_numpy(np.int64) + 3000, d.start_ts.to_numpy(), T, p, sq, c); Fp["rel"] = F["rel"] + 3.0
        F.index = Fm.index = Fp.index = d.index
        out.append((F, Fm, Fp))
        del T, p, sq; gc.collect()
    return (pd.concat([o[0] for o in out]), pd.concat([o[1] for o in out]), pd.concat([o[2] for o in out]))


def acc(p, y):
    return round(float(((p > 0.5) == y).mean()), 4) if len(y) else None


def main():
    D, A, S17 = sys.argv[1], sys.argv[2], sys.argv[3]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "m0", "rank", "start_ts", "day"])
    P = P[P.wallet.isin(["DS", "GF", "XM"])].reset_index(drop=True)
    fit = P.day.isin(["2026-10-17", "2026-10-18", "2026-10-19"]).to_numpy()
    y = P.up.to_numpy() == 1
    # out-of-time orders (oot17's construction)
    win = pd.read_parquet(f"{S17}/post17_windows.parquet"); fl = pd.read_parquet(f"{S17}/post17_fills.parquet"); xr = pd.read_parquet(f"{S17}/post17_xms.parquet")
    assert not any(sealed.is_sealed(int(t), "btc5m-bot") for t in win.start_ts)
    o = fl[(fl.role == "T") & (fl.side == 0) & fl.wallet.isin(["DS", "GF", "XM"])].copy(); o["tx"] = o.tx.str.lower()
    o = o.drop_duplicates(["tx", "wallet", "token"]); mt = xr.dropna(subset=["s"]).groupby("tx").s.min(); o["m"] = o.tx.map(mt)
    n_all = len(o); o = o[o.m.notna()].copy(); o["m"] = o.m.astype(np.int64)
    a_ts, b_ts = int(win.start_ts.min()) - 10, int(win.end_ts.max()) + 10
    xT, xp, xq = [], [], []
    for r in live.iter_live("btc5m_bnspot2", a_ts, b_ts):
        if r.get("k") == "x":
            xT.append(r["T"]); xp.append(float(r["p"])); xq.append(-float(r["q"]) if r["m"] else float(r["q"]))
    xT = np.asarray(xT, np.int64); oq = np.argsort(xT, kind="stable"); xT = xT[oq]; xp = np.asarray(xp)[oq]; xq = np.asarray(xq)[oq]
    o = o[(o.m >= xT[0] + 2500 + 300) & (o.m <= xT[-1] + 1000)].copy().reset_index(drop=True)
    res = {"prereg": "17", "in_time_orders_fit_score": [int(fit.sum()), int((~fit).sum())], "oot_orders_all": int(n_all), "oot_orders_scored": int(len(o)),
           "oot_trade_msgs": int(len(xT)), "variants": {}}
    for c in (260, 230, 300):
        F, Fm, Fp = build(P, A, c)
        F, Fm, Fp = F.loc[P.index], Fm.loc[P.index], Fp.loc[P.index]
        mdl = lgb.train(PARAMS, lgb.Dataset(F[fit], label=y[fit].astype(int)), ROUNDS)
        ps = mdl.predict(F[~fit]); yv = y[~fit]; Pv = P[~fit]
        r = {"in_time_per_order": acc(ps, yv), "in_time_first_legs": acc(ps[(Pv["rank"] == 0).to_numpy()], yv[(Pv["rank"] == 0).to_numpy()]),
             "in_time_placebo_m-3s_m+3s": [acc(mdl.predict(Fm[~fit]), yv), acc(mdl.predict(Fp[~fit]), yv)],
             "in_time_by_wallet": {w: acc(ps[(Pv.wallet == w).to_numpy()], yv[(Pv.wallet == w).to_numpy()]) for w in ("DS", "GF", "XM")},
             "in_time_by_day": {d: acc(ps[(Pv.day == d).to_numpy()], yv[(Pv.day == d).to_numpy()]) for d in sorted(Pv.day.unique())}}
        sv = session(Pv.m.to_numpy())
        r["in_time_by_session"] = {s: [acc(ps[sv == s], yv[sv == s]), int((sv == s).sum())] for s in ("closed", "open_us", "open_other")}
        Fo = feats(o.m.to_numpy(np.int64), o.start_ts.to_numpy(), xT, xp, xq, c)
        po = mdl.predict(Fo); yo = o.is_up.to_numpy(bool)
        Fom = feats(o.m.to_numpy(np.int64) - 3000, o.start_ts.to_numpy(), xT, xp, xq, c); Fom["rel"] = Fo["rel"] - 3.0
        Fop = feats(o.m.to_numpy(np.int64) + 3000, o.start_ts.to_numpy(), xT, xp, xq, c); Fop["rel"] = Fo["rel"] + 3.0
        oo = o.sort_values(["cid", "is_up", "m"]); new = ((oo.cid != oo.cid.shift()) | (oo.is_up != oo.is_up.shift()) | (oo.m - oo.m.shift() >= 300)).reindex(o.index).to_numpy()
        st = o.start_ts.to_numpy(); us = np.unique(st); md = us[len(us) // 2]
        r["oot_per_order"] = acc(po, yo); r["oot_first_legs"] = acc(po[new], yo[new])
        r["oot_placebo_m-3s_m+3s"] = [acc(mdl.predict(Fom), yo), acc(mdl.predict(Fop), yo)]
        r["oot_by_wallet"] = {w: [acc(po[(o.wallet == w).to_numpy()], yo[(o.wallet == w).to_numpy()]), int((o.wallet == w).sum())] for w in ("DS", "GF", "XM")}
        r["oot_halves"] = [acc(po[st < md], yo[st < md]), acc(po[st >= md], yo[st >= md])]
        r["oot_session"] = sorted(set(session(o.m.to_numpy())))
        if c == 260:
            r["passes_bars_0.80"] = bool(r["in_time_per_order"] >= 0.80 and r["oot_per_order"] >= 0.80)
            r["feature_gain"] = dict(zip(mdl.feature_name(), [round(float(g), 1) for g in mdl.feature_importance("gain")]))
            mdl.save_model(_ROOT + "/research/reverse_engineering/btc5m-bot/code/model_it19_tradeside.txt")
        res["variants"][f"c{c}"] = r
        print(c, json.dumps(r), flush=True)
        del F, Fm, Fp; gc.collect()
    json.dump(res, open(f"{R}/oot19.json", "w"), indent=1)


if __name__ == "__main__":
    main()

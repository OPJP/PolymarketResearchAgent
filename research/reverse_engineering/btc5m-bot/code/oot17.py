"""Iteration 17, PRE-REGISTRATION 11 (NOTES.md, written 09:45 UTC 11-01 before scoring): out-of-time score of the frozen decision-clock
side route dc_exam14 on the first new-regime decision record (11-01 06:00-09:30 development windows; code/post17.py).
Orders: operator taker BUY orders (one per (tx, wallet, token)); m = min server ms 's' of the live lab's trade records with the tx hash.
Binance: rec_bn15 v2 feed btc5m_bnspot2 (every bookTicker / trade message, laptop receive clock). Clock substitution: book receive
times shifted by (131 - tau_lap), tau_lap = median(receive ms - T) of the block's trade messages; trades by T. Model, features, anchor
and threshold are dc_exam14's. Also reported (not pre-registered as claims): per-30-min tau_lap drift, a per-window tau variant, the
book-message rate, and the W4 / W5 orders as a separate line.
Usage: python oot17.py"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
import dc_exam14 as dx
import lightgbm as lgb

S = os.environ["RE16_SCRATCH"] + "/it17"
win = pd.read_parquet(S + "/post17_windows.parquet")
fl = pd.read_parquet(S + "/post17_fills.parquet")
xr = pd.read_parquet(S + "/post17_xms.parquet")
assert not any(sealed.is_sealed(int(t), "btc5m-bot") for t in win.start_ts)
o = fl[(fl.role == "T") & (fl.side == 0)].copy()
o["tx"] = o.tx.str.lower()
o = o.drop_duplicates(["tx", "wallet", "token"])
mt = xr.dropna(subset=["s"]).groupby("tx").s.min()
o["m"] = o.tx.map(mt)
n_all = len(o)
o = o[o.m.notna()].copy(); o["m"] = o.m.astype(np.int64)
a_ts, b_ts = int(win.start_ts.min()) - 10, int(win.end_ts.max()) + 10
qt, qb, qB, qa, qA, xt, xT, xp = [], [], [], [], [], [], [], []
for r in live.iter_live("btc5m_bnspot2", a_ts, b_ts):
    k = r.get("k")
    if k == "q":
        qt.append(r["t"]); qb.append(float(r["b"])); qB.append(float(r["B"])); qa.append(float(r["a"])); qA.append(float(r["A"]))
    elif k == "x":
        xt.append(r["t"]); xT.append(r["T"]); xp.append(float(r["p"]))
qt = np.asarray(qt, np.int64); qb, qB, qa, qA = map(np.asarray, (qb, qB, qa, qA))
xt = np.asarray(xt, np.int64); xT = np.asarray(xT, np.int64); xp = np.asarray(xp, float)
oq = np.argsort(qt, kind="stable"); qt, qb, qB, qa, qA = qt[oq], qb[oq], qB[oq], qa[oq], qA[oq]
ox = np.argsort(xT, kind="stable"); xt, xT, xp = xt[ox], xT[ox], xp[ox]
res = {"orders_all": int(n_all), "orders_with_m": int(len(o)), "book_msgs": int(len(qt)), "trade_msgs": int(len(xT))}
lag = xt - xT
tau = float(np.median(lag)); res["tau_lap_ms"] = tau
hh = (xT // 1800000)
res["tau_lap_by_30min"] = {str(pd.to_datetime(int(k) * 1800, unit="s"))[11:16]: float(np.median(lag[hh == k])) for k in np.unique(hh)}
res["first_v2_ms"] = int(qt[0]) if len(qt) else None
dur = (qt[-1] - qt[0]) / 1000.0 if len(qt) > 1 else np.nan
res["book_rate_per_s"] = round(len(qt) / dur, 1) if dur == dur else None
# keep orders whose 2-s history lies inside the v2 recording (on the shifted clock)
lo_ms = int(qt[0] - tau + 131) + 2500 + dx.C_EX_MS
o = o[(o.m >= lo_ms) & (o.m <= int(xT[-1]) + 1000)].copy()
res["orders_scored"] = int(len(o)); res["coverage_of_taker_orders"] = round(len(o) / n_all, 4)
mic = (qb * qA + qa * qB) / (qB + qA); mid = (qb + qa) / 2
mdl = lgb.Booster(model_file=dx.MODEL); FN = mdl.feature_name()


def score(oo, Tb):
    oo = oo.sort_values(["cid", "is_up", "m"]).reset_index(drop=True)
    new = (oo.cid != oo.cid.shift()) | (oo.is_up != oo.is_up.shift()) | (oo.m - oo.m.shift() >= 300)
    oo["m0"] = oo.m.where(new).ffill().astype(np.int64); oo["first"] = new
    m = oo.m.to_numpy(np.int64); st = oo.start_ts.to_numpy(np.int64); up = oo.is_up.to_numpy(bool)
    p = mdl.predict(dx.features(m, st, Tb, mic, mid, xT, xp)[FN])
    pd0 = mdl.predict(dx.features(oo.m0.to_numpy(np.int64), st, Tb, mic, mid, xT, xp)[FN])
    out = {"n": int(len(oo)), "acc_per_order": round(float(((p > 0.5) == up).mean()), 4),
           "acc_per_decision": round(float(((pd0 > 0.5) == up).mean()), 4),
           "acc_first_legs": round(float(((p > 0.5) == up)[oo["first"].to_numpy()].mean()), 4)}
    for nm, sh in (("placebo_m_minus_3s", -3000), ("placebo_m_plus_3s", 3000)):
        Xp = dx.features(m + sh, st, Tb, mic, mid, xT, xp); Xp["rel"] = Xp.rel + sh / 1000.0
        out[nm] = round(float(((mdl.predict(Xp[FN]) > 0.5) == up).mean()), 4)
    w = oo.wallet.to_numpy()
    out["by_wallet"] = {x: [round(float(((p > 0.5) == up)[w == x].mean()), 4), int((w == x).sum())] for x in ("DS", "GF", "XM", "W4", "W5") if (w == x).any()}
    us = np.unique(st); md = us[len(us) // 2]
    out["halves"] = [round(float(((p > 0.5) == up)[st < md].mean()), 4), round(float(((p > 0.5) == up)[st >= md].mean()), 4)]
    out["by_minute"] = {int(k): round(float(v), 4) for k, v in pd.Series((p > 0.5) == up).groupby(((m / 1000 - st) // 60).astype(int)).mean().items()}
    return out, oo.assign(p=p, pdc=pd0)


three = o[o.wallet.isin(["DS", "GF", "XM"])]
sib = o[o.wallet.isin(["W4", "W5"])]
res["preregistered"], sc = score(three, qt - tau + 131)
res["preregistered"]["passes_bar_0.80"] = bool(res["preregistered"]["acc_per_order"] >= 0.80)
res["siblings_W4_W5"], _ = score(sib, qt - tau + 131) if len(sib) else (None, None)
# robustness (not a claim): tau per window from trades in [start - 60, end]
tw = {}
for r in win.itertuples():
    mk = (xT >= (r.start_ts - 60) * 1000) & (xT < r.end_ts * 1000)
    tw[r.start_ts] = float(np.median(lag[mk])) if mk.any() else tau
res["tau_per_window_range"] = [min(tw.values()), max(tw.values())]
sc.to_parquet(S + "/oot17_pred.parquet", index=False)
json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/oot17_side.json", "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))

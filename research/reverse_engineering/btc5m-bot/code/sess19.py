"""Iteration 19, X193 (assumptions panel iter18 P3) and X191 diagnostics.

PRE-REGISTRATION 18 (written 11-01 ~13:30 UTC, before the first run). Session-aware side routes on the dcclock14 frame (operator taker
orders of 10-17..22, features at the frozen exchange-clock anchor, dcfit14's PARAMS / ROUNDS and SPOT columns):
  base  = dc14_spot as frozen (reproduces dcfit14);
  ind   = dc14_spot + a Globex-open indicator (public CME calendar) as a feature;
  split = separate dc14_spot fits on open and on closed orders.
Forward: fit 10-17..19, score 10-20..22. Reverse: fit 10-20..22, score 10-17..19. ADOPT a variant only if the pooled per-order side
improves on BOTH splits and closed-session orders are non-inferior (within 0.005) on both. Reported by session, per wallet and halves.
Diagnostics (no claim): (a) the knee-profile gain G = acc(k160) - acc(k260) of first legs by UTC hour of day on Globex-open weekdays
against closed hours (does the leading input follow CME BTC's US-hours liquidity, or is it flat over the Globex day?); (b) the mixture
share pi of open-hour decisions whose trigger is invisible on Binance at the knee: pi = (acc_closed - acc_open) / (acc_closed - a_g) at
c = 260 for a_g in {0.5, 0.6}.
Usage: python sess19.py FRAME_DIR"""
import os, sys, json
import numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dcfit14 import PARAMS, ROUNDS, SPOT, mat
from knee19 import session

R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
FIT = ["2026-10-17", "2026-10-18", "2026-10-19"]


def acc(p, y, m=None):
    ok = (p > 0.5) == y
    if m is not None:
        ok = ok[m]
    return round(float(ok.mean()), 4) if len(ok) else None


def main():
    D = sys.argv[1]
    X = pd.read_parquet(f"{D}/dcclock14_frame.parquet", columns=["wallet", "up", "m", "m0", "rank", "start_ts", "day", "rel"] + [f"own_{c}" for c in SPOT] + ["k260", "k160"])
    X = X[X.wallet.isin(["DS", "GF", "XM"])].reset_index(drop=True)
    y = X.up.to_numpy() == 1
    ses = session(X.m.to_numpy()); opn = ses != "closed"
    res = {"prereg": "18", "n": int(len(X)), "splits": {}}
    M = mat(X, "own", SPOT); M["globex_open"] = opn.astype(float)
    base_cols = ["rel"] + SPOT
    for nm, fitm in (("forward", X.day.isin(FIT).to_numpy()), ("reverse", ~X.day.isin(FIT).to_numpy())):
        sc = ~fitm; out = {}
        pb = lgb.train(PARAMS, lgb.Dataset(M.loc[fitm, base_cols], label=y[fitm].astype(int)), ROUNDS).predict(M.loc[sc, base_cols])
        pi = lgb.train(PARAMS, lgb.Dataset(M.loc[fitm, base_cols + ["globex_open"]], label=y[fitm].astype(int)), ROUNDS).predict(M.loc[sc, base_cols + ["globex_open"]])
        ps = np.zeros(sc.sum())
        o_sc = opn[sc]
        for flag in (True, False):
            fm = fitm & (opn == flag)
            mdl = lgb.train(PARAMS, lgb.Dataset(M.loc[fm, base_cols], label=y[fm].astype(int)), ROUNDS)
            ps[o_sc == flag] = mdl.predict(M.loc[sc, base_cols][o_sc == flag])
        yv = y[sc]; Wv = X.wallet.to_numpy()[sc]; st = X.start_ts.to_numpy()[sc]; us = np.unique(st); md = us[len(us) // 2]
        for vn, p in (("base", pb), ("ind", pi), ("split", ps)):
            out[vn] = {"pooled": acc(p, yv), "open": acc(p, yv, o_sc), "closed": acc(p, yv, ~o_sc),
                       "by_wallet": {w: acc(p, yv, Wv == w) for w in ("DS", "GF", "XM")}, "halves": [acc(p, yv, st < md), acc(p, yv, st >= md)]}
        out["n_open_closed"] = [int(o_sc.sum()), int((~o_sc).sum())]
        res["splits"][nm] = out
        print(nm, json.dumps(out), flush=True)
    adopt = {}
    for vn in ("ind", "split"):
        ok = all(res["splits"][s][vn]["pooled"] > res["splits"][s]["base"]["pooled"] and res["splits"][s][vn]["closed"] >= res["splits"][s]["base"]["closed"] - 0.005
                 for s in ("forward", "reverse"))
        adopt[vn] = bool(ok)
    res["adopt"] = adopt
    # diagnostics on first legs
    F = X[X["rank"] == 0]
    yf = np.where(F.up.to_numpy() == 1, 1, -1)
    def a(col, m):
        v = F[col].to_numpy()[m]; yy = yf[m]
        return float(np.where(np.isfinite(v) & (v != 0), np.sign(np.nan_to_num(v)) == yy, 0.5).mean())
    sf = session(F.m0.to_numpy()); hh = pd.to_datetime(F.m0.to_numpy(), unit="ms", utc=True).hour.to_numpy()
    byh = {}
    for h in range(24):
        m = (sf != "closed") & (hh == h)
        mc = (sf == "closed") & (hh == h)
        byh[h] = {"open": [int(m.sum()), round(a("k160", m) - a("k260", m), 4) if m.sum() > 200 else None],
                  "closed": [int(mc.sum()), round(a("k160", mc) - a("k260", mc), 4) if mc.sum() > 200 else None]}
    res["G_by_utc_hour_first_legs"] = byh
    ac, ao = a("k260", sf == "closed"), a("k260", sf != "closed")
    res["mixture_share_pi"] = {"acc_k260_closed": round(ac, 4), "acc_k260_open": round(ao, 4),
                               "pi_if_a_g_0.5": round((ac - ao) / (ac - 0.5), 3), "pi_if_a_g_0.6": round((ac - ao) / (ac - 0.6), 3)}
    print(json.dumps({k: res[k] for k in ("adopt", "mixture_share_pi")}), flush=True)
    print({h: v for h, v in byh.items()}, flush=True)
    json.dump(res, open(f"{R}/sess19.json", "w"), indent=1)


if __name__ == "__main__":
    main()

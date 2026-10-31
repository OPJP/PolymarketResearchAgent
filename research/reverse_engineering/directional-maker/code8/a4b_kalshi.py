"""Iteration 8, catalog A4b / X48 (first measurement): Kalshi KXBTC15M (same quarter-hour BTC up/down) against the Polymarket
BTC 15m book, development block 10-31 12:15-16:45 UTC. Kalshi public trades (api.elections.kalshi.com, no key), per
quarter: ticker KXBTC15M-26OCT31HHMM-MM with HHMM the close in US Eastern time (UTC-4 on 10-31). Polymarket 15m Up mid
from the shared recorder ('q'). Lead-lag of 1-s changes (Kalshi yes price vs Polymarket Up mid) at lags -10..+10 s, and
whether the Kalshi price change over the previous 5 s predicts the cluster's 15m fill side beyond the Chainlink posture.
    python code8/a4b_kalshi.py 1793450700 1793466900
"""
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import final_rule as F  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
API = "https://api.elections.kalshi.com/trade-api/v2/markets/trades"


def kalshi_trades(ticker, cl):
    out, cur = [], None
    for _ in range(40):
        params = {"ticker": ticker, "limit": 1000}
        if cur:
            params["cursor"] = cur
        r = cl.get(API, params=params)
        if r.status_code == 429:
            time.sleep(2)
            continue
        if r.status_code != 200:
            break
        j = r.json()
        for t in j.get("trades", []):
            out.append((pd.Timestamp(t["created_time"]).timestamp(), float(t["yes_price_dollars"]), float(t.get("count_fp") or 0)))
        cur = j.get("cursor")
        if not cur or not j.get("trades"):
            break
        time.sleep(0.25)
    return out


def main(a, b):
    w15 = F._windows15(a, b)
    w15["up_token"] = w15.up_token.astype(str)
    cl = httpx.Client(timeout=20)
    K = {}
    for st, en in zip(w15.start_ts, w15.end_ts):
        close_et = pd.Timestamp(int(en), unit="s", tz="UTC").tz_convert("US/Eastern")
        tk = f"KXBTC15M-{close_et.strftime('%y%b%d%H%M').upper()}-{close_et.strftime('%M')}"
        tr = kalshi_trades(tk, cl)
        K[int(st)] = (tk, tr)
        print(tk, len(tr), flush=True)
    ups = set(w15.up_token)
    mids = {}
    for r in F._iter_live_xq(a, b, ups):
        if r.get("k") == "q" and str(r.get("a")) in ups:
            bq, oq = r.get("b") or [], r.get("o") or []
            if bq and oq:
                mids.setdefault(str(r["a"]), []).append((int(r.get("s") or r["t"]) / 1000, (max(float(x[0]) for x in bq) + min(float(x[0]) for x in oq)) / 2))
    res = {"quarters": len(K), "kalshi_trades": int(sum(len(v[1]) for v in K.values()))}
    cc = {L: [] for L in range(-10, 11)}
    for st, en, u in zip(w15.start_ts, w15.end_ts, w15.up_token):
        tr = K.get(int(st), (None, []))[1]
        if len(tr) < 50 or u not in mids:
            continue
        sec = np.arange(int(st) + 30, int(en) - 30)
        kt = np.array(sorted(tr))
        kp = kt[:, 1][np.clip(np.searchsorted(kt[:, 0], sec, side="right") - 1, 0, None)]
        mm = np.array(mids[u])
        mm = mm[np.argsort(mm[:, 0])]
        pp = mm[:, 1][np.clip(np.searchsorted(mm[:, 0], sec, side="right") - 1, 0, None)]
        dk, dp = np.diff(kp), np.diff(pp)
        for L in cc:
            if L >= 0:
                x, y = dk[:len(dk) - L], dp[L:]
            else:
                x, y = dk[-L:], dp[:len(dp) + L]
            cc[L].append((x, y))
    res["corr_dKalshi_t_dPM_t+L"] = {str(L): round(float(np.corrcoef(np.concatenate([p[0] for p in v]), np.concatenate([p[1] for p in v]))[0, 1]), 4)
                                     for L, v in cc.items() if v}
    (HERE.parent / "results" / f"iter8_a4b_kalshi_{a}_{b}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))


def control(a, b):
    """Does Kalshi lead the Polymarket 15m mid beyond Binance? OLS of dPM(t+1) on dKalshi(t) and Binance spot 1-s log returns
    at t-1, t, t+1 (signed by nothing: both are Up-probability changes vs BTC moves), standardised; R^2 with / without Kalshi."""
    w15 = F._windows15(a, b)
    w15["up_token"] = w15.up_token.astype(str)
    cl = httpx.Client(timeout=20)
    ups = set(w15.up_token)
    mids = {}
    for r in F._iter_live_xq(a, b, ups):
        if r.get("k") == "q" and str(r.get("a")) in ups:
            bq, oq = r.get("b") or [], r.get("o") or []
            if bq and oq:
                mids.setdefault(str(r["a"]), []).append((int(r.get("s") or r["t"]) / 1000, (max(float(x[0]) for x in bq) + min(float(x[0]) for x in oq)) / 2))
    secs, px = zip(*F._binance_rest_seconds(a - 60, b + 60))
    secs, px = np.array(secs, dtype=np.int64), np.array(px)
    rows = []
    for st, en, u in zip(w15.start_ts, w15.end_ts, w15.up_token):
        close_et = pd.Timestamp(int(en), unit="s", tz="UTC").tz_convert("US/Eastern")
        tk = f"KXBTC15M-{close_et.strftime('%y%b%d%H%M').upper()}-{close_et.strftime('%M')}"
        tr = kalshi_trades(tk, cl)
        if len(tr) < 50 or u not in mids:
            continue
        sec = np.arange(int(st) + 30, int(en) - 30)
        kt = np.array(sorted(tr))
        kp = kt[:, 1][np.clip(np.searchsorted(kt[:, 0], sec, side="right") - 1, 0, None)]
        mm = np.array(mids[u])
        mm = mm[np.argsort(mm[:, 0])]
        pp = mm[:, 1][np.clip(np.searchsorted(mm[:, 0], sec, side="right") - 1, 0, None)]
        sp = px[np.clip(np.searchsorted(secs, sec, side="right") - 1, 0, None)]
        dk, dp, ds = np.diff(kp), np.diff(pp), np.diff(np.log(sp))
        for i in range(1, len(dk) - 1):
            rows.append((dp[i + 1], dk[i], ds[i - 1], ds[i], ds[i + 1]))
    D = pd.DataFrame(rows, columns=["dpm1", "dk0", "ds_m1", "ds0", "ds1"])
    Z = (D - D.mean()) / D.std()
    import numpy.linalg as la
    def r2(cols):
        X = np.c_[np.ones(len(Z)), Z[cols].to_numpy()]
        beta = la.lstsq(X, Z.dpm1.to_numpy(), rcond=None)[0]
        res = Z.dpm1.to_numpy() - X @ beta
        return 1 - res.var() / Z.dpm1.var(), dict(zip(["c"] + cols, np.round(beta, 4)))
    out = {"n": int(len(D))}
    out["binance_only"] = r2(["ds_m1", "ds0", "ds1"])
    out["binance_plus_kalshi"] = r2(["ds_m1", "ds0", "ds1", "dk0"])
    out = json.loads(json.dumps(out, default=float))
    (HERE.parent / "results" / f"iter8_a4b_kalshi_control_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

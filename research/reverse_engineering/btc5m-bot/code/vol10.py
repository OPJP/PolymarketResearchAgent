"""Iteration 10 (X75 step 2 follow-up): is the maker share of the operator's fills in the sampled hours (delayreg10) explained by
BTC volatility rather than by the taker-delay regime? Binance spot BTCUSDT 1-s klines by REST for each sampled hour (16-17 UTC,
all before H; not cached), realized vol = RMS of 1-s log returns (bp); per hour: cluster maker share, fills; OLS of the maker
share on log vol and the regime dummies (D = 250 / 50 early / 50 late / 150).
Usage: python vol10.py OUT_JSON"""
import os, sys, json, time, calendar
import numpy as np, httpx

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
H = 1792713600


def klines(t0, t1, cl):
    out = []
    s = t0 * 1000
    while s < t1 * 1000:
        r = cl.get("https://api.binance.com/api/v3/klines", params={"symbol": "BTCUSDT", "interval": "1s", "startTime": s, "endTime": t1 * 1000 - 1, "limit": 1000}, timeout=30)
        j = r.json()
        if not isinstance(j, list) or not j:
            break
        out += [(int(x[0]) // 1000, float(x[4])) for x in j]
        s = int(j[-1][0]) + 1000
        time.sleep(0.15)
    return out


def main(out):
    d = json.load(open(os.path.join(R, "delayreg10.json")))
    cl = httpx.Client()
    rows = []
    for per, hrs in d["per_hour"].items():
        for h in hrs:
            t0 = calendar.timegm(time.strptime(f"{h['day']} {h['hour']:02d}", "%Y-%m-%d %H")); t1 = t0 + 3600
            assert t1 <= H
            k = klines(t0, t1, cl)
            p = np.array([c for _, c in k])
            r = np.diff(np.log(p)) * 1e4 if len(p) > 10 else np.array([np.nan])
            m = sum(c["M"] for w, c in h["by_wallet"].items() if w != "W4"); n = sum(c["M"] + c["T"] for w, c in h["by_wallet"].items() if w != "W4")
            rows.append({"period": per, "day": h["day"], "vol_bp": round(float(np.sqrt(np.nanmean(r ** 2))), 4), "abs_move_bp": round(float(abs(np.log(p[-1] / p[0]) * 1e4)) if len(p) > 10 else None, 1),
                         "maker_share": round(m / max(n, 1), 4), "fills": n})
    X = np.array([[1.0, np.log(r_["vol_bp"]), r_["period"] == "D50_after_0817", r_["period"] == "D50_before_0904", r_["period"] == "D150_after_0904"] for r_ in rows], float)
    y = np.array([r_["maker_share"] for r_ in rows])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    b0, *_ = np.linalg.lstsq(X[:, :2], y, rcond=None)
    corr = float(np.corrcoef(X[:, 1], y)[0, 1])
    res = {"hours": rows, "corr(maker_share, log vol)": round(corr, 4),
           "ols_vol_only [a, b_logvol]": [round(float(x), 4) for x in b0],
           "ols_vol_plus_regimes [a, b_logvol, D50_after_0817, D50_before_0904, D150_after_0904] (base D250)": [round(float(x), 4) for x in b],
           "corr(fills, log vol)": round(float(np.corrcoef(X[:, 1], [r_["fills"] for r_ in rows])[0, 1]), 4)}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

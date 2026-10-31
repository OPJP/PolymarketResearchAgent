"""Iteration 9 (information I8-5 = X78; strong form of X48 / A4b): Kalshi KXBTC15M as a side input for the cluster's BTC
15m fills, raced against the slow-sigma posture, on the 10-31 12:00-18:00 match-clock fill table (side_D; development).
Kalshi yes = P(BRTI 60-s average at close >= floor_strike), floor_strike = BRTI 60-s average before the open; Polymarket
Up = P(Chainlink TWAP-60 at close >= priceToBeat), priceToBeat = Chainlink TWAP-60 before the open. With a constant
BRTI - Chainlink basis over the quarter both are the same probability, so the Kalshi yes price is compared with the
Polymarket Up mid directly; the basis floor_strike - priceToBeat is reported per quarter as a check.
Predictor: Up iff Kalshi yes (last trade before the match ms) > Polymarket Up mid ("PM cheap relative to Kalshi").
    python code9/kalshi_side.py
"""
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
API = "https://api.elections.kalshi.com/trade-api/v2/markets"
A, B = 1793448000, 1793469600


def trades(cl, ticker, t_lo):
    out, cur = [], None
    for _ in range(80):
        params = {"ticker": ticker, "limit": 1000}
        if cur:
            params["cursor"] = cur
        r = cl.get(API + "/trades", params=params)
        if r.status_code == 429:
            time.sleep(2)
            continue
        if r.status_code != 200:
            break
        j = r.json()
        tr = j.get("trades", [])
        for t in tr:
            out.append((pd.Timestamp(t["created_time"]).timestamp(), float(t["yes_price_dollars"])))
        cur = j.get("cursor")
        if not cur or not tr or min(x[0] for x in out) < t_lo:
            break
        time.sleep(0.2)
    return out


def main():
    D = pd.read_parquet(C / "it9" / f"side_D_{A}_{B}.parquet")
    D = D[(D.en - D.st) == 900].reset_index(drop=True)
    cl = httpx.Client(timeout=20)
    kp = {}
    meta = {}
    for st, en in sorted(set(zip(D.st, D.en))):
        close_et = pd.Timestamp(int(en), unit="s", tz="UTC").tz_convert("US/Eastern")
        tk = f"KXBTC15M-{close_et.strftime('%y%b%d%H%M').upper()}-{close_et.strftime('%M')}"
        tlo = int(D[D.st == st]["T"].min() // 1000) - 60
        tr = trades(cl, tk, tlo)
        r = cl.get(f"{API}/{tk}")
        fs = r.json().get("market", {}).get("floor_strike") if r.status_code == 200 else None
        kp[int(st)] = np.array(sorted(tr)) if tr else np.zeros((0, 2))
        meta[int(st)] = {"ticker": tk, "trades": len(tr), "floor_strike": fs, "first_trade": float(kp[int(st)][0, 0]) if len(tr) else None}
        print(tk, len(tr), fs, flush=True)
    sp = pd.read_parquet(C / "it9" / f"spot1s_rest_{A - 7200}_{B}.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    ti = (D["T"].to_numpy() // 1000) - 1 - b0
    v3600 = np.sqrt((cs[ti + 1] - cs[ti + 1 - 3600]) / 3600)
    v300 = np.sqrt((cs[ti + 1] - cs[ti + 1 - 300]) / 300)
    tau = np.maximum(D.en.to_numpy() - D["T"].to_numpy() / 1000, 1.0)
    x = np.log(D.cl.to_numpy(float) / D.K.to_numpy(float))
    m = D.mid_up.to_numpy()
    y = D.is_up.to_numpy() == 1
    slow = norm.cdf(x / (v3600 * np.sqrt(tau))) > m
    frz = norm.cdf(x / (1.4 * v300 * np.sqrt(tau))) > m
    kal = np.full(len(D), np.nan)
    age = np.full(len(D), np.nan)
    for i, (st, T) in enumerate(zip(D.st, D["T"])):
        k = kp.get(int(st))
        if k is None or not len(k):
            continue
        j = np.searchsorted(k[:, 0], T / 1000, side="right") - 1
        if j >= 0:
            kal[i] = k[j, 1]
            age[i] = T / 1000 - k[j, 0]
    ok = np.isfinite(kal) & (age < 30)
    kside = kal > m
    out = {"fills_15m": int(len(D)), "with_kalshi": int(ok.sum()), "quarters": meta,
           "acc_kalshi_cheap": float(np.mean((kside == y)[ok])), "acc_slow_posture": float(np.mean((slow == y)[ok])),
           "acc_frozen_posture": float(np.mean((frz == y)[ok])),
           "agree_slow_kalshi_share": float(np.mean((slow == kside)[ok])),
           "acc_when_agree": float(np.mean((slow == y)[ok & (slow == kside)])),
           "acc_slow_when_disagree": float(np.mean((slow == y)[ok & (slow != kside)])),
           "acc_kalshi_when_disagree": float(np.mean((kside == y)[ok & (slow != kside)])),
           "n_disagree": int((ok & (slow != kside)).sum())}
    bas = {}
    for st, mt in meta.items():
        K = D[D.st == st].K.iloc[0]
        if mt["floor_strike"] is not None:
            bas[str(st)] = round(float(mt["floor_strike"]) - float(K), 2)
    out["basis_floor_strike_minus_ptb"] = bas
    print(json.dumps({k: v for k, v in out.items() if k != "quarters"}, indent=1))
    (HERE.parent / "results" / "iter9_kalshi_side.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()

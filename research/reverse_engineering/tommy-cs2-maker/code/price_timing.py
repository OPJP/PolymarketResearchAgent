"""Quote placement and timing of the wallet's maker orders against the public taker tape (development data).

For each filled maker order (B1 signing time t, outcome oi, limit price p):
  last_p   = outcome-oi probability implied by the last public taker print in the market with block ts < t
             (wallet transactions excluded), age = t - ts of that print;
  vwap_p   = volume-weighted p over prints in [t-60, t);
  d_last   = p - last_p (cents), d_vwap = p - vwap_p;
Event study: rate of the wallet's signings around public taker prints, and around large public moves.
Writes .cache/re/tommy-cs2-maker/orders_ctx.parquet and results/price_timing.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, RES, TAPES  # noqa: E402


def load_tape(cid: str, bad: set) -> pd.DataFrame | None:
    p = TAPES / f"{cid}_tkw.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    if len(d) == 0:
        return None
    d = d[(d["timestamp"] < H) & ~d["transactionHash"].isin(bad)].copy()
    d["price"] = d["price"].astype(float)
    d["size"] = d["size"].astype(float)
    oi = d["outcomeIndex"].astype(int)
    d["p0"] = np.where(oi == 0, d["price"], 1 - d["price"])
    d["usd"] = d["price"] * d["size"]
    return d.sort_values("timestamp", kind="stable").reset_index(drop=True)


def main() -> None:
    o = pd.read_parquet(OUT / "orders.parquet")
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    from common import WALLET
    bad = set(cd.loc[cd["maker"] == WALLET, "tx"])
    mk = o[o["role"] == "maker"].copy()
    rows = []
    ev_lags = []  # event study: sign time minus each public print's time, |lag| <= 60
    big_lags = []
    n_prints = 0
    for cid, g in mk.groupby("cid"):
        d = load_tape(cid, bad)
        if d is None:
            continue
        ts = d["timestamp"].to_numpy(np.int64)
        p0 = d["p0"].to_numpy(float)
        usd = d["usd"].to_numpy(float)
        st = g["sign_ts"].to_numpy(float)
        i = np.searchsorted(ts, st, side="left")  # prints with ts < sign time (block ts in whole seconds)
        has = i > 0
        lp0 = np.where(has, p0[np.maximum(i - 1, 0)], np.nan)
        age = np.where(has, st - ts[np.maximum(i - 1, 0)], np.nan)
        cu = np.concatenate([[0.0], np.cumsum(usd)])
        cpu = np.concatenate([[0.0], np.cumsum(usd * p0)])
        j = np.searchsorted(ts, st - 60, side="left")
        vol = cu[i] - cu[j]
        vw = np.where(vol > 0, (cpu[i] - cpu[j]) / np.where(vol > 0, vol, 1), np.nan)
        oi = g["oi"].to_numpy(int)
        last_p = np.where(oi == 0, lp0, 1 - lp0)
        vwap_p = np.where(oi == 0, vw, 1 - vw)
        # public move in the previous 10 s / next 10 s (outcome-oi terms)
        j10 = np.searchsorted(ts, st - 10, side="left")
        p_before = np.where(j10 > 0, p0[np.maximum(j10 - 1, 0)], np.nan)
        k10 = np.searchsorted(ts, st + 10, side="left")
        p_after = np.where(k10 > 0, p0[np.maximum(k10 - 1, 0)], np.nan)
        mv_prev = np.where(oi == 0, lp0 - p_before, -(lp0 - p_before))
        mv_next = np.where(oi == 0, p_after - lp0, -(p_after - lp0))
        rows.append(pd.DataFrame({"cid": cid, "sign_ts": st, "price": g["price"].to_numpy(), "oi": oi,
                                  "last_p": last_p, "age": age, "vwap_p": vwap_p, "vol60": vol,
                                  "mv_prev10": mv_prev, "mv_next10": mv_next, "life_first": g["life_first"].to_numpy(),
                                  "shares": g["shares"].to_numpy(), "gs_ts": g["gs_ts"].to_numpy(), "smt": g["smt"].to_numpy()}))
        # event study around prints (sign times relative to prints of the same market)
        n_prints += len(ts)
        for t in st:
            a, b = np.searchsorted(ts, t - 60), np.searchsorted(ts, t + 60)
            ev_lags.append(t - ts[a:b])
        dp = np.abs(np.diff(p0))
        big = ts[1:][dp >= 0.04]
        for t in st:
            a, b = np.searchsorted(big, t - 60), np.searchsorted(big, t + 60)
            big_lags.append(t - big[a:b])
    x = pd.concat(rows, ignore_index=True)
    x["d_last"] = np.round((x["price"] - x["last_p"]) * 100, 1)
    x["d_vwap"] = (x["price"] - x["vwap_p"]) * 100
    x.to_parquet(OUT / "orders_ctx.parquet", index=False)
    res = {"n": len(x), "has_last": float(x["last_p"].notna().mean())}
    fresh = x[x["age"] < 30]
    res["d_last_cents_all"] = x["d_last"].describe(percentiles=[.05, .25, .5, .75, .95]).round(2).to_dict()
    res["d_last_cents_fresh"] = fresh["d_last"].describe(percentiles=[.05, .25, .5, .75, .95]).round(2).to_dict()
    res["d_last_top_fresh"] = fresh["d_last"].round(0).value_counts(normalize=True).head(12).round(3).to_dict()
    res["d_vwap_cents"] = x["d_vwap"].describe(percentiles=[.05, .25, .5, .75, .95]).round(2).to_dict()
    res["age_of_last_print"] = x["age"].describe(percentiles=[.05, .25, .5, .75, .95]).round(1).to_dict()
    res["mv_prev10_mean_c"] = float(np.nanmean(x["mv_prev10"]) * 100)
    res["mv_next10_mean_c"] = float(np.nanmean(x["mv_next10"]) * 100)
    lags = np.concatenate(ev_lags) if ev_lags else np.array([])
    h, e = np.histogram(lags, bins=np.arange(-60, 61, 2))
    res["sign_minus_print_hist_2s"] = {f"{int(a)}": int(c) for a, c in zip(e[:-1], h)}
    bl = np.concatenate(big_lags) if big_lags else np.array([])
    h, e = np.histogram(bl, bins=np.arange(-30, 31, 1))
    res["sign_minus_bigmove_hist_1s"] = {f"{int(a)}": int(c) for a, c in zip(e[:-1], h)}
    json.dump(res, open(RES / "results/price_timing.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("sign_minus")}, indent=1))
    print("bigmove", res["sign_minus_bigmove_hist_1s"])
    print("print", res["sign_minus_print_hist_2s"])


if __name__ == "__main__":
    main()

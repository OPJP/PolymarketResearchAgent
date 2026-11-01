"""iteration 15, T1d (post hoc, follows T1b): the non-BTC posture with a PUBLIC market price.
For each cluster BUY on a non-BTC family (VALIDATE aggregate, STUDY, development after T0), the market price of the
bought outcome = the last clean taker print of the market stamped <= T - 2 (data-api taker tape; transactions holding
a cluster trade dropped; the other token's print mapped to 1 - p). Rules: posture_public = F_s(k) > p_s(last print),
k in {0.7, 1.0, 1.4}; market favourite from the same print; in the money (T1). Fill-price posture reported beside it.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code15/nb_public.py
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from nb_side import Spot, C, RES  # noqa: E402


def main():
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    a = pd.read_parquet(C / "it15_nb_side.parquet")
    a = a[(~a.btc_core) & a.rule_ok.notna() & (a.fold.str.startswith("STUDY") | a.fold.isin(["VALIDATE", "dev_after_T0"]))].reset_index(drop=True)
    ctx = set(a.transactionHash.str.lower())
    # every cluster tx of the period (all families) is excluded from the clean tape
    allc = pd.read_parquet(C / "it15_nb_side.parquet", columns=["transactionHash"])
    ctx |= set(allc.transactionHash.str.lower())
    a = a[~a.fam.str.endswith("-daily")].reset_index(drop=True)  # daily tapes are too long to page in this iteration
    mk = a.drop_duplicates("conditionId")[["conditionId", "st", "L"]]
    t0 = time.time()

    def get(row):
        cid, st, L = row
        try:
            rows, _, _ = pm.market_trades(cid, start=int(st) - 3600, end=int(st + L) + 60, taker_only=True)
        except Exception as ex:  # noqa: BLE001
            return cid, None
        return cid, [(int(r["timestamp"]), str(r.get("asset")), float(r["price"]), str(r.get("transactionHash", "")).lower()) for r in rows]
    tapes = {}
    with ThreadPoolExecutor(3) as ex:
        for i, (cid, rows) in enumerate(ex.map(get, mk.itertuples(index=False, name=None))):
            tapes[cid] = rows
            if i % 200 == 0:
                print("tapes", i, len(mk), round(time.time() - t0), "s", flush=True)
    ps = np.full(len(a), np.nan)
    # cluster transactions per market (a matchOrders transaction settles one market)
    allm = pd.read_parquet(C / "it15_nb_side.parquet", columns=["conditionId", "transactionHash"])
    ctx_m = {c: set(h.str.lower()) for c, h in allm.groupby("conditionId").transactionHash}
    print("scoring", flush=True)
    for cid, g in a.groupby("conditionId"):
        rows = tapes.get(cid)
        if not rows:
            continue
        cs = ctx_m.get(cid, set())
        rows = [x for x in rows if x[3] not in cs]
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        ts = np.array([x[0] for x in rows], np.int64)
        assets = [x[1] for x in rows]
        pr = np.array([x[2] for x in rows], float)
        k = np.searchsorted(ts, g.timestamp.to_numpy(np.int64) - 2, side="right") - 1
        for j, kk, asset in zip(g.index, k, g.asset.astype(str)):
            if kk < 0:
                continue
            ps[j] = pr[kk] if assets[kk] == asset else 1 - pr[kk]
    a["p_pub"] = ps
    sp = Spot(); sig = np.full(len(a), np.nan)
    for sym, g in a.groupby("sym"):
        t = g.timestamp.to_numpy(np.int64) - 3
        grid = t[:, None] + np.arange(-300, 1)[None, :]
        v = np.log(sp.close_at(sym, grid.ravel()).reshape(grid.shape))
        with np.errstate(invalid="ignore"):
            sig[g.index] = np.nanstd(np.diff(v, axis=1), axis=1)
    tau = np.maximum(a.st + a.L - a.timestamp, 1).to_numpy(float)
    z = np.log(a.S / a.K).to_numpy(float)
    up = a.up.to_numpy(float)
    fg = a.fam.str.replace(r"^(eth|sol|xrp|bnb|doge)-(5m|15m)$", r"alt-\2", regex=True).str.replace(r"^\w+-4h$", "4h", regex=True).str.replace(r"^\w+-hourly$", "hourly", regex=True).str.replace(r"^\w+-daily$", "daily", regex=True)
    fd = np.where(a.fold.str.startswith("STUDY"), "STUDY", a.fold)
    d = pd.DataFrame({"fg": fg, "fold": fd, "phase": a.phase, "itm": a.rule_ok, "has_pub": np.isfinite(ps)})
    d["mktfav_pub"] = np.where(np.isfinite(ps) & (ps != 0.5), (ps > 0.5).astype(float), np.nan)
    for k in (0.7, 1.0, 1.4):
        Fu = norm.cdf(z / (k * sig * np.sqrt(tau))); Fs = np.where(up == 1, Fu, 1 - Fu)
        d[f"post_pub_k{k}"] = np.where(np.isfinite(Fs) & np.isfinite(ps), (Fs > ps).astype(float), np.nan)
        d[f"post_fill_k{k}"] = np.where(np.isfinite(Fs), (Fs > a.price.to_numpy()).astype(float), np.nan)
    a.assign(**{c: d[c].to_numpy() for c in d.columns if c.startswith("post_pub") or c == "mktfav_pub"}).to_parquet(C / "it15_nb_public_lot.parquet", index=False)
    cols = [c for c in d.columns if c not in ("fg", "fold", "phase", "has_pub")]
    out = {"n": int(len(a)), "with_public_price": float(d.has_pub.mean()),
           "by_fold": d[d.has_pub].groupby("fold")[cols].mean().round(4).assign(n=d[d.has_pub].groupby("fold").size()).reset_index().to_dict("records"),
           "by_fold_group": d[d.has_pub].groupby(["fold", "fg"])[cols].mean().round(4).assign(n=d[d.has_pub].groupby(["fold", "fg"]).size()).reset_index().to_dict("records"),
           "by_fold_phase": d[d.has_pub].groupby(["fold", "phase"])[cols].mean().round(4).assign(n=d[d.has_pub].groupby(["fold", "phase"]).size()).reset_index().to_dict("records")}
    (RES / "iter15_nb_public.json").write_text(json.dumps(out, indent=1, default=float))
    for k in ("by_fold", "by_fold_phase", "by_fold_group"):
        print(pd.DataFrame(out[k]).to_string(index=False))


if __name__ == "__main__":
    main()

"""X182 step 1b (assumptions panel iter-12 P3): does its quote level lead the market when the target is other traders'
EXECUTED prices (joiners cannot move it by resting), not the others' mid? BUILD-live (10-31 12-18), uncensored adds
(linked_adds_dev; the same own-add label as add_level_info.py). For each add: offset = bid - others' mid 100 ms before
(cents, own token space; others_mid_dev); target = VWAP of public trades in (t + 5 s, t + 60 s] on that market (data-api
tape at block time, the wallet's transactions excluded, mapped to the add's token space) minus that mid. Spearman for
own adds vs other makers' adds (placebo), and a null with own offsets re-paired to shifted times (+-30..300 s, 200 draws).
Output: results/lead_vs_trades.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
B0, B1 = 1793448000, 1793469600


def main():
    A = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    A["a"] = A.a.astype(str)
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    A = A[A.kind == "add"]
    M = pd.read_parquet(OUT / "others_mid_dev.parquet").sort_values(["a", "s"])
    M["a"] = M.a.astype(str)
    mids = {a: (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M.groupby("a")}
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    tok = {}
    for r in dm.itertuples():
        tok[str(r.tok0)] = (r.cid, 0)
        tok[str(r.tok1)] = (r.cid, 1)
    cd = pd.read_parquet(OUT / "calldata_dev.parquet", columns=["tx", "maker"])
    wtx = set(cd.loc[cd.maker.str.lower() == W, "tx"])
    pm = PolymarketData()
    tapes = {}
    for cid in {tok[a][0] for a in A.a.unique() if a in tok}:
        rows, _, _ = pm.market_trades(cid, start=B0 - 3600, end=B1 + 3600, taker_only=False)
        d = pd.DataFrame(rows)
        if not len(d):
            continue
        d = d[~d.transactionHash.isin(wtx)]
        # one row per print: data-api returns maker and taker rows; keep taker rows if flagged, else all
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        tapes[cid] = (d.timestamp.to_numpy(float), p0, d["size"].astype(float).to_numpy())
    rows = []
    for r in A.itertuples():
        x = mids.get(r.a)
        if x is None or r.a not in tok or tok[r.a][0] not in tapes:
            continue
        ts, md = x
        j0 = np.searchsorted(ts, r.s - 100, side="right") - 1
        if j0 < 0:
            continue
        tok0 = r.side == "BUY"
        bid = r.p if tok0 else 1 - r.p
        m0 = md[j0] if tok0 else 1 - md[j0]
        cid, oi = tok[r.a]
        tt, pp, sz = tapes[cid]
        q = (tt > r.s / 1000 + 5) & (tt <= r.s / 1000 + 60)
        if not q.any():
            continue
        v0 = float(np.sum(pp[q] * sz[q]) / np.sum(sz[q]))
        v = v0 if oi == 0 else 1 - v0
        # orient to the add's token space: mids are of the token 'a'; a BUY on token a -> token space a
        rows.append({"a": r.a, "s": float(r.s), "own": bool(r.vown), "off": (bid - m0) * 100, "dv": (v - m0) * 100 if tok0 else ((1 - v) - m0) * 100,
                     "cid": cid, "oi": oi, "tok0": tok0})
    X = pd.DataFrame(rows)
    X = X[np.isfinite(X.off) & (X.off.abs() <= 15)]
    o, p = X[X.own], X[~X.own]
    res = {"own_adds": int(len(o)), "other_adds": int(len(p))}
    ro, rp = spearmanr(o.off, o.dv)[0], spearmanr(p.off, p.dv)[0]
    rng = np.random.default_rng(13)
    nul = []
    for _ in range(200):
        dv = []
        for r in o.itertuples():
            tt, pp, sz = tapes[r.cid]
            ts, md = mids[r.a]
            sh = r.s + rng.choice([-1, 1]) * rng.uniform(30000, 300000)
            j0 = np.searchsorted(ts, sh - 100, side="right") - 1
            q = (tt > sh / 1000 + 5) & (tt <= sh / 1000 + 60)
            if j0 < 0 or not q.any():
                dv.append(0.0)
                continue
            m0 = md[j0] if r.tok0 else 1 - md[j0]
            v0 = float(np.sum(pp[q] * sz[q]) / np.sum(sz[q]))
            v = v0 if r.oi == 0 else 1 - v0
            dv.append((v - m0) * 100 if r.tok0 else ((1 - v) - m0) * 100)
        nul.append(spearmanr(o.off, dv)[0])
    res.update({"own_spearman": round(float(ro), 4), "other_spearman": round(float(rp), 4), "null_mean": round(float(np.mean(nul)), 4),
                "null_p95": round(float(np.percentile(nul, 95)), 4), "p_own_vs_null": round(float(np.mean(np.array(nul) >= ro)), 4)})
    (RES / "lead_vs_trades.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

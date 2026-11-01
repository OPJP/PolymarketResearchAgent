"""X224 (mechanics panel iter-15 P2), historical part: an own-inventory skew on the order-unit price rule.
Pre-registered in NOTES iteration 16. Order unit at signing (filled maker orders, 16-22 Oct, as evaluate() scores it):
anchor a = round(last taker print before signing, 2) on the order's token (evaluate()'s tape); rule = a - k(bucket),
bucket of the wallet's net position in the order's token at signing (<= 0, 0-200, 200-600, > 600 shares; own state from
its earlier fills), k the integer cent in 0..4 that maximizes the within-tick share on BUILD; scored on VALIDATE against
k = 0 (the frozen 0.322 rule) and a single global k (no own state). Output: results/inventory_skew.json"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SPLIT = 1792540800  # 2026-10-21 00:00 UTC (BUILD / VALIDATE by game start)
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    o = pd.read_parquet(OUT / "orders_inv.parquet")
    o = o[o.role == "maker"].drop_duplicates(["salt", "sign_ms"]).copy()
    cdw = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    wtx = set(cdw.loc[cdw.maker == W, "tx"])
    rows = []
    for cid, g in o.groupby("cid"):
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p).sort_values("timestamp")
        for nm, dd in (("eval_tape", d), ("wallet_free", d[~d.transactionHash.isin(wtx)])):
            ts = dd.timestamp.to_numpy(float)
            p0 = np.where(dd.outcomeIndex.astype(int) == 0, dd.price.astype(float), 1 - dd.price.astype(float))
            k = np.searchsorted(ts, g.sign_ms.to_numpy(float) / 1000, side="left")
            lp = np.where(k > 0, p0[np.maximum(k - 1, 0)], np.nan)
            lp = np.where(g.oi.to_numpy() == 0, lp, 1 - lp)
            rows.append(pd.DataFrame({"cid": cid, "tape": nm, "p": g.price.to_numpy(float), "a": np.round(lp, 2),
                                      "net": g.own_net.to_numpy(float), "gs": g.gs_ts.to_numpy(float)}))
    R = pd.concat(rows, ignore_index=True).dropna(subset=["a"])
    R["build"] = R.gs < SPLIT
    R["bucket"] = pd.cut(R.net, [-1e9, 0, 200, 600, 1e9], labels=["<=0", "0-200", "200-600", ">600"]).astype(str)
    out = {"own_net_definition": "orders_inv.own_net (net shares of the order's token minus its complement at signing, from earlier own fills)"}
    for tape, X in R.groupby("tape"):
        def score(df, kk):
            a = df.a - kk / 100.0
            tick = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
            return float((np.abs(df.p - a) <= tick + 1e-9).mean())
        B, V = X[X.build], X[~X.build]
        kg = max(range(5), key=lambda kk: score(B, kk))
        kb = {b: max(range(5), key=lambda kk: score(B[B.bucket == b], kk)) for b in B.bucket.unique()}
        V2 = V.assign(k=V.bucket.map(lambda b: float(kb.get(b, kg))).astype(float))
        a = V2.a - V2.k / 100.0
        tick = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
        out[tape] = {"n_build": int(len(B)), "n_validate": int(len(V)),
                     "validate_k0": round(score(V, 0), 3), "global_k_build": kg, "validate_global_k": round(score(V, kg), 3),
                     "bucket_k_build": kb, "validate_bucket_k_own_state": round(float((np.abs(V2.p - a) <= tick + 1e-9).mean()), 3),
                     "validate_by_bucket": {b: {"n": int((V.bucket == b).sum()), "k0": round(score(V[V.bucket == b], 0), 3),
                                                "k_fit": round(score(V[V.bucket == b], kb.get(b, kg)), 3),
                                                "median_offset_c": round(float(((V.p - V.a)[V.bucket == b]).median() * 100), 2)}
                                            for b in sorted(V.bucket.unique())}}
    (RES / "inventory_skew.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()

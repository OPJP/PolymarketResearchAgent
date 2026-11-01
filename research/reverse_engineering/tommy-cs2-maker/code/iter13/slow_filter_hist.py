"""X174 historical form (information panel iter-12 P3): is its quote level a rounded slow filter of public prices?
V_filter(t) = round_1c(EMA_h(prints up to t) + offset), prints of the same market in team-A space with the wallet's
transactions excluded (point in time: prints stamped before signing), h in {0 (last print), 2, 5, 15, 60, 180} s
(exponential weights on print age), the same book only (the event composite with the round books is the live form,
which waits for VALIDATE-live). One offset fitted on BUILD as the median of price - filter (in the order's token space);
score on VALIDATE: within one tick (1c inside [0.04, 0.96]) of its maker orders (deduped), the last print as reference.
Output: results/slow_filter_hist.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
HS = [0, 2, 5, 15, 60, 180]
SPLIT = 1792540800


def ema_at(ts, ys, q, h):
    """EMA with half-life h seconds of the print series (ts, ys), evaluated at query times q (prints strictly before q)."""
    k = np.searchsorted(ts, q, side="left") - 1
    out = np.full(len(q), np.nan)
    if h == 0:
        ok = k >= 0
        out[ok] = ys[k[ok]]
        return out
    lam = np.log(2) / h
    # recursive EMA on irregular prints: e_i = e_{i-1} * exp(-lam dt) + y_i * (1 - exp(-lam dt)) (first = y_0)
    e = np.empty(len(ts))
    e[0] = ys[0]
    for i in range(1, len(ts)):
        a = np.exp(-lam * (ts[i] - ts[i - 1]))
        e[i] = a * e[i - 1] + (1 - a) * ys[i]
    ok = k >= 0
    out[ok] = e[k[ok]]
    return out


def main():
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "token_id", "price", "sign_ms", "salt", "cid", "oi", "gs_ts"])
    cd["maker"] = cd.maker.str.lower()
    wtx = set(cd.loc[cd.maker == W, "tx"])
    wo = cd[(cd.maker == W) & (cd.idx != -1)].drop_duplicates(["salt", "sign_ms"]).copy()
    rows = []
    for cid, g in wo.groupby("cid"):
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        if len(d) < 5:
            continue
        ts = d.timestamp.to_numpy(float)
        y0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        q = g.sign_ms.to_numpy() / 1000.0
        oi = g.oi.to_numpy().astype(int)
        rec = {"cid": cid, "price": g.price.to_numpy(float), "oi": oi, "gs": g.gs_ts.to_numpy(float)}
        for h in HS:
            f = ema_at(ts, y0, q, h)
            rec[f"f{h}"] = np.where(oi == 0, f, 1 - f)
        rows.append(pd.DataFrame(rec))
    R = pd.concat(rows, ignore_index=True)
    R = R.dropna()
    bu, va = R[R.gs < SPLIT], R[R.gs >= SPLIT]
    out = {"n_build": int(len(bu)), "n_validate": int(len(va)), "by_h": {}}
    for h in HS:
        col = f"f{h}"
        off = float(np.median(bu.price - bu[col]))
        for name, X in (("BUILD", bu), ("VALIDATE", va)):
            v = np.round((X[col] + off) * 100) / 100
            tick = np.where((v >= 0.04) & (v <= 0.96), 0.01, 0.001)
            w = np.abs(X.price - v) <= tick + 1e-9
            raw = np.round(X[col], 2)
            w0 = np.abs(X.price - raw) <= np.where((raw >= 0.04) & (raw <= 0.96), 0.01, 0.001) + 1e-9
            out["by_h"].setdefault(str(h), {})[name] = {"offset_c": round(off * 100, 2), "within_tick_with_offset": round(float(w.mean()), 3),
                                                       "within_tick_no_offset": round(float(w0.mean()), 3)}
    (RES / "slow_filter_hist.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

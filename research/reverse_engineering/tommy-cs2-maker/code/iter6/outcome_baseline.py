"""Iteration 6, X82 (assumptions panel iter5 P3): an activity baseline and single-leg ceilings for the outcome item.

Per market (the wallet's 229 CS2 / Dota 2 markets of 16-22 Oct, development data), against the wallet's settlement
PnL (per_market.parquet):
  activity baselines (wallet txs excluded): count of in-play public taker prints, their USD, total variation of the
  10-s last price (in-play), net displacement; a "c x prints" pseudo-PnL has the same correlation as the count;
  single legs of the wallet's own fills, settled at resolution: maker fills only, taker fills only;
  the locked margin of its own pairs (pairs x (1 - pair cost));
  partial correlation of each quantity with the wallet's PnL given the print count (Pearson on residuals of a linear
  fit on log1p(prints); Spearman on rank residuals).
Splits by game start: BUILD < 10-21, VALIDATE >= 10-21. Event bootstrap (markets resampled by event) for the CI of
the baseline correlations.
Output: results/outcome_baseline.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr, rankdata

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
VAL0 = 1792540800
rng = np.random.default_rng(66)


def partial(y, x, z, kind):
    if kind == "spearman":
        y, x, z = rankdata(y), rankdata(x), rankdata(z)
    A = np.c_[np.ones(len(z)), z]
    ry = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    rx = x - A @ np.linalg.lstsq(A, x, rcond=None)[0]
    return float(np.corrcoef(ry, rx)[0, 1])


def main():
    pm = pd.read_parquet(OUT / "per_market.parquet")
    ca = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "maker", "oi", "fill", "price", "cid", "gs_ts", "bts"])
    w = ca[ca.maker == WALLET].copy()
    wtx = set(ca.tx)
    win = dict(zip(pm.cid, pm.win))
    w["win"] = w.cid.map(win)
    w["pnl"] = np.where(w.oi == w.win, w.fill, 0.0) - w.fill * w.price
    leg = w.assign(role=np.where(w.idx == -1, "taker", "maker")).groupby(["cid", "role"]).pnl.sum().unstack(fill_value=0.0)
    rows = []
    for r in pm.itertuples():
        tp = OUT / "tapes" / f"{r.cid}_tkw.parquet"
        if not tp.exists():
            continue
        d = pd.read_parquet(tp, columns=["timestamp", "price", "size", "outcomeIndex", "transactionHash"])
        d = d[(~d.transactionHash.isin(wtx)) & (d.timestamp >= r.gs)].sort_values("timestamp")
        p0 = np.where(d.outcomeIndex.to_numpy(int) == 0, d.price.to_numpy(float), 1 - d.price.to_numpy(float))
        if len(d):
            t = d.timestamp.to_numpy(float)
            grid = np.arange(t[0], t[-1] + 10, 10.0)
            j = np.searchsorted(t, grid, side="right") - 1
            path = p0[np.clip(j, 0, None)]
            tv = float(np.abs(np.diff(path)).sum())
            disp = float(path[-1] - path[0])
        else:
            tv = disp = 0.0
        rows.append({"cid": r.cid, "gs": r.gs, "pnl": r.pnl, "prints": len(d), "usd": float((d["size"] * d.price).sum()),
                     "tv": tv, "disp": disp, "margin": r.pairs * (1 - r.pair_cost) if np.isfinite(r.pair_cost) else 0.0,
                     "maker_leg": float(leg.loc[r.cid, "maker"]) if r.cid in leg.index and "maker" in leg else 0.0,
                     "taker_leg": float(leg.loc[r.cid, "taker"]) if r.cid in leg.index and "taker" in leg else 0.0})
    D = pd.DataFrame(rows).dropna(subset=["pnl"])
    ev = pd.read_parquet(OUT / "orders.parquet", columns=["cid", "event_slug"]).drop_duplicates("cid") if "event_slug" in pd.read_parquet(OUT / "orders.parquet").columns else None
    res = {}
    for sp, x in (("BUILD", D[D.gs < VAL0]), ("VALIDATE", D[D.gs >= VAL0])):
        out = {"markets": int(len(x)), "pnl_sum": round(float(x.pnl.sum()), 0)}
        for col in ("prints", "usd", "tv", "disp", "margin", "maker_leg", "taker_leg"):
            xx = x[col].to_numpy(float)
            yy = x.pnl.to_numpy(float)
            out[col] = {"pearson": round(float(pearsonr(xx, yy)[0]), 3), "spearman": round(float(spearmanr(xx, yy)[0]), 3)}
            if col != "prints":
                z = np.log1p(x.prints.to_numpy(float))
                out[col]["partial_pearson_given_prints"] = round(partial(yy, xx, z, "pearson"), 3)
                out[col]["partial_spearman_given_prints"] = round(partial(yy, xx, z, "spearman"), 3)
            if col in ("maker_leg", "taker_leg"):
                out[col]["sum"] = round(float(xx.sum()), 0)
        bs = []
        n = len(x)
        for _ in range(2000):
            ii = rng.integers(0, n, n)
            bs.append((pearsonr(x.prints.to_numpy(float)[ii], x.pnl.to_numpy(float)[ii])[0],
                       spearmanr(x.prints.to_numpy(float)[ii], x.pnl.to_numpy(float)[ii])[0]))
        bs = np.array(bs)
        out["prints"]["ci95_pearson"] = [round(float(v), 3) for v in np.percentile(bs[:, 0], [2.5, 97.5])]
        out["prints"]["ci95_spearman"] = [round(float(v), 3) for v in np.percentile(bs[:, 1], [2.5, 97.5])]
        res[sp] = out
    (RES / "outcome_baseline.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

"""Outcome target (assumptions panel X: the position path): an executable two-sided ladder replayed on the public taker
tape, per-market PnL vs the wallet's per-market settlement PnL.

Rule (point-in-time, strict fills): from gameStartTime, every REQ s, fair0 = last public print of outcome 0 known at
t - LAT (wallet transactions excluded from the tape entirely); rest BUY bids of SIZE shares on both outcomes at
floor_cent(fair - DELTA) - k cents, k = 0..L-1. A bid fills only on later taker prints that trade THROUGH it (taker SELL
of that outcome below the bid, or taker BUY of the other outcome above 1 - bid), up to SIZE per level per requote
window. Never sells; pairs are merged at 1 (equivalent to holding both to settlement); residual settles at the outcome.
Universe: CS2 match/map-winner markets; reported on the wallet's traded markets and on the union with the selection rule.
Parameters chosen on BUILD (max Pearson), reported on VALIDATE."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import H, OUT, RES, SPLIT, MAKER_START, TAPES, chain_fills  # noqa: E402

REQ, LAT, SIZE = 10, 2, 100.0


def replay(d, gs, pay0, delta, L):
    ts = d.timestamp.to_numpy().astype(float)
    oi = d.outcomeIndex.astype(int).to_numpy()
    side = d.side.to_numpy()
    pr = d.price.astype(float).to_numpy()
    sz = d["size"].astype(float).to_numpy()
    p0 = np.where(oi == 0, pr, 1 - pr)
    if len(ts) < 5:
        return 0.0, 0.0
    pnl, usd = 0.0, 0.0
    sh = np.zeros(2)
    cost = np.zeros(2)
    for t0 in np.arange(max(gs, ts[0]), ts[-1], REQ):
        k = np.searchsorted(ts, t0 - LAT, side="right") - 1
        if k < 0:
            continue
        lo, hi = np.searchsorted(ts, t0, side="right"), np.searchsorted(ts, t0 + REQ, side="right")
        if hi <= lo:
            continue
        for o, fair in ((0, p0[k]), (1, 1 - p0[k])):
            top = np.floor((fair - delta) * 100 + 1e-9) / 100
            for lv in range(L):
                q = round(top - 0.01 * lv, 2)
                if q < 0.01 or q > 0.99:
                    continue
                m = slice(lo, hi)
                thr = ((oi[m] == o) & (side[m] == "SELL") & (pr[m] < q - 1e-9)) | ((oi[m] != o) & (side[m] == "BUY") & (pr[m] > 1 - q + 1e-9))
                f = min(SIZE, float(sz[m][thr].sum()))
                if f <= 0:
                    continue
                sh[o] += f
                cost[o] += f * q
    pnl = sh[0] * pay0 + sh[1] * (1 - pay0) - cost.sum()
    return float(pnl), float(cost.sum())


def wallet_pnl():
    f = chain_fills()
    u = pd.read_parquet(OUT / "universe.parquet")
    pay = {}
    for cid, r in zip(u.cid, u.res_outcome_prices):
        try:
            pay[cid] = float(json.loads(r)[0])
        except Exception:
            pass
    f = f[f.cid.isin(pay)]
    f["pay"] = np.where(f.oi == 0, f.cid.map(pay), 1 - f.cid.map(pay))
    return (f.shares * f.pay - f.usdc).groupby(f.cid).sum(), pay


def main():
    wp, pay = wallet_pnl()
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[u.smt.isin(["moneyline", "child_moneyline"]) & (u.gs_ts >= MAKER_START) & (u.gs_ts < H) & u.cid.isin(pay)]
    ev = pd.read_parquet(OUT / "events_sel.parquet")[["event_slug", "y"]]
    sel = pd.read_parquet(OUT / "selection_scores.parquet") if (OUT / "selection_scores.parquet").exists() else None
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    traded = set(wp.index)
    keep = u[u.cid.isin(traded) | (u.event_slug.isin(set(sel[sel.selected].event_slug)) if sel is not None else False)]
    tapes = {}
    for cid in keep.cid:
        p = TAPES / f"{cid}_tkw.parquet"
        if p.exists():
            d = pd.read_parquet(p, columns=["timestamp", "price", "size", "side", "outcomeIndex", "transactionHash"])
            tapes[cid] = d[(~d.transactionHash.isin(wtx)) & (d.timestamp < H)].sort_values("timestamp")
    grid = [(dl, L) for dl in (0.0, 0.01, 0.02, 0.03) for L in (1, 3)]
    res = {"markets_traded": len(traded), "markets_union": len(keep)}
    rows = []
    for dl, L in grid:
        for cid, gs in zip(keep.cid, keep.gs_ts.astype(int)):
            if cid not in tapes:
                continue
            pnl, usd = replay(tapes[cid], gs, pay[cid], dl, L)
            rows.append({"cid": cid, "gs": gs, "delta": dl, "L": L, "rule_pnl": pnl, "rule_usd": usd, "wallet_pnl": float(wp.get(cid, 0.0)), "traded": cid in traded})
    x = pd.DataFrame(rows)
    x.to_parquet(OUT / "pnl_replay.parquet", index=False)
    out = []
    for (dl, L), s in x.groupby(["delta", "L"]):
        r = {"delta": dl, "L": L}
        for sp, q in (("BUILD", s[s.gs < SPLIT]), ("VALIDATE", s[s.gs >= SPLIT])):
            for scope, qq in (("traded", q[q.traded]), ("union", q)):
                if len(qq) < 5:
                    continue
                r[f"{sp}_{scope}_pearson"] = round(float(np.corrcoef(qq.rule_pnl, qq.wallet_pnl)[0, 1]), 3)
                r[f"{sp}_{scope}_spearman"] = round(float(qq.rule_pnl.rank().corr(qq.wallet_pnl.rank())), 3)
                r[f"{sp}_{scope}_rule_ret"] = round(float(qq.rule_pnl.sum() / max(qq.rule_usd.sum(), 1)), 4)
                r[f"{sp}_{scope}_n"] = len(qq)
        out.append(r)
    res["grid"] = out
    json.dump(res, open(RES / "results/pnl_replay.json", "w"), indent=1)
    print(pd.DataFrame(out).to_string())


if __name__ == "__main__":
    main()

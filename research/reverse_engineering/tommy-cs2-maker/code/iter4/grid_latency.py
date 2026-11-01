"""Iteration 4, X51 (assumptions iter3 P5): the old GRID taker regime as a natural experiment on the latency class of
the wallet's input.

Taker regime 10-01..10-15 (its orders were pre-signed, so the decision time is taken as block time - 2 s): every
in-play wallet TRADE (data-api activity), team bet on = the bought outcome (BUY) or the other outcome (SELL). Markets:
every non-GRID market it traded then, plus a random sample of GRID markets (seed 11). Public price path of that team
from the market's taker tape (data-api, taker_only; every tx with a wallet trade excluded), last print at
d + tau for tau in TAUS, relative to the print at d - 60 s (cents). Reference: the maker regime's taker orders of
16-22 Oct with the same clock convention (block time - 2 s) on the windowed tapes already on disk.
If its input were official-grade, the GRID path would be flat before d and jump after it, like the maker regime's;
if it is slower than official data, the GRID move comes before d.
Output: results/grid_latency.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
T1, T2 = 1791158400, 1792108800  # 10-01 .. 10-16 00:00 UTC
TAUS = (-30, -10, -5, -2, 0, 2, 5, 10, 30, 60)
N_GRID = 70


def meta():
    m = json.load(open(OUT / "markets_taker.json"))
    rows = []
    for cid, x in m.items():
        ev = (x.get("events") or [{}])[0]
        md = ev.get("eventMetadata") or {}
        if isinstance(md, str):
            try:
                md = json.loads(md)
            except ValueError:
                md = {}
        gs = x.get("gameStartTime")
        try:
            g = pd.Timestamp(str(gs).replace("+00", "+00:00") if str(gs).endswith("+00") else str(gs)).timestamp()
        except Exception:  # noqa: BLE001
            g = np.nan
        rows.append({"cid": cid, "grid": md.get("gridSeriesId") is not None, "gs": g, "smt": x.get("sportsMarketType")})
    return pd.DataFrame(rows).set_index("cid")


def path_stats(rows):
    x = pd.DataFrame(rows)
    out = {"n": int(len(x))}
    for t in TAUS:
        v = x[f"d{t}"].dropna()
        out[str(t)] = {"mean_c": round(float(v.mean()), 2), "median_c": round(float(v.median()), 2), "n": int(len(v))} if len(v) else None
    return out


def paths(trades, tapes, own_tx):
    rows = []
    for r in trades.itertuples():
        d = tapes.get(r.cid)
        if d is None:
            continue
        ts, p0 = d
        dec = r.ts - 2.0
        k0 = np.searchsorted(ts, dec - 60, side="right") - 1
        if k0 < 0:
            continue
        team0 = (r.oi == 0) == (r.side == "BUY")
        ref = p0[k0] if team0 else 1 - p0[k0]
        rec = {}
        for t in TAUS:
            k = np.searchsorted(ts, dec + t, side="right") - 1
            v = p0[k] if team0 else 1 - p0[k]
            rec[f"d{t}"] = (v - ref) * 100
        rows.append(rec)
    return rows


def main():
    a = pd.read_parquet(OUT / "activity_taker.parquet", columns=["timestamp", "conditionId", "type", "side", "outcomeIndex", "transactionHash"])
    a = a[(a.type == "TRADE")]
    a["ts"] = a.timestamp.astype(float)
    a = a[(a.ts >= T1) & (a.ts < T2)].rename(columns={"conditionId": "cid", "outcomeIndex": "oi"})
    a["oi"] = a.oi.astype(int)
    mt = meta()
    a = a.join(mt, on="cid")
    a = a[a.gs.notna() & (a.ts >= a.gs)]  # in play
    own_tx = set(a.transactionHash)
    ng = sorted(set(a[~a.grid.fillna(True)].cid))
    gr = sorted(set(a[a.grid.fillna(False)].cid))
    rng = np.random.default_rng(11)
    gr = list(rng.choice(gr, min(N_GRID, len(gr)), replace=False))
    pm = PolymarketData()
    tapes = {}
    for cid in ng + gr:
        g = a[a.cid == cid]
        rows, _, _ = pm.market_trades(cid, start=int(g.ts.min()) - 900, end=int(g.ts.max()) + 900, taker_only=True, max_rows=60_000)
        if not rows:
            continue
        d = pd.DataFrame(rows)
        d = d[~d.transactionHash.isin(own_tx)].sort_values("timestamp", kind="stable")
        if len(d) < 5:
            continue
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        tapes[cid] = (d.timestamp.to_numpy(float), p0)
    res = {"taker_regime_markets": {"non_grid": len(ng), "grid_sampled": len(gr), "with_tape": len(tapes)}}
    res["taker_regime_GRID"] = path_stats(paths(a[a.cid.isin(gr)], tapes, own_tx))
    res["taker_regime_nonGRID"] = path_stats(paths(a[a.cid.isin(ng)], tapes, own_tx))
    # maker regime reference: its taker orders (BUY) 16-22 Oct at block time - 2 s on the windowed tapes on disk
    o = pd.read_parquet(OUT / "orders.parquet", columns=["role", "cid", "oi", "first_fill_ts", "gs_ts"])
    o = o[(o.role == "taker") & o.first_fill_ts.notna()].copy()
    o["ts"] = o.first_fill_ts.astype(float)
    o["side"] = "BUY"
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "maker"])
    own2 = set(cd[cd.maker == WALLET].tx)
    t2 = {}
    for cid in o.cid.unique():
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if p.exists():
            d = pd.read_parquet(p, columns=["transactionHash", "timestamp", "outcomeIndex", "price"])
            d = d[~d.transactionHash.isin(own2)].sort_values("timestamp", kind="stable")
            if len(d) >= 5:
                p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
                t2[cid] = (d.timestamp.to_numpy(float), p0)
    res["maker_regime_takes_nonGRID"] = path_stats(paths(o, t2, own2))
    json.dump(res, open(RES / "grid_latency.json", "w"), indent=1)
    for k, v in res.items():
        if isinstance(v, dict) and "n" in v:
            print(k, v["n"], {t: (v[str(t)] or {}).get("mean_c") for t in TAUS})
        else:
            print(k, v)


if __name__ == "__main__":
    main()

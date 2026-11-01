"""Taker tapes (window gs-1h .. gs+4h10m) of CS2 match/map-winner markets of the maker-regime leagues with game start
2026-09-26 .. 10-16 (before the wallet's switch), plus a 1-in-4 sample of GRID events of the same days (control).
Question: was the informed pack already in these leagues before the wallet switched (C4b / X1, R5, R8)?"""
from __future__ import annotations
import sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
OUT = ROOT / ".cache/re/tommy-cs2-maker"; TAPES = OUT / "tapes"
COLS = ["proxyWallet", "side", "asset", "outcomeIndex", "size", "price", "timestamp", "transactionHash"]
WL = ["DraculaN", "1win Private Club", "1win", "Stake Pulse", "Stake Ranked", "PGL", "Circuit X", "NODWIN Clutch Series", "CIS LAN Championship"]

def main(d0=1790380800, d1=1792108800):
    pm = PolymarketData(); u = pd.read_parquet(OUT / "universe.parquet"); em = pd.read_parquet(OUT / "events_meta.parquet")
    u = u.merge(em[["event_slug", "grid_series_id"]], on="event_slug", how="left")
    u = u[u.smt.isin(["moneyline", "child_moneyline"]) & (u.gs_ts >= d0) & (u.gs_ts < d1)]
    wl = u[u.league.isin(WL) & u.grid_series_id.isna()]
    gr = u[u.grid_series_id.notna()]; gev = sorted(gr.event_slug.unique())[::4]; gr = gr[gr.event_slug.isin(gev)]
    sel = pd.concat([wl, gr]).drop_duplicates("cid"); t0 = time.time(); print("markets", len(sel), "wl", len(wl), "grid", len(gr), flush=True)
    for i, (cid, gs) in enumerate(zip(sel.cid, sel.gs_ts.astype("int64"))):
        path = TAPES / f"{cid}_tkw.parquet"
        if path.exists(): continue
        start, end = int(gs) - 3600, int(gs) + 4 * 3600 + 600
        try: rows, _, cov = pm.market_trades(cid, start=start, end=end, taker_only=True, max_rows=200_000)
        except Exception as e: print("ERR", cid, str(e)[:100], flush=True); continue
        df = pd.DataFrame(rows)
        if df.empty: df = pd.DataFrame(columns=COLS)
        df = df[[c for c in COLS if c in df.columns]]
        df.to_parquet(path, index=False)
        if i % 25 == 0: print(i, len(df), f"{time.time()-t0:.0f}s", flush=True)
    print("done", f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()

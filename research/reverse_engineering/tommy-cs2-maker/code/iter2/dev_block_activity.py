"""Wallet activity in development blocks after T0 (only units whose gameStartTime is in a development block >= T0;
every other row is dropped before anything is counted). Output: .cache/re/tommy-cs2-maker/activity_devblocks.parquet"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import sealed  # noqa: E402
KEY = "tommy-cs2-maker"; WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"; T0 = 1793404800
OUT = ROOT / ".cache/re/tommy-cs2-maker"

def main():
    pm = PolymarketData(); now = int(time.time())
    rows, src, cov = pm.activity(WALLET, start=T0, end=now)
    df = pd.DataFrame(rows)
    if df.empty:
        print("no rows"); return
    cids = sorted(set(df.conditionId.dropna()))
    mk, _ = pm.markets_by_condition(cids)
    gs = {}
    for cid, x in mk.items():
        try: gs[cid] = pd.Timestamp(str(x.get("gameStartTime")).replace("+00", "+00:00") if str(x.get("gameStartTime")).endswith("+00") else x.get("gameStartTime")).timestamp()
        except Exception: gs[cid] = None
    df["gs"] = df.conditionId.map(gs)
    keep = df[df.gs.notna() & (df.gs >= T0) & df.gs.map(lambda g: g is not None and g == g and not sealed.is_sealed(int(g), KEY))].copy()
    for c in keep.columns:
        if keep[c].dtype == object: keep[c] = keep[c].astype(str)
    keep.to_parquet(OUT / "activity_devblocks.parquet", index=False)
    print("kept dev-unit rows", len(keep), "markets", keep.conditionId.nunique(), keep.type.value_counts().to_dict() if len(keep) else {})
    if len(keep): print(keep.groupby(["eventSlug"]).agg(n=("type", "size"), gs=("gs", "min")).to_string())

if __name__ == "__main__":
    main()

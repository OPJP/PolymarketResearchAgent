"""X176 step 4 (mechanics panel iter-12 P1): the operator's other accounts over time (activity before H only).
Daily TRADE counts of the wallet and the three same-process accounts; for 0x7d67f01d (the BUY-only + MERGE account
active since June) the CS2 events it traded split by GRID flag (listing field), the market types, its sides and sizes
per title and month; the wallet's own taker-regime events (until 10-15) on the same split.
Output: results/sibling_history.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
H = 1792713600
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
ACC = ["0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14", "0x52661b8e13158f23d94a9e8302ab0295704c22ac",
       "0x671190333b064b0899b4ac1aec86744b1f82885b"]


def main():
    pm = PolymarketData()
    ev = pd.read_parquet(OUT / "events_meta.parquet", columns=["event_slug", "grid_series_id", "league", "league_tier"])
    grid = dict(zip(ev.event_slug, ev.grid_series_id.notna() & (ev.grid_series_id.astype(str) != "")))
    out = {"daily": {}, "accounts": {}}
    acts = {}
    for a in [W] + ACC:
        if a == W:
            df = pd.read_parquet(OUT / "activity_dev.parquet")
            if "eventSlug" not in df:
                df = pd.DataFrame()
            rows_t, *_ = pm.activity(W, 1791158400, H - 1)  # 10-05 .. H
            df = pd.DataFrame(rows_t)
        else:
            rows, *_ = pm.activity(a, 1781000000, H - 1)
            df = pd.DataFrame(rows)
        df = df[df.timestamp < H]
        acts[a] = df
        tr = df[df["type"] == "TRADE"]
        d = pd.to_datetime(tr.timestamp, unit="s").dt.strftime("%m-%d")
        out["daily"][a[:10]] = {k: int(v) for k, v in tr.groupby(d).size().items() if k >= "10-01"}
    for a in ACC + [W]:
        df = acts[a]
        tr = df[df["type"] == "TRADE"].copy()
        tr["evs"] = tr.eventSlug.astype(str)
        tr["title"] = tr.evs.str.split("-").str[0]
        tr["month"] = pd.to_datetime(tr.timestamp, unit="s").dt.strftime("%m")
        tr["day"] = pd.to_datetime(tr.timestamp, unit="s").dt.strftime("%m-%d")
        cs = tr[tr.title == "cs2"].copy()
        cs["grid"] = cs.evs.map(grid)
        rec = {"cs2_events_by_grid_flag_oct": cs[cs.month == "10"].drop_duplicates("evs").grid.value_counts(dropna=False).to_dict(),
               "cs2_trades_by_grid_flag_oct_before_1016": cs[(cs.month == "10") & (cs.day < "10-16")].grid.value_counts(dropna=False).to_dict(),
               "cs2_trades_by_grid_flag_1016_1022": cs[(cs.day >= "10-16")].grid.value_counts(dropna=False).to_dict(),
               "sides_by_month": tr.groupby("month").side.value_counts().unstack(fill_value=0).to_dict(orient="index"),
               "size_mode_by_title_month": {f"{k[0]}_{k[1]}": float(v) for k, v in tr.groupby(["title", "month"])["size"].agg(lambda s: s.astype(float).round(0).mode().iloc[0]).items()},
               "merges_by_month": df[df["type"] == "MERGE"].groupby(pd.to_datetime(df[df["type"] == "MERGE"].timestamp, unit="s").dt.strftime("%m")).size().to_dict(),
               "name": str(df["name"].dropna().iloc[0]) if "name" in df and df["name"].notna().any() else None,
               "pseudonym": str(df["pseudonym"].dropna().iloc[0]) if "pseudonym" in df and df["pseudonym"].notna().any() else None}
        out["accounts"][a] = rec
    # shared events between the wallet and 0x7d67f01d, by day
    wt = acts[W][acts[W]["type"] == "TRADE"]
    st = acts[ACC[0]][acts[ACC[0]]["type"] == "TRADE"]
    wd = wt.groupby(pd.to_datetime(wt.timestamp, unit="s").dt.strftime("%m-%d")).eventSlug.agg(lambda s: set(s.astype(str)))
    sd = st.groupby(pd.to_datetime(st.timestamp, unit="s").dt.strftime("%m-%d")).eventSlug.agg(lambda s: set(s.astype(str)))
    out["shared_events_by_day_wallet_vs_7d67"] = {d: [len(wd.get(d, set())), len(sd.get(d, set())), len(wd.get(d, set()) & sd.get(d, set()))]
                                                  for d in sorted(set(wd.index) | set(sd.index)) if d >= "10-05"}
    (RES / "sibling_history.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=0, default=str)[:6000])


if __name__ == "__main__":
    main()

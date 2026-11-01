"""X187 (self-proposed, iteration 13): does the frozen selection rule describe the operator's maker selection on its
earlier account, out of sample? Universe: every CS2 event (Gamma series 10310, listing fields from events_meta) whose
first game start lies in 10-01..10-15 (before the wallet's switch; never used to fit any rule). Label: 0x7d67f01d
('BACKTESTEOCARAIO1', the same process) traded the event (activity before H). Score: the frozen v4/v5 league component
s_lg from final_rule (exam constants: GRID -> 0, else the league's traded rate shrunk to the tier rate), which needs no
tape; AUC, and the GRID / non-GRID split. Also the wallet's own CS2 events in the same window (its GRID taker regime).
Output: results/sibling_selection.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import final_rule as F  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
A = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
T1, T2 = 1791158400, 1792540800  # 10-05 .. 10-21 is not it: use 10-01 .. 10-16
T1, T2 = 1790812800, 1792108800  # 2026-10-01 00:00 .. 2026-10-16 00:00


def main():
    em = pd.read_parquet(OUT / "events_meta.parquet")
    em = em[(em.gs_min >= T1) & (em.gs_min < T2) & em.event_slug.str.startswith("cs2-")].copy()
    em["grid"] = em.grid_series_id.notna() & (em.grid_series_id.astype(str) != "") & (em.grid_series_id.astype(str) != "None")
    C = dict(F.CALL[F.CONSTANTS])
    tier = em.league_tier.astype(str).str.replace(r"\.0$", "", regex=True)
    tr = tier.map(C["tier_rate"]).fillna(C["prior"]).astype(float)
    s = em.league.map(C["league_sum"]).fillna(0).astype(float)
    n = em.league.map(C["league_n"]).fillna(0).astype(float)
    em["s_lg"] = np.where(em.grid.to_numpy(), 0.0, ((s + C["k"] * tr) / (n + C["k"])).to_numpy())
    em["league_seen"] = em.league.isin(C["league_n"].keys())
    pm = PolymarketData()
    out = {"events": int(len(em)), "grid_events": int(em.grid.sum())}
    for name, acc in (("sibling_7d67", A), ("wallet", W)):
        rows, *_ = pm.activity(acc, T1, T2 - 1)
        df = pd.DataFrame(rows)
        evs = set(df.loc[df["type"] == "TRADE", "eventSlug"].astype(str)) if len(df) else set()
        y = em.event_slug.isin(evs).astype(int).to_numpy()
        rec = {"traded": int(y.sum()), "traded_grid": int(y[em.grid.to_numpy()].sum()), "traded_nongrid": int(y[~em.grid.to_numpy()].sum())}
        if 0 < y.sum() < len(y):
            rec["auc_s_lg"] = round(F._auc(em.s_lg.to_numpy(), y), 4)
            ng = ~em.grid.to_numpy()
            if 0 < y[ng].sum() < ng.sum():
                rec["auc_s_lg_nongrid_only"] = round(F._auc(em.s_lg.to_numpy()[ng], y[ng]), 4)
                seen = ng & em.league_seen.to_numpy()
                if 0 < y[seen].sum() < seen.sum():
                    rec["auc_s_lg_nongrid_seen_leagues"] = round(F._auc(em.s_lg.to_numpy()[seen], y[seen]), 4)
                rec["nongrid_events"] = int(ng.sum())
                rec["nongrid_seen_league_events"] = int(seen.sum())
                rec["traded_rate_nongrid_seen_vs_unseen"] = [round(float(y[seen].mean()), 3) if seen.any() else None,
                                                             round(float(y[ng & ~em.league_seen.to_numpy()].mean()), 3) if (ng & ~em.league_seen.to_numpy()).any() else None]
        out[name] = rec
    (RES / "sibling_selection.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

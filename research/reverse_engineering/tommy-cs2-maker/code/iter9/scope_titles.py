"""Iteration 9, X130 (assumptions panel iter8 P4): scope insurance. (1) The wallet's TRADE rows in development data by
title (event slug prefix): 16-22 Oct (activity_dev) and the cached 10-31 development-block rows. (2) Group P members'
public activity (data-api, development dates 16-22 Oct only) by title: does Feed P's subscriber set trade LoL /
Valorant / other titles? Output: results/scope_titles.json"""
import json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
def title(s):
    s = str(s or "")
    return s.split("-")[0] if "-" in s else (s or "unknown")
res = {}
for nm, f in (("wallet_16_22", "activity_dev.parquet"), ("wallet_devblocks", "activity_devblocks.parquet")):
    a = pd.read_parquet(OUT / f)
    a = a[a["type"] == "TRADE"]
    col = "eventSlug" if "eventSlug" in a else "slug"
    res[nm] = {k: int(v) for k, v in a[col].map(title).value_counts().items()}
members = json.load(open(RES / "selection_groupP.json"))["members"]
pm = PolymarketData()
res["group_P_16_22"] = {}
for m in members:
    rows, _, _ = pm.activity(m, start=1792108800, end=1792713599)
    a = pd.DataFrame(rows)
    if a.empty:
        res["group_P_16_22"][m] = {}
        continue
    a = a[a["type"] == "TRADE"]
    col = "eventSlug" if "eventSlug" in a else "slug"
    res["group_P_16_22"][m] = {k: int(v) for k, v in a[col].map(title).value_counts().head(8).items()}
print(json.dumps(res, indent=1))
json.dump(res, open(RES / "scope_titles.json", "w"), indent=1)

"""E5 (information dimensions), hourly screen: GDELT DOC 2.0 article counts for "counter-strike" (timelinevolraw, hourly,
16-22 Oct, fetched once and cached in iter16/gdelt_cs_1016_1022.json) against the wallet's hourly V-change decisions and
its maker orders, with its in-play event count per hour as the activity control (Spearman, partial by rank regression).
Also: the hours with the largest decision residual (decisions given in-play activity) and their article counts.
A news input could at most steer selection / hour-level activity; it cannot carry the sub-second timing.
Output: results/e5_gdelt_hourly.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SP = Path(r"C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/m14/dark_split.parquet")
g = json.load(open(OUT / "iter16/gdelt_cs_1016_1022.json"))
ser = g["timeline"][0]["data"]
G = pd.DataFrame({"h": [pd.Timestamp(x["date"]).timestamp() for x in ser], "art": [x["value"] for x in ser]})
d = pd.read_parquet(SP)
d["h"] = (d.t / 1000 // 3600) * 3600
o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "event", "gs_ts", "role"])
o = o[o.role == "maker"]
o["h"] = (o.sign_ms / 1000 // 3600) * 3600
dec = d.groupby("h").size().rename("dec")
mo = o.groupby("h").size().rename("orders")
ev = o.groupby("h").event.nunique().rename("events")
X = G.set_index("h").join([dec, mo, ev]).fillna(0)
X = X[(X.index >= 1792108800) & (X.index < 1792713600)]
out = {"hours": int(len(X)), "articles_total": int(X.art.sum()), "articles_hour_quantiles": [float(q) for q in np.percentile(X.art, [50, 90, 99])]}
for col in ("dec", "orders", "events"):
    r = stats.spearmanr(X.art, X[col])
    out[f"spearman_art_{col}"] = [round(float(r.correlation), 3), round(float(r.pvalue), 4)]
# partial: residualize ranks on in-play events and hour of day
R = X.rank()
hod = pd.get_dummies(((X.index.values % 86400) // 3600).astype(int), prefix="h", drop_first=True).astype(float).values
Z = np.c_[np.ones(len(X)), R.events.values, hod]
def res(y):
    return y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]
pr = stats.pearsonr(res(R.art.values.astype(float)), res(R.dec.values.astype(float)))
out["partial_rank_corr_art_dec_given_events_hod"] = [round(float(pr[0]), 3), round(float(pr[1]), 4)]
act = X[X.events > 0]
if len(act) > 10:
    rr = stats.spearmanr(act.art, act.dec / act.events)
    out["active_hours_spearman_art_vs_decisions_per_event"] = [round(float(rr.correlation), 3), round(float(rr.pvalue), 4), int(len(act))]
(RES / "e5_gdelt_hourly.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

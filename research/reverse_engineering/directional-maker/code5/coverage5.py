"""Q1 (panel X20): coverage of fills and absolute PnL by market family, STUDY case by case, VALIDATE aggregate.

Per market: cash-flow PnL = SELL + MERGE + REDEEM - BUY - SPLIT (redemptions arrive ~90 s after the end; lot activity
runs to 2026-10-30 23:59). Unit time = start ts from the slug (updown-<h>-<ts>) or the first trade (dated slugs).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache" / "re" / "directional-maker"
OUT = ROOT / "research" / "reverse_engineering" / "directional-maker" / "results"
STUDY = (1792713600, 1793059200)
VALID = (1793059200, 1793404800)


def family(slug):
    s = slug or ""
    m = re.match(r"^([a-z]+)-updown-(5m|15m|4h)-\d+$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^([a-z]+)-up-or-down-on-", s)
    if m:
        return f"{m.group(1)}-daily"
    m = re.match(r"^([a-z]+)-up-or-down-", s)
    if m:
        return f"{m.group(1)}-hourly"
    return "other"


rows = []
for w in ("bosona", "almach", "momoney"):
    a = pd.read_parquet(C / "exam" / f"activity_{w}.parquet")
    a["w"] = w
    rows.append(a)
a = pd.concat(rows, ignore_index=True)
a["fam"] = a.slug.map(family)
a["ts_slug"] = pd.to_numeric(a.slug.str.extract(r"-(\d{9,})$")[0], errors="coerce")
first_trade = a[a.type == "TRADE"].groupby(["w", "conditionId"]).timestamp.min()
a = a.join(first_trade.rename("t_first"), on=["w", "conditionId"])
a["unit_t"] = a.ts_slug.fillna(a.t_first)
sign = np.select([a.type.eq("TRADE") & a.side.eq("BUY"), a.type.eq("TRADE") & a.side.eq("SELL"), a.type.isin(["MERGE", "REDEEM"]),
                  a.type.eq("SPLIT")], [-1.0, 1.0, 1.0, -1.0], 0.0)
a["cf"] = sign * a.usdcSize.astype(float)
a["is_fill"] = a.type.eq("TRADE")
mk = a[a.conditionId.notna() & (a.conditionId != "")].groupby(["w", "conditionId"]).agg(
    fam=("fam", "first"), unit_t=("unit_t", "min"), pnl=("cf", "sum"), fills=("is_fill", "sum"),
    buy_usd=("usdcSize", lambda s: 0.0)).reset_index()
buy = a[a.type.eq("TRADE") & a.side.eq("BUY")].groupby(["w", "conditionId"]).usdcSize.sum().rename("buy_usd")
mk = mk.drop(columns="buy_usd").join(buy, on=["w", "conditionId"])
mk = mk[mk.fills > 0]

res = {}
for name, (s0, s1) in (("study", STUDY), ("validate", VALID)):
    m = mk[(mk.unit_t >= s0) & (mk.unit_t < s1)]
    out = {}
    for who, g in list(m.groupby("w")) + [("pooled", m)]:
        fam = g.groupby("fam").agg(fills=("fills", "sum"), abs_pnl=("pnl", lambda x: x.abs().sum()), pnl=("pnl", "sum"),
                                   buy=("buy_usd", "sum"), markets=("pnl", "size"))
        fam["fill_share"] = fam.fills / fam.fills.sum()
        fam["abs_pnl_share"] = fam.abs_pnl / fam.abs_pnl.sum()
        fam["ret"] = fam.pnl / fam.buy
        fam = fam.sort_values("fills", ascending=False)
        cum = fam[["fill_share", "abs_pnl_share"]].cumsum()
        out[who] = {"by_family": fam.round(4).head(12).to_dict("index"),
                    "cum_top": cum.round(4).head(8).to_dict("index")}
    res[name] = out
    p = out["pooled"]["by_family"]
    print(name, "pooled:")
    for f, v in list(p.items())[:10]:
        print(f"  {f:14s} fills {v['fills']:6.0f} ({v['fill_share']:.3f})  absPnL {v['abs_pnl']:9.0f} ({v['abs_pnl_share']:.3f})  "
              f"PnL {v['pnl']:9.0f} ret {v['ret']:+.3f} mk {v['markets']:.0f}")
    print("  cum:", {k: (v['fill_share'], v['abs_pnl_share']) for k, v in out['pooled']['cum_top'].items()})
(OUT / "iter5_coverage.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")

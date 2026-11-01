"""X142 follow-up: the cluster's withdrawal time (seconds left at its last maker BUY fill per window) by day, against the
market's last clean taker print, over the switch sample (07-31..08-20), the stable sample (09-11..10-11) and the October
BUILD days (10-12..22, same hours). History rows: it12/hist_btc.parquet + activity_*.parquet."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
h = pd.read_parquet(C / "it12/hist_btc.parquet", columns=["timestamp", "type", "side", "slug", "price", "size"])
h = h[(h.type == "TRADE") & (h.side == "BUY") & h.slug.str.startswith("btc-updown-5m-")]
rows = [h[["timestamp", "slug"]]]
for nm in ("almach", "bosona", "momoney"):
    a = pd.read_parquet(C / f"activity_{nm}.parquet", columns=["timestamp", "type", "side", "slug"])
    a = a[(a.type == "TRADE") & (a.side == "BUY") & a.slug.astype(str).str.startswith("btc-updown-5m-") & (a.timestamp > 1791417542)]
    rows.append(a[["timestamp", "slug"]])
A = pd.concat(rows)
A["st"] = A.slug.str.rsplit("-", n=1).str[1].astype(np.int64)
A = A[(A.st % 86400 // 3600).isin([2, 8, 14, 20])]
last = A.groupby("st").timestamp.max()
left = (last.index.to_numpy() + 300 - last.to_numpy())
L = pd.DataFrame({"st": last.index, "left": left})
L["day"] = pd.to_datetime(L.st // 86400 * 86400, unit="s").dt.strftime("%m-%d")
L = L[(L.st >= 1785456000) & (L.st < 1792713600)]
out = {"by_day": {d: [int(len(g)), float(g.left.median()), float((g.left >= 60).mean())] for d, g in L.groupby("day")}}
for nm, a_, b_ in (("spot 07-31..08-06", 1785456000, 1786060800), ("twap30 08-07..13", 1786060800, 1786665600), ("twap60 08-14..20", 1786665600, 1787270400),
                   ("twap60 09-11..10-11", 1789084800, 1791763200), ("twap60 10-12..22", 1791763200, 1792713600)):
    g = L[(L.st >= a_) & (L.st < b_)]
    out[nm] = {"windows": int(len(g)), "median_left": float(g.left.median()), "q25": float(g.left.quantile(0.25)), "q75": float(g.left.quantile(0.75)),
               "share_left_ge_60": float((g.left >= 60).mean()), "share_left_ge_90": float((g.left >= 90).mean())}
print(json.dumps({k: v for k, v in out.items() if k != "by_day"}, indent=1))
for d, v in out["by_day"].items():
    if d <= "08-21" or d >= "10-10":
        print(d, v)
(HERE.parent / "results/iter13_withdraw_time.json").write_text(json.dumps(out, indent=1))

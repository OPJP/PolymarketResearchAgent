"""Iteration 14 (X161 input): side statistics of the cluster's BUY trades per crypto family (development folds; VALIDATE
aggregate). Favourite = bought at a price > 0.5. Reported per fold for the families that carry the weekend blocks."""
import json, re
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]; C = ROOT / ".cache/re/directional-maker"
parts = []
for n in ("bosona", "almach", "momoney"):
    for p in (C / f"activity_{n}.parquet", C / "exam" / f"activity_{n}.parquet"):
        parts.append(pd.read_parquet(p, columns=["timestamp", "type", "slug", "side", "size", "price", "usdcSize", "transactionHash", "asset"]))
D = pd.concat(parts, ignore_index=True)
D = D[(D.type == "TRADE") & (D.side == "BUY")].drop_duplicates(subset=["transactionHash", "asset", "size", "price", "timestamp"])
def fam(s):
    s = str(s); m = re.match(r"^(btc|eth|sol|xrp|bnb|doge|hype)-updown-(5m|15m|4h)-", s)
    if m: return m.group(1) + "_" + m.group(2)
    for k, a_ in (("bitcoin", "btc"), ("ethereum", "eth"), ("solana", "sol"), ("xrp", "xrp"), ("bnb", "bnb"), ("dogecoin", "doge"), ("hyperliquid", "hype")):
        if s.startswith(k + "-up-or-down-on-"): return a_ + "_daily"
        if s.startswith(k + "-up-or-down-"): return a_ + "_hourly"
    return "other"
D["fam"] = D.slug.map(fam)
dow = pd.to_datetime(D.timestamp - 4 * 3600, unit="s").dt.dayofweek
D["wkend"] = dow.isin([5, 6]) | ((dow == 4) & (pd.to_datetime(D.timestamp - 4 * 3600, unit="s").dt.hour >= 18))
out = {}
for fo, (a, b) in (("build", (1791417600, 1792713600)), ("study", (1792713600, 1793059200)), ("validate_agg", (1793059200, 1793404800))):
    g = D[(D.timestamp >= a) & (D.timestamp < b)]
    r = {}
    for f, gg in g.groupby("fam"):
        if gg.usdcSize.sum() < 2000: continue
        r[f] = {"buys": int(len(gg)), "usd": round(float(gg.usdcSize.sum())), "fav_share": round(float((gg.price > 0.5).mean()), 3),
                "fav_share_usd": round(float(gg.usdcSize[gg.price > 0.5].sum() / gg.usdcSize.sum()), 3),
                "weekend_fav_share": round(float((gg[gg.wkend].price > 0.5).mean()), 3) if gg.wkend.any() else None,
                "median_price": round(float(gg.price.median()), 3), "schedule_size_share": round(float(gg["size"].round(0).isin([12, 62, 100, 250, 500, 1000]).mean()), 3)}
    out[fo] = dict(sorted(r.items(), key=lambda kv: -kv[1]["usd"]))
print(json.dumps(out, indent=0)[:4000])
(Path(__file__).resolve().parent.parent / "results/iter14_family_side.json").write_text(json.dumps(out, indent=1))

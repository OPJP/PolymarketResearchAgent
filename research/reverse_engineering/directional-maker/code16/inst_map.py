"""iteration 16, T1 = X177 (assumptions P1 + mechanics P2): instance-module map from activity.
Per 15-min slot: BTC 5m + 15m BUY fills per wallet by price band (deep <= 0.10 or >= 0.90; mid 0.10-0.90).
Split := one wallet holds >= 0.80 of the mid-band fills of a slot with >= 20 of them (pre-registered 09:07 UTC).
Folds: BUILD 10-08..22, STUDY 10-23..26, VALIDATE 10-27..30 (aggregate only), development blocks after T0.
Units in sealed blocks are dropped by window start (sealed.is_sealed)."""
import json, re, sys, time
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools")); import sealed
KEY = "directional-maker"; C = ROOT / ".cache/re/directional-maker"
WALLETS = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
T0 = 1793404800


def load():
    fr = []
    for src in ("", "exam/"):
        for n in WALLETS:
            d = pd.read_parquet(C / f"{src}activity_{n}.parquet", columns=None)
            d["wallet"] = n; fr.append(d)
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData(); now = int(time.time()) - 60
    for a, b in sealed.intervals(KEY, T0, now, sealed=False):
        for n, w in WALLETS.items():
            f = C / f"act15_{n}_{a}_{b}.parquet"
            if f.exists() and b < now - 600:
                d = pd.read_parquet(f)
            else:
                rows, _, _ = pm.activity(w, start=a, end=b - 1); d = pd.DataFrame(rows)
                if len(d): d = d[(d.timestamp >= a) & (d.timestamp < b)]
                if b < now - 600: d.to_parquet(f, index=False)
            if len(d):
                d = d[[c for c in fr[0].columns if c in d.columns and c != "wallet"]].copy(); d["wallet"] = n; fr.append(d)
    a = pd.concat(fr, ignore_index=True)
    a = a[(a.type == "TRADE")].drop_duplicates(["transactionHash", "asset", "wallet", "size", "timestamp"])
    return a


a = load()
m = a.slug.astype(str).str.extract(r"^btc-updown-(5m|15m)-(\d+)$")
a = a[m[0].notna()].copy(); a["fam"] = m[0][m[0].notna()]; a["st"] = m[1][m[0].notna()].astype(int)
a = a[a.side == "BUY"]
a = a[~a.st.map(lambda s: sealed.is_sealed(int(s), KEY))]
a = a[~a.timestamp.map(lambda t: sealed.is_sealed(int(t), KEY))]
a["band"] = np.where((a.price <= 0.10) | (a.price >= 0.90), "deep", "mid")
a["slot"] = (a.timestamp // 900) * 900
ts = a.timestamp
fold = np.select([ts < 1791417600, ts < 1792713600, ts < 1793059200, ts < T0], ["pre", "BUILD", "STUDY", "VALIDATE"], "dev")
a["fold"] = fold
a = a[a.fold != "pre"]
mid = a[a.band == "mid"]
g = mid.groupby(["fold", "slot", "wallet"]).size().unstack(fill_value=0)
for n in WALLETS:
    if n not in g.columns: g[n] = 0
g["n"] = g[list(WALLETS)].sum(axis=1); g["top"] = g[list(WALLETS)].max(axis=1) / g.n.clip(lower=1)
g["topw"] = g[list(WALLETS)].idxmax(axis=1)
g = g[g.n >= 20]; g["split"] = g.top >= 0.80
out = {"rule": "split = one wallet >= 0.80 of mid-band BTC 5m+15m BUY fills in a 15-min slot with >= 20 of them"}
for f_, gg in g.groupby(level=0):
    out[f_] = {"slots": int(len(gg)), "split_slots": int(gg.split.sum()), "split_share": round(float(gg.split.mean()), 3),
               "median_top_share": round(float(gg.top.median()), 3),
               "split_by_wallet": gg[gg.split].topw.value_counts().to_dict()}
# development detail per slot (dev blocks only)
dv = g.loc["dev"] if "dev" in g.index.get_level_values(0) else None
if dv is not None:
    out["dev_slots"] = [{"slot": time.strftime("%m-%d %H:%M", time.gmtime(int(s))), "n": int(r.n), "bosona": int(r.bosona),
                         "almach": int(r.almach), "momoney": int(r.momoney), "split": bool(r.split)} for s, r in dv.iterrows()]
# deep-band share per wallet per fold (BTC 5m+15m BUY fills)
dd = a.groupby(["fold", "wallet"]).band.apply(lambda s: round(float((s == "deep").mean()), 3)).unstack()
out["deep_share"] = dd.to_dict()
cnt = a.groupby(["fold", "wallet"]).size().unstack(); out["fills"] = cnt.to_dict()
# dev blocks: per block and wallet, fills by band and first BTC fill time
dev = a[a.fold == "dev"].copy(); dev["blk"] = (dev.timestamp // 21600) * 21600
blk = {}
for (bk, w_), x in dev.groupby(["blk", "wallet"]):
    blk.setdefault(time.strftime("%m-%d %H", time.gmtime(int(bk))), {})[w_] = {
        "mid": int((x.band == "mid").sum()), "deep": int((x.band == "deep").sum()),
        "first": time.strftime("%H:%M:%S", time.gmtime(int(x.timestamp.min()))),
        "median_price": round(float(x.price.median()), 3)}
out["dev_blocks"] = blk
# hourly per wallet in dev blocks (mid / deep)
dev["hr"] = (dev.timestamp // 3600) * 3600
hh = dev.groupby(["hr", "wallet", "band"]).size().unstack(["wallet", "band"], fill_value=0)
out["dev_hourly"] = {time.strftime("%m-%d %H", time.gmtime(int(h))): {f"{w_}_{b_}": int(v) for (w_, b_), v in r.items()} for h, r in hh.iterrows()}
print(json.dumps({k: v for k, v in out.items() if k not in ("dev_slots",)}, indent=1)[:5000])
(HERE.parent / "results/iter16_inst_map.json").write_text(json.dumps(out, indent=1, default=int))

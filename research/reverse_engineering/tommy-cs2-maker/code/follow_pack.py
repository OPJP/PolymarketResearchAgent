"""Exploratory: can a public-data taker follow the informed pack? Trigger: the first print (in 60 s) of a pack
address buying team X in a market the wallet trades; entry = last public print of X at trigger + LAT s + 1c.
Pack = same-team co-movers of its taker orders (results/copy_check.json; identified on all development data, so
VALIDATE is not clean). Reports settlement edge and next-jump favour by split. Development data."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET, H, TAPES, SPLIT  # noqa: E402

PACK = ("0x93078b5d", "0x4ebc2722", "0xfe8a28be", "0x2529c68d", "0x72aaaaf9", "0x2005d16a")

def main():
    m = json.load(open(OUT / "markets_dev.json"))
    win = {}
    for cid, x in m.items():
        op = x.get("outcomePrices"); op = json.loads(op) if isinstance(op, str) else op
        v = [float(a) for a in op]; win[cid] = int(np.argmax(v)) if max(v) > 0.9 else -1
    o = pd.read_parquet(OUT / "orders.parquet")
    gs_of = o.groupby("cid").gs_ts.first().to_dict()
    res = {}
    for LAT in (1, 3, 10):
        rows = []
        for cid, gs in gs_of.items():
            p = TAPES / f"{cid}_tkw.parquet"
            if not p.exists() or win.get(cid, -1) < 0: continue
            d = pd.read_parquet(p); d = d[(d.timestamp < H) & (d.proxyWallet != WALLET)].sort_values("timestamp")
            if len(d) < 5: continue
            ts = d.timestamp.to_numpy(np.int64); oi = d.outcomeIndex.astype(int).to_numpy()
            p0 = np.where(oi == 0, d.price.astype(float), 1 - d.price.astype(float))
            ispack = d.proxyWallet.str[:10].isin(PACK).to_numpy()
            last = {0: -1e18, 1: -1e18}
            for k in np.where(ispack)[0]:
                team = oi[k]
                if ts[k] - last[team] < 60: last[team] = ts[k]; continue
                last[team] = ts[k]
                i2 = np.searchsorted(ts, ts[k] + LAT, side="right")
                e = (p0[i2 - 1] if team == 0 else 1 - p0[i2 - 1]) + 0.01
                if not (0.05 <= e <= 0.95): continue
                rows.append({"gs": gs, "edge": float(win[cid] == team) - e, "entry": e})
        x = pd.DataFrame(rows)
        res[f"LAT{LAT}"] = {sp: {"n": int(len(s)), "edge_pct": round(float(s.edge.sum() / s.entry.sum() * 100), 2)}
                            for sp, s in (("BUILD", x[x.gs < SPLIT]), ("VALIDATE", x[x.gs >= SPLIT]))}
    json.dump(res, open(RES / "results/follow_pack.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()

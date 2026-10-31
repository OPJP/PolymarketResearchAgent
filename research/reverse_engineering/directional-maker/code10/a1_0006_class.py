"""Iteration 10 (A1 class test on a fresh development block): region D by rung class on 10-31 00:00-06:00 UTC (no live
recording; block clock as in a1_0006.py, which reproduced the match-clock truth on 10-31 14:06-16:30). The calldata of every
cluster BTC 5m fill transaction of the block is fetched (publicnode via code4/calldata.py) for the filled orders' original
sizes. Prediction from the lot (written before this script ran): 500-class rungs follow Chainlink in region D (>= 0.9),
62/250 rungs do not (~0.5)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE.parent / "code4"))
sys.path.insert(0, str(HERE))
import final_rule as F  # noqa: E402
import cl_source  # noqa: E402
import calldata  # noqa: E402
import a1_0006 as B  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
CLU = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
       "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}


def main():
    act = B.fills()
    act["tx"] = act.transactionHash.str.lower()
    cache = C / "calldata" / "it10_0006_orders.parquet"
    if cache.exists():
        od = pd.read_parquet(cache)
    else:
        rows = []
        for h, tx in calldata.fetch_txs(list(dict.fromkeys(act.tx))):
            r = calldata.decode(tx["input"]) if tx else None
            if not r:
                continue
            for o in r.get("makers", []):
                if o["maker"].lower() in CLU and int(o["oside"]) == 0:
                    rows.append((h, CLU[o["maker"].lower()], str(o["token_id"]), round(int(o["taker_amount"]) / 1e6, 2)))
        od = pd.DataFrame(rows, columns=["tx", "wn", "token", "orig"])
        od.to_parquet(cache, index=False)
    om = od.drop_duplicates(["tx", "wn", "token"]).set_index(["tx", "wn", "token"]).orig
    act["wn"] = act.w.astype(str).str.lower().map(lambda a: CLU.get(a, a))
    act["orig"] = [om.get((t, w, str(a)), np.nan) for t, w, a in zip(act.tx, act.wn, act.asset)]
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    w = F._windows(B.A - 300, B.B + 300)
    w = w[(w.start_ts >= B.A) & (w.start_ts < B.B)]
    ptb = F._ptb(w)
    tk = F._tapes(w, pm, B.B + 600, local=False)
    ctx = set(F._txint(act.transactionHash.str.lower()))
    clean = tk[~tk.tx.isin(ctx)].copy()
    up = dict(zip(w.cid, w.up_token.astype(str)))
    clean["pup"] = np.where(clean.asset.astype(str) == clean.cid.astype(str).map(up), clean.price.astype(float), 1 - clean.price.astype(float))
    G = {k: (g.ts.to_numpy(), g.pup.to_numpy()) for k, g in clean.sort_values("ts", kind="stable").groupby("cid", observed=True)}
    mids = []
    for r in act.itertuples(index=False):
        g = G.get(r.conditionId)
        if g is None:
            mids.append(np.nan)
            continue
        j = np.searchsorted(g[0], int(r.timestamp) - 3, side="right") - 1
        mids.append(g[1][j] if j >= 0 and g[0][j] >= r.st - 60 else np.nan)
    act["mid_up"] = mids
    act["K"] = act.st.map(ptb)
    act["stamp"] = act.timestamp.astype(np.int64) - 4
    clv = cl_source.cl_values(act.stamp.unique(), fetch=False)
    act["cl"] = act.stamp.map(clv)
    act["is_up"] = (act.outcome == "Up").astype(int)
    h = act.dropna(subset=["cl", "K", "mid_up"]).copy()
    x = np.log(h.cl / h.K).to_numpy()
    m = h.mid_up.to_numpy()
    y = h.is_up.to_numpy() == 1
    D = ((x > 0) != (m > 0.5)) & (x != 0)
    hit = (x > 0) == y
    o = h.orig.fillna(-1)
    cls = np.select([o.isin([500, 1000, 2000]), (o == 62) | ((o - 61.99).abs() < 0.02), o.isin([250, 125]), o.isin([100, 12]), o < 0],
                    ["500", "62", "250", "100_12", "unjoined"], "other")
    hr = (h.timestamp.to_numpy() // 3600) % 24
    out = {"n": int(len(h)), "calldata_orders": int(len(od)), "class_mix": pd.Series(cls).value_counts().to_dict(),
           "region_D_by_class": {c: [int((D & (cls == c)).sum()), round(float(np.mean(hit[D & (cls == c)])), 3) if (D & (cls == c)).any() else None,
                                     int(h.st.to_numpy()[D & (cls == c)].size and pd.Series(h.st.to_numpy()[D & (cls == c)]).nunique())] for c in np.unique(cls)},
           "class_by_hour": {int(k): pd.Series(cls[hr == k]).value_counts().to_dict() for k in np.unique(hr)},
           "region_D_by_hour_class": {f"{int(k)}|{c}": [int((D & (hr == k) & (cls == c)).sum()), round(float(np.mean(hit[D & (hr == k) & (cls == c)])), 3)]
                                      for k in np.unique(hr) for c in np.unique(cls) if (D & (hr == k) & (cls == c)).any()}}
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_a1_0006_class.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

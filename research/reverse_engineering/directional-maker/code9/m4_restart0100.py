"""Iteration 9 (X82 positive control): the cluster's salt counters around the daily 01:00 UTC restart on 10-31
(development block 00-06): calldata of every cluster fill transaction in 00:40-01:20 UTC."""
import glob
import sys
from pathlib import Path
import httpx
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code4"))
import calldata as CD  # noqa: E402
C = HERE.parents[3] / ".cache/re/directional-maker"
W = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach", "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "mo-money"}
a, b = 1793408400, 1793411400
act = pd.read_parquet(C / "live_activity_1793404800_1793426400.parquet")
act = act[(act.type == "TRADE") & (act.timestamp >= a) & (act.timestamp < b)].copy()
act["tx"] = act.transactionHash.str.lower()
ts = act.groupby("tx").timestamp.min().to_dict(); slug = act.groupby("tx").slug.first().to_dict()
f = C / "calldata" / f"it9rs_{a}_{b}.parquet"
if f.exists():
    D = pd.read_parquet(f)
else:
    rows = []
    for h, tx in CD.fetch_txs(sorted(ts, key=ts.get), batch=25, pause=0.2, client=httpx.Client(timeout=30)):
        if tx is None:
            continue
        d = CD.decode(tx.get("input", ""))
        if d is None:
            continue
        for i, o in enumerate([d["taker"]] + d["makers"]):
            rows.append({"tx": h.lower(), "maker": str(o.get("maker", "")).lower(), "salt": str(o.get("salt")), "role": "taker" if i == 0 else "maker"})
    D = pd.DataFrame(rows)
    D.to_parquet(f)
D = D[D.maker.isin(W)].copy()
D["salt"] = pd.to_numeric(D.salt, errors="coerce"); D["ts"] = D.tx.map(ts); D["slug"] = D.tx.map(slug)
D = D.dropna(subset=["ts"]).sort_values("ts").drop_duplicates(["maker", "salt"])
for w, nm in W.items():
    g = D[D.maker == w]
    g = g.assign(t=pd.to_datetime(g.ts, unit="s").dt.strftime("%H:%M:%S"), fam=g.slug.str.replace(r"-\d{9,}$", "", regex=True).str[:16])
    # print only around resets: rows where salt drops, plus neighbours
    s = g.salt.to_numpy(); idx = set()
    for j in np.where(np.diff(s) < 0)[0]:
        idx |= {j - 1, j, j + 1, j + 2}
    print("==", nm, "orders", len(g), "resets", int((np.diff(s) < 0).sum()), "first", g.t.iloc[0] if len(g) else None, "salt", s[0] if len(s) else None, "last", g.t.iloc[-1] if len(g) else None, "salt", s[-1] if len(s) else None)
    if idx:
        print(g.iloc[sorted(i for i in idx if 0 <= i < len(g))][["t", "salt", "role", "fam"]].to_string(index=False))

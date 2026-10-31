"""For each sampled market, fetch the public taker tape of the two sibling markets of the same event
that RN1 traded most (by RN1 USD volume over the window - a market-selection choice; the sibling's
tape itself is public PIT data) over the sampled market's tape window."""
import json, sys, pickle
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import S
from polyrea.adapters.polymarket import PolymarketData

pm = PolymarketData()
t = pd.read_pickle(S / "rn1_trades.pkl")
meta = json.load(open(S / "sample_meta.json"))
markets = pickle.load(open(S / "rn1_markets.pkl", "rb"))
es = t[t.condition_id.isin(meta["cids"])].groupby("condition_id").event_slug.first()
per = t[t.event_slug.isin(es.unique())].groupby(["event_slug", "condition_id"]).agg(usd=("usdc", "sum")).reset_index()
jobs = []
for cid, e in es.items():
    a, b = meta["active"][cid]
    x = per[(per.event_slug == e) & (per.condition_id != cid)].sort_values("usd", ascending=False).head(2)
    for sib in x.condition_id:
        jobs.append((cid, sib, a - 1800, b + 600))
print("jobs", len(jobs))


def run(j):
    cid, sib, a, b = j
    m = markets.get(sib) or {}
    tokens = json.loads(m.get("clobTokenIds") or "[]")
    rows, _, cov = pm.market_trades(sib, start=a, end=b, taker_only=True)
    out = [{"target": cid, "sib": sib, "ts": int(r["timestamp"]), "outcome": tokens.index(str(r["asset"])) if str(r["asset"]) in tokens else -1,
            "side": r.get("side"), "price": float(r["price"]), "size": float(r["size"])} for r in rows]
    return pd.DataFrame(out), cov.status

with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(run, jobs))
df = pd.concat([r[0] for r in res], ignore_index=True)
df.to_pickle(S / "sibling_taker.pkl")
print("rows", len(df), "coverage", pd.Series([r[1] for r in res]).value_counts().to_dict())

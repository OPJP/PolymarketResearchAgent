"""Load RN1's window and the 140-market sample used by maker_replicability_study
(seed=5, identical sampling) and save taker + maker rows of the public tape.

Run from repo root with POLYREA_CACHE_DIR pointing at the scratch copy of the cache.
"""
import json, random, sys, time, pickle
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info, market_family
from polyrea.workflows.investigate import load_window, default_as_of

OUT = Path(sys.argv[1])
W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
t0 = time.time()
pm = PolymarketData()
AS_OF = 1793318400  # frozen as_of used by the project (2026-10-30 00:00 UTC)
win = load_window(W, days=30, as_of=AS_OF, pm=pm)
print("as_of", win["as_of"], "load_window s", round(time.time() - t0, 1), "trades", len(win["trades"]))
t, markets = win["trades"], win["markets"]
t.to_pickle(OUT / "rn1_trades.pkl")
# listing-time metadata only (we keep the full dict; decision code below only reads listing fields)
pickle.dump(markets, open(OUT / "rn1_markets.pkl", "wb"))

agg = t.groupby("condition_id").agg(first=("ts", "min"), last=("ts", "max"), n=("ts", "size"), usd=("usdc", "sum"))
agg = agg[agg["n"] >= 5]
rng = random.Random(5)
cids = list(agg.index)
if len(cids) > 160:
    cids = rng.sample(cids, 160)
payouts, active = {}, {}
for cid in cids:
    r = resolution_info(markets.get(cid) or {})
    tokens = json.loads((markets.get(cid) or {}).get("clobTokenIds") or "[]")
    if r["resolved"] and len(tokens) == 2:
        payouts[cid] = r["payout"].get(str(tokens[0]), 0.0)
        active[cid] = (int(agg.at[cid, "first"]), int(agg.at[cid, "last"]))
cids = [c for c in cids if c in payouts]
print("sampled markets", len(cids))


def load(cid):
    a, b = active[cid]
    m = markets[cid]
    tokens = json.loads(m.get("clobTokenIds") or "[]")
    taker, _, c1 = pm.market_trades(cid, start=a - 1800, end=b + 600, taker_only=True)
    full, _, c2 = pm.market_trades(cid, start=a - 1800, end=b + 600, taker_only=False)
    keys = {}
    trow = []
    for r in taker:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        keys[k] = keys.get(k, 0) + 1
        if str(r.get("asset")) in tokens:
            trow.append({"condition_id": cid, "ts": int(r["timestamp"]), "outcome": tokens.index(str(r["asset"])), "side": r.get("side"),
                         "price": float(r["price"]), "size": float(r["size"]), "wallet": (r.get("proxyWallet") or "").lower(), "tx": r.get("transactionHash")})
    mrow = []
    for r in full:
        k = (r.get("transactionHash"), (r.get("proxyWallet") or "").lower(), str(r.get("asset")), r.get("side"))
        if keys.get(k, 0) > 0:
            keys[k] -= 1
            continue
        if str(r.get("asset")) in tokens:
            mrow.append({"condition_id": cid, "ts": int(r["timestamp"]), "outcome": tokens.index(str(r["asset"])), "side": r.get("side"),
                         "price": float(r["price"]), "size": float(r["size"]), "wallet": (r.get("proxyWallet") or "").lower(), "tx": r.get("transactionHash")})
    return pd.DataFrame(trow), pd.DataFrame(mrow), (c1.status, c2.status)


t1 = time.time()
with ThreadPoolExecutor(6) as ex:
    parts = list(ex.map(load, cids))
print("tapes s", round(time.time() - t1, 1))
taker = pd.concat([p[0] for p in parts], ignore_index=True)
maker = pd.concat([p[1] for p in parts], ignore_index=True)
cov = {c: p[2] for c, p in zip(cids, parts)}
taker.to_pickle(OUT / "sample_taker.pkl")
maker.to_pickle(OUT / "sample_maker.pkl")
meta = {"cids": cids, "payouts": payouts, "active": active, "coverage": cov,
        "family": {c: market_family(markets[c].get("slug"), markets[c]) for c in cids},
        "slug": {c: markets[c].get("slug") for c in cids},
        "gameStartTime": {c: markets[c].get("gameStartTime") for c in cids},
        "feeSchedule": {c: markets[c].get("feeSchedule") for c in cids},
        "as_of": win["as_of"]}
json.dump(meta, open(OUT / "sample_meta.json", "w"), default=str)
print("taker rows", len(taker), "maker rows", len(maker), "rn1 maker rows", int((maker.wallet == W).sum()),
      "rn1 taker rows", int((taker.wallet == W).sum()))
print("coverage statuses", pd.Series([v[0] + "/" + v[1] for v in cov.values()]).value_counts().to_dict())

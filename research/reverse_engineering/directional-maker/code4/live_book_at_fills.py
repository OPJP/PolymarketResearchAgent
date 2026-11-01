"""Live lab (development block 2026-10-31 12:00-18:00): the recorded CLOB book just before each cluster BTC 5m maker
fill. Where is the fill price relative to the best bid on its token, how long has that best level existed, spread,
depth. Recorder keeps the Up token's book; the Down book is its mirror (Down bid = 1 - Up ask)."""
import glob, json, sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import livex
C = ".cache/re/directional-maker/"
act = pd.read_parquet(sorted(glob.glob(C + "live_activity_1793448000_*.parquet"))[-1])
t = act[(act.type == "TRADE") & act.slug.str.startswith("btc-updown-5m")].copy()
# Up token per window from the subs feed
subs = {}
for r in livex.iter_live("subs", 1793448000, 1793470000):
    for slug, toks in (r.get("markets") or {}).items():
        if slug.startswith("btc-updown-5m"):
            subs[slug] = toks
t = t[t.slug.isin(subs)]
t["up_tok"] = t.slug.map(lambda s: subs[s][0])
t["is_up"] = t.asset == t.up_tok
lo, hi = int(t.timestamp.min()) - 60, int(t.timestamp.max()) + 5
books = {}
for r in livex.iter_live("clob_crypto", lo, hi):
    if r["k"] in ("q", "f") and r["a"] in set(t.up_tok):
        books.setdefault(r["a"], []).append((r.get("s", r["t"]) / 1000.0, r["b"], r["o"]))
rows = []
for x in t.itertuples():
    bk = books.get(x.up_tok)
    if not bk:
        continue
    ts = np.array([b[0] for b in bk])
    T = x.timestamp - 2.0  # block time minus ~2 s: approximate match time
    i = np.searchsorted(ts, T) - 1
    if i < 0:
        continue
    _, bids, asks = bk[i]
    # bids on the cluster's token
    if x.is_up:
        tb = [(p, z) for p, z in bids]
        ta = [(p, z) for p, z in asks]
    else:
        tb = [(round(1 - p, 3), z) for p, z in asks]
        ta = [(round(1 - p, 3), z) for p, z in bids]
    best_b = tb[0][0] if tb else np.nan; best_a = ta[0][0] if ta else np.nan
    depth_at = dict(tb).get(round(x.price, 3), 0.0)
    # how long has the best bid been at >= the fill price
    j = i; age = 0.0
    while j > 0:
        _, b2, a2 = bk[j - 1]
        bb = (b2[0][0] if b2 else np.nan) if x.is_up else ((round(1 - a2[0][0], 3)) if a2 else np.nan)
        if not (bb >= x.price - 1e-9):
            break
        j -= 1
    age = T - bk[j][0]
    rows.append({"ts": x.timestamp, "w": x.w, "price": x.price, "size": x.size, "best_bid": best_b, "best_ask": best_a,
                 "price_minus_best_bid": round(x.price - best_b, 3), "spread": round(best_a - best_b, 3), "depth_at_price": depth_at,
                 "best_ge_price_age_s": round(age, 2)})
d = pd.DataFrame(rows)
print(len(t), "fills;", len(d), "with a book snapshot")
print("price - best bid (match time ~ block - 2 s):", d.price_minus_best_bid.value_counts().head(8).to_dict())
print("spread:", d.spread.value_counts().head(6).to_dict())
print("age of best bid >= fill price (s) quantiles", d.best_ge_price_age_s.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(2).to_dict())
print("depth at fill price (shares) quantiles", d.depth_at_price.quantile([0.1, 0.5, 0.9]).round(1).to_dict())
d.to_parquet(C + "live_book_at_fills.parquet")

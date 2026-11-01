"""Iteration 10 (I9-1 = X87, step 1: version check pilot). One hour of the public pmxt archive of the unaggregated
CLOB market-channel stream (https://r2v2.pmxt.dev/polymarket_orderbook_YYYY-MM-DDTHH.parquet, range reads of the row
groups holding the cluster's BTC 5m markets; nothing raw is stored). Development data (July 2026).
Checks: (1) calldata of a sample of the hour's cluster fills: timestamp / metadata / builder = 0, per-wallet sequential
salt, original sizes; (2) book fingerprints of the October engine: the filled order's add (an add of exactly its original
size at its price on its token, 0.05-3 s before the trade with the same tx hash), its age, whether it was at the touch,
how long after the market's previous trade it was posted, and same-size same-price adds by 2-3 orders within 20 ms
(the three-wallet burst). Usage: pmxt_pilot.py 2026-07-22 13"""
import collections
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "code4"))
SCR = Path("C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i9")
sys.path.insert(0, str(SCR))
from rangefile import RangeFile  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
import calldata  # noqa: E402

W = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
     "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def main(day, hh):
    url = f"https://r2v2.pmxt.dev/polymarket_orderbook_{day}T{hh}.parquet"
    a = int(pd.Timestamp(f"{day} {hh}:00", tz="UTC").timestamp())
    b = a + 3600
    pm = PolymarketData()
    acts = []
    for n, w in W.items():
        rows, _, _ = pm.activity(w, a, b)
        d = pd.DataFrame(rows)
        d["wallet"] = n
        acts.append(d)
    act = pd.concat(acts)
    act = act[act.type == "TRADE"]
    b5 = act[act.slug.str.startswith("btc-updown-5m")].copy()
    b5["tx"] = b5.transactionHash.str.lower()
    cids = set(b5.conditionId.str.lower())
    out = {"hour": f"{day}T{hh}", "cluster_btc5m_trades": int(len(b5)), "markets": len(cids)}
    # (1) calldata sample
    txs = list(dict.fromkeys(b5.tx))[:150]
    dec = []
    for h, tx in calldata.fetch_txs(txs):
        r = calldata.decode(tx["input"]) if tx else None
        if r:
            for o in r.get("makers", []) + ([r["taker"]] if r.get("taker") else []):
                o = dict(o)
                o["tx"] = h
                dec.append(o)
    cd = pd.DataFrame(dec)
    if len(cd):
        cd["maker"] = cd.maker.str.lower()
        cl = cd[cd.maker.isin(set(W.values()))].copy()
        out["calldata"] = {"txs": len(txs), "cluster_orders": int(len(cl)),
                           "timestamp_zero_share": float((cl.sign_ms.astype(float) == 0).mean()),
                           "metadata_zero_share": float((cl.metadata.astype(str).str.strip("0") == "").mean()),
                           "orig_size_top": {str(k): int(v) for k, v in pd.Series((np.where(cl.oside.astype(int) == 0, cl.taker_amount.astype(float), cl.maker_amount.astype(float)) / 1e6).round(2)).value_counts().head(8).items()}}
        sal = {}
        for n, w in W.items():
            s = cl[cl.maker == w].copy()
            if len(s) > 3:
                s["salt"] = s.salt.astype(float)
                s = s.merge(b5[["tx", "timestamp"]].drop_duplicates("tx"), on="tx")
                s = s.sort_values("timestamp")
                sal[n] = {"n": int(len(s)), "salt_min": float(s.salt.min()), "salt_max": float(s.salt.max()),
                          "monotone_share": float((np.diff(s.salt.to_numpy()) >= 0).mean()),
                          "rate_per_s": float((s.salt.max() - s.salt.min()) / max(s.timestamp.max() - s.timestamp.min(), 1))}
        out["salt"] = sal
        cl["orig"] = (np.where(cl.oside.astype(int) == 0, cl.taker_amount.astype(float), cl.maker_amount.astype(float)) / 1e6).round(2)
        cl["lim"] = np.where(cl.oside.astype(int) == 0, cl.maker_amount.astype(float) / cl.taker_amount.astype(float), cl.taker_amount.astype(float) / cl.maker_amount.astype(float)).round(4)
    # (2) the book
    cache = ROOT / ".cache/re/directional-maker/pmxt" / f"ev_{day}T{hh}.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        ev = pd.read_parquet(cache)
        out["book"] = {"bytes_MB": 0, "events": int(len(ev)), "types": ev.event_type.value_counts().to_dict(), "from_cache": True}
    else:
        ev = None
    f = RangeFile(url) if ev is None else None
    pf = pq.ParquetFile(pa.PythonFile(f, mode="r")) if f is not None else None
    md = pf.metadata if pf is not None else None
    names = pf.schema_arrow.names if pf is not None else []
    mi = names.index("market") if names else 0
    cand = [] if md is None else [i for i in range(md.num_row_groups)
            if any(md.row_group(i).column(mi).statistics.min.decode() <= c <= md.row_group(i).column(mi).statistics.max.decode() for c in cids)]
    evs = []
    for i in cand:
        t = pf.read_row_group(i, columns=["timestamp", "market", "event_type", "asset_id", "price", "size", "side", "best_bid", "best_ask", "transaction_hash"])
        m = pc.cast(t["market"], pa.binary()).to_pylist()
        t = t.filter(pa.array(np.array([x.decode() in cids for x in m])))
        evs.append(t.to_pandas())
    if ev is None:
        ev = pd.concat(evs)
        ev.to_parquet(cache, index=False)
        out["book"] = {"bytes_MB": round(f.bytes / 1e6, 1), "events": int(len(ev)), "types": ev.event_type.value_counts().to_dict()}
    ev["ms"] = (pd.to_datetime(ev["timestamp"], utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)
    ev = ev.sort_values("ms", kind="stable")
    pc_ = ev[ev.event_type == "price_change"].copy()
    pc_["price"] = pc_.price.astype(float)
    pc_["size"] = pc_["size"].astype(float)
    pc_["key"] = pc_.asset_id.astype(str) + "|" + pc_.side.astype(str) + "|" + pc_.price.round(3).astype(str)
    pc_["prev"] = pc_.groupby("key")["size"].shift(1).fillna(0.0)
    pc_["delta"] = (pc_["size"] - pc_["prev"]).round(2)
    adds = pc_[(pc_.delta > 0) & (pc_.side.astype(str).str.upper() == "BUY")]
    lt = ev[ev.event_type == "last_trade_price"].copy()
    lt["tx"] = lt.transaction_hash.astype(str).str.lower()
    # cluster filled orders: the add of exactly the original size at the limit price on its token before its trade
    res = []
    if len(cd):
        b5tok = b5[["tx", "asset", "wallet"]].drop_duplicates()
        for r in cl.itertuples(index=False):
            if int(r.oside) != 0:
                continue
            tr = lt[lt.tx == r.tx]
            if not len(tr):
                continue
            T = int(tr.ms.min())
            tok = str(r.token_id)
            g = adds[(adds.asset_id.astype(str) == tok) & ((adds.price - r.lim).abs() < 0.0005) & ((adds.delta - r.orig).abs() < 0.011) & (adds.ms < T - 50) & (adds.ms > T - 3000)]
            if not len(g):
                res.append((r.maker, r.orig, None, None, None, None))
                continue
            x = g.iloc[-1]
            prior = lt[(lt.market == x.market) & (lt.ms < x.ms)]
            since_trade = float(x.ms - prior.ms.max()) if len(prior) else None
            bb = float(x.best_bid) if pd.notna(x.best_bid) else np.nan
            burst = int(((adds.asset_id == x.asset_id) & ((adds.price - x.price).abs() < 0.0005) & ((adds.delta - x.delta).abs() < 0.011) & ((adds.ms - x.ms).abs() <= 20)).sum())
            res.append((r.maker, r.orig, float(T - x.ms), bool(abs(x.price - bb) < 0.0005), since_trade, burst))
    R = pd.DataFrame(res, columns=["maker", "orig", "age_ms", "at_touch", "since_trade_ms", "burst_n"])
    out["filled_orders"] = {"n": int(len(R)), "add_found": float(R.age_ms.notna().mean()) if len(R) else None,
                            "age_ms_median": float(R.age_ms.median()) if R.age_ms.notna().any() else None,
                            "at_touch_share": float(R.at_touch.dropna().mean()) if R.at_touch.notna().any() else None,
                            "since_trade_ms_median": float(R.since_trade_ms.median()) if R.since_trade_ms.notna().any() else None,
                            "burst_ge2_share": float((R.burst_n.dropna() >= 2).mean()) if R.burst_n.notna().any() else None,
                            "orig_sizes": R.orig.value_counts().head(8).to_dict() if len(R) else {}}
    # generic: share of BUY adds of the July schedule sizes that come in same-size same-price bursts within 20 ms
    adds = adds.copy()
    adds["k2"] = adds.asset_id.astype(str) + "|" + adds.price.round(3).astype(str) + "|" + adds.delta.astype(str)
    gb = []
    for k2, g in adds.groupby("k2"):
        ms = g.ms.to_numpy()
        n = np.searchsorted(ms, ms + 20, side="right") - np.searchsorted(ms, ms - 20, side="left")
        gb.append(pd.DataFrame({"delta": g.delta.to_numpy(), "nb": n}))
    gb = pd.concat(gb)
    out["burst_by_size"] = {str(s): {"adds": int((gb.delta == s).sum()), "burst_ge2": float((gb.nb[gb.delta == s] >= 2).mean())} for s in (5.0, 10.0, 50.0, 100.0, 300.0, 500.0) if (gb.delta == s).any()}
    out["burst_other_sizes"] = float((gb.nb[~gb.delta.isin([5.0, 10.0, 50.0, 100.0, 300.0, 500.0])] >= 2).mean())
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(ROOT / f"research/reverse_engineering/directional-maker/results/iter10_pmxt_pilot_{day}T{hh}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

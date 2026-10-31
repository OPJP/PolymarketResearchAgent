"""Iteration 11 (X98 / X60): the bot's VIEW LAG of the Polymarket book in the 250-ms regime (pmxt hour 08-06 16-17 UTC,
development), to compare with Lambda = 30 ms on 10-31 (lam11). If the extra ~130 ms of the August wallet gap floor (pmxt11:
q01 377-393 ms = D + ~130) is distance to Polymarket's engine, the limits should match o's ask ~130+ ms before the arrival.
Touch: pmxt price_change rows (server ms, per-asset best_ask) for the hour's 13 BTC 5m markets, read through HTTP range
requests (nothing stored). Limits: V2 calldata of the cluster's taker-first txs of the hour (decoded in memory; limit =
maker_amt / taker_amt of the operator's BUY order). Arrival a = m - 250. Profile P(limit == ask(a - Lambda)) for Lambda =
-250..500 ms on decisions whose ask changed in [a - 400, a].
Usage: python lam11b.py OUT_JSON 2026-08-06T16"""
import os, sys, json, time, calendar
import numpy as np, pandas as pd
import pyarrow.parquet as pq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calldata, pmxt11

C = pmxt11.C
OPS = {"0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS", "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM"}


def r4(x):
    return round(float(x), 4)


def main(out, hour):
    tag = hour.replace("-", "").replace("T", "_")
    mk = json.load(open(f"{C}/it11/pmxt_{tag}_markets.json")); cids = mk["cids"]
    F = pd.read_parquet(f"{C}/it11/pmxt_{tag}_cluster.parquet")
    f = pmxt11.RangeFile(f"https://r2v2.pmxt.dev/polymarket_orderbook_{hour}.parquet")
    pf = pq.ParquetFile(f); md = pf.metadata
    mcol = [i for i in range(md.num_columns) if md.schema.column(i).name == "market"][0]
    want = [k for k in range(md.num_row_groups) if any(md.row_group(k).column(mcol).statistics.min.decode().lower() <= c <= md.row_group(k).column(mcol).statistics.max.decode().lower() for c in cids)]
    parts = []
    for k in want:
        tb = pf.read_row_group(k, columns=["timestamp", "market", "event_type", "asset_id", "best_ask", "best_bid"]).to_pandas()
        tb["market"] = tb.market.map(lambda x: x.decode().lower() if isinstance(x, (bytes, bytearray)) else str(x).lower())
        tb = tb[tb.market.isin(cids) & (tb.event_type == "price_change") & tb.best_ask.notna()]
        parts.append(tb[["timestamp", "asset_id", "best_ask"]])
    P = pd.concat(parts, ignore_index=True)
    P["ms"] = P.timestamp.to_numpy().astype("datetime64[ms]").astype("int64"); P["ask"] = P.best_ask.astype(float)
    P = P.sort_values("ms", kind="stable")
    ser = {str(a): (g.ms.to_numpy(np.int64), g.ask.to_numpy(float)) for a, g in P.groupby("asset_id")}
    txs = list(F[(F.role == "T") & F.m.notna() & (F.w != "W4")].drop_duplicates("tx").tx)
    cd = calldata.to_frame(calldata.fetch_txs(txs, threads=2, log_every=10 ** 6))
    cd["txl"] = cd.tx.str.lower()
    o = cd[(cd.role == "T") & cd.maker.isin(OPS) & (cd.oside == 0)].drop_duplicates(["txl", "maker"]).copy()
    o["Lim"] = (o.maker_amt.astype(float) / o.taker_amt.astype(float)).round(4)
    mm = F.drop_duplicates("tx").set_index("tx").m
    o["m"] = o.txl.map(mm); o = o[o.m.notna()]
    o["a"] = o.m.astype(np.int64) - 250
    lams = np.arange(-250, 510, 10)
    eq = []; chg = []
    for r in o.itertuples():
        s = ser.get(str(r.token))
        if s is None:
            continue
        T, A = s
        tt = r.a - lams
        j = np.searchsorted(T, tt, "right") - 1
        v = np.where(j >= 0, A[np.clip(j, 0, None)], np.nan)
        w = (lams >= 0) & (lams <= 400)
        chg.append(np.isfinite(v[w]).all() and (np.nanmax(v[w]) - np.nanmin(v[w]) > 0.005))
        eq.append(np.abs(np.round(v, 4) - r.Lim) < 1e-6)
    eq = np.array(eq, float); chg = np.array(chg, bool)
    res = {"hour": hour, "taker_orders": int(len(eq)), "with_ask_change": int(chg.sum()), "price_change_rows": int(len(P))}
    for nm, sel in (("all", np.ones(len(eq), bool)), ("changed", chg)):
        prof = eq[sel].mean(0)
        k = int(np.argmax(prof))
        res[nm] = {"n": int(sel.sum()), "peak_lambda_ms": int(lams[k]), "peak_eq": r4(prof[k]), "eq_by_lambda": {int(l): r4(e) for l, e in zip(lams, prof) if l % 50 == 0}}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

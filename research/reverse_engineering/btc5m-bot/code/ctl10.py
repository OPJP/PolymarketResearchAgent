"""Iteration 10 (X73 step 1 control): the signing-to-match floor of fresh-signed taker orders on markets WITHOUT the crypto taker
delay. Trades of the shared recorder's clob_wallets feed (sports / esports / event markets, development block 10-31 12-18 via
iter_live), a sample of tx hashes, V2 calldata (decoded fields only, kept in memory), match = the recorded server ms of the trade.
The market flags (itode and any delay field) are read from the CLOB market record of the sampled condition ids (listing fields).
Usage: python ctl10.py OUT_JSON"""
import os, sys, json, time
import numpy as np, pandas as pd, httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import calldata


def main(out):
    tr = {}
    for r in L.recs("clob_wallets", 1793448000, 1793469300):
        if r.get("k") == "x" and r.get("h"):
            h = r["h"].lower(); s = int(r["s"])
            if h not in tr or s < tr[h][0]:
                tr[h] = (s, str(r.get("a")))
    df = pd.DataFrame([(h, s, a) for h, (s, a) in tr.items()], columns=["h", "s", "a"])
    res = {"trades_txs": int(len(df)), "tokens": int(df.a.nunique())}
    rng = np.random.default_rng(10)
    samp = df.groupby("a", group_keys=False).apply(lambda g: g.sample(min(len(g), 8), random_state=1)).sample(frac=1, random_state=2).head(500)
    rows = calldata.fetch_txs(samp.h.tolist(), threads=2, log_every=1000)
    cd = calldata.to_frame(rows)
    cd["txl"] = cd.tx.str.lower()
    cd["s"] = cd.txl.map(dict(zip(df.h, df.s)))
    t = cd[(cd.role == "T") & cd.sign_ms.notna() & cd.s.notna()].copy()
    t["dt"] = t.s - t.sign_ms
    fr = t[(t.dt >= -500) & (t.dt < 3000)]
    pos = fr[fr.dt >= 0]
    res["decoded_txs"] = int(cd.tx.nunique()); res["taker_orders"] = int(len(t)); res["fresh_dt_-500_3000"] = int(len(fr))
    res["dt_q1_5_10_25_50"] = [float(x) for x in np.percentile(pos.dt, [1, 5, 10, 25, 50])] if len(pos) else None
    res["n_dt_0_100"] = int(((fr.dt >= 0) & (fr.dt < 100)).sum()); res["n_dt_100_180"] = int(((fr.dt >= 100) & (fr.dt < 180)).sum())
    res["n_dt_180_250"] = int(((fr.dt >= 180) & (fr.dt < 250)).sum())
    mins = pos.groupby("maker").dt.agg(["min", "size"]).query("size >= 3").sort_values("min").head(10)
    res["fastest_wallet_minima"] = {k[:10]: [float(v["min"]), int(v["size"])] for k, v in mins.iterrows()}
    # market flags for the most frequent condition ids among fresh orders
    cids = pos.cid.value_counts().head(6).index.tolist()
    flags = {}
    cl = httpx.Client(timeout=15)
    for c in cids:
        try:
            rr = cl.get(f"https://clob.polymarket.com/clob-markets/{c}")
            j = rr.json() if rr.status_code == 200 else {}
            keep = {k: j.get(k) for k in j if any(x in k.lower() for x in ("itode", "delay", "tick", "neg", "fee"))} if isinstance(j, dict) else {}
            flags[c[:12]] = {"http": rr.status_code, "fields": keep, "fresh_orders": int((pos.cid == c).sum()),
                             "dt_min": float(pos[pos.cid == c].dt.min())}
        except Exception as e:
            flags[c[:12]] = {"error": type(e).__name__}
        time.sleep(0.5)
    res["market_flags"] = flags
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    main(sys.argv[1])

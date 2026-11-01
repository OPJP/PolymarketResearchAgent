"""Iteration 11 (X60 = panel iteration 8 information P2, first test): the 250-ms taker-delay regime as a natural experiment on the
pmxt v2 archive (r2v2.pmxt.dev, hourly parquet with server-ms trades and tx hashes; verified HTTP 206 without a key; coverage ends
08-10). Mechanism under test (iteration 10, finding 1 / 6): each wallet has one order in flight, blocked for the delay D plus a round
trip, so the per-wallet gap between consecutive TAKER matches has a floor ~D + RTT: on 10-31 (D = 150 ms) DS q1 254 ms, GF 196, XM
152. With D = 250 ms the floor should sit ~100 ms higher.
Data: one development hour (2026-08-01 12:00-13:00 UTC, before H, inside the 250-ms regime). The archive is sorted by market, so only
the row groups whose market range holds a BTC 5m condition id are read, column subset only, through HTTP range requests (a lazy
range-backed file object; nothing of the archive is stored). Cluster tx hashes from the operator wallets' OrderFilled logs (V1 + V2
exchanges, 100-block chunks); role T when topic3 is the exchange. Match ms = the archive's server timestamp of the tx's
last_trade_price event (min over the tx).
Usage: python pmxt11.py OUT_JSON [YYYY-MM-DDTHH]"""
import os, sys, json, io, time, calendar
import numpy as np, pandas as pd, httpx
import pyarrow.parquet as pq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, delayreg10 as D10

H = 1792713600
WAL = D10.WAL
C = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..")) + "/.cache/re/btc5m-bot"
UPTOK = {}


class RangeFile(io.RawIOBase):
    def __init__(self, url, block=1 << 21):
        self.url, self.block, self.pos, self.cache = url, block, 0, {}
        self.cl = httpx.Client(timeout=60)
        r = self.cl.get(url, headers={"Range": "bytes=0-0"}); r.raise_for_status()
        self.size = int(r.headers["content-range"].split("/")[1]); self.fetched = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def _blk(self, k):
        if k not in self.cache:
            a = k * self.block; b = min(self.size, a + self.block) - 1
            for t in range(4):
                try:
                    r = self.cl.get(self.url, headers={"Range": f"bytes={a}-{b}"}); r.raise_for_status()
                    self.cache[k] = r.content; self.fetched += len(r.content); break
                except Exception:
                    time.sleep(2 + 2 * t)
            if len(self.cache) > 24:  # bounded memory
                for kk in sorted(self.cache)[:8]:
                    if kk != k:
                        self.cache.pop(kk, None)
        return self.cache[k]

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        if n <= 0:
            return 0
        out = bytearray(); p = self.pos
        while len(out) < n:
            k = p // self.block; b = self._blk(k); o = p - k * self.block
            take = b[o:o + (n - len(out))]; out += take; p += len(take)
        buf[:n] = out; self.pos += n
        return n


def btc5m_cids(t0, t1):
    out = {}
    with httpx.Client(timeout=20, headers={"User-Agent": "polyrea-research"}) as c:
        for st in range(t0 - 300, t1, 300):
            j = c.get("https://gamma-api.polymarket.com/markets", params={"slug": f"btc-updown-5m-{st}", "closed": "true"}).json()
            if j:
                out[j[0]["conditionId"].lower()] = st  # listing fields only (condition id, token ids, outcomes)
                try:
                    tks = json.loads(j[0]["clobTokenIds"]); oc = json.loads(j[0]["outcomes"])
                    UPTOK[j[0]["conditionId"].lower()] = tks[oc.index("Up")] if "Up" in oc else tks[0]
                except Exception:
                    pass
            time.sleep(0.15)
    return out


def main(out, hour):
    t0 = calendar.timegm(time.strptime(hour, "%Y-%m-%dT%H")); t1 = t0 + 3600
    assert t1 <= H
    cids = btc5m_cids(t0, t1)
    url = f"https://r2v2.pmxt.dev/polymarket_orderbook_{hour}.parquet"
    f = RangeFile(url)
    pf = pq.ParquetFile(f)
    md = pf.metadata
    mcol = [i for i in range(md.num_columns) if md.schema.column(i).name == "market"][0]
    want = set()
    for k in range(md.num_row_groups):
        st_ = md.row_group(k).column(mcol).statistics
        lo, hi = st_.min.decode().lower(), st_.max.decode().lower()
        if any(lo <= c <= hi for c in cids):
            want.add(k)
    cols = ["timestamp", "market", "event_type", "asset_id", "price", "size", "side", "transaction_hash"]
    trades = []
    for k in sorted(want):
        tb = pf.read_row_group(k, columns=cols).to_pandas()
        tb["market"] = tb.market.map(lambda x: x.decode().lower() if isinstance(x, (bytes, bytearray)) else str(x).lower())
        tb = tb[tb.market.isin(cids) & (tb.event_type == "last_trade_price")]
        trades.append(tb[["timestamp", "market", "asset_id", "price", "size", "side", "transaction_hash"]])
    T = pd.concat(trades, ignore_index=True)
    T["ms"] = T.timestamp.to_numpy().astype("datetime64[ms]").astype("int64")
    txms = T.groupby(T.transaction_hash.str.lower()).ms.min()
    # cluster fills from chain logs
    anchors = {1785542400: D10.find_block(1785542400)}
    head_t = t0 + 7200; anchors[head_t] = D10.find_block(head_t)
    at = np.array(sorted(anchors)); ab = np.array([anchors[t] for t in at])
    b0 = int(np.interp(t0, at, ab)) - 60; b1 = int(np.interp(t1, at, ab)) + 60
    cl = httpx.Client()
    inv = {rpc.pad(a): w for w, a in WAL.items()}
    rows = []
    for x in range(b0, b1 + 1, 100):
        for lg in D10.logs(x, min(x + 99, b1), cl):
            w = inv.get(lg["topics"][2].lower())
            if w is None:
                continue
            role = "T" if lg["topics"][3].lower() == rpc.pad(lg["address"]) else "M"
            rows.append((w, role, lg["transactionHash"].lower(), int(lg["blockNumber"], 16)))
        time.sleep(0.2)
    F = pd.DataFrame(rows, columns=["w", "role", "tx", "block"]).drop_duplicates(["w", "role", "tx"])
    F["m"] = F.tx.map(txms)
    tag = hour.replace("-", "").replace("T", "_")
    T[["ms", "market", "asset_id", "price", "size", "side", "transaction_hash"]].astype({"price": float, "size": float}).to_parquet(f"{C}/it11/pmxt_{tag}_trades.parquet")
    F.to_parquet(f"{C}/it11/pmxt_{tag}_cluster.parquet")
    json.dump({"cids": cids, "up_tokens": UPTOK}, open(f"{C}/it11/pmxt_{tag}_markets.json", "w"))
    res = {"hour": hour, "btc5m_markets": len(cids), "row_groups_read": len(want), "bytes_fetched_MB": round(f.fetched / 1e6, 1), "archive_trades_btc5m": int(len(T)),
           "cluster_fill_rows": int(len(F)), "cluster_txs_with_ms": int(F.m.notna().sum())}
    for w, g in F[(F.role == "T") & F.m.notna()].groupby("w"):
        m = np.sort(g.m.to_numpy(np.int64)); gap = np.diff(m)
        if len(gap) >= 10:
            res.setdefault("taker_gap_ms", {})[w] = {"n_matches": int(len(m)), "min": int(gap.min()), "q01": float(np.percentile(gap, 1)), "q05": float(np.percentile(gap, 5)),
                                                    "q25": float(np.percentile(gap, 25)), "share_lt_250": round(float((gap < 250).mean()), 4), "share_lt_350": round(float((gap < 350).mean()), 4),
                                                    "hist_0_600_50ms": [int(v) for v in np.histogram(gap, bins=np.arange(0, 650, 50))[0]]}
    allT = np.sort(F[(F.role == "T") & F.m.notna() & (F.w != "W4")].m.to_numpy(np.int64))
    if len(allT) > 10:
        g2 = np.diff(allT)
        res["cluster_any_wallet_gap_share_lt_100"] = round(float((g2 < 100).mean()), 4)
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "2026-08-01T12")

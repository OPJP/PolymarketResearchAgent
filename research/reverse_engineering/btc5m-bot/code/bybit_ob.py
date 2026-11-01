"""Iteration 5: Bybit historical ORDER BOOK (orderbook.200 snapshot + delta stream, public daily archive
quote-saver.bycsi.com) for a pre-H UTC day. The zip is STREAMED: its single member is inflated on the fly from the local
file header (nothing raw is written to disk) and the book is rebuilt from snapshot/delta messages. Reduced to 100-ms buckets
(last best bid / ask, sizes at the touch, top-5 depth per side, update count) in .cache/re/btc5m-bot/bybit_ob/<mkt>_<day0>.parquet.
Run with python -I (downloaded data is untrusted). Usage: python -I bybit_ob.py linear|spot YYYY-MM-DD [END_HOURS]"""
import os, sys, json, zlib, struct, calendar, time
import httpx, numpy as np, pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
OUT = _ROOT + "/.cache/re/btc5m-bot/bybit_ob"
H = 1792713600
SYM = os.environ.get("BYBIT_SYM", "BTCUSDT")  # iteration 6: ETHUSDT for the ETH perp microprice (the strongest live trigger)
URL = "https://quote-saver.bycsi.com/orderbook/{m}/" + SYM + "/{d}_" + SYM + "_ob200.data.zip"


def run(mkt, d, end_hours=24.0):
    day0 = calendar.timegm(time.strptime(d, "%Y-%m-%d")); assert day0 + 86400 <= H
    end_ms = int((day0 + end_hours * 3600) * 1000)
    path = f"{OUT}/{mkt}_{day0}.parquet" if SYM == "BTCUSDT" else f"{OUT}/{mkt}_{SYM}_{day0}.parquet"
    if os.path.exists(path):
        return
    dec = zlib.decompressobj(-15)
    head = b""; started = False; buf = b""; nbytes = 0; t0 = time.time()
    bids, asks = {}, {}
    rows = []  # (bucket, bid, ask, bq, aq, bq5, aq5)
    last_b = None; cur = None; cnt = 0; done = False
    with httpx.stream("GET", URL.format(m=mkt, d=d), timeout=180, follow_redirects=True) as r:
        r.raise_for_status()
        for chunk in r.iter_bytes(1 << 20):
            nbytes += len(chunk)
            if not started:
                head += chunk
                if len(head) < 30:
                    continue
                sig, _, flag, meth, _, _, _, _, _, nlen, xlen = struct.unpack("<IHHHHHIIIHH", head[:30])
                assert sig == 0x04034B50 and meth == 8, "unexpected zip member"
                chunk = head[30 + nlen + xlen:]; started = True
            buf += dec.decompress(chunk)
            lines = buf.split(b"\n"); buf = lines.pop()
            for ln in lines:
                if not ln:
                    continue
                msg = json.loads(ln)
                ts = int(msg["ts"]); dd = msg["data"]
                if msg.get("type") == "snapshot":
                    bids = {float(p): float(q) for p, q in dd["b"]}; asks = {float(p): float(q) for p, q in dd["a"]}
                else:
                    for p, q in dd["b"]:
                        p = float(p); q = float(q)
                        if q == 0.0:
                            bids.pop(p, None)
                        else:
                            bids[p] = q
                    for p, q in dd["a"]:
                        p = float(p); q = float(q)
                        if q == 0.0:
                            asks.pop(p, None)
                        else:
                            asks[p] = q
                if not bids or not asks:
                    continue
                b = ts // 100
                if last_b is not None and b != last_b and cur is not None:
                    rows.append((last_b,) + cur + (cnt,)); cnt = 0
                bb = sorted(bids, reverse=True)[:5]; aa = sorted(asks)[:5]
                cur = (bb[0], aa[0], bids[bb[0]], asks[aa[0]], sum(bids[x] for x in bb), sum(asks[x] for x in aa))
                last_b = b; cnt += 1
                if ts >= end_ms:
                    done = True; break
            if done:
                break
    if cur is not None:
        rows.append((last_b,) + cur + (cnt,))
    df = pd.DataFrame(rows, columns=["b", "bid", "ask", "bq", "aq", "bq5", "aq5", "n"])
    df = df[(df.b >= day0 * 10) & (df.b < min(H, day0 + 86400) * 10)]
    lo, hi = (10_000, 1_000_000) if SYM == "BTCUSDT" else (300, 50_000)  # price sanity range per symbol
    assert df.b.max() < H * 10 and df.bid.between(lo, hi).all()
    os.makedirs(OUT, exist_ok=True)
    df.to_parquet(path, index=False)
    print(mkt, d, len(df), "buckets", round(nbytes / 1e6, 1), "MB read", round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 24.0)

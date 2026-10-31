"""Iteration 5: Bybit BTCUSDT perpetual top-of-book features (public orderbook.200 daily archive, quote-saver.bycsi.com).
No side effects at import (used by side_book.py and final_rule.py).
- stream_day(day0, path): streams the day's zip (inflates its single member on the fly, nothing raw on disk), rebuilds the
  book from snapshot/delta messages and saves 100-ms buckets (b = ms // 100: last best bid / ask, sizes at the touch, top-5
  depth per side, update count).
- book_arrays(d0, paths): dense forward-filled 100-ms arrays for UTC day d0 (+ the last 2 minutes of day d0-1).
- book_feats(s_sec, A): point-in-time features for block seconds s using buckets < (s-1)*10 (data with T < (s-1)*1000 ms)."""
import os, json, zlib, struct, time
import numpy as np, pandas as pd

URL = "https://quote-saver.bycsi.com/orderbook/linear/BTCUSDT/{d}_BTCUSDT_ob200.data.zip"
BK = ["BK_imb", "BK_imb5", "BK_imb_avg1", "BK_imb5_avg1", "BK_imb_d1", "BK_micro", "BK_mid1", "BK_mid3", "BK_mid_d21", "BK_spread"]
BK_LAG = ["BK_imb_l1", "BK_imb_l2", "BK_imb5_l1", "BK_imb5_l2", "BK_imb_last3", "BK_mid_d32"]  # decision-lag segments [s-3, s-2), [s-4, s-3); last 300 ms


def stream_day(day0: int, path: str, h_guard: int) -> bool:
    import httpx
    assert day0 + 86400 <= h_guard or h_guard <= 0
    d = time.strftime("%Y-%m-%d", time.gmtime(day0))
    dec = zlib.decompressobj(-15)
    head = b""; started = False; buf = b""
    bids, asks = {}, {}
    rows = []; last_b = None; cur = None; cnt = 0
    with httpx.stream("GET", URL.format(d=d), timeout=180, follow_redirects=True) as r:
        if r.status_code != 200:
            return False
        for chunk in r.iter_bytes(1 << 20):
            if not started:
                head += chunk
                if len(head) < 30:
                    continue
                sig, _, flag, meth, _, _, _, _, _, nlen, xlen = struct.unpack("<IHHHHHIIIHH", head[:30])
                if sig != 0x04034B50 or meth != 8:
                    return False
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
    if cur is not None:
        rows.append((last_b,) + cur + (cnt,))
    df = pd.DataFrame(rows, columns=["b", "bid", "ask", "bq", "aq", "bq5", "aq5", "n"])
    df = df[(df.b >= day0 * 10) & (df.b < (day0 + 86400) * 10)]
    if h_guard > 0:
        assert df.b.max() < h_guard * 10
    if not len(df) or not df.bid.between(10_000, 1_000_000).all():
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)
    return True


def book_arrays(d0: int, paths: dict):
    """paths: {day0: parquet path or None}. Returns dense arrays from (d0 - 120 s) to d0 + 1 day, or None."""
    parts = []
    for dd in (d0 - 86400, d0):
        fp = paths.get(dd)
        if fp and os.path.exists(fp):
            q = pd.read_parquet(fp)
            if dd < d0:
                q = q[q.b >= (d0 - 120) * 10]
            parts.append(q)
    if not parts or not any(p.b.ge(d0 * 10).any() for p in parts):
        return None
    q = pd.concat(parts).drop_duplicates("b", keep="last").sort_values("b")
    b0 = (d0 - 120) * 10; n = (d0 + 86400) * 10 - b0
    A = {}
    for c in ("bid", "ask", "bq", "aq", "bq5", "aq5"):
        a = np.full(n, np.nan); a[(q.b - b0).to_numpy()] = q[c].to_numpy(float)
        A[c] = pd.Series(a).ffill().to_numpy()
    A["b0"] = b0
    return A


def book_feats(s_sec, A):
    s_sec = np.asarray(s_sec, np.int64)
    out = {k: np.full(len(s_sec), np.nan, np.float32) for k in BK + BK_LAG}
    if A is None:
        return out
    n = len(A["bid"])

    def at(arr, idx):
        j = idx - 1
        ok = (j >= 0) & (j < n)
        v = np.full(len(idx), np.nan); v[ok] = arr[j[ok]]
        return v
    B = (s_sec - 1) * 10 - A["b0"]
    with np.errstate(all="ignore"):
        mid = (A["bid"] + A["ask"]) / 2
        imb = (A["bq"] - A["aq"]) / (A["bq"] + A["aq"])
        imb5 = (A["bq5"] - A["aq5"]) / (A["bq5"] + A["aq5"])
        micro = (A["bid"] * A["aq"] + A["ask"] * A["bq"]) / (A["bq"] + A["aq"])
        m1, m10, m20, m30 = at(mid, B), at(mid, B - 10), at(mid, B - 20), at(mid, B - 30)
        out["BK_imb"] = at(imb, B); out["BK_imb5"] = at(imb5, B)
        out["BK_imb_avg1"] = np.nanmean(np.vstack([at(imb, B - k) for k in range(10)]), 0)
        out["BK_imb5_avg1"] = np.nanmean(np.vstack([at(imb5, B - k) for k in range(10)]), 0)
        out["BK_imb_d1"] = at(imb, B) - at(imb, B - 10)
        out["BK_micro"] = 1e4 * (at(micro, B) / m1 - 1)
        out["BK_mid1"] = 1e4 * np.log(m1 / m10); out["BK_mid3"] = 1e4 * np.log(m1 / m30); out["BK_mid_d21"] = 1e4 * np.log(m10 / m20)
        out["BK_spread"] = 1e4 * (at(A["ask"], B) - at(A["bid"], B)) / m1
        out["BK_imb_l1"] = np.nanmean(np.vstack([at(imb, B - 10 - k) for k in range(10)]), 0)
        out["BK_imb_l2"] = np.nanmean(np.vstack([at(imb, B - 20 - k) for k in range(10)]), 0)
        out["BK_imb5_l1"] = np.nanmean(np.vstack([at(imb5, B - 10 - k) for k in range(10)]), 0)
        out["BK_imb5_l2"] = np.nanmean(np.vstack([at(imb5, B - 20 - k) for k in range(10)]), 0)
        out["BK_imb_last3"] = np.nanmean(np.vstack([at(imb, B - k) for k in range(3)]), 0)
        out["BK_mid_d32"] = 1e4 * np.log(m20 / m30)
    return {k: np.asarray(v, np.float32) for k, v in out.items()}

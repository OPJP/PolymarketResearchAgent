"""Iteration 13 (PRE-REGISTRATION 4, X113 step 6): exam route of the DECISION-CLOCK side, imported by final_rule.evaluate().

For every cluster taker order (fills role T, one per (tx, wallet, token)) the matching-engine ms m is read from the public CC0 capture
Fahri-5/updown-5m-polymarket-raw (revision pinned below: trade rows, exchangeTimestampMs by transactionHash); the decision instant
is a = m - 180 ms (150-ms taker delay + 30-ms posting latency). Features at a, all from the same capture's btc/ day file (Binance
spot BTCUSDT book on the collector's receive clock): microprice and mid returns over [a - K, a) for K = 100 / 250 / 500 / 1000 /
2000 ms, and rel (s since the window start). Frozen model: model_it13_dcside_spot.txt (LightGBM, fitted on the 10-17..19 operator
taker orders; 10-20..22: 74.2% per order, DS 72.1 / GF 77.8 / XM 78.1%, XM one-sided windows 81.4%). Only row groups whose
time statistics overlap the evaluation period are read (HTTP range requests, coalesced, 429 backoff). A development run never
opens a day file that starts at or after H; only the examiner's driver (allow_sealed=True) reaches those days."""
import io, os, time
import numpy as np, pandas as pd

H = 1792713600
REPO = "Fahri-5/updown-5m-polymarket-raw"
REV = "f848a77ccfce4421d3cedbbe585576db77d36662"
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_it13_dcside_spot.txt")
KS = (100, 250, 500, 1000, 2000)
DECISION_LAG_MS = 180


class _RF(io.RawIOBase):
    def __init__(self, cl, url, size):
        self.cl, self.url, self.size, self.pos, self.cache = cl, url, size, 0, []

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, wh=0):
        self.pos = off if wh == 0 else (self.pos + off if wh == 1 else self.size + off)
        return self.pos

    def fetch(self, a, e):
        for k in range(10):
            try:
                r = self.cl.get(self.url, headers={"Range": f"bytes={a}-{e}"})
                r.raise_for_status()
                return r.content
            except Exception as ex:
                if k == 9:
                    raise
                time.sleep(45 if "429" in str(ex) else 2 * (k + 1))

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        for c0, cb in self.cache:
            if c0 <= self.pos and self.pos + n <= c0 + len(cb):
                b = cb[self.pos - c0:self.pos - c0 + n]; self.pos += len(b); return b
        b = self.fetch(self.pos, min(self.pos + n, self.size) - 1); self.pos += len(b)
        return b

    def readinto(self, buf):
        b = self.read(len(buf)); buf[:len(b)] = b
        return len(b)


def _read(cl, sub, day, cols, tcol, t0, t1):
    import pyarrow as pa, pyarrow.parquet as pq
    url = f"https://huggingface.co/datasets/{REPO}/resolve/{REV}/{sub}/{day}.parquet"
    h = cl.head(url)
    if h.status_code != 200:
        return None
    size = int(h.headers["content-length"])
    md = pq.ParquetFile(_RF(cl, url, size)).metadata
    names = [md.schema.column(j).path for j in range(md.num_columns)]
    jt = names.index(tcol)
    parts = []
    for i in range(md.num_row_groups):
        st = md.row_group(i).column(jt).statistics
        if st is None or not st.has_min_max or st.max < t0 or st.min > t1:
            continue
        f = _RF(cl, url, size); rg = md.row_group(i); rr = []
        for j in range(rg.num_columns):
            c = rg.column(j)
            if c.path_in_schema.split(".")[0] in cols:
                a0 = c.dictionary_page_offset if c.has_dictionary_page and c.dictionary_page_offset else c.data_page_offset
                rr.append([a0, a0 + c.total_compressed_size])
        rr.sort(); mg = []
        for a, e in rr:
            if mg and a - mg[-1][1] <= 65536:
                mg[-1][1] = max(mg[-1][1], e)
            else:
                mg.append([a, e])
        for a, e in mg:
            f.cache.append((a, f.fetch(a, e - 1)))
        parts.append(pq.ParquetFile(f, metadata=md).read_row_group(i, columns=cols).to_pandas())
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)


def _at(T, X, tt):
    i = np.searchsorted(T, tt, "right") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def decision_clock_side(fills: pd.DataFrame, start_ts: int, end_ts: int, allow_sealed: bool = False) -> dict | None:
    import httpx, lightgbm as lgb
    if fills is None or not len(fills):
        return None
    f = fills[fills.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy()
    if not len(f):
        return None
    cl = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "research-exam-route"})
    lo_ms, hi_ms = (int(start_ts) - 70) * 1000, (int(end_ts) + 400) * 1000
    mt, books, days_read = {}, [], []
    for d0 in range((int(start_ts) // 86400 - 1) * 86400, int(end_ts) + 86400, 86400):
        if d0 + 86400 > H and not allow_sealed:
            continue  # development runs never open a day file that starts at or after H
        day = time.strftime("%Y-%m-%d", time.gmtime(d0))
        t = _read(cl, "polymarket", day, ["eventType", "exchangeTimestampMs", "transactionHash"], "exchangeTimestampMs", lo_ms, hi_ms)
        if t is None or not len(t):
            continue
        days_read.append(day)
        t = t[t.eventType == "last_trade_price"]
        for h, m in zip(t.transactionHash.str.lower(), t.exchangeTimestampMs):
            if h and (h not in mt or m < mt[h]):
                mt[h] = int(m)
        b = _read(cl, "btc", day, ["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"], "receivedTimestampMs", lo_ms - 3000, hi_ms)
        if b is not None and len(b):
            books.append(b[b.type == "book"])
    if not mt or not books:
        return {"orders": int(len(f)), "matched": 0, "days_read": days_read}
    bk = pd.concat(books, ignore_index=True).sort_values("receivedTimestampMs", kind="stable")
    Tb = bk.receivedTimestampMs.to_numpy(np.int64)
    mic = ((bk.bidPrice * bk.askQuantity + bk.askPrice * bk.bidQuantity) / (bk.bidQuantity + bk.askQuantity)).to_numpy(float)
    mid = ((bk.bidPrice + bk.askPrice) / 2).to_numpy(float)
    f["m"] = f.tx.str.lower().map(mt)
    n_all = len(f)
    f = f[f.m.notna()].copy()
    if not len(f):
        return {"orders": int(n_all), "matched": 0, "days_read": days_read}
    a = f.m.to_numpy(np.int64) - DECISION_LAG_MS
    X = pd.DataFrame({"rel": a / 1000.0 - f.start_ts.to_numpy(float)})
    for nm, S in (("mic", mic), ("mid", mid)):
        x0 = _at(Tb, S, a)
        for K in KS:
            r = (x0 / _at(Tb, S, a - K) - 1) * 1e4
            r[(a - K < Tb[0])] = np.nan
            X[f"bs_{nm}_{K}"] = r.astype(np.float32)
    mdl = lgb.Booster(model_file=MODEL)
    p = mdl.predict(X[mdl.feature_name()])
    up = f.is_up.to_numpy(bool); ok = (p > 0.5) == up
    wal = f.wallet.to_numpy(); st = f.start_ts.to_numpy(np.int64)
    out = {"orders": int(n_all), "matched": int(len(f)), "match_coverage": round(len(f) / n_all, 4), "days_read": days_read,
           "accuracy_per_order": round(float(ok.mean()), 4),
           "by_wallet": {w: [round(float(ok[wal == w].mean()), 4), int((wal == w).sum())] for w in ("DS", "GF", "XM") if (wal == w).any()}}
    us = np.unique(st); mid_st = us[len(us) // 2] if len(us) else 0
    out["halves"] = {"first": round(float(ok[st < mid_st].mean()), 4) if (st < mid_st).any() else None, "second": round(float(ok[st >= mid_st].mean()), 4) if (st >= mid_st).any() else None}
    g = pd.DataFrame({"cid": f.cid.to_numpy(), "w": wal, "up": up.astype(int), "p": p, "st": st})
    one = {}
    for w in ("DS", "GF", "XM"):
        x = g[g.w == w].groupby("cid").agg(up=("up", "mean"), p=("p", "mean"), st=("st", "first"))
        if len(x):
            o = x[(x.up == 0) | (x.up == 1)]
            okw = (o.p > 0.5).astype(int) == o.up.astype(int)
            one[w] = {"windows": int(len(x)), "one_sided_share": round(float(len(o) / len(x)), 4),
                      "one_sided_window_side_acc": round(float(okw.mean()), 4) if len(o) else None,
                      "one_sided_window_side_acc_halves": [round(float(okw[o.st < mid_st].mean()), 4) if (o.st < mid_st).any() else None,
                                                           round(float(okw[o.st >= mid_st].mean()), 4) if (o.st >= mid_st).any() else None]}
    out["one_sided_windows"] = one
    return out

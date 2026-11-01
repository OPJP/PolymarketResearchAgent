"""Iteration 15 (pivot: depth-limited execution; mechanics P1 / information P5 = X140 / X144): reduce one DEVELOPMENT day of the
public capture Fahri-5/updown-5m-polymarket-raw (pinned revision f848a77c) to the ASK-side L2 book of every BTC 5m token, read by HTTP
range requests row group by row group (columns eventType, exchangeTimestampMs, tokenId, askPrice, askSize, bestAsk, asks only;
<= 2 threads; nothing raw is stored). The market channel mirrors the two outcomes (an Up ask at p is a Down bid at 1 - p), so the
askPrice / askSize rows of both tokens give the asks of both tokens. Per token, the book (cent levels 1..100; sub-cent rows are
counted and dropped) is rebuilt from the 'book' snapshots plus the 'price_change' level sizes, and sampled (state after every event
with exchange ms <= t):
  (a) at three instants of every operator taker order (role T fill, one per (tx, wallet, token)) with a capture match ms m:
      t = m - 1 (the book the order met), m - 150 (arrival), m - 180 (the bot's view): the full 100-level ask vector;
  (b) on a 50-ms grid from window start - 60 s to window end, for both tokens: best ask and the cumulative ask depth at best + 0..4 c.
Validation: the reconstructed best ask against the capture's own bestAsk after each ask row.
Days >= 2026-10-23 are refused. Usage: python -I l2ingest15.py DAY HF_DIR OUT_DIR [threads]"""
import sys, io, time, json, os
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
import pyarrow.parquet as pq, pyarrow.compute as pc

DAY, HF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
TH = int(sys.argv[4]) if len(sys.argv) > 4 else 2
assert DAY < "2026-10-23", "sealed day refused"
ROOT = os.getcwd()
C = ROOT + "/.cache/re/btc5m-bot"
src = open(HF + "/../hfingest13.py").read().split("def main():")[0]
src = src.replace("SHA = sys.argv[5] if len(sys.argv) > 5 else None", "SHA=None").replace("DAY, OUT = sys.argv[1], sys.argv[2]", "DAY, OUT='2026-10-20','x'").replace(
    "TH = int(sys.argv[3]) if len(sys.argv) > 3 else 6", "TH=1").replace("CONF = sys.argv[4] if len(sys.argv) > 4 else \"polymarket\"", "CONF='polymarket'").replace(
    'assert DAY < "2026-10-23", "sealed day refused"', "")
g = {}; exec(src, g)
cl, RangeFile = g["cl"], g["RangeFile"]
SHA = "f848a77ccfce4421d3cedbbe585576db77d36662"
NL = 101  # cent levels 0..100 (0 unused)
GRID_MS = 50


def main():
    t0 = time.time()
    d0 = int(pd.Timestamp(DAY, tz="UTC").timestamp()); d0ms = d0 * 1000
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
    win = win[(win.start_ts >= d0 - 3600) & (win.start_ts < d0 + 86400 + 3600)].reset_index(drop=True)
    toks = {}
    rows_tok = []
    for r in win.itertuples():
        for s, tk in ((1, r.up_token), (0, r.down_token)):
            toks[str(tk)] = len(rows_tok); rows_tok.append((str(tk), r.cid, s, int(r.start_ts)))
    NT = len(rows_tok)
    tok_start = np.array([x[3] for x in rows_tok], np.int64)
    # operator taker orders of windows starting this day with a capture match ms
    tr = pd.read_parquet(f"{HF}/pm_trades_{DAY}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "start_ts", "token", "is_up", "shares", "oh", "cid", "price"])
    fl = fl[(fl.start_ts >= d0) & (fl.start_ts < d0 + 86400) & (fl.role == "T")].drop_duplicates(["tx", "wallet", "token"]).copy()
    fl["m"] = fl.tx.str.lower().map(mt)
    fl = fl[fl.m.notna()].copy(); fl["m"] = fl.m.astype(np.int64)
    fl["ti"] = fl.token.astype(str).map(toks)
    fl = fl[fl.ti.notna()].copy(); fl["ti"] = fl.ti.astype(np.int64)
    fl = fl.sort_values("m", kind="stable").reset_index(drop=True)
    QOFF = tuple(int(x) for x in os.environ.get('L2_QOFF', '1,150,180').split(','))
    NQO = len(QOFF)
    # query table: (time, token, kind, slot); kind 0 = order query (slot = order row * 3 + j), 1 = grid (slot = grid row)
    qt, qtok, qslot, qkind = [], [], [], []
    for j, off in enumerate(QOFF):
        qt.append(fl.m.to_numpy() - off); qtok.append(fl.ti.to_numpy().astype(np.int32)); qslot.append((np.arange(len(fl)) * NQO + j).astype(np.int32)); qkind.append(np.zeros(len(fl), np.int8))
    ngrid = 0 if os.environ.get('L2_NOGRID') else (360000) // GRID_MS
    gk = np.arange(ngrid, dtype=np.int64)
    gtimes = (tok_start[:, None] * 1000 - 60000 + GRID_MS * gk[None, :])  # NT x ngrid
    qt.append(gtimes.ravel()); del gtimes; qtok.append(np.repeat(np.arange(NT, dtype=np.int32), ngrid)); qslot.append(np.arange(NT * ngrid, dtype=np.int32)); qkind.append(np.ones(NT * ngrid, np.int8))
    qt = np.concatenate(qt); qtok = np.concatenate(qtok); qslot = np.concatenate(qslot); qkind = np.concatenate(qkind)
    o = np.argsort(qt, kind='stable'); qt, qtok, qslot, qkind = qt[o], qtok[o], qslot[o], qkind[o]; del o
    ord_vec = np.zeros((len(fl) * NQO, NL), np.float32)
    grid_best = np.zeros(NT * ngrid, np.int8)
    grid_cum = np.zeros((NT * ngrid, 5), np.float32)
    state = np.zeros((NT, NL), np.float32)
    seen = np.zeros(NT, bool)

    def answer(qsel, tk, vecs):
        """vecs: (len(qsel), NL) states for queries qsel of token tk."""
        k = qkind[qsel]; sl = qslot[qsel]
        if (k == 0).any():
            ord_vec[sl[k == 0]] = vecs[k == 0]
        if (k == 1).any():
            v = vecs[k == 1]; s = sl[k == 1]
            pos = v[:, 1:] > 0
            has = pos.any(1)
            b = np.where(has, pos.argmax(1) + 1, 0)
            grid_best[s] = b
            cs = np.cumsum(v, 1)
            for kk in range(5):
                hi = np.clip(b + kk, 0, NL - 1)
                grid_cum[s, kk] = np.where(has, cs[np.arange(len(b)), hi] - cs[np.arange(len(b)), np.clip(b - 1, 0, NL - 1)], 0)

    sz = int(cl.head(f"https://huggingface.co/datasets/Fahri-5/updown-5m-polymarket-raw/resolve/{SHA}/polymarket/{DAY}.parquet").headers["content-length"])
    url = f"https://huggingface.co/datasets/Fahri-5/updown-5m-polymarket-raw/resolve/{SHA}/polymarket/{DAY}.parquet"
    md = pq.ParquetFile(RangeFile(url, sz)).metadata
    nrg = md.num_row_groups
    cols = ["eventType", "exchangeTimestampMs", "tokenId", "askPrice", "askSize", "bestAsk", "asks"]
    stats = {"bytes": 0, "ask_rows": 0, "subcent": 0, "snap": 0, "val_n": 0, "val_ok": 0, "other_tok_rows": 0}

    def fetch(i):
        f = RangeFile(url, sz); rg = md.row_group(i); rr = []
        for j in range(rg.num_columns):
            cc = rg.column(j)
            if cc.path_in_schema.split(".")[0] in cols:
                a0 = cc.dictionary_page_offset if cc.has_dictionary_page and cc.dictionary_page_offset else cc.data_page_offset
                rr.append((a0, a0 + cc.total_compressed_size))
        f.prefetch(rr)
        t = pq.ParquetFile(f, metadata=md).read_row_group(i, columns=cols)
        f.cache = []
        stats["bytes"] += f.nbytes
        ev = t.column("eventType")
        keep = pc.or_(pc.and_(pc.equal(ev, "price_change"), pc.invert(pc.is_null(t.column("askPrice")))), pc.equal(ev, "book"))
        t = t.filter(keep)
        return i, t

    qp = 0  # query pointer (queries sorted by time)
    NQ = len(qt)
    with ThreadPoolExecutor(TH) as ex:
        for k, (i, t) in enumerate(ex.map(fetch, range(nrg))):
            d = t.to_pandas()
            del t
            d["ti"] = d.tokenId.map(toks)
            stats["other_tok_rows"] += int(d.ti.isna().sum())
            d = d[d.ti.notna()]
            if len(d) == 0:
                continue
            d["ti"] = d.ti.astype(np.int64)
            d = d.sort_values("exchangeTimestampMs", kind="stable")
            lo, hi = int(d.exchangeTimestampMs.iloc[0]), int(d.exchangeTimestampMs.iloc[-1])
            # queries strictly before this row group's first event: answered from the carried state
            j1 = np.searchsorted(qt, lo, "left")
            if j1 > qp:
                sel = np.arange(qp, j1)
                for tk in np.unique(qtok[sel]):
                    s2 = sel[qtok[sel] == tk]
                    answer(s2, tk, np.repeat(state[tk][None, :], len(s2), 0))
                qp = j1
            j2 = np.searchsorted(qt, hi, "right")  # queries answered inside this row group
            sel_all = np.arange(qp, j2)
            for tk, x in d.groupby("ti", sort=False):
                ts = x.exchangeTimestampMs.to_numpy(np.int64)
                isb = (x.eventType == "book").to_numpy()
                px = x.askPrice.to_numpy(float); zz = x.askSize.to_numpy(float)
                n = len(x)
                M = np.full((n + 1, NL), np.nan, np.float32)
                M[0] = state[tk]
                if isb.any():
                    stats["snap"] += int(isb.sum())
                    for r_i in np.nonzero(isb)[0]:
                        row = np.zeros(NL, np.float32)
                        al = x.asks.iloc[r_i]
                        if al is not None:
                            for lv in al:
                                p_, s_ = float(lv["price"]), float(lv["size"])
                                c_ = int(round(p_ * 100))
                                if abs(p_ * 100 - c_) < 1e-6 and 1 <= c_ <= 100:
                                    row[c_] = s_
                        M[r_i + 1] = row
                ch = ~isb
                cpx = np.round(px * 100)
                okc = ch & (np.abs(px * 100 - cpx) < 1e-6) & (cpx >= 1) & (cpx <= 100)
                stats["subcent"] += int((ch & ~okc).sum()); stats["ask_rows"] += int(ch.sum())
                rr_ = np.nonzero(okc)[0]
                M[rr_ + 1, cpx[rr_].astype(np.int64)] = zz[rr_].astype(np.float32)
                # snapshot rows reset every level: forward fill must not carry across them -> rows already full
                M = pd.DataFrame(M).ffill().to_numpy(np.float32)
                M = np.nan_to_num(M, nan=0.0)
                state[tk] = M[-1]; seen[tk] = True
                # validation: best ask after each ask row vs the capture's bestAsk
                ba = x.bestAsk.to_numpy(float)
                vv = np.nonzero(okc & ~np.isnan(ba))[0]
                if len(vv) > 4000:
                    vv = vv[:: len(vv) // 4000]
                if len(vv):
                    pos = M[vv + 1, 1:] > 0
                    b = np.where(pos.any(1), pos.argmax(1) + 1, 0)
                    stats["val_n"] += len(vv); stats["val_ok"] += int((b == np.round(ba[vv] * 100)).sum())
                # queries of this token inside [lo, hi]
                s2 = sel_all[qtok[sel_all] == tk]
                if len(s2):
                    idx = np.searchsorted(ts, qt[s2], "right")  # number of events with ts <= q -> row idx in M
                    answer(s2, tk, M[idx])
                del M
            # queries of tokens absent from this row group: carried state
            if len(sel_all):
                pres = set(d.ti.unique().tolist())
                s3 = sel_all[~np.isin(qtok[sel_all], list(pres))]
                for tk in np.unique(qtok[s3]):
                    s4 = s3[qtok[s3] == tk]
                    answer(s4, tk, np.repeat(state[tk][None, :], len(s4), 0))
            qp = j2
            if k % 50 == 0:
                print(k, nrg, round(stats["bytes"] / 1e6), "MB", round(time.time() - t0), "s", "val", stats["val_ok"], stats["val_n"], flush=True)
    if qp < NQ:
        sel = np.arange(qp, NQ)
        for tk in np.unique(qtok[sel]):
            s2 = sel[qtok[sel] == tk]
            answer(s2, tk, np.repeat(state[tk][None, :], len(s2), 0))
    # outputs
    ov = ord_vec.reshape(len(fl), NQO, NL)
    od = fl[["tx", "wallet", "token", "is_up", "shares", "oh", "cid", "price", "m", "start_ts"]].copy()
    SUF = os.environ.get("L2_SUF", "")
    np.save(f"{OUT}/l2ord{SUF}_{DAY}.npy", ov.astype(np.float32))
    od.to_parquet(f"{OUT}/l2ord{SUF}_{DAY}.parquet", index=False)
    json.dump(list(QOFF), open(f"{OUT}/l2ord{SUF}_{DAY}_qoff.json", "w"))
    if ngrid == 0:
        print("DONE (no grid)", flush=True); return
    gtab = pd.DataFrame({"ti": np.repeat(np.arange(NT), ngrid).astype(np.int32), "k": np.tile(gk, NT).astype(np.int32), "best": grid_best})
    for kk in range(5):
        gtab[f"c{kk}"] = grid_cum[:, kk]
    gtab.to_parquet(f"{OUT}/l2grid_{DAY}.parquet", index=False)
    pd.DataFrame(rows_tok, columns=["token", "cid", "is_up", "start_ts"]).to_parquet(f"{OUT}/l2tok_{DAY}.parquet", index=False)
    info = {"day": DAY, "sha": SHA, "orders": len(fl), "tokens": NT, "tokens_seen": int(seen.sum()), "MB": round(stats["bytes"] / 1e6, 1), "s": round(time.time() - t0),
            **{k2: v for k2, v in stats.items() if k2 != "bytes"}, "val_share": round(stats["val_ok"] / max(stats["val_n"], 1), 5)}
    json.dump(info, open(f"{OUT}/l2ingest_{DAY}.json", "w"))
    print("DONE", json.dumps(info), flush=True)


if __name__ == "__main__":
    main()

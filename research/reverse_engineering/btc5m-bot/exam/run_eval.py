"""Examiner r1 driver: runs the FROZEN code/final_rule.evaluate() unchanged on chunks of the h1 lot.

No file in code/ is edited. From this driver only:
  - final_rule.ALLOW_SEALED = True (the examiner switch the rule exposes);
  - final_rule.EVAL_DIR -> .cache/exam/btc5m-bot/eval (so no sealed archive / tape lands in the RE's .cache/re/btc5m-bot);
  - POLYREA_CACHE_DIR must be .cache/exam/btc5m-bot (checked), so the shared HTTP cache never holds sealed data;
  - read-only instrumentation: wrappers that SAVE intermediate arrays (fills, windows, the cell frame, model predictions, the
    tracker target flows, the hazard frame, decoded calldata) to .cache/exam/btc5m-bot/chunks/<a>_<b>/ and return the original
    result unchanged; a disk memo of the public HF capture row groups (dc_exam13._read) that returns exactly the rows the original
    returns to its consumers (polymarket rows are kept only for eventType == last_trade_price, the only rows any consumer uses).
Usage: python run_eval.py A B [A B ...]   (each pair = one chunk [A, B), evaluated with intervals=[(A, B)])."""
import os, sys, json, time, pickle, ctypes
from ctypes import wintypes
assert os.environ.get("POLYREA_CACHE_DIR", "").replace("\\", "/").rstrip("/").endswith(".cache/exam/btc5m-bot"), "set POLYREA_CACHE_DIR=.cache/exam/btc5m-bot"
ROOT = os.getcwd()
CODE = f"{ROOT}/research/reverse_engineering/btc5m-bot/code"
EX = f"{ROOT}/.cache/exam/btc5m-bot"
sys.path.insert(0, CODE); sys.path.insert(0, ROOT)
import numpy as np, pandas as pd

import final_rule as fr
import dc_exam13 as d13
import dc_hazard14 as hz
import calldata as cdm

fr.ALLOW_SEALED = True
fr.EVAL_DIR = f"{EX}/eval"
os.makedirs(fr.EVAL_DIR, exist_ok=True)
CAP = f"{EX}/capture"; os.makedirs(CAP, exist_ok=True)


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def mem_mb():
    k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = wintypes.HANDLE
    p = PMC(); p.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(k.GetCurrentProcess()), ctypes.byref(p), p.cb)
    return round(p.PeakWorkingSetSize / 1e6), round(p.WorkingSetSize / 1e6)


# ------------------------------------------------------------------ capture memo (exact semantics of dc_exam13._read)
UNION = {"polymarket": ["eventType", "exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSide", "tradeSize"],
         "btc": ["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price", "quantity", "isBuyerMaker"]}
_META = {}
_MD = {}
_orig_read = d13._read


def _meta(cl, sub, day):
    k = (sub, day)
    if k in _META:
        return _META[k]
    mp = f"{CAP}/{sub}_{day}_meta.pkl"
    if os.path.exists(mp):
        _META[k] = pickle.load(open(mp, "rb")); return _META[k]
    import pyarrow.parquet as pq
    url = f"https://huggingface.co/datasets/{d13.REPO}/resolve/{d13.REV}/{sub}/{day}.parquet"
    h = cl.head(url)
    if h.status_code != 200:
        _META[k] = None; return None
    size = int(h.headers["content-length"])
    md = pq.ParquetFile(d13._RF(cl, url, size)).metadata
    names = [md.schema.column(j).path for j in range(md.num_columns)]
    stats = {}
    for tcol in ("exchangeTimestampMs", "receivedTimestampMs"):
        if tcol in names:
            jt = names.index(tcol); lst = []
            for i in range(md.num_row_groups):
                st = md.row_group(i).column(jt).statistics
                lst.append((st is not None and st.has_min_max, st.min if st is not None and st.has_min_max else None, st.max if st is not None and st.has_min_max else None))
            stats[tcol] = lst
    M = {"url": url, "size": size, "stats": stats, "n_rg": md.num_row_groups}
    pickle.dump(M, open(mp, "wb")); _META[k] = M
    return M


def _rg(cl, sub, day, M, i):
    p = f"{CAP}/{sub}_{day}_rg{i}.parquet"
    if os.path.exists(p):
        return p
    import pyarrow.parquet as pq
    url, size = M["url"], M["size"]
    if url not in _MD:
        _MD[url] = pq.ParquetFile(d13._RF(cl, url, size)).metadata
    md = _MD[url]
    f = d13._RF(cl, url, size); rg = md.row_group(i); rr = []
    cols = UNION[sub]
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
    present = [c for c in cols if c in [md.schema.column(j).path for j in range(md.num_columns)]]
    df = pq.ParquetFile(f, metadata=md).read_row_group(i, columns=present).to_pandas()
    if sub == "polymarket":
        df = df[df.eventType == "last_trade_price"].reset_index(drop=True)
    df.to_parquet(p + ".tmp", index=False); os.replace(p + ".tmp", p)
    return p


def memo_read(cl, sub, day, cols, tcol, t0, t1):
    if sub not in UNION or any(c not in UNION[sub] for c in cols):
        return _orig_read(cl, sub, day, cols, tcol, t0, t1)
    M = _meta(cl, sub, day)
    if M is None:
        return None
    idx = [i for i, (has, mn, mx) in enumerate(M["stats"][tcol]) if has and not (mx < t0 or mn > t1)]
    todo = [i for i in idx if not os.path.exists(f"{CAP}/{sub}_{day}_rg{i}.parquet")]
    if todo:  # prefetch missing row groups in parallel (each with its own range client); order of the result is unchanged
        import httpx
        from concurrent.futures import ThreadPoolExecutor
        _rg(cl, sub, day, M, todo[0])  # loads the footer once
        def one(i, _c={}):
            import threading
            k = threading.get_ident()
            if k not in _c:
                _c[k] = httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "research-exam-route"})
            return _rg(_c[k], sub, day, M, i)
        with ThreadPoolExecutor(4) as ex:
            list(ex.map(one, todo[1:]))
    parts = [pd.read_parquet(f"{CAP}/{sub}_{day}_rg{i}.parquet", columns=cols) for i in idx]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)


d13._read = memo_read

# ------------------------------------------------------------------ read-only instrumentation
CUR = {"dir": None, "pred": {}, "trk": [], "trk_res": []}
_o = {k: getattr(fr, k) for k in ("cluster_fills", "load_windows", "_predict", "_predict_named", "_block_keep", "_strict_tracker")}
_o_tf = cdm.to_frame


def w_cluster_fills(a, b, win):
    f = _o["cluster_fills"](a, b, win)
    f.to_parquet(f"{CUR['dir']}/fills.parquet", index=False)
    return f


def w_load_windows(a, b):
    w = _o["load_windows"](a, b)
    w.to_parquet(f"{CUR['dir']}/windows_all.parquet", index=False)
    return w


def w_predict(model_file, df, cols, chunk=200_000):
    p = _o["_predict"](model_file, df, cols, chunk)
    CUR["pred"].setdefault(os.path.basename(model_file), []).append(np.asarray(p, np.float32))
    return p


def w_predict_named(model_file, df, chunk=200_000):
    p = _o["_predict_named"](model_file, df, chunk)
    nm = os.path.basename(model_file)
    CUR["pred"].setdefault(nm, []).append(np.asarray(p, np.float32))
    if nm == os.path.basename(fr.MODEL_DP_FULL) and not os.path.exists(f"{CUR['dir']}/cells.parquet"):
        c = df.copy()
        for k in c.columns:
            if c[k].dtype == np.float64:
                c[k] = c[k].astype(np.float32)
        c.to_parquet(f"{CUR['dir']}/cells.parquet", index=False); del c
    return p


def w_block_keep(t, pairs):
    k = _o["_block_keep"](t, pairs)
    np.save(f"{CUR['dir']}/block_keep.npy", k)
    return k


def w_strict_tracker(up, dn, flow, win, fills, conv="a"):
    r = _o["_strict_tracker"](up, dn, flow, win, fills, conv)
    CUR["trk"].append(np.asarray(flow, np.float32)); CUR["trk_res"].append({"conv": conv, "res": r})
    return r


def w_to_frame(rows):
    d = _o_tf(rows)
    try:
        keep = [c for c in d.columns if c not in ("input", "raw", "sig", "signature")]
        p = f"{CUR['dir']}/calldata.parquet"
        d[keep].to_parquet(p, index=False)
    except Exception as e:
        print("calldata save failed", repr(e)[:120], flush=True)
    return d


fr.cluster_fills = w_cluster_fills; fr.load_windows = w_load_windows; fr._predict = w_predict; fr._predict_named = w_predict_named
fr._block_keep = w_block_keep; fr._strict_tracker = w_strict_tracker; cdm.to_frame = w_to_frame


def run_chunk(a, b):
    d = f"{EX}/chunks/{a}_{b}"
    if os.path.exists(f"{d}/evaluate.json"):
        print("skip", a, b, flush=True); return
    os.makedirs(d, exist_ok=True)
    CUR.update({"dir": d, "pred": {}, "trk": [], "trk_res": []})
    t0 = time.time()
    res = fr.evaluate(a, b, intervals=[(a, b)])
    el = round(time.time() - t0, 1)
    np.savez_compressed(f"{d}/pred.npz", **{f"{k}__{i}": v for k, lst in CUR["pred"].items() for i, v in enumerate(lst)})
    np.savez_compressed(f"{d}/trk.npz", **{f"flow{i}_{x['conv']}": v for i, (v, x) in enumerate(zip(CUR["trk"], CUR["trk_res"]))})
    try:
        for key, val in list(hz._CACHE.items()):
            X, hs, days, nf = val
            if X is not None:
                X.to_parquet(f"{d}/hazard_rows.parquet", index=False)
            if hs is not None:
                hs.to_parquet(f"{d}/hazard_h.parquet", index=False)
    except Exception as e:
        print("hazard save failed", repr(e)[:200], flush=True)
    pk, ws = mem_mb()
    res["_exam"] = {"elapsed_s": el, "peak_working_set_mb": pk, "working_set_mb": ws}
    json.dump(res, open(f"{d}/evaluate.json", "w"), indent=1, default=str)
    tm = res.get("target_metrics") or {}
    print(f"chunk {a} {b} done {el}s peakMB {pk} err={res.get('historical_error')} presence={tm.get('presence_auc')} base={tm.get('presence_baseline')} "
          f"side={tm.get('side_accuracy')} pnl={tm.get('pnl_corr_pearson')}/{tm.get('pnl_corr_spearman')}", flush=True)


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:]]
    for a, b in zip(args[::2], args[1::2]):
        run_chunk(a, b)
    print("ALL DONE", flush=True)

"""Examiner r1: scan the RE's cache and workspace for sealed-unit data (filenames, parquet time ranges)."""
import os, re, sys, json, collections, pathlib
import pyarrow.parquet as pq
import numpy as np

H, T0 = 1792713600, 1793404800
sys.path.insert(0, "research/reverse_engineering/tools")
import sealed as S

roots = [".cache/re/btc5m-bot", "research/reverse_engineering/btc5m-bot"]
DATES = ["2026-10-%02d" % d for d in range(23, 31)] + ["202610%02d" % d for d in range(23, 31)]
TIMECOLS = ["ts", "timestamp", "T", "sec", "start_ts", "s", "m", "t", "block_ts", "sign_ms", "exchangeTimestampMs", "E", "ms"]
out = {"filename_hits": [], "parquet_hits": [], "dirs": {}}
for root in roots:
    for dp, dn, fn in os.walk(root):
        if "exam" in pathlib.Path(dp).parts and root.startswith("research"):
            continue
        k = pathlib.Path(dp).as_posix()
        out["dirs"][k] = out["dirs"].get(k, 0) + len(fn)
        for f in fn:
            p = (pathlib.Path(dp) / f).as_posix()
            for m in re.findall(r"(?<!\d)(\d{10})(?!\d)", f):
                v = int(m)
                if H <= v < T0:
                    out["filename_hits"].append(p)
            for d in DATES:
                if d in f:
                    out["filename_hits"].append(p)
            if f.endswith(".parquet"):
                try:
                    pf = pq.ParquetFile(p)
                    names = pf.schema_arrow.names
                    for c in TIMECOLS:
                        if c in names:
                            st = None
                            mx, mn = None, None
                            for rg in range(pf.num_row_groups):
                                s = pf.metadata.row_group(rg).column(names.index(c)).statistics
                                if s is None or not s.has_min_max:
                                    continue
                                try:
                                    a, b = float(s.min), float(s.max)
                                except Exception:
                                    continue
                                mn = a if mn is None else min(mn, a); mx = b if mx is None else max(mx, b)
                            if mx is None:
                                continue
                            # normalize to seconds
                            sc = 1.0
                            if mx > 1e14: sc = 1e6
                            elif mx > 1e11: sc = 1e3
                            lo, hi = mn / sc, mx / sc
                            if hi >= H and lo < 4102444800 and hi > 1.6e9:
                                out["parquet_hits"].append({"file": p, "col": c, "min": lo, "max": hi, "rows": pf.metadata.num_rows})
                            break
                except Exception as e:
                    pass
out["filename_hits"] = sorted(set(out["filename_hits"]))
json.dump(out, open(sys.argv[1], "w"), indent=1)
print("filename hits", len(out["filename_hits"]))
for h in out["filename_hits"][:60]:
    print("  ", h)
print("parquet files with max time >= H:", len(out["parquet_hits"]))
for h in out["parquet_hits"][:200]:
    print("  ", h["file"], h["col"], int(h["min"]), int(h["max"]), h["rows"])

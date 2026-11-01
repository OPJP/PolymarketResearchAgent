"""Iteration 10 (I9-2 = X88, step 1b): the quote-unit label from the OWN slim exam recorder dx_clob (code6/examrec.py,
which records schedule-size deltas within 3 ticks of the touch with server ms, for BTC 5m current+next and 15m current,
through the sealed blocks until 11-03 00:00) vs the raw-recorder label (it6/a4_secs_*), on the overlap 15:53-16:30 UTC
of 10-31 (development). dx label for (window, side, second t): a pc row in (t-1 s, t] with delta exactly +500 at the
touch of s (Up: side 1 at p = best bid; Down: side 0 = an Up ask at p = best ask, i.e. a Down bid at 1 - p)."""
import calendar
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import rawread  # noqa: E402
import sealed  # noqa: E402

C = ROOT / ".cache/re/directional-maker"


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def main():
    lab = pd.read_parquet(C / "it6/a4_secs_1793455600_1793464202.parquet")
    a = 1793461987
    lab = lab[lab.st >= (a // 300 + 1) * 300].copy()
    keys = {1: set(), 2: set()}
    nrec = 0
    for p in sorted((ROOT / ".cache/live/dev/dx_clob").glob("*.jsonl.gz")):
        hour = calendar.timegm(time.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= a or hour >= int(lab.st.max()) + 400:
            continue
        for chunk in rawread._members(p.read_bytes()):
            for line in chunk.split(b"\n"):
                if b'"k":"pc"' not in line or b"btc-updown-5m-" not in line:
                    continue
                r = json.loads(line)
                if sealed.future_block_sealed(r.get("t", 0) / 1000.0):
                    continue
                nrec += 1
                st = int(r["w"].rsplit("-", 1)[1])
                ms = int(r.get("s") or r.get("t"))
                sec = int(np.ceil(ms / 1000.0)) - st
                bb, ba = float(r.get("bb") or 0), float(r.get("ba") or 0)
                for side, px, z, d in r.get("c", []):
                    if abs(d - 500) > 0.01:
                        continue
                    if side == 1 and px >= bb - 1e-9:
                        keys[1].add((st, sec, 1))
                    if side == 0 and px <= ba + 1e-9:
                        keys[1].add((st, sec, 0))
                    if side == 1 and px >= bb - 0.0201:
                        keys[2].add((st, sec, 1))
                    if side == 0 and px <= ba + 0.0201:
                        keys[2].add((st, sec, 0))
    lab["key"] = list(zip(lab.st.astype(int), lab.rel.astype(int), lab.s_up.astype(int)))
    y = lab.y.to_numpy()
    out = {"cells": int(len(lab)), "windows": int(lab.st.nunique()), "raw_base_rate": float(y.mean()), "dx_records": nrec}
    for k in (1, 2):
        yy = lab.key.map(lambda x: x in keys[k]).to_numpy().astype(int)
        tp = int(((yy == 1) & (y == 1)).sum())
        near = lab.key.map(lambda x: any((x[0], x[1] + dd, x[2]) in keys[k] for dd in (-1, 0, 1))).to_numpy().astype(int)
        out[f"dx_L{k}"] = {"base_rate": float(yy.mean()), "precision": float(tp / max(yy.sum(), 1)), "recall": float(tp / max(y.sum(), 1)),
                           "recall_pm1s": float(((near == 1) & (y == 1)).sum() / max(y.sum(), 1)),
                           "auc_e_cl_dx_label": auc(yy, lab.e_cl.to_numpy()), "auc_e_cl_raw_label": auc(y, lab.e_cl.to_numpy())}
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "research/reverse_engineering/directional-maker/results/iter10_i92_dx.json", "w"), indent=1)


if __name__ == "__main__":
    main()

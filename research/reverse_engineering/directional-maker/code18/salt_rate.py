"""iteration 18, T18 = X216 step 1 light (mechanics panel P2; pre-registered in NOTES.md 13:30 UTC 11-01): does each wallet's
salt counter rate drop by the BTC 5m quantum (~3-4 orders/s) when the BTC 5m module switches off at 10-31 16:53:54 UTC
while the rest runs on? Data: the decoded calldata of the cluster's live fills on 10-31 (calldata/live1031_0002..0004,
~1,900 cluster orders, blocks 96,499,879-96,505,816), block times interpolated linearly between two eth_getBlockByNumber
calls. Per wallet: slope of salt on time (orders/s) over [16:23:54, 16:53:54) and over [16:53:54, 17:05:00) (before the
ad-hoc restarts), with a monotone filter (each wallet's counter is sequential). Reading: the post slope is lower by >= 2
orders/s in every wallet whose counter runs through the window -> the counter rate reads the module state; else not."""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpClient  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
SW = 1793465634  # 16:53:54 UTC 10-31


def block_time(hc, b):
    for url in ("https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"):
        try:
            r, _ = hc.post_json(url, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [hex(int(b)), False]}, adapter="polygon_rpc")
            return int(r["result"]["timestamp"], 16)
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("no block time")


def main():
    fr = [pd.read_parquet(f) for f in sorted(glob.glob(str(C / "calldata" / "live1031_000[2-4].parquet")))]
    X = pd.concat(fr, ignore_index=True)
    X = X[X.maker.str.lower().isin(CL)].copy()
    X["w"] = X.maker.str.lower().map(CL)
    X["salt"] = X.salt.astype(float)
    X = X.drop_duplicates(["w", "salt"])
    hc = HttpClient()
    b0, b1 = int(X.block.min()), int(X.block.max())
    t0, t1 = block_time(hc, b0), block_time(hc, b1)
    X["t"] = t0 + (X.block - b0) * (t1 - t0) / max(b1 - b0, 1)
    out = {"blocks": [b0, b1], "times_utc": [pd.Timestamp(t0, unit="s").strftime("%H:%M:%S"), pd.Timestamp(t1, unit="s").strftime("%H:%M:%S")],
           "sec_per_block": round((t1 - t0) / max(b1 - b0, 1), 4)}
    for w, g in X.groupby("w"):
        g = g.sort_values("t")
        rec = {"orders": int(len(g))}
        for nm, (a, b) in (("pre_30min", (SW - 1800, SW)), ("post_to_17_05", (SW, 1793466300)), ("post_17_05_17_35", (1793466300, 1793468100))):
            x = g[(g.t >= a) & (g.t < b)]
            if len(x) >= 6:
                # robust monotone fit: drop points that break the running max by > 10,000 (restarts / other counters)
                s = x.salt.to_numpy()
                tt = x.t.to_numpy()
                med = np.median(np.diff(s) / np.maximum(np.diff(tt), 1)) if len(s) > 2 else np.nan
                A = np.vstack([tt - tt.mean(), np.ones(len(tt))]).T
                coef, *_ = np.linalg.lstsq(A, s, rcond=None)
                res = s - A @ coef
                keep = np.abs(res) < 3 * np.median(np.abs(res)) + 1
                coef2, *_ = np.linalg.lstsq(A[keep], s[keep], rcond=None)
                rec[nm] = {"n": int(len(x)), "slope_orders_per_s": round(float(coef2[0]), 2), "median_pairwise": round(float(med), 2),
                           "monotone_share": round(float(np.mean(np.diff(s) > 0)), 2)}
            else:
                rec[nm] = {"n": int(len(x))}
        out[w] = rec
    drops = [out[w]["pre_30min"].get("slope_orders_per_s", np.nan) - out[w]["post_to_17_05"].get("slope_orders_per_s", np.nan) for w in CL.values() if w in out]
    out["drops"] = [round(float(d), 2) for d in drops]
    out["reading_met"] = bool(all(np.isfinite(d) and d >= 2 for d in drops))
    (HERE.parent / "results" / "iter18_salt_rate.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

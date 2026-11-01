"""iteration 18, T18 (X216 step 1 light) on the right data: the live1031 calldata ends at 16:29:40 UTC, so the switch-off
window is rebuilt from the cluster's own 10-31 activity (act15_*_1793448000_1793469600: trades with block timestamps and
transaction hashes) in [16:23:54, 17:05:00), whose transactions are decoded (code4/calldata.fetch_txs) for each wallet's
own order salt. Per wallet: the outlier-trimmed slope of salt on time before and after 16:53:54 UTC (same reading as
NOTES T18: a drop >= 2 orders/s in every wallet)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code4"))
import calldata as cd  # noqa: E402

C = HERE.parents[3] / ".cache/re/directional-maker"
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
SW, A, B = 1793465634, 1793463834, 1793466300


def slope(t, s):
    if len(t) < 5:
        return None
    Am = np.vstack([t - t.mean(), np.ones(len(t))]).T
    coef, *_ = np.linalg.lstsq(Am, s, rcond=None)
    res = s - Am @ coef
    keep = np.abs(res) < 3 * np.median(np.abs(res)) + 1
    coef2, *_ = np.linalg.lstsq(Am[keep], s[keep], rcond=None)
    return round(float(coef2[0]), 2)


def main():
    acts = []
    for ad, nm in CL.items():
        a = pd.read_parquet(C / f"act15_{nm}_1793448000_1793469600.parquet", columns=["timestamp", "type", "transactionHash"])
        a = a[(a.type == "TRADE") & (a.timestamp >= A) & (a.timestamp < B)]
        acts.append(a.assign(w=nm))
    Ac = pd.concat(acts, ignore_index=True)
    txs = list(dict.fromkeys(Ac.transactionHash.str.lower()))
    tmap = dict(zip(Ac.transactionHash.str.lower(), Ac.timestamp))
    rows = []
    for h, tx in cd.fetch_txs(txs):
        d = cd.decode(tx["input"]) if tx else None
        if not d:
            continue
        for o in d.get("makers", []) + ([d["taker"]] if d.get("taker") else []):
            mk = str(o.get("maker", "")).lower()
            if mk in CL:
                rows.append((CL[mk], int(tmap.get(h.lower(), 0)), float(o["salt"])))
    R = pd.DataFrame(rows, columns=["w", "t", "salt"]).drop_duplicates(["w", "salt"])
    out = {"tx": len(txs), "orders": int(len(R))}
    for w, g in R.groupby("w"):
        g = g.sort_values("t")
        pre, post = g[g.t < SW], g[g.t >= SW]
        out[w] = {"n_pre": int(len(pre)), "n_post": int(len(post)),
                  "slope_pre": slope(pre.t.to_numpy(float), pre.salt.to_numpy()), "slope_post": slope(post.t.to_numpy(float), post.salt.to_numpy()),
                  "salt_jump_across": float(post.salt.iloc[0] - pre.salt.iloc[-1]) if len(pre) and len(post) else None,
                  "gap_s_across": int(post.t.iloc[0] - pre.t.iloc[-1]) if len(pre) and len(post) else None}
    drops = [out[w]["slope_pre"] - out[w]["slope_post"] for w in CL.values() if w in out and out[w]["slope_pre"] is not None and out[w]["slope_post"] is not None]
    out["drops"] = drops
    out["reading_met"] = bool(len(drops) == 3 and all(d >= 2 for d in drops))
    (HERE.parent / "results" / "iter18_salt_rate2.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

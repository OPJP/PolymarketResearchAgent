"""Iteration 7, X95 step 4 (mechanics panel iter6 P4): sibling scan with the wallet's merge-loop law.

Wallets: the 30 makers with the most filled maker orders in the wallet's markets (calldata_all + calldata_pub, 16-22 Oct)
plus the feed subscribers (P4e, 0x2005d16a, 0xf1ee4842, 0x8a80528d, 0xddb6e624, P93). MERGE activity only, development
period [10-15, H), through the cached polyrea adapter. Law test: passes = merges <= 20 s apart; for consecutive passes
the phase residual r = (start1 - end0 - 307) mod 300 folded to [-150, 150); share with |r| <= 10 s (the wallet: 99.2%);
phase lock to the wallet: share of the sibling's pass starts within 10 s of (a wallet pass end + 307 + 300 k).
Output: results/merge_siblings.json
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
S0, H = 1792022400, 1792713600  # 10-15 00:00 .. H
SUBS = ["0x4ebc27222b1b9e6e5a5ff1b4c2a67b4eae2ca05a"]


def passes(ts):
    ts = np.sort(np.asarray(ts, float))
    if len(ts) == 0:
        return []
    P, cur = [], [ts[0]]
    for t in ts[1:]:
        if t - cur[-1] <= 20:
            cur.append(t)
        else:
            P.append((cur[0], cur[-1], len(cur)))
            cur = [t]
    P.append((cur[0], cur[-1], len(cur)))
    return P


def fold(x):
    return ((x + 150) % 300) - 150


def main():
    cols = ["maker", "idx"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])
    m = pd.concat([a, b])
    m = m[m.idx >= 0]
    m["maker"] = m.maker.str.lower()
    top = [x for x in m.maker.value_counts().index if x != W][:30]
    allm = set(m.maker)
    full = {x[:10]: x for x in allm}
    subs = [full.get(p) for p in ("0x4ebc2722", "0x2005d16a", "0xf1ee4842", "0x8a80528d", "0xddb6e624", "0x93078b5d")]
    # taker-only subscribers may not be makers: look them up from the taker rows
    t = pd.concat([pd.read_parquet(OUT / "calldata_all.parquet", columns=["maker", "idx"]),
                   pd.concat([pd.read_parquet(f, columns=["maker", "idx"]) for f in sorted(glob.glob(str(OUT / "calldata_pub/*.parquet")))])])
    tfull = {x[:10]: x for x in set(t.maker.str.lower())}
    subs = [s or tfull.get(p) for s, p in zip(subs, ("0x4ebc2722", "0x2005d16a", "0xf1ee4842", "0x8a80528d", "0xddb6e624", "0x93078b5d"))]
    wallets = list(dict.fromkeys([x for x in top + subs if x]))
    pm = PolymarketData()
    wr, _, _ = pm.activity(W, start=S0, end=H - 1, types=("MERGE",))
    wP = passes([r["timestamp"] for r in wr if r.get("type") == "MERGE"])
    w_end = np.array([p[1] for p in wP], float)
    res = {"wallet_passes": len(wP), "wallets": {}}
    for x in wallets:
        try:
            rows, _, _ = pm.activity(x, start=S0, end=H - 1, types=("MERGE",))
        except Exception as e:  # noqa: BLE001
            res["wallets"][x[:10]] = {"error": repr(e)[:120]}
            continue
        ts = [r["timestamp"] for r in rows if r.get("type") == "MERGE"]
        P = passes(ts)
        o = {"merges": len(ts), "passes": len(P)}
        if len(P) >= 5:
            r = np.array([fold(s1 - e0 - 307) for (_, e0, _), (s1, _, _) in zip(P[:-1], P[1:])])
            o["law_share_abs_r_le10"] = round(float((np.abs(r) <= 10).mean()), 3)
            st = np.array([p[0] for p in P], float)
            lock = []
            for s in st:
                j = np.searchsorted(w_end, s) - 1
                if j >= 0 and s - w_end[j] < 3600:
                    lock.append(abs(fold(s - w_end[j] - 307)) <= 10)
            o["phase_lock_share"] = round(float(np.mean(lock)), 3) if lock else None
            o["min_merge"] = round(float(min(float(r.get("size") or 0) for r in rows if r.get("type") == "MERGE")), 2)
        res["wallets"][x[:10]] = o
        print(x[:10], o, flush=True)
    (RES / "merge_siblings.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

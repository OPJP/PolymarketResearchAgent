"""Iteration 3, mechanics panel P5 (X29): a historical match-clock tape for the price anchor.

Public prints carry block time, 2-4 s after the CLOB match, while the CLOB publishes each trade at match time. For a
taker order signed at sign_ms, the in-play match happens at about sign_ms + 1,040 ms for fast signers (calibrated on
the 10-31 dev block: wallet 1,040, fast others 1,038-1,082; slow signers 2-4 s). Here: match_ms = min(block_ms,
taker sign_ms + 1,040) for every public taker tx of the wallet's VALIDATE markets (taker sign_ms from calldata_pub /
calldata_all; txs without calldata keep block time). Anchor = the last print with match_ms < the wallet's maker order
signing; price within one in-play tick (0.01 for mid-range prices) on VALIDATE maker orders, next to the block-time
anchor. The match-clock anchor can be up to ~3 s early for slow signers (a possible look-ahead), so it is reported
for the examiner to rule on, not adopted. Output: results/match_clock_price.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_clock import OUT, RES, WALLET  # noqa: E402

VAL0, H = 1792540800, 1792713600


def main():
    o = pd.read_parquet(OUT / "orders.parquet")
    mo = o[(o.role == "maker") & (o.gs_ts >= VAL0) & (o.gs_ts < H)].copy()
    parts = [pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx", "idx", "sign_ms", "maker"])]
    for p in (OUT / "calldata_pub").glob("*.parquet"):
        parts.append(pd.read_parquet(p, columns=["tx", "idx", "sign_ms", "maker"]))
    cd = pd.concat(parts)
    tks = cd[(cd.idx == -1) & (cd.sign_ms > 1.7e12) & (cd.sign_ms < 1.8e12)].drop_duplicates("tx").set_index("tx")
    own_tx = set(cd.loc[cd.maker == WALLET, "tx"])  # every tx with a wallet order (taker or maker): never a feature
    out = {"orders": int(len(mo))}
    rows = []
    cover = []
    for cid, g in mo.groupby("cid"):
        p = OUT / "tapes" / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        d = d[(d.proxyWallet.str.lower() != WALLET) & ~d.transactionHash.isin(own_tx)]
        if len(d) == 0:
            continue
        blk = d.timestamp.astype(float).to_numpy() * 1000
        sg = d.transactionHash.map(tks.sign_ms).to_numpy(float)
        cover.append(np.isfinite(sg).mean())
        mt = np.where(np.isfinite(sg), np.minimum(blk, sg + 1040), blk)
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        for lab, T in (("block", blk), ("match", mt)):
            order = np.argsort(T, kind="stable")
            Ts, Ps = T[order], p0[order]
            k = np.searchsorted(Ts, g.sign_ms.to_numpy(float), side="left") - 1
            lp = np.where(k >= 0, Ps[np.maximum(k, 0)], np.nan)
            lp = np.where(g.oi.to_numpy() == 0, lp, 1 - lp)
            for q, a in zip(g.price.to_numpy(), np.round(lp, 2)):
                rows.append((lab, q, a))
    x = pd.DataFrame(rows, columns=["clock", "p", "a"]).dropna()
    tick = np.where((x.a >= 0.04) & (x.a <= 0.96), 0.01, 0.001)
    x["ok"] = np.abs(x.p - x.a) <= tick + 1e-9
    x["exact"] = np.abs(x.p - x.a) <= 0.001 + 1e-9
    out["calldata_sign_coverage_of_prints"] = round(float(np.mean(cover)), 3) if cover else None
    for lab, g in x.groupby("clock"):
        out[lab] = {"n": int(len(g)), "within_tick": round(float(g.ok.mean()), 3), "exact": round(float(g.exact.mean()), 3),
                    "price_minus_anchor_cents": {str(int(k)): round(float(v), 3) for k, v in
                                                 ((g.p - g.a) * 100).round().value_counts(normalize=True).sort_index().items() if abs(k) <= 4}}
    json.dump(out, open(RES / "match_clock_price.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

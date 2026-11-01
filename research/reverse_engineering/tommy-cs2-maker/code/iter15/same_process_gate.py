"""X215 step 2 (assumptions panel iter-14 P2) and the identity check of mechanics critique 4: do the sibling accounts
that traded the development-block units run the wallet's process?
Gate per account (filled orders from calldata, development units only, clamped to the unit's block end):
  design: BUY share, whole-cent share, band [0.05, 0.95], burst structure (orders on a token chained within 50 ms:
          multi-level ladders 1c apart = the wallet's five-slot machine), size distribution;
  identity: 0-5 ms co-signing with the studied wallet's orders on OTHER markets in the same session (10-31 12-18),
          per-ms rate in 0-5 ms against 5-50 ms (the X176 bar: siblings 7.8-28.9x, everyone else <= 4.5x).
Accounts: 0xd2bb9459 (GRID events), 0x7d67f01d (cs2-1win-5s, dota2-xe-hn on 10-31; dota2-synaps-hn on 11-01).
Output: results/same_process_gate.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402
import grid_socket_clock as g1  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = g1.OUT
RES = g1.RES
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
A7 = "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14"
D2 = g1.D2
BLOCKS = [(1793448000, 1793469600), (1793512800, 1793534400)]
EXTRA = ["dota2-xe-hn-2026-10-31", "dota2-synaps-hn-2026-11-01"]


def design(c):
    c = c.sort_values("sign_ms")
    o = {"orders": int(len(c)), "buy_share": round(float((c.side == 0).mean()), 3),
         "whole_cent": round(float((np.abs(c.price * 100 - np.round(c.price * 100)) < 1e-6).mean()), 3),
         "band": round(float(((c.price >= 0.05 - 1e-9) & (c.price <= 0.95 + 1e-9)).mean()), 3),
         "sizes_top": {str(k): int(v) for k, v in c.shares.round(0).value_counts().head(8).items()}}
    bs, gaps = [], []
    for _, h in c.groupby("token_id"):
        s = h.sign_ms.to_numpy(float)
        p = h.price.to_numpy(float)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1] - s[j] <= 50:
                j += 1
            bs.append(j - i + 1)
            if j > i:
                gaps += list(np.round(-np.diff(np.sort(p[i:j + 1])[::-1]) * 100, 1))
            i = j + 1
    o["burst_size_counts"] = {str(k): int(v) for k, v in pd.Series(bs).value_counts().sort_index().items()}
    o["multi_level_share_of_orders"] = round(float(sum(b for b in bs if b > 1) / max(sum(bs), 1)), 3)
    o["slot_gap_c_counts"] = {str(k): int(v) for k, v in pd.Series(gaps).value_counts().head(6).items()}
    return o


def cosign(a_ms, a_tok, w_ms, w_tok):
    """pairs of (account order, wallet order) on different tokens with |dt| in [0, 5] ms vs (5, 50] ms; per-ms ratio."""
    w = np.sort(w_ms)
    n05, n550 = 0, 0
    for t in a_ms:
        lo, hi = np.searchsorted(w, t - 50), np.searchsorted(w, t + 50, side="right")
        d = np.abs(w[lo:hi] - t)
        n05 += int((d <= 5).sum())
        n550 += int(((d > 5) & (d <= 50)).sum())
    rate = (n05 / 11.0) / (n550 / 90.0) if n550 else None
    return {"pairs_0_5ms": n05, "pairs_5_50ms": n550, "per_ms_ratio": round(rate, 2) if rate else None}


def main():
    u = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/universe_t0.parquet")
    u = u[u.event_slug.isin(EXTRA)].copy()
    u["egs"] = u.groupby("event_slug").gs_ts.transform("min")
    pm = PolymarketData()
    tr = [pd.read_parquet(OUT / "op_trades.parquet")]
    rows = []
    for r in u.itertuples():
        assert not sealed.is_sealed(float(r.egs), "tommy-cs2-maker"), r.event_slug
        blk = [b for a, b in BLOCKS if a <= r.egs < b][0]
        rws, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 3600, end=int(blk) - 1, taker_only=False)
        for x in rws:
            x = dict(x)
            x.update(cid=r.cid, event=r.event_slug, smt=r.smt, outcomes=r.outcomes, is_taker_row=None)
            rows.append(x)
    if rows:
        t2 = pd.DataFrame(rows)
        t2["proxyWallet"] = t2.proxyWallet.str.lower()
        tr.append(t2[[c for c in tr[0].columns if c in t2.columns]])
    T = pd.concat(tr, ignore_index=True)
    tx7 = T.loc[T.proxyWallet == A7, "transactionHash"].unique()
    cd = g1.decode(list(set(tx7) | set(T.loc[T.proxyWallet == D2, "transactionHash"].unique())))
    cd["mk"] = cd.maker.str.lower()
    cd = cd[cd.sign_ms > 1.7e12]
    wal = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/calldata_dev.parquet")
    wal = wal[(wal.maker.str.lower() == W) & (wal.sign_ms > 1.7e12)].drop_duplicates(["salt", "sign_ms"])
    out = {}
    for name, acct in (("0xd2bb9459", D2), ("0x7d67f01d", A7)):
        c = cd[cd.mk == acct].drop_duplicates(["salt", "sign_ms"])
        o = {"design": design(c) if len(c) else None}
        c31 = c[(c.sign_ms / 1000 >= BLOCKS[0][0]) & (c.sign_ms / 1000 < BLOCKS[0][1])]
        o["cosign_with_wallet_1031"] = cosign(c31.sign_ms.to_numpy(float), c31.token_id.astype(str).to_numpy(),
                                              wal.sign_ms.to_numpy(float), wal.token_id.astype(str).to_numpy()) if len(c31) else None
        o["orders_1031"] = int(len(c31))
        out[name] = o
    # control: every other maker in the wallet's 10-31 calldata with >= 50 orders
    oth = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/calldata_dev.parquet")
    oth = oth[oth.sign_ms > 1.7e12].drop_duplicates(["salt", "sign_ms"])
    ctl = []
    for mk_, g in oth.groupby(oth.maker.str.lower()):
        if mk_ == W or len(g) < 50:
            continue
        cs = cosign(g.sign_ms.to_numpy(float), None, wal.sign_ms.to_numpy(float), None)
        ctl.append((mk_[:10], cs["per_ms_ratio"], cs["pairs_0_5ms"]))
    ctl = sorted(ctl, key=lambda x: -(x[1] or 0))
    out["control_other_makers_top"] = ctl[:8]
    out["control_other_makers_median_ratio"] = float(np.median([x[1] for x in ctl if x[1] is not None])) if ctl else None
    (RES / "same_process_gate.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()

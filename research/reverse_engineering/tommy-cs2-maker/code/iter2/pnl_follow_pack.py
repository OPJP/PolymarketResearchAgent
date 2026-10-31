"""Outcome target, executable on the public tape: follow the pack's prints (a historical stand-in for the book collapse,
which has no history before 10-31). Rule: for each first public print of a pack address buying team X in a market
(cluster of 10 s), buy X at the first public print price of X at or after block time + LAT (+1c), SIZE shares; settle at
the outcome. Optionally add the generic join-the-touch ladder (delta 0, 1 level). Per-market PnL vs the wallet's on the
wallet's markets, BUILD and VALIDATE. The pack was identified on all development data, so VALIDATE is not clean
(exploratory)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H, OUT, RES, SPLIT, TAPES  # noqa: E402
from pnl_replay import wallet_pnl, replay  # noqa: E402

PACK = {"0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3", "0xfe8a28be83ba295a9384f72f240d2cfa96bc23ce",
        "0x2529c68db36ce8aa64c64affe620267744a3548a", "0x72aaaaf9f6b0286e390de5b568af0f99a00c90e0", "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"}
LAT, SIZE = 2, 100.0


def follow(d, gs, pay0):
    d = d[d.timestamp >= gs].sort_values("timestamp")
    ts = d.timestamp.to_numpy().astype(float)
    oi = d.outcomeIndex.astype(int).to_numpy()
    side = d.side.to_numpy()
    pr = d.price.astype(float).to_numpy()
    team = np.where(side == "BUY", oi, 1 - oi)
    pack = d.proxyWallet.isin(PACK).to_numpy()
    p_team0 = np.where(oi == 0, pr, 1 - pr)
    pnl, last = 0.0, {0: -1e18, 1: -1e18}
    for i in np.where(pack)[0]:
        x = team[i]
        if ts[i] - last[x] < 10:
            continue
        last[x] = ts[i]
        j = np.searchsorted(ts, ts[i] + LAT, side="left")
        if j >= len(ts):
            continue
        px = (p_team0[j] if x == 0 else 1 - p_team0[j]) + 0.01
        if px >= 0.99:
            continue
        pay = pay0 if x == 0 else 1 - pay0
        pnl += SIZE * (pay - px)
    return pnl


def main():
    wp, pay = wallet_pnl()
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[u.cid.isin(wp.index) & u.cid.isin(pay)]
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    rows = []
    for cid, gs in zip(u.cid, u.gs_ts.astype(int)):
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        d = d[(~d.transactionHash.isin(wtx)) & (d.timestamp < H)]
        if len(d) < 5:
            continue
        f = follow(d, gs, pay[cid])
        lad, _ = replay(d.sort_values("timestamp"), gs, pay[cid], 0.0, 1)
        rows.append({"cid": cid, "gs": gs, "follow": f, "ladder": lad, "both": f + lad, "wallet": float(wp[cid])})
    x = pd.DataFrame(rows)
    res = {}
    for sp, s in (("BUILD", x[x.gs < 1792540800]), ("VALIDATE", x[x.gs >= 1792540800])):
        r = {"n": len(s)}
        for c in ("follow", "ladder", "both"):
            r[c] = {"pearson": round(float(np.corrcoef(s[c], s.wallet)[0, 1]), 3), "spearman": round(float(s[c].rank().corr(s.wallet.rank())), 3),
                    "rule_pnl": round(float(s[c].sum()), 0)}
        res[sp] = r
    json.dump(res, open(RES / "results/pnl_follow_pack.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

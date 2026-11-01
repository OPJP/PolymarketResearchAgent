"""X183 historical form (assumptions panel iter-12 P4): does its maker leg act on the feed messages it does not take?
Pack take clusters of 16-22 Oct (pack_clusters: informed takers' clusters per event, has_W = the wallet took in it)
WITHOUT a wallet take, split by P4e present / absent. Membership = a filled wallet maker order signed within
[t0 - 30, t0 + 30] ms on any book of the event (t0 = the cluster's first signing time); null = the same at t0 shifted
by +-2..10 s (8 shifts). Reference: clusters WITH a wallet take. Censored record (filled orders only), so the levels are
lower bounds; the excess over the shifted rate is the statistic. Direction: does the member order's team (its bought
token's team) equal the pack's bought team (the cluster's team)?
Output: results/declined_messages.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    pc = pd.read_parquet(OUT / "pack_clusters.parquet")
    po = pd.read_parquet(OUT / "pack_orders.parquet", columns=["cluster", "team", "event"])
    cd = pd.read_parquet(OUT / "calldata_all.parquet", columns=["idx", "maker", "sign_ms", "salt", "event", "oi", "cid", "smt"])
    cd["maker"] = cd.maker.str.lower()
    wo = cd[(cd.maker == W) & (cd.idx != -1)].drop_duplicates(["salt", "sign_ms"])
    # team of the wallet's bought token in pack_orders' convention: pack_orders 'team' is 0/1 by outcome of the match
    by_ev = {e: np.sort(g.sign_ms.to_numpy(np.int64)) for e, g in wo.groupby("event")}

    def member(ev, t):
        arr = by_ev.get(ev)
        if arr is None:
            return False
        return bool(np.searchsorted(arr, t + 30, side="right") - np.searchsorted(arr, t - 30, side="left") > 0)
    rows = []
    for r in pc.itertuples():
        t0 = int(r.t0)
        m = member(r.event, t0)
        sh = [member(r.event, t0 + s) for s in (-10000, -7000, -4000, -2000, 2000, 4000, 7000, 10000)]
        rows.append({"has_W": bool(r.has_W), "has_P4e": bool(r.has_P4e), "n_who": int(r.n_who), "m": m, "null": float(np.mean(sh)),
                     "ev_has_wallet": r.event in by_ev})
    D = pd.DataFrame(rows)
    D = D[D.ev_has_wallet]
    out = {}
    for name, sel in (("no_wallet_take_P4e", (~D.has_W) & D.has_P4e), ("no_wallet_take_noP4e", (~D.has_W) & ~D.has_P4e),
                      ("no_wallet_take_multi_who", (~D.has_W) & (D.n_who >= 2)), ("with_wallet_take", D.has_W)):
        X = D[sel]
        if not len(X):
            continue
        out[name] = {"clusters": int(len(X)), "member_rate": round(float(X.m.mean()), 4), "shifted_rate": round(float(X.null.mean()), 4),
                     "ratio": round(float(X.m.mean() / max(X.null.mean(), 1e-9)), 2)}
    (RES / "declined_messages.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

"""X203 step 4 (behavioural confirmation of the fingerprint candidates): for each deposit wallet whose owner delegates
to 0x63c0c19a (results/owner_census.json), the number of its orders signed within 0-5 ms of an order of one of the
four known operator accounts on the same market (condition id), against the rate in the 5-50 ms band scaled to the
same width (the X176 census statistic), plus its taker sign-time lag behind P4e on the same token (+-2 s), titles of
its markets (from the event slugs of the wallet's universe where known). Output: results/owner_census_cosign.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
OPS = {"0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2", "0x7d67f01d3e7b7c56c3df7b2ea08a58917d7f5f14",
       "0x52661b8e13158f23d94a9e8302ab0295704c22ac", "0x671190333b064b0899b4ac1aec86744b1f82885b"}
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"


def main():
    oc = json.load(open(RES / "owner_census.json"))
    cand = [d["addr"] for d in oc["operator_delegate_accounts"] if d["known"] == "NEW"]
    cols = ["tx", "idx", "maker", "side", "price", "shares", "sign_ms", "token_id", "condition_id"]
    parts = [pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)]
    for d in ["calldata_pub", "sib7d67/calldata", "sib7d67_sep/calldata", "sib7d67_jun/calldata", "sib_grid/calldata", "sib5266_sport/calldata"]:
        p = OUT / d
        if p.exists():
            for f in sorted(p.glob("*.parquet")):
                try:
                    parts.append(pd.read_parquet(f, columns=cols))
                except Exception:  # noqa: BLE001
                    pass
    c = pd.concat(parts, ignore_index=True).drop_duplicates(["tx", "idx"])
    c["maker"] = c.maker.str.lower()
    c = c[(c.sign_ms > 1.7e12) & (c.sign_ms < 1.8e12)]
    ops = c[c.maker.isin(OPS)]
    opt = {k: np.sort(g.sign_ms.to_numpy()) for k, g in ops.groupby("condition_id")}
    p4 = c[(c.maker == P4E) & (c.idx == -1)]
    p4t = {k: np.sort(g.sign_ms.to_numpy()) for k, g in p4.groupby("token_id")}
    u = pd.read_parquet(OUT / "universe.parquet", columns=["cid", "event_slug"])
    evs = dict(zip(u.cid, u.event_slug))
    out = []
    for a in cand:
        g = c[c.maker == a].drop_duplicates(["sign_ms", "token_id"])
        near = band = 0
        lags = []
        for r in g.itertuples():
            t = opt.get(r.condition_id)
            if t is not None and len(t):
                d = np.abs(t - r.sign_ms)
                near += int((d <= 5).any())
                band += int(((d > 5) & (d <= 50)).any())
            if r.idx == -1:
                q = p4t.get(r.token_id)
                if q is not None and len(q):
                    j = np.searchsorted(q, r.sign_ms)
                    best = None
                    for jj in (j - 1, j):
                        if 0 <= jj < len(q) and abs(r.sign_ms - q[jj]) <= 2000:
                            best = r.sign_ms - q[jj] if best is None or abs(r.sign_ms - q[jj]) < abs(best) else best
                    if best is not None:
                        lags.append(best)
        titles = pd.Series([str(evs.get(x, "?")).split("-")[0] for x in g.condition_id]).value_counts().head(5).to_dict()
        rec = {"addr": a, "orders": int(len(g)), "taker_orders": int((g.idx == -1).sum()), "near_0_5ms_operator": near,
               "band_5_50ms_operator": band, "ratio_per_ms": round((near / 5) / max(band / 45, 1e-9), 2) if band else None,
               "taker_pairs_with_P4e_2s": len(lags), "taker_lag_vs_P4e_median_ms": float(np.median(lags)) if lags else None,
               "taker_lag_in_0_100ms_share": round(float(np.mean((np.array(lags) >= 0) & (np.array(lags) < 100))), 3) if lags else None,
               "titles": titles, "first": str(pd.to_datetime(g.sign_ms.min(), unit="ms")), "last": str(pd.to_datetime(g.sign_ms.max(), unit="ms"))}
        out.append(rec)
        print(json.dumps(rec), flush=True)
    (RES / "owner_census_cosign.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

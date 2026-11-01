"""X228 step 1 (assumptions panel iter-15 P2): does the operator's shadow fingerprint on the GRID accounts persist into
16-22 Oct? Development data only (activity and calldata before H). Shadows 0x67119033 (20-share) and 0x52661b8e
(5-share); leaders 0xd2bb9459 and 0x10d79cc7. Steps: data-api activity of all four accounts 10-16 00:00 .. H-1; the
shadows' trade txs in events the studied wallet did not trade, and the leaders' trade txs in the same markets within
+-1 h of a shadow trade, decoded (publicnode); per shadow order, leader orders on the same token signed 0-5 ms before
it against 5-50 ms (per-ms ratio; X176 bar: siblings 7.8-28.9x, everyone else <= 4.5x). Control: the same statistic
against every other maker seen in those txs with >= 30 orders. Output: results/shadow_persistence.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
CODE = ROOT / "research/reverse_engineering/tommy-cs2-maker/code"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE / "iter15"))
import grid_socket_clock as g1  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker/iter16"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
H = 1792713600
A0 = 1792108800  # 10-16 00:00 UTC
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SH = {"0x67119033": "0x671190333b064b0899b4ac1aec86744b1f82885b", "0x52661b8e": "0x52661b8e13158f23d94a9e8302ab0295704c22ac"}
LD = {"0xd2bb9459": "0xd2bb94594762beda042e596598800d83f781bd8e", "0x10d79cc7": "0x10d79cc72df76ea3d6bdc2d54f41dbcbbb18bbf6"}


def activity():
    p = OUT / "shadow_activity.parquet"
    if p.exists():
        return pd.read_parquet(p)
    pm = PolymarketData()
    rows = []
    for nm, a in {**SH, **LD}.items():
        r = pm.activity(a, A0, H - 1)
        r = r[0] if isinstance(r, tuple) else r
        for x in r:
            x = dict(x)
            if x.get("type") != "TRADE":
                continue
            rows.append({"acct": nm, "tx": x.get("transactionHash"), "cid": x.get("conditionId"), "event": x.get("eventSlug"),
                         "ts": float(x.get("timestamp")), "asset": str(x.get("asset")), "price": float(x.get("price") or 0),
                         "size": float(x.get("size") or 0)})
    d = pd.DataFrame(rows)
    d = d[d.ts < H]
    d.to_parquet(p, index=False)
    return d


def decode(txs):
    p = OUT / "shadow_calldata.parquet"
    have = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    todo = sorted(set(txs) - (set(have.tx) if len(have) else set()))
    if todo:
        old = g1.OUT
        g1.OUT = OUT
        tmp = OUT / "op_calldata.parquet"
        if tmp.exists():
            tmp.unlink()
        new = g1.decode(todo)
        g1.OUT = old
        if tmp.exists():
            tmp.unlink()
        have = pd.concat([have, new], ignore_index=True) if len(have) else new
        have.to_parquet(p, index=False)
    return have


def ratio(sh_ms, ld_ms):
    ld_ms = np.sort(ld_ms)
    n05 = n550 = 0
    for t in sh_ms:
        lo, hi = np.searchsorted(ld_ms, t - 50), np.searchsorted(ld_ms, t, side="right")
        d = t - ld_ms[lo:hi]
        n05 += int(((d >= 0) & (d <= 5)).sum())
        n550 += int(((d > 5) & (d <= 50)).sum())
    return n05, n550, (round((n05 / 6.0) / (n550 / 45.0), 2) if n550 else (None if not n05 else float("inf")))


def main():
    act = activity()
    wev = set(pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/orders.parquet", columns=["event"]).event.unique())
    out = {"activity_rows": act.groupby("acct").size().to_dict(),
           "shadow_events_not_traded_by_wallet": {k: int(v.event[~v.event.isin(wev)].nunique()) for k, v in act[act.acct.isin(SH)].groupby("acct")}}
    sh = act[act.acct.isin(SH) & ~act.event.isin(wev)]
    ld = act[act.acct.isin(LD) & act.cid.isin(set(sh.cid))]
    # leaders' txs within +-1 h of a shadow trade in the same market
    keep = []
    for cid, g in ld.groupby("cid"):
        st = np.sort(sh.loc[sh.cid == cid, "ts"].to_numpy(float))
        j = np.searchsorted(st, g.ts.to_numpy(float))
        dmin = np.minimum(np.abs(g.ts.to_numpy(float) - st[np.clip(j - 1, 0, len(st) - 1)]), np.abs(st[np.clip(j, 0, len(st) - 1)] - g.ts.to_numpy(float)))
        keep.append(g[dmin <= 3600])
    ld = pd.concat(keep) if keep else ld.iloc[:0]
    txs = set(sh.tx) | set(ld.tx)
    out["txs_to_decode"] = int(len(txs))
    cd = decode(list(txs))
    cd = cd[(cd.sign_ms > 1.7e12) & (cd.sign_ms < H * 1000)].copy()
    cd["mk"] = cd.maker.str.lower()
    cd = cd.drop_duplicates(["mk", "token_id", "sign_ms", "price"])
    res = {}
    for snm, sa in SH.items():
        s = cd[cd.mk == sa]
        r = {"orders": int(len(s))}
        for lnm, la in LD.items():
            l_ = cd[cd.mk == la]
            n05 = n550 = 0
            same_px = 0
            for tok, gs in s.groupby("token_id"):
                gl = l_[l_.token_id == tok]
                if not len(gl):
                    continue
                a, b, _ = ratio(gs.sign_ms.to_numpy(float), gl.sign_ms.to_numpy(float))
                n05 += a
                n550 += b
                ls, lp = gl.sign_ms.to_numpy(float), gl.price.to_numpy(float)
                for t, p in zip(gs.sign_ms.to_numpy(float), gs.price.to_numpy(float)):
                    k = (t - ls >= 0) & (t - ls <= 5)
                    same_px += int((np.abs(lp[k] - p) < 1e-9).any())
            r[lnm] = {"pairs_0_5ms": n05, "pairs_5_50ms": n550, "per_ms_ratio": round((n05 / 6.0) / (n550 / 45.0), 2) if n550 else (None if not n05 else "inf"),
                      "shadow_orders_with_same_price_leader_0_5ms": same_px, "leader_orders": int(len(l_))}
        # control: every other maker with >= 30 orders in these txs
        ctl = []
        for mk_, g in cd[~cd.mk.isin(set(SH.values()) | set(LD.values()) | {W})].groupby("mk"):
            if len(g) < 30:
                continue
            n05 = n550 = 0
            for tok, gs in s.groupby("token_id"):
                gl = g[g.token_id == tok]
                if len(gl):
                    a, b, _ = ratio(gs.sign_ms.to_numpy(float), gl.sign_ms.to_numpy(float))
                    n05 += a
                    n550 += b
            if n05 + n550:
                ctl.append((mk_[:10], n05, n550, round((n05 / 6.0) / (n550 / 45.0), 2) if n550 else None))
        r["control_top"] = sorted(ctl, key=lambda x: -(x[3] or 0))[:6]
        r["control_median_ratio"] = float(np.median([c[3] for c in ctl if c[3] is not None])) if ctl else None
        res[snm] = r
    out["result"] = res
    out["by_day_shadow_orders"] = {k: v.groupby(pd.to_datetime(v.sign_ms, unit="ms").dt.strftime("%m-%d")).size().to_dict()
                                   for k, v in ((nm, cd[cd.mk == a]) for nm, a in SH.items())}
    (RES / "shadow_persistence.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()

"""Examiner round 2: scope of the rule's universe (BTC 5m + BTC 15m) on lot f1, from the examiner's own fetch.

Every TRADE row of the three wallets in a unit that STARTS in the lot (every record of the unit counts, whatever its
timestamp), per family, per half (listing cut) and per wallet; per-market PnL held to resolution (buys (payout - price) x
size, sells the negative; merges and redeems are conversions at the resolution value), from Gamma outcomePrices.
Writes .cache/exam/directional-maker/trades_f1.parquet and results/exam_r2_scope.json.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from r2_common import CLUSTER, EXC, LOT, LOT_START, LOT_END, RES, in_lot

from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows  # noqa: E402

ET = ZoneInfo("America/New_York")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                      "october", "november", "december"], 1)}


def unit_of(slug: str):
    m = re.match(r"^(\w+)-updown-(5m|15m|4h)-(\d+)$", slug)
    if m:
        return f"{m[1]}-{m[2]}", int(m[3])
    m = re.match(r"^([a-z]+)-up-or-down-on-([a-z]+)-(\d+)-(\d{4})$", slug)
    if m:
        end = datetime(int(m[4]), MONTHS[m[2]], int(m[3]), 12, 0, tzinfo=ET)
        return f"{m[1]}-daily", int((end - timedelta(days=1)).timestamp())
    m = re.match(r"^([a-z]+)-up-or-down-([a-z]+)-(\d+)-(\d{4})-(\d+)(am|pm)-et$", slug)
    if m:
        h = int(m[5]) % 12 + (12 if m[6] == "pm" else 0)
        return f"{m[1]}-hourly", int(datetime(int(m[4]), MONTHS[m[2]], int(m[3]), h, 0, tzinfo=ET).timestamp())
    return "other", None


def main():
    t0 = time.time()
    pm = PolymarketData()
    L = pd.read_parquet(EXC / "listing_f1.parquet")
    L = L[L.listed]
    lst = dict(zip(L.cid, zip(L.fam, L.start_ts)))
    cut = json.loads((RES / "exam_r2_step0.json").read_text())["cut_ts"]
    rows = []
    for addr, name in CLUSTER.items():
        act, _, cov = pm.activity(addr, start=LOT_START - 4 * 3600, end=LOT_END + 6 * 3600 - 1)
        for r in act:
            rows.append(dict(wallet=name, type=r.get("type"), ts=int(r["timestamp"]), slug=str(r.get("slug") or ""),
                             cid=str(r.get("conditionId") or ""), asset=str(r.get("asset") or ""), side=r.get("side"),
                             price=float(r.get("price") or 0), size=float(r.get("size") or 0), usd=float(r.get("usdcSize") or 0),
                             outcome=str(r.get("outcome") or ""), tx=str(r.get("transactionHash") or "").lower()))
        print(name, len(act), getattr(cov, "status", cov), round(time.time() - t0, 1), flush=True)
    A = pd.DataFrame(rows)
    fam, ust = [], []
    for c, s in zip(A.cid, A.slug):
        if c in lst:
            fam.append(lst[c][0]); ust.append(float(lst[c][1]))
        else:
            f, u = unit_of(s)
            fam.append(f); ust.append(float(u) if u is not None else np.nan)
    A["fam"], A["unit_start"] = fam, ust
    A["in_lot"] = [in_lot(u) if np.isfinite(u) else False for u in A.unit_start]
    A.to_parquet(EXC / "activity_f1_all.parquet", index=False)
    T = A[(A.type == "TRADE") & A.in_lot].copy()
    # outcomes (settlement only)
    slugs = sorted(set(T.slug))
    raw = fetch_windows(slugs)
    pay = {}
    for cid, m in raw.items():
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
            pr = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        except (TypeError, ValueError):
            continue
        for tk, p in zip(toks, pr):
            pay[str(tk)] = p
    T["payout"] = T.asset.map(pay)
    sgn = np.where(T.side == "BUY", 1.0, -1.0)
    T["pnl"] = sgn * (T.payout - T.price) * T["size"]
    T["half"] = np.where(T.unit_start < cut, "early", "late")
    T["universe"] = T.fam.isin(["btc-5m", "btc-15m"])
    T.to_parquet(EXC / "trades_f1.parquet", index=False)

    def scope(d):
        if not len(d):
            return {"trades": 0}
        mk = d.groupby("cid").agg(pnl=("pnl", "sum"), uni=("universe", "first"))
        return {"trades": int(len(d)), "share_trades_universe": float(d.universe.mean()),
                "usd": round(float(d.usd.sum()), 0), "share_usd_universe": float(d.loc[d.universe, "usd"].sum() / d.usd.sum()) if d.usd.sum() else None,
                "markets": int(len(mk)), "abs_pnl": round(float(mk.pnl.abs().sum()), 1),
                "share_abs_pnl_universe": float(mk.loc[mk.uni, "pnl"].abs().sum() / mk.pnl.abs().sum()) if mk.pnl.abs().sum() else None,
                "pnl": round(float(mk.pnl.sum()), 1), "pnl_universe": round(float(mk.loc[mk.uni, "pnl"].sum()), 1),
                "payout_missing": int(d.payout.isna().sum())}
    out = {"pooled": scope(T), "halves": {h: scope(T[T.half == h]) for h in ("early", "late")},
           "per_wallet": {n: scope(T[T.wallet == n]) for n in CLUSTER.values()},
           "per_wallet_half": {f"{n}_{h}": scope(T[(T.wallet == n) & (T.half == h)]) for n in CLUSTER.values() for h in ("early", "late")},
           "by_family": {f: {"trades": int(len(g)), "usd": round(float(g.usd.sum()), 0), "pnl": round(float(g.pnl.sum()), 1),
                             "markets": int(g.cid.nunique())} for f, g in T.groupby("fam")},
           "by_family_half": {f"{f}_{h}": int(len(g)) for (f, h), g in T.groupby(["fam", "half"])},
           "by_block_hour": {time.strftime("%m-%dT%H", time.gmtime(int(k))): {"trades": int(len(g)), "univ": int(g.universe.sum())}
                             for k, g in T.groupby(T.unit_start // 3600 * 3600)},
           "activity_types_in_lot_units": A[A.in_lot].type.value_counts().to_dict(),
           "secs": round(time.time() - t0, 1)}
    (RES / "exam_r2_scope.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("pooled", "halves", "per_wallet", "by_family")}, indent=1, default=str))


if __name__ == "__main__":
    main()

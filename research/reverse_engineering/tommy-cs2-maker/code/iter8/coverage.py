"""Iteration 8 (X112, scope item 1): share of the wallet's fills and of its absolute settlement PnL that a CS2-only
and a CS2 + Dota 2 match / map-winner universe covers, per unit-start day (16-22 Oct) and on the 10-31 12-18
development block (development units only).

Per-market settlement PnL = sum over BUY fills of shares x payout(outcome) - USDC (the wallet never sells; merges and
redeems do not change settlement PnL). Payouts from Gamma outcomePrices of development units only.
Output: results/coverage_iter8.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402

KEY = "tommy-cs2-maker"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
H = 1792713600
CACHE = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def pay0(s):
    try:
        return float(json.loads(s)[0])
    except Exception:  # noqa: BLE001
        return np.nan


def per_market(tr, payout):
    tr = tr.copy()
    tr["p0"] = tr["conditionId"].map(payout)
    tr["val"] = tr["size"].astype(float) * np.where(tr["outcomeIndex"].astype(int) == 0, tr["p0"], 1 - tr["p0"])
    g = tr.groupby("conditionId").agg(fills=("size", "size"), usd=("usdcSize", lambda s: s.astype(float).sum()),
                                      val=("val", "sum"), p0=("p0", "first"))
    g["pnl"] = g["val"] - g["usd"]
    return g


def shares(g, cs2, dota):
    out = {}
    tot_f, tot_p = g["fills"].sum(), g["pnl"].abs().sum()
    for name, s in (("cs2_only", cs2), ("cs2_dota", cs2 | dota)):
        m = g.index.isin(list(s))
        out[name] = {"coverage_fills": round(float(g.loc[m, "fills"].sum() / max(tot_f, 1)), 4),
                     "coverage_abs_pnl": round(float(g.loc[m, "pnl"].abs().sum() / max(tot_p, 1e-9)), 4),
                     "coverage_usd": round(float(g.loc[m, "usd"].sum() / max(g["usd"].sum(), 1e-9)), 4)}
    out["fills"] = int(tot_f)
    out["markets"] = int(len(g))
    out["markets_unsettled"] = int(g["p0"].isna().sum())
    out["dota_fills"] = int(g.loc[g.index.isin(list(dota)), "fills"].sum())
    out["dota_pnl"] = round(float(g.loc[g.index.isin(list(dota)), "pnl"].sum()), 1)
    out["cs2_pnl"] = round(float(g.loc[g.index.isin(list(cs2)), "pnl"].sum()), 1)
    return out


def main():
    u = pd.read_parquet(CACHE / "universe.parquet")
    u = u[u["smt"].isin(["moneyline", "child_moneyline"])]
    ud = pd.read_parquet(CACHE / "universe_dota.parquet")
    ut = pd.read_parquet(CACHE / "universe_t0.parquet")
    cs2 = set(u["cid"]) | set(ut.loc[ut["series"] == "10310", "cid"])
    dota = set(ud["cid"])
    mk = json.load(open(CACHE / "markets_dev.json"))
    payout = {k: pay0(x.get("outcomePrices")) for k, x in mk.items()}
    for df in (u, ud, ut):
        for c, r in zip(df["cid"], df["res_outcome_prices"]):
            if r is not None and c not in payout:
                payout[c] = pay0(r)
    gsm = {}
    for df in (u, ud, ut):
        gsm.update(dict(zip(df["cid"], df["gs_ts"])))
    for k, x in mk.items():
        if k not in gsm:
            try:
                gsm[k] = pd.Timestamp(str(x.get("gameStartTime")).replace("+00", "+00:00")).timestamp()
            except Exception:  # noqa: BLE001
                pass
    a = pd.read_parquet(CACHE / "activity_dev.parquet")
    a = a[(a["type"] == "TRADE") & (a["timestamp"] < H)].copy()
    a["gs"] = a["conditionId"].map(gsm)
    a = a[a["gs"].notna() & (a["gs"] < H) & (a["gs"] >= 1792108800)]
    a["day"] = pd.to_datetime(a["gs"], unit="s").dt.strftime("%m-%d")
    res = {"by_day": {}}
    for day, g0 in a.groupby("day"):
        res["by_day"][day] = shares(per_market(g0, payout), cs2, dota)
    res["build_16_20"] = shares(per_market(a[a["day"] <= "10-20"], payout), cs2, dota)
    res["validate_21_22"] = shares(per_market(a[a["day"] >= "10-21"], payout), cs2, dota)
    # 10-31 12-18 development block: activity rows of development units (fetched 14:55 UTC, complete denominator)
    b = pd.read_parquet(CACHE / "activity_devblocks.parquet")
    b = b[b["type"] == "TRADE"].copy()
    for c in ("size", "usdcSize", "price"):
        b[c] = b[c].astype(float)
    b["outcomeIndex"] = b["outcomeIndex"].astype(int)
    b = b[b["gs"].map(lambda g: not sealed.is_sealed(int(g), KEY))]
    res["devblock_10_31_12_18_to_1455"] = shares(per_market(b, payout), cs2, dota)
    # full block, universe markets of development units: wallet trades via the market tape (no sealed unit is queried)
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    blk = ut[(ut["gs_ts"] >= 1793448000) & (ut["gs_ts"] < 1793469600)]
    blk = blk[blk["gs_ts"].map(lambda g: not sealed.is_sealed(int(g), KEY))]
    rows = []
    for r in blk.itertuples():
        x, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 6 * 3600, end=int(r.gs_ts) + 8 * 3600, taker_only=False)
        for t in x:
            if str(t.get("proxyWallet", "")).lower() == WALLET:
                rows.append({"conditionId": r.cid, "size": float(t["size"]), "usdcSize": float(t["size"]) * float(t["price"]),
                             "outcomeIndex": int(t["outcomeIndex"]), "timestamp": int(t["timestamp"])})
    w = pd.DataFrame(rows)
    if len(w):
        res["devblock_10_31_12_18_universe_tapes"] = shares(per_market(w, payout), cs2, dota)
        res["devblock_10_31_12_18_universe_tapes"]["note"] = ("denominator = CS2 + Dota universe markets only (wallet "
                                                               "fills from the market tapes); data-api /trades rows")
    res["dota_events_traded_dev"] = sorted(set(a.loc[a["conditionId"].isin(dota), "eventSlug"]))
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / "coverage_iter8.json", "w"), indent=1)


if __name__ == "__main__":
    main()

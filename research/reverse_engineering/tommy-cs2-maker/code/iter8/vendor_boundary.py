"""Iteration 8, X102 (information P2): which listing-time boundary describes the feed's coverage? Label = a feed
subscriber's in-event taker presence (P4e for CS2; the 0x8a80528d / 0xddb6e624 process and 0xf1ee4842 for Dota 2),
wallet-independent. Boundaries fitted alone: GRID flag, leagueTier, GRID x tier, league. CS2 events of 16-22 Oct
(events_sel + tapes) and Dota 2 events of 10-16..10-22 (market tapes through the cached data-api adapter).
Output: results/vendor_boundary.json"""
from __future__ import annotations
import glob, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
DOTA_SUBS = {"0x8a80528dce46711a54aa3455c2cc81dea51e11c5", "0xddb6e6246546230503f153506ac1e9914978b9b3",
             "0xf1ee4842fa0c7283632185e42577027452d4519c"}
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def auc(s, y):
    from scipy.stats import rankdata
    s, y = np.asarray(s, float), np.asarray(y).astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def rates(X, lab):
    o = {}
    for col in ("grid", "tier", "gt"):
        t = X.groupby(col)[lab].agg(["mean", "size"])
        o[col] = {str(k): [round(float(r["mean"]), 3), int(r["size"])] for k, r in t.iterrows()}
        sc = X[col].map(X.groupby(col)[lab].mean())
        o[f"auc_{col}_insample"] = round(auc(sc, X[lab]), 4)
    sc = X.league.map(X.groupby("league")[lab].mean())
    o["auc_league_insample"] = round(auc(sc, X[lab]), 4)
    o["wallet_y_vs_label_auc"] = round(auc(X[lab], X.y), 4) if "y" in X else None
    return o


def main():
    u = pd.read_parquet(OUT / "universe.parquet")
    cid_ev = dict(zip(u.cid, u.event_slug))
    pres = {}
    for f in glob.glob(str(OUT / "tapes" / "*_tkw.parquet")):
        e = cid_ev.get(Path(f).name.split("_")[0])
        if e is None:
            continue
        d = pd.read_parquet(f, columns=["proxyWallet"])
        pres[e] = pres.get(e, False) or bool((d.proxyWallet.str.lower() == P4E).any())
    es = pd.read_parquet(OUT / "events_sel.parquet")
    es = es[es.event_slug.isin(pres)].copy()
    es["p4e"] = es.event_slug.map(pres).astype(int)
    es["grid"] = es.grid.astype(bool)
    es["tier"] = es.tier.astype(str)
    es["gt"] = es.grid.map({True: "G", False: "N"}) + es.tier
    res = {"cs2": {"events": int(len(es)), "p4e_events": int(es.p4e.sum()), **rates(es, "p4e")}}
    res["cs2"]["wallet_traded_given_p4e"] = round(float(es.loc[es.p4e == 1, "y"].mean()), 3)
    res["cs2"]["wallet_traded_given_no_p4e"] = round(float(es.loc[es.p4e == 0, "y"].mean()), 3)
    res["cs2"]["p4e_given_wallet_traded"] = round(float(es.loc[es.y == 1, "p4e"].mean()), 3)
    res["cs2"]["p4e_by_league_top"] = {k: [round(float(v["mean"]), 2), int(v["size"])] for k, v in
                                       es.groupby("league").p4e.agg(["mean", "size"]).sort_values("size", ascending=False).head(25).iterrows()}
    # Dota 2 (10-16..H): subscriber presence from market tapes
    from polyrea.adapters.polymarket import PolymarketData
    pm = PolymarketData()
    ud = pd.read_parquet(OUT / "universe_dota.parquet")
    ud = ud[(ud.gs_ts >= 1792108800) & (ud.gs_ts < 1792713600)]
    a = pd.read_parquet(OUT / "activity_dev.parquet")
    tr = set(a.loc[a.type == "TRADE", "eventSlug"])
    rows = []
    for e, g in ud.groupby("event_slug"):
        sp, ww = False, False
        for r in g.itertuples():
            x, _, _ = pm.market_trades(r.cid, start=int(r.gs_ts) - 3600, end=int(min(r.gs_ts + 4 * 3600 + 600, 1792713599)), taker_only=True)
            ws = {str(t.get("proxyWallet", "")).lower() for t in x}
            sp |= bool(ws & DOTA_SUBS)
        rows.append({"event_slug": e, "league": g.league.iloc[0], "tier": str(g.league_tier.iloc[0]),
                     "grid": bool(g.grid_series_id.notna().any()), "sub": int(sp), "y": int(e in tr)})
    D = pd.DataFrame(rows)
    D["gt"] = D.grid.map({True: "G", False: "N"}) + D.tier
    res["dota2"] = {"events": int(len(D)), "sub_events": int(D["sub"].sum()), **rates(D, "sub"),
                    "by_league": {k: [round(float(v["mean"]), 2), int(v["size"])] for k, v in D.groupby("league")["sub"].agg(["mean", "size"]).iterrows()},
                    "wallet_traded_by_league": {k: [int(v["sum"]), int(v["size"])] for k, v in D.groupby("league").y.agg(["sum", "size"]).iterrows()}}
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / "vendor_boundary.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

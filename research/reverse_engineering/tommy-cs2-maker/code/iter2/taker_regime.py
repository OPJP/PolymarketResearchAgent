"""Taker regime (06-16 .. 10-15) vs maker regime: leagues, GRID share, market types, sides, daily cash PnL.
PnL per market = SELL + REDEEM - BUY (+ MERGE) from data-api activity (clamped before H); markets are grouped by the day
of their first trade. Development data only."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import H, OUT, RES  # noqa: E402

def meta_of(mfile):
    m = json.load(open(OUT / mfile)); rows = []
    for cid, x in m.items():
        ev = (x.get("events") or [{}])[0]; md = ev.get("eventMetadata") or {}
        if isinstance(md, str):
            try: md = json.loads(md)
            except Exception: md = {}
        rows.append({"conditionId": cid, "smt": x.get("sportsMarketType"), "league": md.get("league"), "tier": md.get("leagueTier"),
                     "grid": md.get("gridSeriesId") is not None, "grid_key": "gridSeriesId" in md, "q": (x.get("question") or "")[:40],
                     "game": (x.get("question") or "").split(":")[0]})
    return pd.DataFrame(rows)

def main():
    a1 = pd.read_parquet(OUT / "activity_taker.parquet"); a2 = pd.read_parquet(OUT / "activity_dev.parquet")
    a = pd.concat([a1, a2]).drop_duplicates(["transactionHash", "conditionId", "type", "side", "size", "asset"])
    a = a[a.timestamp.astype(int) < H]
    meta = pd.concat([meta_of("markets_taker.json"), meta_of("markets_dev.json")]).drop_duplicates("conditionId")
    a = a.merge(meta, on="conditionId", how="left")
    a["usd"] = a.usdcSize.astype(float); a["ts"] = a.timestamp.astype(int)
    t = a[a.type == "TRADE"].copy(); t["day"] = pd.to_datetime(t.ts, unit="s").dt.strftime("%m-%d")
    t["regime"] = np.where(t.ts < 1792108800, "taker", "maker")
    res = {}
    for rg, s in t.groupby("regime"):
        ev = s.drop_duplicates("conditionId")
        res[rg] = {"trades": len(s), "usd": round(float(s.usd.sum())), "markets": int(s.conditionId.nunique()), "days_active": int(s.day.nunique()),
                   "sell_share": round(float((s.side == "SELL").mean()), 3), "grid_market_share": round(float(ev.grid.mean()), 3),
                   "grid_usd_share": round(float(s.loc[s.grid, "usd"].sum() / s.usd.sum()), 3),
                   "game_share": ev.game.value_counts(normalize=True).round(3).head(4).to_dict(),
                   "smt_share": ev.smt.value_counts(normalize=True).round(3).head(6).to_dict(),
                   "top_leagues_usd": s.groupby("league").usd.sum().sort_values(ascending=False).head(12).round(0).to_dict()}
    # month x grid
    t["month"] = pd.to_datetime(t.ts, unit="s").dt.strftime("%Y-%m")
    res["by_month"] = t.groupby("month").agg(trades=("usd", "size"), usd=("usd", "sum"), grid_usd=("usd", lambda s: s[t.loc[s.index, "grid"]].sum()), sell=("side", lambda s: (s == "SELL").mean())).round(3).to_dict("index")
    # per-market cash PnL
    def cash(s):
        buy = s.loc[(s.type == "TRADE") & (s.side == "BUY"), "usd"].sum(); sell = s.loc[(s.type == "TRADE") & (s.side == "SELL"), "usd"].sum()
        red = s.loc[s.type == "REDEEM", "usd"].sum(); mer = s.loc[s.type == "MERGE", "usd"].sum()
        return pd.Series({"pnl": sell + red + mer - buy, "first": s.ts.min(), "buy": buy})
    pm = a[a.type.isin(["TRADE", "REDEEM", "MERGE"])].groupby("conditionId").apply(cash)
    pm["day"] = pd.to_datetime(pm["first"], unit="s").dt.strftime("%m-%d")
    pm = pm.merge(meta.set_index("conditionId")[["grid", "league"]], left_index=True, right_index=True, how="left")
    daily = pm.groupby("day").pnl.sum()
    reb = a[a.type.isin(["TAKER_REBATE", "MAKER_REBATE", "REWARD"])].assign(day=lambda d: pd.to_datetime(d.ts, unit="s").dt.strftime("%m-%d")).groupby(["day", "type"]).usd.sum().unstack(fill_value=0)
    res["daily_cash_pnl_by_first_trade_day"] = daily.round(0).to_dict()
    res["rebates_by_day"] = reb.round(0).to_dict("index")
    pm["regime"] = np.where(pm["first"] < 1792108800, "taker", "maker")
    res["pnl_by_regime_grid"] = pm.groupby(["regime", "grid"]).agg(pnl=("pnl", "sum"), buy=("buy", "sum"), n=("pnl", "size")).round(0).reset_index().to_dict("records")
    res["pnl_by_month"] = pm.assign(month=pd.to_datetime(pm["first"], unit="s").dt.strftime("%Y-%m")).groupby("month").agg(pnl=("pnl", "sum"), buy=("buy", "sum")).round(0).to_dict("index")
    json.dump(res, open(RES / "results/taker_regime.json", "w"), indent=1, default=str)
    out = {k: v for k, v in res.items() if k not in ("daily_cash_pnl_by_first_trade_day", "rebates_by_day")}
    print(json.dumps(out, indent=1, default=str))
    pm.to_parquet(OUT / "per_market_cash_all.parquet")

if __name__ == "__main__":
    main()

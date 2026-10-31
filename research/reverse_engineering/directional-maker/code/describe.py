"""Describe the cluster's BTC 5m maker orders on BUILD (development data only)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker"
BUILD = (1791504000, 1792108800)


def q(x, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    return [round(float(v), 3) for v in np.quantile(x, qs)] if len(x) else []


def main(lo: int, hi: int) -> None:
    f = pd.read_parquet(OUT / "fills_enriched.parquet")
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    tok = pd.concat([w[["cid", "up_token", "start_ts", "end_ts", "up_payout"]].rename(columns={"up_token": "token_id"}).assign(is_up=1),
                     w[["cid", "down_token", "start_ts", "end_ts", "up_payout"]].rename(columns={"down_token": "token_id"}).assign(is_up=0)])
    f = f.merge(tok.rename(columns={"cid": "wcid"}), on="token_id", how="left")
    f = f[(f["ts"] >= lo) & (f["ts"] < hi)]
    print("fills in period", len(f), "btc5m share", round(f["wcid"].notna().mean(), 3))
    print("role x side", f.groupby(["role", "side"]).size().to_dict())
    print("by wallet x role", f.groupby(["wallet", "role"]).size().to_dict())
    b = f[f["wcid"].notna()].copy()
    mk = b[(b["role"] == "maker") & (b["side"] == "BUY")].copy()
    mk["rel"] = mk["ts"] - mk["start_ts"]
    mk["won"] = np.where(mk["is_up"] == 1, mk["up_payout"], 1 - mk["up_payout"])
    print("\nBTC5m maker BUY fills", len(mk), "usdc", round(mk["usdc"].sum()), "windows", mk["wcid"].nunique(), "of", w[(w.start_ts >= lo) & (w.start_ts < hi)].shape[0])
    px = mk["price"].to_numpy()
    on_cent = np.isclose(px * 100, np.round(px * 100), atol=1e-6).mean()
    on_mil = np.isclose(px * 1000, np.round(px * 1000), atol=1e-6).mean()
    print("price on 0.01 grid", round(on_cent, 3), "on 0.001 grid", round(on_mil, 3), "price q", q(px))
    print("fill time rel to window start q", q(mk["rel"]), "share before start", round((mk["rel"] < 0).mean(), 3))
    hist = pd.cut(mk["rel"], [-86400, -600, -300, -120, -60, 0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300]).value_counts(sort=False)
    print("rel-time hist (share)", (hist / hist.sum()).round(3).to_dict())
    print("win rate", round(mk["won"].mean(), 4), "avg price", round(mk["price"].mean(), 4), "usd-weighted edge",
          round(((mk["won"] - mk["price"]) * mk["shares"]).sum() / mk["usdc"].sum(), 4))
    # orders
    o = mk.groupby("order_hash").agg(wallet=("wallet", "first"), cid=("wcid", "first"), is_up=("is_up", "first"), n=("tx", "size"),
                                     shares=("shares", "sum"), usdc=("usdc", "sum"), pmin=("price", "min"), pmax=("price", "max"),
                                     t0=("ts", "min"), t1=("ts", "max"), start=("start_ts", "first"), won=("won", "first"))
    o["life"] = o["t1"] - o["t0"]
    o["rel0"] = o["t0"] - o["start"]
    print("\norders", len(o), "fills/order q", q(o["n"]), "single-price orders", round((o["pmin"] == o["pmax"]).mean(), 4))
    print("filled shares/order q", q(o["shares"]), "top sizes", o["shares"].round(2).value_counts().head(8).to_dict())
    print("order life (first->last fill) q", q(o["life"]), "share life>0", round((o["life"] > 0).mean(), 3))
    print("order first-fill rel time q", q(o["rel0"]))
    # per window
    pw = o.groupby("cid").agg(n_orders=("n", "size"), sides=("is_up", "nunique"), up_sh=("shares", lambda s: s[o.loc[s.index, "is_up"] == 1].sum()),
                              sh=("shares", "sum"), nprice=("pmin", "nunique"), wallets=("wallet", "nunique"))
    pw["up_frac"] = pw["up_sh"] / pw["sh"]
    print("\nper window: orders q", q(pw["n_orders"]), "two-sided share", round((pw["sides"] == 2).mean(), 3),
          "one-sided(>=70%) share", round(((pw["up_frac"] >= 0.7) | (pw["up_frac"] <= 0.3)).mean(), 3), "wallets/window q", q(pw["wallets"]))
    # counterparties
    tk = mk["taker"].value_counts()
    print("\ndistinct takers", len(tk), "top10 share", round(tk.head(10).sum() / tk.sum(), 3), "top5", (tk.head(5) / tk.sum()).round(3).to_dict())
    # same-tx co-fills across wallets
    co = mk.groupby("tx")["wallet"].nunique()
    print("txs", len(co), "share with >=2 cluster wallets", round((co >= 2).mean(), 3))
    mk.to_parquet(OUT / f"mk5_{lo}_{hi}.parquet", index=False)
    o.reset_index().to_parquet(OUT / f"orders5_{lo}_{hi}.parquet", index=False)


if __name__ == "__main__":
    lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else BUILD
    main(lo, hi)

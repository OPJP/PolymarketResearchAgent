"""Iteration 3, family N7b (who picks the cluster off, descriptive): per cluster maker BUY fill in BTC 5m, the
taker of the same transaction (data-api taker tape) and the move of the Binance fair of the filled side over the
next 60 s (from published seconds; description only, never a feature). Is VALIDATE's adverse selection broad or
concentrated in a few (new) takers?"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, WALLETS, H  # noqa: E402

VAL0 = 1792108800


def main():
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H]
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    mk = fills[(fills["role"] == "maker") & (fills["side"] == "BUY")].merge(w, on="cid")
    mk = mk[mk["ts"] < mk["end_ts"] - 60]
    cw = set(WALLETS.values())
    tx = set(mk["tx"])
    tk = []
    for f in sorted(OUT.glob("taker5m_day_*.parquet")):
        t = pd.read_parquet(f, columns=["tx", "wallet", "size"])
        tk.append(t[t["tx"].isin(tx) & ~t["wallet"].isin(cw)])
    tk = pd.concat(tk).groupby("tx").agg(taker=("wallet", "first"), tsize=("size", "sum")).reset_index()
    mk = mk.merge(tk, on="tx", how="left")
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < H]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    up = (mk["token_id"] == mk["up_token"]).to_numpy()
    f0, _ = fair_up(sp, mk["start_ts"].to_numpy(), mk["end_ts"].to_numpy(), mk["ts"].to_numpy())
    f60, _ = fair_up(sp, mk["start_ts"].to_numpy(), mk["end_ts"].to_numpy(), mk["ts"].to_numpy() + 61)
    mk["dF60"] = np.where(up, f60 - f0, f0 - f60)
    mk["won"] = np.where(up, mk["up_payout"], 1 - mk["up_payout"])
    mk["pnl"] = (mk["won"] - mk["price"]) * mk["shares"]
    mk["usd"] = mk["price"] * mk["shares"]
    res = {}
    bt = set(mk.loc[mk["ts"] < VAL0, "taker"].dropna())
    for split, part in (("build", mk[mk["ts"] < VAL0]), ("validate", mk[mk["ts"] >= VAL0])):
        g = part.groupby("taker").agg(n=("dF60", "size"), dF60=("dF60", "mean"), pnl=("pnl", "sum"), usd=("usd", "sum")).sort_values("n", ascending=False)
        top = g.head(10)
        rest = g.iloc[10:]
        r = {"fills": int(len(part)), "takers": int(len(g)), "dF60_all": round(float(part["dF60"].mean()), 4),
             "ret_all": round(float(part["pnl"].sum() / part["usd"].sum()), 4),
             "top10_share_fills": round(float(top["n"].sum() / g["n"].sum()), 3),
             "top10_dF60": round(float((top["n"] * top["dF60"]).sum() / top["n"].sum()), 4),
             "top10_ret": round(float(top["pnl"].sum() / top["usd"].sum()), 4),
             "rest_dF60": round(float((rest["n"] * rest["dF60"]).sum() / rest["n"].sum()), 4),
             "rest_ret": round(float(rest["pnl"].sum() / rest["usd"].sum()), 4),
             "top10": [[k[:10], int(v.n), round(float(v.dF60), 4), round(float(v.pnl / v.usd), 3)] for k, v in top.iterrows()]}
        if split == "validate":
            new = part[~part["taker"].isin(bt)]
            r["takers_new_vs_build_share_fills"] = round(float(len(new) / len(part)), 3)
            r["new_takers_dF60"] = round(float(new["dF60"].mean()), 4)
            r["new_takers_ret"] = round(float(new["pnl"].sum() / new["usd"].sum()), 4)
            old = part[part["taker"].isin(bt)]
            r["old_takers_dF60"] = round(float(old["dF60"].mean()), 4)
            r["old_takers_ret"] = round(float(old["pnl"].sum() / old["usd"].sum()), 4)
        # by taker order size
        q = pd.qcut(part["tsize"], 4, duplicates="drop")
        r["by_taker_size_quartile"] = part.groupby(q, observed=True).agg(n=("dF60", "size"), dF60=("dF60", "mean"),
                                                                         ret=("pnl", lambda s: float(s.sum()))).round(4).reset_index().astype(str).values.tolist()
        res[split] = r
    print(json.dumps(res, indent=1)[:5000])
    (HERE.parent / "results_iter3_who.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()

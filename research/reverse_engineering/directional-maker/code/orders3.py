"""Iteration 3, families N9 (sizing rule) and N10 (when it stops / how it quotes the window's end).

Orders = the cluster's BTC 5m maker BUY fills grouped by on-chain orderHash. For each order: total filled
shares (a lower bound of its size), number of fills, first-fill time in the window, price, and the public
state at the first fill (Binance fair of the side from seconds published by ts-1, |z|, vol). Sizing: is the
order size (ladder class) a function of the edge (fair - price), the price, time, vol, or the wallet?
Stop: the cluster's share of all bid-hit prints by time in the window and by |fair - 0.5|.

python code/orders3.py <chain_fills parquet> <split name>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up  # noqa: E402
from panel2 import OUT, H, WALLETS  # noqa: E402


def size_class(sh):
    sh = np.asarray(sh)
    return np.select([sh >= 990, sh >= 490, (sh >= 240) & (sh < 260), (sh >= 120) & (sh < 130), sh < 20],
                     ["1000", "500", "250", "125", "<20"], "other")


def main(path: str, split: str):
    f = pd.read_parquet(OUT / path)
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[w["end_ts"] <= H]
    tu = dict(zip(w["up_token"], w["cid"]))
    td = dict(zip(w["down_token"], w["cid"]))
    f["token_id"] = f["token_id"].astype(str)
    f = f[(f["role"] == "maker") & (f["side"].astype(str).isin(["BUY", "0"])) & f["token_id"].isin(tu.keys() | td.keys())].copy()
    f["cid"] = [tu.get(t) or td.get(t) for t in f["token_id"]]
    f["is_up"] = f["token_id"].isin(tu.keys())
    f = f.merge(w[["cid", "start_ts", "end_ts", "up_payout"]], on="cid")
    f["ts"] = np.round(f["block_ts_interp"]).astype(np.int64)
    f["price"] = f["usdc"] / f["shares"]
    f = f.sort_values(["order_hash", "ts", "log_index"], kind="stable")
    o = f.groupby("order_hash").agg(n=("ts", "size"), t0=("ts", "min"), t1=("ts", "max"), sh=("shares", "sum"),
                                     px=("price", "first"), wallet=("maker", "first"), is_up=("is_up", "first"),
                                     start=("start_ts", "first"), end=("end_ts", "first"), cid=("cid", "first"),
                                     upp=("up_payout", "first")).reset_index()
    spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
    spd = spd[spd["sec"] < H]
    sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
    fu, z = fair_up(sp, o["start"].to_numpy(), o["end"].to_numpy(), o["t0"].to_numpy() - 1)
    o["fair_s"] = np.where(o["is_up"], fu, 1 - fu)
    o["absz"] = np.abs(z)
    o["edge"] = o["fair_s"] - o["px"]
    o["rel"] = o["t0"] - o["start"]
    o["vol"] = sp.sigma(o["t0"].to_numpy()) * 1e4
    o["cls"] = size_class(o["sh"])
    o["usd"] = o["sh"] * o["px"]
    o["won"] = np.where(o["is_up"], o["upp"], 1 - o["upp"])
    res = {"split": split, "orders": int(len(o)), "fills": int(len(f)), "class_share": o["cls"].value_counts(normalize=True).round(3).to_dict()}
    # sizing vs public state at the first fill (ladder classes only)
    lad = o[o["cls"].isin(["1000", "500", "250", "125"])].copy()
    tab = {}
    for col, bins in (("edge", [-1, -0.02, 0.0, 0.02, 0.05, 1]), ("px", [0, 0.2, 0.4, 0.6, 0.8, 1]), ("rel", [0, 30, 90, 180, 300]),
                      ("vol", [0, 0.3, 0.5, 0.8, 100]), ("absz", [0, 0.5, 1, 2, 100])):
        c = pd.cut(lad[col], bins)
        tab[col] = (pd.crosstab(c, lad["cls"], normalize="index").round(3).assign(n=lad.groupby(c).size())).reset_index().astype(str).values.tolist()
    res["ladder_by_state"] = tab
    res["ladder_by_wallet"] = pd.crosstab(lad["wallet"].str[:8], lad["cls"], normalize="index").round(3).reset_index().values.tolist()
    # does a larger order class come with a better outcome (does it size up when it knows more)?
    res["won_by_class"] = o.groupby("cls").agg(n=("won", "size"), won=("won", "mean"), px=("px", "mean"),
                                               edge=("edge", "mean")).round(3).reset_index().values.tolist()
    res["ret_by_class"] = o.groupby("cls").apply(lambda g: float(((g["won"] - g["px"]) * g["sh"]).sum() / (g["px"] * g["sh"]).sum())).round(4).to_dict()
    # sizing in time: class shares by day
    o["day"] = (o["start"] // 86400).astype(int)
    res["class_by_day"] = pd.crosstab(o["day"], o["cls"], normalize="index").round(2).reset_index().values.tolist()
    # stop rule: last fill per active window and its state
    lastf = o.sort_values("t1").groupby("cid").tail(1)
    res["last_fill_rel_q"] = [float(x) for x in (lastf["t1"] - lastf["start"]).quantile([0.1, 0.25, 0.5, 0.75, 0.9])]
    res["fills_rel_hist_30s"] = np.histogram(f["ts"] - f["start_ts"], bins=range(0, 330, 30))[0].tolist()
    print(json.dumps(res, indent=0, default=str)[:6000])
    (HERE.parent / f"results_iter3_orders_{split}.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

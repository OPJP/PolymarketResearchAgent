"""Size and taker-order decode (components 5 and 6): net inventory (own state) at each order's signing time,
size choice (100 / 10 / odd sizes) vs inventory and price, and the side of its taker orders vs inventory.
Inventory = cumulative filled shares of outcome 0 minus outcome 1 in that market from fills with block ts < sign."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, WALLET, SPLIT  # noqa: E402

def main():
    cd = pd.read_parquet(OUT / "calldata_all.parquet")
    w = cd[cd.maker == WALLET].copy()
    o = pd.read_parquet(OUT / "orders.parquet")
    res = {}
    rows = []
    for cid, g in o.groupby("cid"):
        f = w[w.cid == cid].sort_values("bts")
        ft = f.bts.to_numpy(float); sgn = np.where(f.oi.to_numpy() == 0, 1.0, -1.0) * f.fill.to_numpy()
        cs = np.concatenate([[0.0], np.cumsum(sgn)])
        ca = np.concatenate([[0.0], np.cumsum(np.where(f.oi.to_numpy() == 0, f.fill.to_numpy(), 0))])
        cb = np.concatenate([[0.0], np.cumsum(np.where(f.oi.to_numpy() == 1, f.fill.to_numpy(), 0))])
        i = np.searchsorted(ft, g.sign_ts.to_numpy(), side="left")
        gg = g.assign(net0=cs[i], held_a=ca[i], held_b=cb[i])
        rows.append(gg)
    x = pd.concat(rows, ignore_index=True)
    x["own_net"] = np.where(x.oi == 0, x.net0, -x.net0)  # + = already long the outcome it is buying
    mk = x[x.role == "maker"]; tk = x[x.role == "taker"]
    mk = mk.assign(size_cls=np.select([mk.shares == 100, mk.shares == 10, (mk.shares > 10) & (mk.shares < 100)], ["100", "10", "11-99"], "other"))
    res["maker_size_cls"] = mk.size_cls.value_counts(normalize=True).round(3).to_dict()
    res["maker_size_by_cls"] = mk.groupby("size_cls").agg(n=("price", "size"), px_med=("price", "median"), own_net_med=("own_net", "median"),
                                                         abs_net_med=("net0", lambda s: float(np.median(np.abs(s)))), life_med=("life_first", "median"),
                                                         smt_match=("smt", lambda s: float((s == "moneyline").mean()))).round(3).to_dict("index")
    # price buckets for 10-share orders
    res["share_10_by_price"] = mk.assign(pb=pd.cut(mk.price, [0, .1, .2, .3, .5, .7, .8, .9, 1])).groupby("pb", observed=True).apply(lambda s: round(float((s.shares == 10).mean()), 3)).to_dict()
    res["share_10_by_price"] = {str(k): v for k, v in res["share_10_by_price"].items()}
    # taker orders: side vs own inventory
    res["taker_n"] = len(tk)
    res["taker_buys_short_side"] = round(float((tk.own_net < 0).mean()), 3)
    res["taker_buys_long_side"] = round(float((tk.own_net > 0).mean()), 3)
    res["taker_own_net_q"] = tk.own_net.quantile([.1, .25, .5, .75, .9]).round(0).to_dict()
    res["taker_size_vs_absnet"] = {"corr": round(float(np.corrcoef(tk.shares, tk.own_net.abs())[0, 1]), 3)}
    res["taker_filled_frac_med"] = round(float(tk.fill_frac.median()), 3)
    res["taker_price_q"] = tk.price.quantile([.1, .5, .9]).round(3).to_dict()
    # maker orders: side vs own inventory (do new bids favour the short side?)
    res["maker_buys_short_side"] = round(float((mk.own_net < 0).mean()), 3)
    res["maker_buys_long_side"] = round(float((mk.own_net > 0).mean()), 3)
    res["maker_own_net_q"] = mk.own_net.quantile([.1, .25, .5, .75, .9]).round(0).to_dict()
    x.to_parquet(OUT / "orders_inv.parquet", index=False)
    json.dump(res, open(RES / "results/size_taker.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))

if __name__ == "__main__":
    main()
